"""Shared plotting style so every figure in the project looks the same.

    from tenebres.viz import setup, SERIES, LEANING_COLORS, savefig
    setup()
"""

from __future__ import annotations

import matplotlib as mpl
import matplotlib.pyplot as plt

from .common import FIGURES

# Categorical slots, always assigned in this order (colorblind-validated order).
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]

# Fixed colour per platform/source so a source keeps its colour in every chart.
SOURCE_COLORS = {
    "bluesky": SERIES[0],
    "news": SERIES[1],
    "mastodon": SERIES[2],
    "wikipedia": SERIES[3],
    "reddit": SERIES[4],
    "gdelt": SERIES[6],
}

# Political leaning: diverging red (left) <-> blue (right) with a gray centre,
# following French convention. Non-partisan / uncoded are muted gray.
LEANING_ORDER = ["far-left", "left", "center-left", "center", "center-right", "right", "far-right"]
LEANING_COLORS = {
    "far-left": "#9e2a2a",
    "left": "#e34948",
    "center-left": "#f0a19c",
    "center": "#b5b4ad",
    "center-right": "#86b6ef",
    "right": "#2a78d6",
    "far-right": "#184f95",
    "n/a": "#dcdbd5",
    "uncoded": "#efeee9",
}

INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
SURFACE = "#fcfcfb"


def setup() -> None:
    mpl.rcParams.update(
        {
            "figure.facecolor": SURFACE,
            "axes.facecolor": SURFACE,
            "savefig.facecolor": SURFACE,
            "figure.dpi": 110,
            "savefig.dpi": 160,
            "figure.figsize": (9, 4),
            "font.family": ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"],
            "font.size": 10,
            "text.color": INK,
            "axes.labelcolor": INK_2,
            "axes.titlesize": 12,
            "axes.titleweight": "bold",
            "axes.titlelocation": "left",
            "axes.edgecolor": AXIS,
            "axes.linewidth": 0.8,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "axes.grid.axis": "y",
            "axes.axisbelow": True,
            "grid.color": GRID,
            "grid.linewidth": 0.6,
            "xtick.color": MUTED,
            "ytick.color": MUTED,
            "xtick.labelcolor": INK_2,
            "ytick.labelcolor": INK_2,
            "lines.linewidth": 2,
            "legend.frameon": False,
            "axes.prop_cycle": mpl.cycler(color=SERIES),
        }
    )


def savefig(fig, name: str) -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURES / f"{name}.png", bbox_inches="tight")


def annotate_events(ax, events: dict, y: float = 0.98) -> None:
    """Draw thin vertical markers with short labels for key dates."""
    import pandas as pd

    for d, label in events.items():
        x = pd.Timestamp(d)
        ax.axvline(x, color=AXIS, lw=0.8, ls=(0, (2, 2)), zorder=0)
        ax.text(x, y, f" {label}", transform=ax.get_xaxis_transform(), fontsize=8,
                color=INK_2, va="top", ha="left", rotation=90)
