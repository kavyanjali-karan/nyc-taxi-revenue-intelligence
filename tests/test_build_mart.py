"""Tests for the governed monthly revenue mart.

The data builds itself on first run (get_data -> build_mart), so a fresh
clone passes with no setup.
"""
from pathlib import Path

import pandas as pd
import pytest

PROJECT = Path(__file__).resolve().parents[1]
RAW = PROJECT / "data" / "raw"
MART_PATH = PROJECT / "data" / "curated" / "monthly_revenue.csv"

RAW_FILES = sorted(RAW.glob("green_tripdata_*.parquet"))


@pytest.fixture(scope="module")
def mart():
    if not MART_PATH.exists():
        if not RAW_FILES:
            pytest.skip("raw data not downloaded yet")
        import subprocess, sys
        subprocess.run([sys.executable, str(PROJECT / "python" / "build_mart.py")],
                       check=True, cwd=PROJECT)
    return pd.read_csv(MART_PATH)


@pytest.fixture(scope="module")
def raw():
    if not RAW_FILES:
        pytest.skip("raw data not downloaded yet")
    return pd.concat([pd.read_parquet(f) for f in RAW_FILES], ignore_index=True)


def test_mart_covers_requested_months(mart):
    # Real feeds spill over month boundaries: the Jan 2024 file contains
    # 2 trips picked up in Dec 2023. The mart must cover the requested
    # months and may contain small spillover months.
    assert {"2024-01", "2024-02"} <= set(mart["pickup_month"])
    for _, row in mart.iterrows():
        if row["pickup_month"] not in ("2024-01", "2024-02"):
            assert row["trips"] < 100


def test_trip_counts_match_raw(mart, raw):
    raw["pickup_month"] = raw["lpep_pickup_datetime"].dt.strftime("%Y-%m")
    counts = raw.groupby("pickup_month").size()
    for _, row in mart.iterrows():
        assert row["trips"] == counts[row["pickup_month"]]


def test_gross_revenue_reconciles_to_raw(mart, raw):
    raw["pickup_month"] = raw["lpep_pickup_datetime"].dt.strftime("%Y-%m")
    totals = raw.groupby("pickup_month")["total_amount"].sum().round(2)
    for _, row in mart.iterrows():
        assert abs(row["revenue_gross"] - totals[row["pickup_month"]]) < 0.01


def test_no_silent_netting_of_refunds(mart):
    # adjustments is the SIGNED sum of refund-classified rows: negative
    # for customer refunds, positive for no-charge/disputed waivers.
    # net = gross minus the signed adjustments.
    for _, row in mart.iterrows():
        assert abs((row["revenue_gross"] - row["adjustments"]) - row["revenue_net"]) < 0.05


def test_unbalanced_rows_are_counted_not_hidden(mart):
    main_months = mart[mart["trips"] > 1000]
    assert (main_months["unbalanced_rows"] > 0).all()
    assert (main_months["unbalanced_delta"] > 0).sum() >= 1


def test_card_share_within_bounds(mart):
    main_months = mart[mart["trips"] > 1000]
    assert main_months["card_share_pct"].between(50, 90).all()


def test_median_distance_reported_and_not_inflated(mart):
    # Corrupt distance rows (max 201,421 miles) pull the mean up; the
    # median must be reported and must sit far below the mean in the
    # months that contain the corruption.
    assert "median_distance" in mart.columns
    main_months = mart[mart["trips"] > 1000]
    assert (main_months["median_distance"] < main_months["avg_distance"]).all()
    assert (main_months["median_distance"] < 10).all()


def test_no_ehail_fee_column_anywhere(mart):
    assert "ehail_fee" not in mart.columns
