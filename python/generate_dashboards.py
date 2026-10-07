"""Generate the interactive NYC taxi dashboard from the governed mart.

Reads data/curated/monthly_revenue.csv, distributions.json and metrics.json
(all produced by build_mart.py) and writes an interactive Chart.js dashboard
plus a small landing page for GitHub Pages.

Usage: python python/generate_dashboards.py
Output: assets/dashboard.html, assets/index.html
"""
import csv
import json
import tempfile
from pathlib import Path

# Chart.js is inlined when a local copy exists (CI downloads one), so the
# dashboard works offline and without depending on a CDN at view time.
CHART_JS = Path(tempfile.gettempdir()) / "chart.min.js"
CHART_JS_URL = "https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"
if CHART_JS.exists():
    CHART_JS_TAG = "<script>\n" + CHART_JS.read_text(encoding="utf-8") + "\n</script>"
else:
    CHART_JS_TAG = f'<script src="{CHART_JS_URL}"></script>'

ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "data" / "curated"
OUT_DASH = ROOT / "assets" / "dashboard.html"
OUT_INDEX = ROOT / "assets" / "index.html"

MONTH_LABELS = {"2023-12": "Dec 2023", "2024-01": "Jan 2024", "2024-02": "Feb 2024"}


def main():
    with open(DATA_DIR / "monthly_revenue.csv", encoding="utf-8") as f:
        mart = list(csv.DictReader(f))
    metrics = json.loads((DATA_DIR / "metrics.json").read_text(encoding="utf-8"))
    dists = json.loads((DATA_DIR / "distributions.json").read_text(encoding="utf-8"))

    months = [r["pickup_month"] for r in mart if int(r["trips"]) >= 1000]
    spillover = {r["pickup_month"]: int(r["trips"]) for r in mart if int(r["trips"]) < 1000}
    gov = metrics["governance"]
    head = metrics["headline"]

    unbal_delta = sum(float(r["unbalanced_delta"]) for r in mart if int(r["trips"]) >= 1000)
    spill_note = ", ".join(
        f"{MONTH_LABELS.get(k, k)}: {v} trips" for k, v in sorted(spillover.items())
    ) or "none"

    options = '<option value="all">All months</option>' + "".join(
        f'<option value="{m}">{MONTH_LABELS.get(m, m)}</option>' for m in months)

    kpis = [
        ("Real trips", f"{head['trips']:,}", "official TLC parquets, nothing seeded"),
        ("Gross revenue", f"${head['revenue_gross'] / 1e6:.2f}M", "metered totals, as recorded"),
        ("Net revenue", f"${head['revenue_net'] / 1e6:.2f}M", "gross minus signed adjustments"),
        ("Card share", f"{head['card_share_pct']}%", "of trips with a recorded payment type"),
        ("Unbalanced fares", f"{gov['unbalanced_pct']}%",
         f"{gov['unbalanced_rows']:,} rows · ${unbal_delta:,.2f} unexplained"),
        ("Signed adjustments", f"+${gov['adjustments_total']:,.2f}",
         f"{gov['refund_rows']:,} refund rows, kept and reported"),
    ]
    kpi_html = "".join(
        f'<div class="kpi"><div class="kpi-label">{label}</div>'
        f'<div class="kpi-val">{val}</div><div class="kpi-note">{note}</div></div>'
        for label, val, note in kpis)

    gov_rows = [
        ("ehail_fee column", "100% null", "dropped, documented"),
        ("Payment block nulls", f"{gov['null_block_rows']:,} rows",
         "kept for trip counts, excluded from payment-mix percentages"),
        ("Refund-classified trips", f"{gov['refund_rows']:,}",
         f"net signed adjustment +${gov['adjustments_total']:,.2f}, never silently netted"),
        ("Fare parts don't sum to the total", f"{gov['unbalanced_rows']:,} ({gov['unbalanced_pct']}%)",
         "flagged is_unbalanced; delta quantified per month"),
        ("Zero-distance trips", f"{gov['zero_distance_trips']:,}", "counted, reported"),
        ("RatecodeID 99 (absent from the dictionary)", f"{gov['ratecode_99_rows']} rows",
         "counted, left intact"),
        ("Trips recorded over 50 miles", f"{gov['trips_over_50_miles']}",
         f"max {gov['max_recorded_distance_miles']:,.2f} mi; median reported alongside mean"),
        ("Pickups dated before the file's month", spill_note,
         "own mart month, covered by a test"),
    ]
    gov_html = "".join(
        f'<tr><td>{a}</td><td class="num">{b}</td><td>{c}</td></tr>'
        for a, b, c in gov_rows)

    data = {
        "months": months,
        "labels": {m: MONTH_LABELS.get(m, m) for m in months},
        "mart": mart,
        "payment_mix": {m: dists["payment_mix"].get(m, {}) for m in months},
        "payment_not_recorded": {m: dists["payment_not_recorded"].get(m, 0) for m in months},
        "hourly": {m: dists["hourly"].get(m, []) for m in months},
        "distance_buckets": {m: dists["distance_buckets"].get(m, {}) for m in months},
    }

    html = (TEMPLATE
            .replace("__CHART_JS__", CHART_JS_TAG)
            .replace("__DATA_JSON__", json.dumps(data, ensure_ascii=False))
            .replace("__KPI_CARDS__", kpi_html)
            .replace("__GOV_ROWS__", gov_html)
            .replace("__MONTH_OPTIONS__", options)
            .replace("__SUBTITLE__",
                     f"{head['trips']:,} real TLC trips · Jan–Feb 2024 files · governed mart"))
    OUT_DASH.parent.mkdir(exist_ok=True)
    OUT_DASH.write_text(html, encoding="utf-8")

    index = (INDEX_TEMPLATE
             .replace("__TRIPS__", f"{head['trips']:,}")
             .replace("__GROSS__", f"${head['revenue_gross'] / 1e6:.2f}M"))
    OUT_INDEX.write_text(index, encoding="utf-8")
    print(f"Dashboard generated: {OUT_DASH}")
    print(f"  Trips: {head['trips']:,} | Gross: ${head['revenue_gross'] / 1e6:.2f}M "
          f"| Card share: {head['card_share_pct']}%")


TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NYC Green Taxi — Revenue Intelligence</title>
    __CHART_JS__
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', system-ui, sans-serif; background: #f5f7fa; color: #1e293b; }
        .topbar { background: #0f172a; color: #fff; padding: 10px 24px; display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; }
        .topbar h1 { font-size: 15px; font-weight: 600; }
        .topbar .sub { color: #94a3b8; font-size: 11px; }
        .topbar select { background: #1e293b; color: #e2e8f0; border: 1px solid #334155; border-radius: 5px; padding: 4px 8px; font-size: 12px; }
        .dash { padding: 16px 24px; }
        .kpi-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 14px; margin-bottom: 16px; }
        .kpi { background: #fff; border-radius: 8px; padding: 14px 16px; box-shadow: 0 1px 2px rgba(0,0,0,0.06); border-left: 4px solid #0ea5e9; }
        .kpi:nth-child(2) { border-left-color: #10b981; }
        .kpi:nth-child(3) { border-left-color: #8b5cf6; }
        .kpi:nth-child(4) { border-left-color: #f59e0b; }
        .kpi:nth-child(5) { border-left-color: #ef4444; }
        .kpi:nth-child(6) { border-left-color: #0f766e; }
        .kpi-label { font-size: 11px; color: #64748b; text-transform: uppercase; margin-bottom: 4px; }
        .kpi-val { font-size: 24px; font-weight: 700; }
        .kpi-note { font-size: 10px; color: #94a3b8; margin-top: 3px; }
        .row { display: grid; gap: 14px; margin-bottom: 16px; }
        .row-2 { grid-template-columns: 3fr 2fr; }
        .row-eq { grid-template-columns: 1fr 1fr; }
        .box { background: #fff; border-radius: 8px; padding: 16px 18px; box-shadow: 0 1px 2px rgba(0,0,0,0.06); }
        .box-title { font-size: 12px; font-weight: 600; color: #475569; margin-bottom: 4px; text-transform: uppercase; }
        .box-sub { font-size: 10px; color: #94a3b8; margin-bottom: 12px; }
        .note { font-size: 10px; color: #64748b; margin-top: 10px; }
        table.dt { width: 100%; border-collapse: collapse; font-size: 12px; }
        table.dt th { text-align: left; padding: 7px 8px; background: #f8fafc; border-bottom: 2px solid #e2e8f0; font-weight: 600; color: #64748b; font-size: 10px; text-transform: uppercase; }
        table.dt td { padding: 6px 8px; border-bottom: 1px solid #f1f5f9; }
        table.dt td.num { white-space: nowrap; font-weight: 600; }
        .footer { text-align: center; padding: 14px; font-size: 10px; color: #cbd5e1; }
        @media (max-width: 900px) { .row-2, .row-eq { grid-template-columns: 1fr; } }
    </style>
</head>
<body>
<div class="topbar">
    <h1>&#x1F695; NYC Green Taxi — Revenue Intelligence</h1>
    <span class="sub">__SUBTITLE__</span>
    <select id="monthSel">__MONTH_OPTIONS__</select>
</div>
<div class="dash">
    <div class="kpi-row">
__KPI_CARDS__
    </div>

    <div class="row row-2">
        <div class="box">
            <div class="box-title">Revenue: gross, net, and signed adjustments</div>
            <div class="box-sub">Refund-classified rows stay visible instead of being netted away</div>
            <canvas id="revenueChart" height="185"></canvas>
        </div>
        <div class="box">
            <div class="box-title">Payment mix (recorded types)</div>
            <canvas id="payChart" height="185"></canvas>
            <div class="note" id="payNote"></div>
        </div>
    </div>

    <div class="row row-eq">
        <div class="box">
            <div class="box-title">Trips by pickup hour</div>
            <div class="box-sub">The real operating shape of the fleet, straight from timestamps</div>
            <canvas id="hourChart" height="185"></canvas>
        </div>
        <div class="box">
            <div class="box-title">Distance profile (log scale)</div>
            <div class="box-sub">Corner hops to the 201,421-mile corrupt reading, one axis</div>
            <canvas id="distChart" height="185"></canvas>
        </div>
    </div>

    <div class="row row-2">
        <div class="box">
            <div class="box-title">Mean vs median trip distance</div>
            <div class="box-sub">Corrupt rows (max 201,421.68 mi) drag the mean; the median tells the truth</div>
            <canvas id="distStats" height="185"></canvas>
        </div>
        <div class="box">
            <div class="box-title">Data reality — counted, not hidden</div>
            <table class="dt">
                <thead><tr><th>What the raw feed looks like</th><th>Size</th><th>How it's handled</th></tr></thead>
                <tbody>
__GOV_ROWS__
                </tbody>
            </table>
        </div>
    </div>
</div>
<div class="footer">Data: NYC TLC green taxi open data · pandas · pytest · GitHub Actions · GitHub Pages</div>

<script>
const D = __DATA_JSON__;
const PAY = ['Card', 'Cash', 'No charge', 'Disputed', 'Unknown', 'Voided'];
const PAY_COLORS = {Card: '#0ea5e9', Cash: '#10b981', 'No charge': '#f59e0b', Disputed: '#ef4444', Unknown: '#8b5cf6', Voided: '#64748b'};
const BUCKETS = ['0-1', '1-2', '2-3', '3-5', '5-10', '10-20', '20+'];
let charts = [];

function rowsFor(ms) { return ms.map(m => D.mart.find(r => r.pickup_month === m)); }
function make(id, cfg) { charts.push(new Chart(document.getElementById(id), cfg)); }

function draw() {
    charts.forEach(c => c.destroy());
    charts = [];
    const sel = document.getElementById('monthSel').value;
    const ms = sel === 'all' ? D.months : [sel];
    const rows = rowsFor(ms);

    make('revenueChart', {
        type: 'bar',
        data: { labels: ms.map(m => D.labels[m]),
            datasets: [
                { label: 'Gross revenue', data: rows.map(r => parseFloat(r.revenue_gross)), backgroundColor: '#0ea5e9', borderRadius: 3 },
                { label: 'Net revenue', data: rows.map(r => parseFloat(r.revenue_net)), backgroundColor: '#10b981', borderRadius: 3 },
                { label: 'Adjustments (signed)', data: rows.map(r => parseFloat(r.adjustments)), backgroundColor: '#ef4444', borderRadius: 3 }
            ] },
        options: { responsive: true,
            plugins: { legend: { position: 'bottom', labels: { boxWidth: 10, font: { size: 10 } } },
                tooltip: { callbacks: { label: c => c.dataset.label + ': $' + c.parsed.y.toLocaleString(undefined, { minimumFractionDigits: 2 }) } } },
            scales: { y: { ticks: { callback: v => '$' + (v / 1000) + 'K' }, grid: { color: '#f1f5f9' } }, x: { grid: { display: false } } } }
    });

    const mix = PAY.map(p => ms.reduce((s, m) => s + (D.payment_mix[m][p] || 0), 0));
    const notRecorded = ms.reduce((s, m) => s + (D.payment_not_recorded[m] || 0), 0);
    document.getElementById('payNote').textContent = notRecorded.toLocaleString() + ' trips carry no recorded payment type and stay out of this mix, per the governance rule.';
    make('payChart', {
        type: 'doughnut',
        data: { labels: PAY, datasets: [{ data: mix, backgroundColor: PAY.map(p => PAY_COLORS[p]), borderWidth: 2, borderColor: '#fff' }] },
        options: { responsive: true, plugins: { legend: { position: 'bottom', labels: { boxWidth: 10, font: { size: 10 } } } } }
    });

    const hours = Array.from({ length: 24 }, (_, h) => ms.reduce((s, m) => {
        const hit = D.hourly[m].find(x => x.hour === h);
        return s + (hit ? hit.trips : 0);
    }, 0));
    make('hourChart', {
        type: 'bar',
        data: { labels: Array.from({ length: 24 }, (_, h) => String(h).padStart(2, '0')),
            datasets: [{ label: 'Trips', data: hours, backgroundColor: 'rgba(14,165,233,0.65)', borderRadius: 2 }] },
        options: { responsive: true, plugins: { legend: { display: false } },
            scales: { y: { grid: { color: '#f1f5f9' } }, x: { grid: { display: false }, ticks: { font: { size: 9 } } } } }
    });

    const buckets = BUCKETS.map(b => ms.reduce((s, m) => s + (D.distance_buckets[m][b] || 0), 0));
    make('distChart', {
        type: 'bar',
        data: { labels: BUCKETS.map(b => b + ' mi'),
            datasets: [{ label: 'Trips', data: buckets, backgroundColor: 'rgba(139,92,246,0.65)', borderRadius: 2 }] },
        options: { responsive: true, plugins: { legend: { display: false } },
            scales: { y: { type: 'logarithmic', grid: { color: '#f1f5f9' } }, x: { grid: { display: false }, ticks: { font: { size: 9 } } } } }
    });

    const mainRows = rowsFor(D.months);
    make('distStats', {
        type: 'bar',
        data: { labels: D.months.map(m => D.labels[m]),
            datasets: [
                { label: 'Mean distance (mi)', data: mainRows.map(r => parseFloat(r.avg_distance)), backgroundColor: '#f59e0b', borderRadius: 3 },
                { label: 'Median distance (mi)', data: mainRows.map(r => parseFloat(r.median_distance)), backgroundColor: '#10b981', borderRadius: 3 }
            ] },
        options: { responsive: true, plugins: { legend: { position: 'bottom', labels: { boxWidth: 10, font: { size: 10 } } } },
            scales: { y: { grid: { color: '#f1f5f9' }, title: { display: true, text: 'miles' } }, x: { grid: { display: false } } } }
    });
}

draw();
document.getElementById('monthSel').addEventListener('change', draw);
</script>
</body>
</html>
"""


INDEX_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NYC Taxi Revenue Intelligence</title>
    <style>
        body { font-family: 'Segoe UI', system-ui, sans-serif; background: #f5f7fa; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; color: #1e293b; }
        .card { background: #fff; border-radius: 10px; padding: 36px 40px; max-width: 560px; margin: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); border-top: 4px solid #0ea5e9; }
        h1 { font-size: 20px; margin: 0 0 10px; }
        p { font-size: 13px; line-height: 1.6; color: #475569; margin: 0 0 18px; }
        a.btn { display: inline-block; background: #0f172a; color: #fff; padding: 9px 18px; border-radius: 6px; text-decoration: none; font-size: 13px; margin-right: 10px; }
        a.ghost { color: #0ea5e9; font-size: 13px; }
    </style>
</head>
<body>
<div class="card">
    <h1>&#x1F695; NYC Taxi Revenue Intelligence</h1>
    <p>__TRIPS__ real NYC TLC green-taxi trips (Jan–Feb 2024 files), cleaned under
    the same governance rules a billing pipeline would use: every headline number
    reconciles to source rows, and the messy parts of the feed are quantified,
    not hidden. Gross revenue in the mart: __GROSS__.</p>
    <a class="btn" href="dashboard.html">Open the dashboard</a>
    <a class="ghost" href="https://github.com/kavyanjali-karan/nyc-taxi-revenue-intelligence">View the pipeline &rarr;</a>
</div>
</body>
</html>
"""


if __name__ == "__main__":
    main()
