"""Download NYC TLC green taxi tripdata parquets from the official CDN.

Usage:
    python data/get_data.py --months 2024-01 2024-02

Files land in data/raw/ as green_tripdata_<month>.parquet and are never
committed to git. Re-running a month that already exists skips the download.
"""
import argparse
from pathlib import Path
import urllib.request

BASE = "https://d37ci6vzurychx.cloudfront.net/trip-data/green_tripdata_{month}.parquet"
RAW = Path(__file__).resolve().parents[1] / "data" / "raw"

MONTHS = [
    "2024-01", "2024-02", "2024-03", "2024-04", "2024-05", "2024-06",
    "2024-07", "2024-08", "2024-09", "2024-10", "2024-11", "2024-12",
]


def fetch(month: str, dest: Path) -> str:
    if dest.exists() and dest.stat().st_size > 0:
        return "cached"
    url = BASE.format(month=month)
    urllib.request.urlretrieve(url, dest)
    return "downloaded"


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--months", nargs="+", default=["2024-01", "2024-02"],
                   help="months in YYYY-MM form (default: 2024-01 2024-02)")
    args = p.parse_args(argv)

    RAW.mkdir(parents=True, exist_ok=True)
    for m in args.months:
        if m not in MONTHS:
            raise SystemExit(f"unknown month {m!r}; use YYYY-MM in 2024")
        dest = RAW / f"green_tripdata_{m}.parquet"
        status = fetch(m, dest)
        print(f"{m}: {status} ({dest.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
