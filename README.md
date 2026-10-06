# NYC Taxi Revenue Intelligence

Real NYC TLC green-taxi trip records, processed with the same governance
discipline as a production billing pipeline: every cleaning rule is
documented, every headline number reconciles to source rows, and the messy
parts of the feed are quantified instead of silently cleaned away.

[![tests: 8 passed](https://img.shields.io/badge/tests-8%20passed-2ea44f)](tests/)

The data comes from the official TLC CDN and it fights back — which is the
point. It is not generated, seeded, or simulated.

## What the raw feed actually looks like

Across 110,128 trips (Jan–Feb 2024 files), the pipeline found and reported:

| Data reality | Size | How it's handled |
|---|---|---|
| `ehail_fee` is 100% null | every row | dropped, documented |
| 6,343 trips have five columns null at once (payment, rate code, passenger count...) | 5.8% | kept for trip counts, excluded from payment-mix percentages |
| 1,062 refund-classified rows (negative totals, no-charge, disputed) | 1.0% | kept as a signed **adjustments** column — refunds (−$3,855.90) and fare waivers (+$5,291.74) net to +$5,069.90; never silently netted into revenue |
| **15,187 trips (13.8%) where fare components don't sum to the metered total** | 13.8% | flagged `is_unbalanced`; $27,528.90 delta quantified per month |
| 5,716 trips with zero distance | 5.2% | counted, reported |
| 83 trips recorded over 50 miles — max **201,421.68 miles** | 0.1% | counted, reported; distance stats report the median alongside the mean, because these rows drag the mean up |
| RatecodeID 99 (value absent from the data dictionary) | 8 rows | counted, left intact |

## Headline numbers

| Metric | Jan 2024 | Feb 2024 |
|---|---|---|
| Trips | 56,555 | 53,571 |
| Gross revenue | $1,267,028.59 | $1,212,509.50 |
| Signed adjustments | +$2,811.44 | +$2,258.46 |
| Net revenue | $1,264,217.15 | $1,210,251.04 |
| Card share (known payment type) | 69.0% | 69.9% |
| Unbalanced fare rows | 8,034 | 7,153 |

*(I never typed any of these numbers by hand — `python python/build_mart.py` recomputes all of it from the raw parquets, and the tests fail if the README's story drifts from the mart)*

## Run it

```bash
pip install -r requirements.txt
python data/get_data.py                # downloads real TLC parquets (~2.6 MB, cached)
python python/build_mart.py            # cleans, governs, writes mart + metrics.json
python python/render_dashboard.py      # renders assets/monthly_revenue_dashboard.png
pytest -q                              # 8 tests reconcile everything
```

A fresh clone reproduces every number: downloads are cached, cleaning rules
live in `python/build_mart.py`, and the tests assert the mart reconciles to
the raw rows.

## Project structure

```
├── data/
│   ├── get_data.py          # official TLC CDN downloader (cached)
│   └── raw/                 # green_tripdata_*.parquet (gitignored)
├── python/
│   ├── build_mart.py        # governed monthly revenue mart
│   └── render_dashboard.py  # dashboard PNG renderer
├── tests/test_build_mart.py # reconciliation + governance tests
├── assets/                  # dashboard PNG
└── data/curated/            # monthly_revenue.csv, metrics.json
```

## Why this matters

Simulated datasets are clean by construction — they never teach you to
handle a 13.8% reconciliation gap, a 100%-null column, signed adjustments
that can net positive, or a 201,000-mile taxi trip. Real revenue data
disagrees with itself, and a governed pipeline has to say so out loud.
