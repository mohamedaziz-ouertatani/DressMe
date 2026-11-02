import numpy as np
from PIL import Image


def crop_from_mask(img, mask, margin=0.05):
    ys, xs = np.where(mask)

    if len(xs) == 0:
        return None

    x0, x1 = xs.min(), xs.max()
    y0, y1 = ys.min(), ys.max()

    pad_x = int((x1 - x0) * margin)
    pad_y = int((y1 - y0) * margin)

    x0 = max(0, x0 - pad_x)
    y0 = max(0, y0 - pad_y)
    x1 = min(img.width, x1 + pad_x)
    y1 = min(img.height, y1 + pad_y)

    return img.crop((x0, y0, x1, y1))


def extract_garments(img, classes):
    garments = []

    top_mask = classes == 1
    bottom_mask = classes == 2
    fullbody_mask = classes == 3

    top = crop_from_mask(img, top_mask)
    if top is not None:
        garments.append(("top", top))

    bottom = crop_from_mask(img, bottom_mask)
    if bottom is not None:
        garments.append(("bottom", bottom))

    fullbody = crop_from_mask(img, fullbody_mask)
    if fullbody is not None:
        garments.append(("fullbody", fullbody))

    return garments