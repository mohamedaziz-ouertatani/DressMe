"""
Background removal for uploaded photos (wardrobe items and /analyze scans).

A photo taken at home or in a friperie shows the item on a bed, a hanger or a
rack. Every model was trained on product shots on WHITE (Fashion Product,
PolyVore), and the colour model drops the white background touching the
border, so the photo is cleaned before it is analysed and saved:

    mask = remover.mask(img)     # 0 = background, 255 = item (rembg, U2-Net)
    img = on_white(img, mask)    # item pasted on white, cropped around it

`on_white` keeps the original photo when the mask finds (almost) nothing, so
a failed removal never loses the item. Tests use a small fake remover.
"""

from PIL import Image

MIN_ITEM_SHARE = 0.03   # mask covers less than 3% of the photo: removal failed
KEEP_ALPHA = 25         # mask values above this count as item when cropping
MARGIN = 0.05           # white margin around the item, as a share of its size


class BackgroundRemover:
    """rembg with a U2-Net model (~170 MB, downloaded once on first use;
    ~1 s per photo on the CPU)."""

    def __init__(self, model="u2net"):
        from rembg import new_session, remove

        self._session = new_session(model)
        self._remove = remove

    def mask(self, img):
        return self._remove(img, session=self._session, only_mask=True).convert("L")


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


def load_remover(settings):
    """The remover, or None if switched off or rembg is not installed."""
    if not settings.remove_background:
        return None
    try:
        return BackgroundRemover(settings.background_model)
    except ImportError:
        print("rembg not installed: uploaded photos keep their background "
              "(pip install -r requirements.txt in backend/)")
        return None
