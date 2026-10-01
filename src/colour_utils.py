"""
Colour helpers shared by the EDA / mapping scripts.

Used to snap a measured RGB colour to the nearest colour of the DressMe
palette (mappings/colour_palette.csv).
"""

from pathlib import Path

import numpy as np
import pandas as pd

PALETTE_PATH = Path(__file__).resolve().parents[1] / "mappings" / "colour_palette.csv"


def rgb_to_lab(rgb):
    """Convert sRGB colours (N x 3, 0-255) to CIE Lab.

    Lab distances are closer to how humans perceive colour differences
    than plain RGB distances, so nearest-colour matching is better.
    """
    c = np.asarray(rgb, dtype=float) / 255.0
    c = np.where(c > 0.04045, ((c + 0.055) / 1.055) ** 2.4, c / 12.92)  # linear RGB
    m = np.array([[0.4124, 0.3576, 0.1805],
                  [0.2126, 0.7152, 0.0722],
                  [0.0193, 0.1192, 0.9505]])
    xyz = c @ m.T / np.array([0.95047, 1.0, 1.08883])  # normalise to D65 white
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    L = 116 * f[:, 1] - 16
    a = 500 * (f[:, 0] - f[:, 1])
    b = 200 * (f[:, 1] - f[:, 2])
    return np.stack([L, a, b], axis=1)


class Palette:
    """The DressMe palette, ready for nearest-colour lookups."""

    def __init__(self, path=PALETTE_PATH):
        pal = pd.read_csv(path, keep_default_na=False)
        pal = pal[pal["hex"] != ""]  # 'multicolour' has no single hex
        self.names = pal["colour"].tolist()
        rgb = [tuple(int(h[i:i + 2], 16) for i in (1, 3, 5)) for h in pal["hex"]]
        self.lab = rgb_to_lab(rgb)

    def nearest(self, rgb):
        """Name of the palette colour closest to one RGB colour."""
        dist = np.linalg.norm(self.lab - rgb_to_lab([rgb]), axis=1)
        return self.names[dist.argmin()]
