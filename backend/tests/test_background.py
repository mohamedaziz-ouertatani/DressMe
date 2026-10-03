"""Background removal: the photo is put on white and cropped before analysis."""

import io

import numpy as np
from PIL import Image

from app.background import on_white
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
