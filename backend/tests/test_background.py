"""Background removal: the photo is put on white and cropped before analysis."""

import io

import numpy as np
from PIL import Image

from app.background import keep_garment, on_white, use_cloth_mask
from tests.conftest import GREEN, RED, sign_up

ITEM_BOX = (40, 50, 120, 150)    # where the red "item" sits in the test photo


class FakeRemover:
    """The 'item' is every pixel that differs from the top-left corner."""

    def mask(self, img):
        px = np.asarray(img)
        return Image.fromarray(np.where((px != px[0, 0]).any(axis=2), 255, 0).astype(np.uint8))


def item_on_background():
    img = Image.new("RGB", (160, 200), GREEN)
    img.paste(Image.new("RGB", (ITEM_BOX[2] - ITEM_BOX[0], ITEM_BOX[3] - ITEM_BOX[1]), RED), ITEM_BOX[:2])
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return img, ("photo.png", buf.getvalue(), "image/png")


def test_on_white_crops_around_the_item():
    img, _ = item_on_background()
    clean = on_white(img, FakeRemover().mask(img))
    assert clean.size == (88, 110)                        # the item + a 5% margin
    assert clean.getpixel((0, 0)) == (255, 255, 255)      # background is now white
    assert clean.getpixel((44, 55)) == RED                # the item is untouched


def test_on_white_keeps_the_photo_when_nothing_is_found():
    img, _ = item_on_background()
    assert on_white(img, Image.new("L", img.size, 0)) is img


def test_upload_is_cleaned_before_analysis(make_client, settings):
    client = make_client(remover=FakeRemover())
    headers = sign_up(client)
    _, upload = item_on_background()
    r = client.post("/items", files={"photo": upload}, headers=headers)
    # the fake analyzer answers by mean colour: green background = dress, red item = top
    assert r.status_code == 201 and r.json()["category"] == "top"
    saved = Image.open(next(settings.storage_dir.rglob("*.jpg")))
    assert saved.size == (88, 110)
    assert all(c > 240 for c in saved.getpixel((1, 1)))  # white corner (JPEG is not exact)


def test_worn_item_keeps_only_the_garment():
    """A 'person': U2-Net keeps the whole body, cloth-seg finds the top inside it."""
    main = np.zeros((100, 60), np.uint8)
    main[5:95, 15:45] = 255                     # head + body + legs
    classes = np.zeros_like(main)
    classes[30:60, 15:45] = 1                   # the top
    classes[60:62, 15:45] = 2                   # a sliver of trousers: the top is bigger
    kept = keep_garment(main, classes) > 128
    assert kept[45, 30] and not kept[10, 30] and not kept[80, 30]   # top yes, head / legs no


def test_worn_dark_garment_is_not_erased_by_weak_main_mask():
    main = np.zeros((100, 60), np.uint8)
    main[5:95, 15:45] = 255
    main[35:55, 15:45] = 10  # U2-Net is uncertain on the black top
    classes = np.zeros_like(main)
    classes[30:60, 15:45] = 1

    kept = keep_garment(main, classes)

    assert kept[45, 30] > 128
    assert kept[10, 30] == 0 and kept[80, 30] == 0


def test_fragmented_garment_mask_keeps_the_black_garment_area():
    main = np.zeros((100, 60), np.uint8)
    main[5:95, 15:45] = 255
    main[35:55, 15:45] = 10
    classes = np.zeros_like(main)
    classes[30:35, 15:45] = 1
    classes[50:60, 15:45] = 1

    kept = keep_garment(main, classes)

    assert kept[45, 30] > 128


def test_item_alone_keeps_the_main_mask():
    main = np.zeros((100, 60), np.uint8)
    main[20:80, 10:50] = 255
    flat = np.zeros_like(main)
    flat[20:80, 10:50] = 1                      # cloth-seg agrees: the item is the object
    assert (keep_garment(main, flat) == main).all()
    nothing = np.zeros_like(main)               # cloth-seg misses a flat item on white
    assert (keep_garment(main, nothing) == main).all()


def test_efficientnet_guidance_requires_a_confident_garment_category():
    assert use_cloth_mask("top", 0.80)
    assert not use_cloth_mask("top", 0.54)
    assert not use_cloth_mask("shoes", 0.95)
