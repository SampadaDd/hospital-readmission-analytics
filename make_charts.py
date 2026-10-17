#!/usr/bin/env python3
"""
Build the project's charts from CSVs exported by psql.
Run after loading the data:  python3 analysis/make_charts.py
Outputs PNGs into charts/.
"""
import csv
from datetime import datetime
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

# --- shared style: clean, recessive gridlines, colorblind-safe hues ---
plt.rcParams.update({
    "figure.dpi": 130,
    "font.size": 11,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.color": "#E6E6E6",
    "grid.linewidth": 0.8,
    "axes.axisbelow": True,
})
INK = "#1A1A1A"
MUTED = "#6B6B6B"
ACCENT = "#2B6CB0"     # calm blue (magnitude)
ALERT = "#C05621"      # burnt orange (the ward to worry about)
NEUTRAL = "#A0AEC0"

def read_csv(path):
    with open(path) as f:
        return [row for row in csv.reader(f) if row and row[0]]

# ============================================================
# Chart 1 — Ward readmission rates (the headline finding)
# ============================================================
rows = read_csv("analysis/ward_rates.csv")
wards = [r[0] for r in rows]
rates = [float(r[3]) for r in rows]
totals = [int(r[1]) for r in rows]
# color the worst ward in alert, the rest in neutral blue
colors = [ALERT if i == 0 else ACCENT for i in range(len(wards))]

fig, ax = plt.subplots(figsize=(7.5, 4.2))
bars = ax.barh(wards[::-1], rates[::-1], color=colors[::-1], height=0.62)
ax.set_xlabel("30-day readmission rate (%)", color=MUTED)
ax.set_title("ICU has the highest 30-day readmission rate",
             fontsize=13, fontweight="bold", color=INK, loc="left", pad=12)
ax.grid(axis="y", visible=False)
for bar, rate, tot in zip(bars, rates[::-1], totals[::-1]):
    ax.text(bar.get_width() + 0.4, bar.get_y() + bar.get_height()/2,
            f"{rate:.1f}%  (n={tot})", va="center", color=INK, fontsize=10)
ax.set_xlim(0, max(rates) * 1.25)
ax.tick_params(colors=MUTED)
fig.text(0.01, -0.02,
         "Overall hospital rate: 16.2%.  Source: 3,000 admissions, 2025.",
         fontsize=8.5, color=MUTED)
fig.tight_layout()
fig.savefig("charts/ward_readmission_rates.png", bbox_inches="tight")
plt.close(fig)
print("wrote charts/ward_readmission_rates.png")

# ============================================================
# Chart 2 — Daily bed occupancy across the year
# ============================================================
rows = read_csv("analysis/occupancy.csv")
days = [datetime.strptime(r[0], "%Y-%m-%d") for r in rows]
occ = [int(r[1]) for r in rows]

fig, ax = plt.subplots(figsize=(9, 4))
ax.plot(days, occ, color=ACCENT, linewidth=1.6)
ax.fill_between(days, occ, color=ACCENT, alpha=0.08)
peak = max(occ); peak_day = days[occ.index(peak)]
ax.scatter([peak_day], [peak], color=ALERT, s=28, zorder=5)
ax.annotate(f"peak {peak} beds\n{peak_day:%b %d}",
            (peak_day, peak), textcoords="offset points", xytext=(8, -6),
            fontsize=9, color=ALERT)
ax.set_ylabel("Beds occupied", color=MUTED)
ax.set_title("Bed occupancy peaks in winter, eases through summer",
             fontsize=13, fontweight="bold", color=INK, loc="left", pad=12)
ax.tick_params(colors=MUTED)
ax.set_ylim(0, peak * 1.15)
fig.text(0.01, -0.02,
         "Computed via interval-overlap over a recursive-CTE date spine; "
         "quiet days correctly included.  (Dec tapers as the sample window ends.)",
         fontsize=8.5, color=MUTED)
fig.tight_layout()
fig.savefig("charts/bed_occupancy.png", bbox_inches="tight")
plt.close(fig)
print("wrote charts/bed_occupancy.png")

# ============================================================
# Chart 3 — Monthly admissions (seasonality)
# ============================================================
rows = read_csv("analysis/monthly.csv")
# drop the final partial month for the trend read, but keep a note
months = [r[0] for r in rows]
counts = [int(r[1]) for r in rows]
labels = [datetime.strptime(m, "%Y-%m").strftime("%b") for m in months]
# gray out the last (partial) month
bar_colors = [ACCENT]*(len(counts)-1) + [NEUTRAL]

fig, ax = plt.subplots(figsize=(9, 4))
bars = ax.bar(labels, counts, color=bar_colors, width=0.68)
ax.set_ylabel("Admissions", color=MUTED)
ax.set_title("Admissions run higher in winter (Jan–Mar, Nov)",
             fontsize=13, fontweight="bold", color=INK, loc="left", pad=12)
ax.grid(axis="x", visible=False)
ax.yaxis.set_major_locator(MaxNLocator(integer=True))
ax.tick_params(colors=MUTED)
ax.text(len(counts)-1, counts[-1]+8, "partial\nmonth", ha="center",
        fontsize=8, color=MUTED)
fig.text(0.01, -0.02, "Source: 3,000 admissions, 2025.",
         fontsize=8.5, color=MUTED)
fig.tight_layout()
fig.savefig("charts/monthly_admissions.png", bbox_inches="tight")
plt.close(fig)
print("wrote charts/monthly_admissions.png")
