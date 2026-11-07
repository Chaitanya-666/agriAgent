"""Draw the held-out trade-off figure for the final report (docs/thesis/figures/tradeoff_holdout.png).

Numbers copied from docs/results/holdout_plant_rules_v3_20261018.md (sugar beet, 90 held-out photos).
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "docs/thesis/figures/tradeoff_holdout.png"
# (label, crop sprayed %, weed recall %, group)
POINTS = [
    ("gate 0.35", 65.45, 1.78, "Grounded SAM label policy"),
    ("gate 0.50", 22.45, 0.0, "Grounded SAM label policy"),
    ("gate 0.70 (deployed)", 0.0, 0.0, "Grounded SAM label policy"),
    ("gate 0.35 + exclusion", 41.92, 1.78, "Grounded SAM label policy"),
    ("gate 0.50 + exclusion", 5.51, 0.0, "Grounded SAM label policy"),
    ("plant rules v3 (product)", 8.84, 77.93, "Plant rules + gate"),
]
COLORS = {"Grounded SAM label policy": "#2a78d6", "Plant rules + gate": "#eb6834"}
OFFSETS = {
    "gate 0.35": (-6, 6, "right"),
    "gate 0.50": (0, 6, "center"),
    "gate 0.70 (deployed)": (6, 9, "left"),
    "gate 0.35 + exclusion": (0, 6, "center"),
    "gate 0.50 + exclusion": (8, -12, "left"),
    "plant rules v3 (product)": (8, -4, "left"),
}

fig, ax = plt.subplots(figsize=(6.4, 4.2), dpi=200)
for spine in ("top", "right"):
    ax.spines[spine].set_visible(False)
for spine in ("left", "bottom"):
    ax.spines[spine].set_color("#9a9a96")
ax.grid(color="#e6e5e0", linewidth=0.6)
ax.set_axisbelow(True)
for group, color in COLORS.items():
    xs = [p[1] for p in POINTS if p[3] == group]
    ys = [p[2] for p in POINTS if p[3] == group]
    ax.scatter(xs, ys, s=70, color=color, edgecolor="white", linewidth=2, label=group, zorder=3)
for label, x, y, _ in POINTS:
    dx, dy, ha = OFFSETS[label]
    ax.annotate(label, (x, y), xytext=(dx, dy), textcoords="offset points", ha=ha, fontsize=8,
                color="#3d3d3a")
ax.annotate("better: more weeds,\nless crop", (2, 95), fontsize=8, color="#6b6b66", va="top")
ax.set_xlim(-3, 72)
ax.set_ylim(-6, 100)
ax.set_xlabel("Crop pixels sprayed (%)  — lower is better", fontsize=9, color="#3d3d3a")
ax.set_ylabel("Weed recall (%)  — higher is better", fontsize=9, color="#3d3d3a")
ax.tick_params(labelsize=8, colors="#3d3d3a")
ax.legend(fontsize=8, frameon=False, loc="center right")
ax.set_title("Held-out sugar beet, 90 photos", fontsize=10, color="#1f1f1d", loc="left")
fig.tight_layout()
OUT.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(OUT)
print(OUT)
