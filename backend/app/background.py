"""
Background removal for uploaded photos (wardrobe items and /analyze scans).

A photo taken at home or in a friperie shows the item on a bed, a hanger, a
rack, or worn by someone. Every model was trained on product shots on WHITE (Fashion Product,
PolyVore), and the colour model drops the white background touching the
border, so the photo is cleaned before it is analysed and saved:

    mask = remover.mask(img)     # 0 = background, 255 = item (rembg, U2-Net)
    img = on_white(img, mask)    # item pasted on white, cropped around it

U2-Net keeps the main "object" of the photo, which is the whole person when
the item is worn (head, arms, legs). A second model, U2-Net cloth-seg, labels
every pixel as upper-body clothes, lower-body clothes or full-body clothes
(dress, jumpsuit); `keep_garment` then keeps only the biggest of those three.
Cloth-seg was trained on people and often misses an item lying flat on white,
so it is only used when it finds a garment that is clearly a PART of the main
object (a person); otherwise the U2-Net mask is kept as it is.

`on_white` keeps the original photo when the mask finds (almost) nothing, so
a failed removal never loses the item. Tests use a small fake remover.
"""

import numpy as np
from PIL import Image, ImageFilter

MIN_ITEM_SHARE = 0.03   # mask covers less than 3% of the photo: removal failed
KEEP_ALPHA = 25         # mask values above this count as item when cropping
MARGIN = 0.05           # white margin around the item, as a share of its size
PART_OF_OBJECT = 0.85   # garment < 85% of the main object: the rest is a person
GUIDANCE_CONFIDENCE = 0.55
GARMENT_CATEGORIES = {"top", "bottom", "dress", "outerwear", "traditional", "swimwear"}
GARMENT_DILATION = 9


class BackgroundRemover:
    """rembg: U2-Net for the main object + U2-Net cloth-seg for worn clothes
    (~170 MB each, downloaded once on first use; ~3-5 s per photo on the CPU)."""

    def __init__(self, model="u2net", cloth_model="u2net_cloth_seg", classifier=None):
        from rembg import new_session, remove

        self._session = new_session(model)
        self._clothes = new_session(cloth_model) if cloth_model else None
        self._remove = remove
        self._classifier = classifier

    def mask(self, img):
        main = np.asarray(self._remove(img, session=self._session, only_mask=True).convert("L"))
        if self._clothes is None:
            return Image.fromarray(main)
        category, confidence = self._classification(img)
        if not use_cloth_mask(category, confidence):
            return Image.fromarray(main)
        return Image.fromarray(keep_garment(main, self.clothes(img)))

    def _classification(self, img):
        if self._classifier is None:
            return None, 0.0
        prediction = self._classifier(img)
        return prediction["category"], float(prediction["category_conf"])

    def clothes(self, img):
        """One class per pixel: 0 = not clothes, 1 = upper, 2 = lower, 3 = full body.
        (rembg's own cloth-seg API returns one picture per class, i.e. runs the
        model three times, so its network is called once here instead.)"""
        out = self._clothes.inner_session.run(None, self._clothes.normalize(
            img, (0.485, 0.456, 0.406), (0.229, 0.224, 0.225), (768, 768)))
        classes = np.argmax(out[0], axis=1)[0].astype(np.uint8)
        return np.asarray(Image.fromarray(classes).resize(img.size, Image.NEAREST))


def keep_garment(main, classes):
    """The U2-Net mask `main` (0-255) cut down to the biggest worn garment, when
    the photo shows a person; otherwise `main` unchanged."""
    obj = main > KEEP_ALPHA
    counts = [np.count_nonzero(obj & (classes == c)) for c in (1, 2, 3)]
    garment_class = 1 + int(np.argmax(counts))
    garment = classes == garment_class
    n = np.count_nonzero(obj & garment)
    if n < MIN_ITEM_SHARE * main.size or n > PART_OF_OBJECT * np.count_nonzero(obj):
        return main                  # no garment found, or it IS the whole object
    # Cloth-seg can fragment dark garments. Expand its region before applying
    # it so uncertain pixels around a detected garment are not discarded.
    garment = np.asarray(Image.fromarray(garment.astype(np.uint8) * 255)
                         .filter(ImageFilter.MaxFilter(GARMENT_DILATION))) > 0
    ys, xs = np.where(classes == garment_class)
    garment[min(ys):max(ys) + 1, min(xs):max(xs) + 1] |= main[min(ys):max(ys) + 1,
                                                               min(xs):max(xs) + 1] > 0
    soft = Image.fromarray(np.where(garment, 255, 0).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1))
    # Cloth-seg is better at retaining dark fabric than U2-Net's object alpha.
    # Use the union inside the selected garment, rather than np.minimum, so a
    # weak U2-Net alpha cannot erase black pixels.
    return np.where(garment, np.maximum(main, np.asarray(soft)), 0).astype(np.uint8)


def use_cloth_mask(category, confidence):
    """Use person-clothing segmentation only for a confident garment prediction."""
    return confidence >= GUIDANCE_CONFIDENCE and category in GARMENT_CATEGORIES


def on_white(img, mask):
    """The item pasted on a white background and cropped around it (RGB)."""
    mask = mask.convert("L").resize(img.size)
    item = mask.point(lambda v: 255 if v > KEEP_ALPHA else 0)
    box = item.getbbox()
    share = sum(item.histogram()[255:]) / (img.width * img.height)
    if box is None or share < MIN_ITEM_SHARE:
        return img
    white = Image.new("RGB", img.size, (255, 255, 255))
    clean = Image.composite(img, white, mask)    # soft edges, no jagged outline
    x0, y0, x1, y1 = box
    pad_x, pad_y = round((x1 - x0) * MARGIN), round((y1 - y0) * MARGIN)
    return clean.crop((max(0, x0 - pad_x), max(0, y0 - pad_y),
                       min(img.width, x1 + pad_x), min(img.height, y1 + pad_y)))


def load_remover(settings, classifier=None):
    """The remover, or None if switched off or rembg is not installed."""
    if not settings.remove_background:
        return None
    try:
        return BackgroundRemover(settings.background_model, settings.cloth_model or None, classifier)
    except ImportError:
        print("rembg not installed: uploaded photos keep their background "
              "(pip install -r requirements.txt in backend/)")
        return None
