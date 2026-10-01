"""
DressMe chart style, shared by every script that draws a chart.

Brand colours: rust #8E4420, gold #C9A063, cream #F2E8DA, dark #23201C.
Charts that need more than a few series use lighter / darker tints of them.

Usage:
    from plot_style import RUST, GOLD, DARK, SERIES, CMAP, apply
    apply()   # once, before drawing
"""

import matplotlib as mpl
from cycler import cycler
from matplotlib.colors import LinearSegmentedColormap

RUST = "#8E4420"
GOLD = "#C9A063"
CREAM = "#F2E8DA"
DARK = "#23201C"

# up to 8 series (e.g. the 8 categories): brand colours first, then tints
SERIES = [RUST, GOLD, DARK, "#C27A55", "#E6D2A8", "#6E655B", "#5E2C14", "#A8987F"]

# heatmaps: cream (low) -> gold -> rust (high)
CMAP = LinearSegmentedColormap.from_list("dressme", [CREAM, GOLD, RUST])


def apply():
    mpl.rcParams.update({
        "axes.prop_cycle": cycler(color=SERIES),
        "text.color": DARK,
        "axes.labelcolor": DARK,
        "axes.edgecolor": DARK,
        "xtick.color": DARK,
        "ytick.color": DARK,
        "axes.titleweight": "bold",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "image.cmap": "dressme",
    })


mpl.colormaps.register(CMAP, force=True)
