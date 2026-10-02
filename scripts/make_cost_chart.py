"""Generate docs/assets/cost-compare.png — yearly-cost bar chart for the README.

Compares VideoTranscriber (free, local, unlimited) against the cheapest
individual paid plan of a few well-known cloud transcription products.
Prices were looked up on each vendor's official pricing page on 2026-09-30 —
see the table in README.md for the exact plan names, prices, and source URLs.
This script is a one-off content-generation tool, not part of the app itself,
so its dependency (matplotlib) is intentionally not in requirements.txt:

    uv pip install matplotlib
    python scripts/make_cost_chart.py

Output: docs/assets/cost-compare.png
"""
from __future__ import annotations

import os

import matplotlib
import matplotlib.pyplot as plt

matplotlib.use("Agg")

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_PATH = os.path.join(HERE, "..", "docs", "assets", "cost-compare.png")

# (label, yearly cost in USD, cheapest-plan billing note)
# See README.md "Comparison" section for plan names, exact prices, source
# URLs, and the date each page was checked (2026-09-30).
DATA = [
    ("Rev  ·  Essentials", 306, "$25.49/mo billed yearly"),
    ("Descript  ·  Hobbyist", 192, "$16/mo billed yearly"),
    ("TurboScribe  ·  Unlimited", 120, "$10/mo billed yearly"),
    ("Otter.ai  ·  Pro", 100, "$8.33/mo billed yearly"),
    ("VideoTranscriber", 0, "free, forever"),
]

# Warm paper + typewriter identity (matches docs/assets/banner.svg).
BG = "#f1e8d3"          # cream paper
FG = "#1b1814"          # ink black
MUTED = "#4a4238"       # faded ink
FREE_COLOR = "#a3281f"  # deep red accent
PAID_COLOR = "#5d6b7c"  # muted ink blue-grey
GRID = "#d3c7ab"
SERIF = ["Georgia", "Times New Roman", "DejaVu Serif"]
MONO = ["Courier New", "Consolas", "DejaVu Sans Mono"]


def main() -> None:
    labels = [d[0] for d in DATA]
    values = [d[1] for d in DATA]
    colors = [PAID_COLOR] * (len(DATA) - 1) + [FREE_COLOR]
    top = max(values)

    fig, ax = plt.subplots(figsize=(9, 4.6), dpi=200)
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)

    ypos = list(range(len(DATA)))[::-1]
    # A sliver so the $0 row still shows a visible red marker.
    shown = [v if v > 0 else top * 0.012 for v in values]
    ax.barh(ypos, shown, color=colors, height=0.62, zorder=3)

    label_bbox = dict(boxstyle="square,pad=0.15", fc=BG, ec="none")
    label_texts = []
    for y, (_, value, note) in zip(ypos, DATA, strict=True):
        price = "$0" if value == 0 else f"${value}/yr"
        color = FREE_COLOR if value == 0 else FG
        x = max(value, top * 0.012) + top * 0.015
        label_texts.append(ax.text(x, y, price, va="center", ha="left", color=color,
                fontsize=13, fontweight="bold", family=MONO, zorder=4, bbox=label_bbox))
        label_texts.append(ax.text(x, y - 0.33, note, va="center", ha="left", color=MUTED,
                fontsize=8.5, family=MONO, zorder=4, bbox=label_bbox))

    ax.set_yticks(ypos, labels)
    ax.tick_params(axis="y", colors=FG, labelsize=11, length=0)
    for tick in ax.get_yticklabels() + ax.get_xticklabels():
        tick.set_family(MONO)
    ax.tick_params(axis="x", colors=MUTED, labelsize=9)
    ax.set_xlim(0, top * 1.28)
    ax.set_xlabel("USD per year (cheapest individual plan, billed yearly) — checked 2026-09-30",
                  color=MUTED, fontsize=8.5, family=MONO)
    ax.set_title("What a year of transcription costs", color=FG, fontsize=14, pad=14,
                 loc="left", fontweight="bold", family=SERIF)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.xaxis.grid(True, color=GRID, linewidth=0.7, zorder=0)
    ax.set_axisbelow(True)

    fig.tight_layout(pad=2.2)

    # Extend the x-axis so the widest label (sub-label text, which can run
    # past the bar) ends with real padding before the image's right edge,
    # instead of running flush against it. Measured in actual rendered
    # pixels so it holds regardless of font/DPI/label-length changes.
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    axis_width_px = ax.get_window_extent(renderer=renderer).width
    left, right = ax.get_xlim()
    max_text_x_data = max(
        ax.transData.inverted().transform((t.get_window_extent(renderer=renderer).x1, 0))[0]
        for t in label_texts
    )
    pad_px = 40
    new_right = left + (max_text_x_data - left) / (1 - pad_px / axis_width_px)
    ax.set_xlim(left, max(right, new_right))

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    fig.savefig(OUT_PATH, facecolor=BG)
    print(f"[make_cost_chart] wrote {os.path.abspath(OUT_PATH)}")


if __name__ == "__main__":
    main()
