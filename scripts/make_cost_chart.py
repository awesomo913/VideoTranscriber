"""Generate docs/assets/cost-compare.png — yearly-cost bar chart for the README.

Compares VideoTranscriber (free, local, unlimited) against the cheapest
individual paid plan of a few well-known cloud transcription products.
Prices were looked up on each vendor's official pricing page on 2026-09-30 —
see the table in README.md for the exact plan names, prices, and source URLs.
This script is a one-off content-generation tool, not part of the app itself,
so its dependency (matplotlib) is intentionally not in requirements.txt:

    pip install matplotlib
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
    ("VideoTranscriber", 0, "Free, forever"),
    ("Otter.ai\n(Pro, annual)", 100, "$8.33/mo"),
    ("TurboScribe\n(Unlimited, annual)", 120, "$10/mo"),
    ("Descript\n(Hobbyist, annual)", 192, "$16/mo"),
    ("Rev\n(Essentials, annual)", 306, "$25.49/mo"),
]

BG = "#12161f"
FG = "#e6edf3"
ACCENT = "#4fc3f7"
MUTED = "#8899aa"
FREE_COLOR = "#4ecca3"
PAID_COLOR = "#4d6a8a"


def main() -> None:
    labels = [d[0] for d in DATA]
    values = [d[1] for d in DATA]
    colors = [FREE_COLOR] + [PAID_COLOR] * (len(DATA) - 1)

    fig, ax = plt.subplots(figsize=(9, 5), dpi=200)
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)

    bars = ax.bar(labels, values, color=colors, width=0.6, zorder=3)

    for bar, (_, value, note) in zip(bars, DATA, strict=True):
        height = bar.get_height()
        label = "$0/yr" if value == 0 else f"${value}/yr"
        ax.text(
            bar.get_x() + bar.get_width() / 2, height + 6,
            label, ha="center", va="bottom", color=FG, fontsize=12, fontweight="bold",
        )
        ax.text(
            bar.get_x() + bar.get_width() / 2, -18,
            note, ha="center", va="top", color=MUTED, fontsize=9,
        )

    ax.set_title(
        "Yearly cost — VideoTranscriber vs. cloud transcription subscriptions",
        color=FG, fontsize=13, pad=16,
    )
    ax.set_ylabel(
        "USD per year (cheapest individual plan, billed annually)",
        color=MUTED, fontsize=9,
    )
    ax.tick_params(colors=FG, labelsize=10)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(MUTED)
    ax.spines["bottom"].set_color(MUTED)
    ax.yaxis.grid(True, color="#2a3444", linewidth=0.7, zorder=0)
    ax.set_axisbelow(True)
    ax.set_ylim(0, max(values) * 1.2)

    fig.tight_layout()
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    fig.savefig(OUT_PATH, facecolor=BG)
    print(f"[make_cost_chart] wrote {os.path.abspath(OUT_PATH)}")


if __name__ == "__main__":
    main()
