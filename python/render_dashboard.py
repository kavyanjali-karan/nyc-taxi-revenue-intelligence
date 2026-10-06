"""Render the monthly revenue dashboard PNG from the curated mart."""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

PROJECT = Path(__file__).resolve().parents[1]
MART = PROJECT / "data" / "curated" / "monthly_revenue.csv"
OUT = PROJECT / "assets"

LABELS = {"2024-01": "Jan 2024", "2024-02": "Feb 2024"}


def main(argv=None):
    if not MART.exists():
        raise SystemExit("run python python/build_mart.py first")
    df = pd.read_csv(MART)
    OUT.mkdir(exist_ok=True)

    x = range(len(df))
    labels = [LABELS.get(m, m) for m in df["pickup_month"]]
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5))

    ax = axes[0]
    ax.bar(x, df["revenue_gross"], color="#2a6f97", label="Gross revenue")
    ax.bar(x, df["revenue_net"], color="#61a5c2", label="Net revenue")
    bars = ax.bar(x, df["adjustments"].abs(), bottom=df["revenue_net"],
                  color="#c1121f", alpha=0.85, label="Refunds/adjustments")
    for b, v in zip(bars, df["adjustments"]):
        sign = "-" if v < 0 else "+"
        ax.text(b.get_x() + b.get_width()/2, b.get_y() + b.get_height() + 1500,
                f"{sign}${abs(v):,.0f}", ha="center", fontsize=8, color="#c1121f")
    ax.set_title("Revenue: gross vs net of refunds")
    ax.set_ylabel("USD")
    ax.set_xticks(x, labels)
    ax.legend(fontsize=8)

    ax = axes[1]
    pct = 100 * df["unbalanced_rows"] / df["trips"]
    bars = ax.bar(x, pct, color="#e09f3e")
    for b, v, n in zip(bars, pct, df["unbalanced_rows"]):
        ax.text(b.get_x() + b.get_width()/2, v + 0.1, f"{v:.1f}%\n({n:,} rows)",
                ha="center", fontsize=8)
    ax.set_title("Fare components that don't sum to the metered total")
    ax.set_ylabel("% of trips")
    ax.set_xticks(x, labels)
    ax.set_ylim(0, max(pct) * 1.35)

    ax = axes[2]
    ax.bar(x, df["card_share_pct"], color="#588157", width=0.5)
    for i, v in enumerate(df["card_share_pct"]):
        ax.text(i, v + 0.5, f"{v}%", ha="center", fontsize=9)
    ax.set_title("Card share of paid trips (payment_type known)")
    ax.set_ylabel("%")
    ax.set_xticks(x, labels)
    ax.set_ylim(0, 100)

    fig.suptitle("NYC Green Taxi - Monthly Revenue Intelligence (Jan-Feb 2024)", fontsize=12)
    fig.tight_layout(rect=[0, 0, 1, 0.93])
    fig.savefig(OUT / "monthly_revenue_dashboard.png", dpi=130)
    print(f"wrote {OUT / 'monthly_revenue_dashboard.png'}")


if __name__ == "__main__":
    main()
