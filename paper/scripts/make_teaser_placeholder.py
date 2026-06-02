#!/usr/bin/env python3
"""Generate a trivial placeholder teaser figure for the OrgMemBench paper.

This is a stand-in for the real Figure 1 (the system diagram). It draws the
four-stage evaluation pipeline as labeled boxes so the paper has *something*
in the Figure 1 slot until the real diagram is produced. Replace it.

Usage:
    python scripts/make_teaser_placeholder.py

Writes: figures/teaser_placeholder.pdf

Requires matplotlib. If matplotlib is not installed, this script exits 0 with a
message rather than failing (the paper's \\IfFileExists guard handles the
missing-file case gracefully).
"""
import os
import sys

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "figures", "teaser_placeholder.pdf")


def main() -> int:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
    except Exception as exc:  # noqa: BLE001
        print(f"matplotlib unavailable ({exc!r}); skipping teaser placeholder.")
        print("The paper falls back to a framed TODO box via \\IfFileExists.")
        return 0

    stages = [
        "Synthetic\norg. corpus",
        "Temporal\nquestions",
        "Memory\nsystem",
        "Answer\nevaluation",
    ]

    fig, ax = plt.subplots(figsize=(9, 2.4))
    ax.set_xlim(0, len(stages) * 2.6)
    ax.set_ylim(0, 2)
    ax.axis("off")

    box_w, box_h, gap = 2.0, 1.2, 0.6
    centers = []
    for i, label in enumerate(stages):
        x = i * (box_w + gap)
        box = FancyBboxPatch(
            (x, 0.4), box_w, box_h,
            boxstyle="round,pad=0.02,rounding_size=0.12",
            linewidth=1.2, edgecolor="#222222", facecolor="#eef2f7",
        )
        ax.add_patch(box)
        ax.text(x + box_w / 2, 0.4 + box_h / 2, label,
                ha="center", va="center", fontsize=11)
        centers.append((x + box_w, x))

    for i in range(len(stages) - 1):
        x_end_prev = centers[i][0]
        x_start_next = centers[i + 1][1]
        arrow = FancyArrowPatch(
            (x_end_prev + 0.05, 1.0), (x_start_next - 0.05, 1.0),
            arrowstyle="-|>", mutation_scale=16, linewidth=1.2, color="#222222",
        )
        ax.add_patch(arrow)

    ax.text(ax.get_xlim()[1] / 2, 1.85,
            "PLACEHOLDER teaser --- replace with the real OrgMemBench system diagram",
            ha="center", va="center", fontsize=8, color="#999999", style="italic")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    fig.savefig(OUT, bbox_inches="tight", dpi=300)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
