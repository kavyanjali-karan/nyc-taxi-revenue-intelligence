"""Build the governed monthly revenue mart from the raw TLC parquets.

Reads data/raw/green_tripdata_*.parquet, applies the documented cleaning
rules, and writes data/curated/monthly_revenue.csv plus a metrics summary
(data/curated/metrics.json) used by the dashboard and the README.

Business decisions (documented, not silent):
  - refund rows (negative amounts, payment_type 3/4) are kept and reported
    separately as "adjustments", never netted silently into revenue
  - trips whose fare components do not sum to total_amount (a 12% gap in
    the raw feed) are kept but flagged unbalanced; reported revenue uses
    the metered total, and the discrepancy is quantified per month
  - the 100%-null ehail_fee column is dropped
  - rows in the 6,343-row null block (store_and_fwd_flag, payment_type,
    trip_type, passenger_count, RatecodeID all null) are kept for trip
    counting but excluded from payment-mix percentages
"""
from pathlib import Path
import json

import pandas as pd

PROJECT = Path(__file__).resolve().parents[1]
RAW = PROJECT / "data" / "raw"
CURATED = PROJECT / "data" / "curated"

DROP_COLS = ["ehail_fee"]
PAYMENT_LABELS = {
    1.0: "Card",
    2.0: "Cash",
    3.0: "No charge",
    4.0: "Disputed",
    5.0: "Unknown",
    6.0: "Voided",
}
COMPONENT_COLS = [
    "fare_amount", "extra", "mta_tax", "tip_amount",
    "tolls_amount", "improvement_surcharge", "congestion_surcharge",
]
TOLERANCE = 0.01


def load() -> pd.DataFrame:
    files = sorted(RAW.glob("green_tripdata_*.parquet"))
    if not files:
        raise SystemExit("no raw parquets found; run: python data/get_data.py")
    frames = [pd.read_parquet(f) for f in files]
    return pd.concat(frames, ignore_index=True)


def clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.drop(columns=[c for c in DROP_COLS if c in df.columns])
    df["pickup_month"] = df["lpep_pickup_datetime"].dt.strftime("%Y-%m")
    df["payment_label"] = df["payment_type"].map(PAYMENT_LABELS).fillna("Unknown")
    df["is_refund"] = (df["total_amount"] < 0) | df["payment_type"].isin([3.0, 4.0])
    components = df[COMPONENT_COLS].sum(axis=1)
    df["is_unbalanced"] = (components - df["total_amount"]).abs() > TOLERANCE
    df["is_zero_distance"] = df["trip_distance"] == 0
    df["has_payment_info"] = df["payment_type"].notna()
    return df


def monthly_mart(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby("pickup_month")
    mart = pd.DataFrame({
        "trips": g.size(),
        "revenue_gross": g["total_amount"].sum().round(2),
        "adjustments": g.apply(lambda x: x.loc[x["is_refund"], "total_amount"].sum()).round(2),
        "revenue_net": g.apply(lambda x: x.loc[~x["is_refund"], "total_amount"].sum()).round(2),
        "unbalanced_rows": g["is_unbalanced"].sum(),
        "unbalanced_delta": g.apply(
            lambda x: (x[COMPONENT_COLS].sum(axis=1) - x["total_amount"])
            .abs()[x["is_unbalanced"]].sum()
        ).round(2),
        "zero_distance_trips": g["is_zero_distance"].sum(),
        "card_share_pct": g.apply(
            lambda x: round(100 * (x.loc[x["has_payment_info"], "payment_label"] == "Card").mean(), 1)
        ),
        "avg_fare": g["fare_amount"].mean().round(2),
        "avg_distance": g["trip_distance"].mean().round(2),
    })
    return mart.reset_index()


def main(argv=None):
    raw = load()
    df = clean(raw)
    CURATED.mkdir(parents=True, exist_ok=True)

    mart = monthly_mart(df)
    mart.to_csv(CURATED / "monthly_revenue.csv", index=False)

    metrics = {
        "source": "NYC TLC green taxi tripdata (official TLC CDN parquets)",
        "months_loaded": sorted(df["pickup_month"].unique().tolist()),
        "raw_rows": int(len(raw)),
        "governance": {
            "ehail_fee_null_pct": round(100 * raw["ehail_fee"].isna().mean(), 1) if "ehail_fee" in raw else None,
            "null_block_rows": int(raw["payment_type"].isna().sum()),
            "refund_rows": int(df["is_refund"].sum()),
            "adjustments_total": round(float(df.loc[df["is_refund"], "total_amount"].sum()), 2),
            "unbalanced_rows": int(df["is_unbalanced"].sum()),
            "unbalanced_pct": round(100 * df["is_unbalanced"].mean(), 1),
            "zero_distance_trips": int(df["is_zero_distance"].sum()),
            "ratecode_99_rows": int((raw["RatecodeID"] == 99).sum()),
            "trips_over_50_miles": int((raw["trip_distance"] > 50).sum()),
            "max_recorded_distance_miles": round(float(raw["trip_distance"].max()), 2),
        },
        "headline": {
            "trips": int(len(df)),
            "revenue_gross": round(float(df["total_amount"].sum()), 2),
            "revenue_net": round(float(df.loc[~df["is_refund"], "total_amount"].sum()), 2),
            "card_share_pct": round(
                100 * (df.loc[df["has_payment_info"], "payment_label"] == "Card").mean(), 1
            ),
        },
    }
    (CURATED / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(mart.to_string(index=False))
    print(f"\nwrote {CURATED / 'monthly_revenue.csv'} and metrics.json")


if __name__ == "__main__":
    main()
