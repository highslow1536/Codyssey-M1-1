"""Render the submission report's recent-price figure from the saved weekly CSV.

Offline and descriptive only. Missing calendar weeks remain gaps; no forecasts
or price imputation are produced. Run from any working directory.
"""

import argparse
import csv
from datetime import date
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".mplconfig"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

INPUT = ROOT / "data/processed/2026-10-23/recent/parts_weekly.csv"
DEFAULT_OUTPUT = ROOT / "data/analysis/2026-10-23/figures"
PRODUCTS = (
    ("B07STGGQ18", "CPU | AMD Ryzen 5 3600", "#3569a8"),
    ("B07MFZY2F2", "SSD | Samsung 970 EVO Plus 1TB", "#257d70"),
)


def make_figure(output_dir=DEFAULT_OUTPUT):
    with INPUT.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    plt.rcParams.update({
        "figure.facecolor": "#fafbfe", "axes.facecolor": "white",
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.edgecolor": "#d3dae5", "text.color": "#18283d",
        "axes.labelcolor": "#29384a", "xtick.color": "#516176",
        "ytick.color": "#516176", "grid.color": "#e6ebf2",
        "font.size": 11, "svg.hashsalt": "codyssey-recent-prices",
    })
    fig, axes = plt.subplots(2, 1, figsize=(12, 8.3), sharex=True)
    fig.subplots_adjust(left=.09, right=.97, top=.77, bottom=.16, hspace=.55)
    fig.suptitle("Observed PC part prices, 2023-2026", x=.09, y=.97,
                 ha="left", fontsize=20, weight="bold")
    fig.text(.09, .91, "US Amazon listing quotes | last observed price per Saturday-Friday week",
             fontsize=11)
    fig.text(.09, .87, "198 calendar weeks per SKU through 2026-10-16; missing weeks stay empty.",
             fontsize=10, color="#516176")
    for ax, (product_id, title, color) in zip(axes, PRODUCTS):
        product = sorted((r for r in rows if r["product_id"] == product_id),
                         key=lambda r: r["week_end"])
        dates = [date.fromisoformat(r["week_end"]) for r in product]
        prices = [float(r["price_usd"]) if r["price_usd"] else float("nan")
                  for r in product]
        observed = [r for r in product if r["price_usd"]]
        last = observed[-1]
        ax.plot(dates, prices, color=color, linewidth=1.8, marker=".", markersize=3)
        ax.set_title(f"{title} | {len(observed)}/{len(product)} observed weeks", loc="left",
                     fontsize=12, pad=27)
        ax.text(0, 1.035,
                f"Last observed week: {last['week_end']} | quote date: {last['quote_date']}"
                f" | USD {float(last['price_usd']):,.2f}",
                transform=ax.transAxes, fontsize=10, color="#516176")
        ax.set_ylabel("Listing price (USD)")
        ax.set_ylim(bottom=0)
        ax.grid(axis="y", linewidth=.7)
        ax.set_xlim(dates[0], dates[-1])
        print(f"{product_id}: {len(observed)}/{len(product)} observed, "
              f"first={observed[0]['week_end']} USD {observed[0]['price_usd']}, "
              f"last={last['week_end']} USD {last['price_usd']}")
    axes[-1].xaxis.set_major_locator(mdates.MonthLocator(bymonth=(1, 7)))
    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    fig.text(.09, .055, "PriceHistory source snapshot: 2026-10-21 | Analysis cutoff: 2026-10-23 | No interpolation",
             fontsize=9, color="#516176")
    fig.text(.09, .025, "Two older SKUs; not a market index, transaction price, current Korean quote, or forecast.",
             fontsize=9, color="#516176")
    output_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_dir / "01_recent_prices.png", dpi=160)
    fig.savefig(output_dir / "01_recent_prices.svg", metadata={"Date": None})
    plt.close(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    make_figure(parser.parse_args().output_dir)
