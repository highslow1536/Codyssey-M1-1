#!/usr/bin/env python3
"""Export the public PC-parts dashboard dataset.

Reads only derived, public analysis/processed CSVs plus the two published
REPORT.md files and writes:

  dashboard/dist/data/dashboard.json
  dashboard/dist/data/downloads/*.csv   (byte-identical copies)
  dashboard/dist/reports/cpu-ssd.md
  dashboard/dist/reports/gpu-mining.md

Rules: no imputation, no synthetic dates, no recomputation of published
statistics, no raw webpages. Numeric CSV fields become JSON numbers (or
null); identifiers such as '005930' or '3070' stay strings. The JSON
output is strict (json.dump with allow_nan=False).
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import re
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

ANALYSIS = ROOT / "data/analysis/2026-10-22"
GPU = ANALYSIS / "gpu_mining"
OVERSEAS_WEEKLY = ROOT / "data/processed/2026-10-21/overseas/weekly_2020_2022.csv"
OVERSEAS_SOURCES = ROOT / "data/processed/2026-10-21/overseas/sources.json"
STOCKS_WEEKLY = ROOT / "data/processed/2026-10-22/stocks/weekly_stocks.csv"
STOCKS_SOURCES = ROOT / "data/processed/2026-10-22/stocks/sources.json"
ETH_DAILY = ROOT / "data/processed/2026-10-22/crypto/eth_daily.csv"
ETH_WEEKLY = ROOT / "data/processed/2026-10-22/crypto/eth_weekly.csv"
CRYPTO_SOURCES = ROOT / "data/processed/2026-10-22/crypto/sources.json"

ALIGNED_WEEKLY = ANALYSIS / "aligned_weekly.csv"
CORRELATIONS = ANALYSIS / "correlations.csv"
LAG_CORRELATIONS = ANALYSIS / "lag_correlations.csv"
COVERAGE = ANALYSIS / "coverage.csv"
STOCK_META = ANALYSIS / "analysis_metadata.json"

SNAPSHOTS = GPU / "aligned_snapshots.csv"
GPU_MONTHLY = GPU / "aligned_monthly.csv"
GPU_WEEKLY = GPU / "aligned_weekly.csv"
GPU_CORRELATIONS = GPU / "correlations.csv"
GPU_CHANGES = GPU / "price_changes.csv"
GPU_PERIODS = GPU / "period_summary.csv"
GPU_SENSITIVITY = GPU / "date_sensitivity.csv"

CPU_SSD_REPORT = ANALYSIS / "REPORT.md"
GPU_REPORT = GPU / "REPORT.md"

OUT_DIR = ROOT / "dashboard/dist/data"
DOWNLOADS_DIR = OUT_DIR / "downloads"
REPORTS_DIR = ROOT / "dashboard/dist/reports"

SCHEMA_VERSION = 1
AS_OF = "2026-10-22"
RANGE = {"start": "2020-01-01", "end": "2022-12-31"}

GPU_IDS = ("3070", "3080", "3090")

# Product names confirmed against docs/overseas_preprocessing.md and
# data/processed/2026-10-21/overseas/sources.json. Never invented here:
# the exporter aborts if the source data disagrees.
EXPECTED_PRODUCTS = {
    "B07STGGQ18": {"name": "AMD Ryzen 5 3600", "category": "CPU"},
    "B07MFZY2F2": {"name": "Samsung 970 EVO Plus 1TB", "category": "SSD"},
}

DOWNLOADS = {
    "cpu_ssd_weekly.csv": ALIGNED_WEEKLY,
    "stock_correlations.csv": CORRELATIONS,
    "stock_lags.csv": LAG_CORRELATIONS,
    "gpu_snapshots.csv": SNAPSHOTS,
    "gpu_monthly.csv": GPU_MONTHLY,
    "gpu_correlations.csv": GPU_CORRELATIONS,
    "gpu_changes.csv": GPU_CHANGES,
    "eth_daily.csv": ETH_DAILY,
}

REPORT_COPIES = {
    "cpu-ssd.md": CPU_SSD_REPORT,
    "gpu-mining.md": GPU_REPORT,
}

# Columns that must stay strings even when they look numeric
# ('005930', '3070', page references, dates, URLs, ...).
STRING_COLUMNS = {
    "correlations": {"product_id", "category", "symbol", "company",
                     "stock_currency", "relationship"},
    "lags": {"product_id", "symbol"},
    "snapshots": {"series_id", "series_label", "kind", "observation_date",
                  "unit", "observation_status", "source_basis",
                  "source_url", "source_file", "source_sha256", "week_end",
                  "crypto_window_start", "crypto_window_end",
                  "previous_observation_date"},
    "gpu_monthly": {"gpu_model", "gpu_label_source", "month",
                    "sale_period_label", "sale_period_type", "source_page",
                    "source_url", "source_title", "source_sha256",
                    "table_header_price", "table_header_qty",
                    "price_missing_reason", "qty_missing_reason",
                    "merge_note", "return_missing_reason", "gpu",
                    "pow_status"},
    "gpu_weekly": {"series_id", "kind", "week_end", "observation_status",
                   "unit", "week_start", "observation_date", "price_date",
                   "rev_date_last", "pow_status", "lastdate", "source_file",
                   "source_sha256"},
    "gpu_correlations": {"dataset", "series_id", "subset", "method",
                         "crypto_metric", "interpretation"},
    "gpu_changes": {"dataset", "series_id", "comparison", "before_start",
                    "before_end", "after_start", "after_end", "unit"},
    "gpu_periods": {"series_id", "period", "start_month", "end_month"},
    "gpu_sensitivity": {"series_id", "method", "crypto_metric"},
    "eth_weekly": {"week_start", "week_end", "price_date", "rev_date_last",
                   "pow_status", "lastdate", "source_file", "source_sha256"},
}

NULL_TOKENS = {"nan", "na", "n/a", "nat", "none", "null",
               "inf", "+inf", "-inf", "infinity", "-infinity"}
INT_RE = re.compile("^[+-]?[0-9]+$")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def read_rows(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def convert(value, string_col):
    """Map one CSV cell to a JSON value: numbers stay numeric, missing
    becomes None, identifiers/dates/URLs stay strings."""
    if value is None:
        return None
    text = value.strip()
    if text == "":
        return None
    if string_col:
        return text
    low = text.lower()
    if low in NULL_TOKENS:
        return None
    if low == "true":
        return True
    if low == "false":
        return False
    if INT_RE.match(text):
        try:
            return int(text)
        except ValueError:
            pass
    try:
        number = float(text)
    except ValueError:
        return text
    return number if math.isfinite(number) else None


def convert_rows(rows, table):
    strings = STRING_COLUMNS.get(table, set())
    return [
        {key: convert(val, key in strings) for key, val in row.items()}
        for row in rows
    ]


def to_bool(value):
    if value is None:
        return None
    text = value.strip()
    if text == "":
        return None
    if text == "1" or text.lower() == "true":
        return True
    if text == "0" or text.lower() == "false":
        return False
    raise ValueError("unexpected boolean token: %r" % (value,))


def build_products(aligned_rows):
    by_product = {}
    for row in aligned_rows:
        pid = row["product_id"]
        week = row["week_end"]
        cell = {
            "date": week,
            "price": convert(row["component_price_usd"], False),
            "return": convert(row["component_return_log"], False),
            "quoteDate": convert(row["component_quote_date"], True),
        }
        if week in by_product.get(pid, {}):
            prev = by_product[pid][week]
            assert prev["price"] == cell["price"], (
                "price differs across symbols for %s %s" % (pid, week))
            assert prev["return"] == cell["return"], (
                "return differs across symbols for %s %s" % (pid, week))
            continue
        by_product.setdefault(pid, {})[week] = cell

    meta = {}
    for row in read_rows(OVERSEAS_WEEKLY):
        pid = row["product_id"]
        entry = meta.setdefault(pid, {
            "name": row["product_name"],
            "category": row["category"],
            "currency": row["currency"],
        })
        assert entry["name"] == row["product_name"], (
            "product name changed mid-file for %s" % pid)
    assert set(meta) == set(EXPECTED_PRODUCTS), (
        "unexpected product ids: %s" % sorted(meta))
    for pid, expected in EXPECTED_PRODUCTS.items():
        assert meta[pid]["name"] == expected["name"], (
            "product name mismatch for %s: %r" % (pid, meta[pid]["name"]))
        assert meta[pid]["category"] == expected["category"], (
            "product category mismatch for %s" % pid)
        assert meta[pid]["currency"] == "USD"

    products = []
    for pid in ("B07STGGQ18", "B07MFZY2F2"):
        weeks = sorted(by_product[pid].values(), key=lambda w: w["date"])
        observed = sum(1 for w in weeks if w["price"] is not None)
        returns = sum(1 for w in weeks if w["return"] is not None)
        products.append({
            "id": pid,
            "category": meta[pid]["category"],
            "name": meta[pid]["name"],
            "currency": meta[pid]["currency"],
            "weeks": weeks,
            "coverage": {"weeks": len(weeks), "observed": observed,
                         "returns": returns},
        })
    return products


def build_stocks(stock_rows, order):
    by_symbol = {}
    info = {}
    for row in stock_rows:
        symbol = row["symbol"].strip()
        info.setdefault(symbol, {"name": row["company"].strip(),
                                 "currency": row["currency"].strip()})
        by_symbol.setdefault(symbol, []).append({
            "date": row["week_end"].strip(),
            "price": convert(row["adjusted_close"], False),
            "return": convert(row["return_log"], False),
        })
    assert set(by_symbol) == set(order), (
        "unexpected stock symbols: %s" % sorted(by_symbol))
    stocks = []
    for symbol in order:
        weeks = sorted(by_symbol[symbol], key=lambda w: w["date"])
        stocks.append({
            "symbol": symbol,
            "name": info[symbol]["name"],
            "currency": info[symbol]["currency"],
            "weeks": weeks,
        })
    return stocks


def build_sources(snapshot_rows, monthly_rows):
    sources = []
    for entry in json.loads(OVERSEAS_SOURCES.read_text(encoding="utf-8")):
        sources.append({
            "name": "pricehistory.app - %s" % entry["name"],
            "url": entry["product_url"],
            "scope": "%s weekly prices" % entry["category"],
        })
    stock_sources = json.loads(STOCKS_SOURCES.read_text(encoding="utf-8"))
    for symbol, detail in stock_sources["symbols"].items():
        sources.append({
            "name": "Yahoo Finance chart - %s (%s)" % (
                detail["company"], symbol),
            "url": detail["chart_url"],
            "scope": "stock weekly prices",
        })
    crypto = json.loads(
        CRYPTO_SOURCES.read_text(encoding="utf-8"))["coinmetrics_community_api"]
    sources.append({
        "name": "CoinMetrics Community API - ETH asset metrics",
        "url": "https://docs.coinmetrics.io/api/v4/",
        "scope": "ETH daily price and network proxies",
    })
    retail_urls = sorted(
        {r["source_url"] for r in snapshot_rows if r["source_url"]})
    sources.append({
        "name": "3DCenter - GPU retail price reports",
        "url": retail_urls[0],
        "scope": "GPU retail snapshots (%d report pages)" % len(retail_urls),
    })
    ebay_urls = sorted(
        {r["source_url"] for r in monthly_rows if r["source_url"]})
    sources.append({
        "name": "Tom's Hardware - eBay historical GPU prices",
        "url": ebay_urls[0],
        "scope": "GPU eBay monthly prices (%d pages)" % len(ebay_urls),
    })
    return sources


def main():
    aligned_rows = read_rows(ALIGNED_WEEKLY)
    stock_rows = read_rows(STOCKS_WEEKLY)
    stock_meta = json.loads(STOCK_META.read_text(encoding="utf-8"))
    stock_order = stock_meta["config"]["stock_order"]

    products = build_products(aligned_rows)
    stocks = build_stocks(stock_rows, stock_order)

    snapshot_rows = read_rows(SNAPSHOTS)
    monthly_rows = read_rows(GPU_MONTHLY)
    gpu_weekly_rows = read_rows(GPU_WEEKLY)
    eth_daily_rows = read_rows(ETH_DAILY)
    eth_weekly_rows = read_rows(ETH_WEEKLY)

    retail = [r for r in convert_rows(snapshot_rows, "snapshots")
              if r["series_id"] in GPU_IDS]
    gpu_weekly = [r for r in convert_rows(gpu_weekly_rows, "gpu_weekly")
                  if r["series_id"] in GPU_IDS]

    eth_daily = [{
        "date": convert(r["date"], True),
        "price": convert(r["price_usd"], False),
        "proxyA": convert(r["rev_usd_per100mh_gross"], False),
        "proxyB": convert(r["iss_usd_per100mh"], False),
        "powTerminated": to_bool(r["pow_terminated"]),
        "partial": to_bool(r["is_partial_transition"]),
        "beaconMixed": to_bool(r["beacon_issuance_included"]),
        "burnIncluded": to_bool(r["london_burn_overincluded"]),
    } for r in eth_daily_rows]

    dashboard = {
        "schemaVersion": SCHEMA_VERSION,
        "asOf": AS_OF,
        "range": RANGE,
        "products": products,
        "stocks": stocks,
        "stockCorrelations": convert_rows(read_rows(CORRELATIONS),
                                          "correlations"),
        "stockLags": convert_rows(read_rows(LAG_CORRELATIONS), "lags"),
        "gpu": {
            "retail": retail,
            "monthly": convert_rows(monthly_rows, "gpu_monthly"),
            "weekly": gpu_weekly,
            "correlations": convert_rows(read_rows(GPU_CORRELATIONS),
                                         "gpu_correlations"),
            "changes": convert_rows(read_rows(GPU_CHANGES), "gpu_changes"),
            "periods": convert_rows(read_rows(GPU_PERIODS), "gpu_periods"),
            "sensitivity": convert_rows(read_rows(GPU_SENSITIVITY),
                                        "gpu_sensitivity"),
        },
        "eth": {
            "daily": eth_daily,
            "weekly": convert_rows(eth_weekly_rows, "eth_weekly"),
        },
        "sources": build_sources(snapshot_rows, monthly_rows),
    }

    input_files = [OVERSEAS_WEEKLY, ALIGNED_WEEKLY, STOCKS_WEEKLY,
                   CORRELATIONS, LAG_CORRELATIONS, COVERAGE, SNAPSHOTS,
                   GPU_MONTHLY, GPU_WEEKLY, GPU_CORRELATIONS, GPU_CHANGES,
                   GPU_PERIODS, GPU_SENSITIVITY, ETH_DAILY, ETH_WEEKLY,
                   OVERSEAS_SOURCES, STOCKS_SOURCES, CRYPTO_SOURCES,
                   STOCK_META, CPU_SSD_REPORT, GPU_REPORT]
    dashboard["inputHashes"] = {
        str(p.relative_to(ROOT)): sha256_file(p) for p in input_files
    }

    # Contract guards: fail loudly instead of shipping a wrong dashboard.
    assert [p["id"] for p in products] == ["B07STGGQ18", "B07MFZY2F2"]
    assert [p["coverage"] for p in products] == [
        {"weeks": 156, "observed": 148, "returns": 140},
        {"weeks": 156, "observed": 135, "returns": 122},
    ]
    assert [s["symbol"] for s in stocks] == stock_order
    assert len(stocks) == 6
    assert all(len(s["weeks"]) == 156 for s in stocks)
    assert len(dashboard["stockCorrelations"]) == 12
    assert len(dashboard["stockLags"]) == 204
    assert len(retail) == 99
    assert len(dashboard["gpu"]["monthly"]) == 108
    assert len(gpu_weekly) == 468
    assert len(dashboard["gpu"]["correlations"]) == 234
    assert len(dashboard["gpu"]["changes"]) == 15
    assert len(dashboard["gpu"]["periods"]) == 18
    assert len(dashboard["gpu"]["sensitivity"]) == 27
    assert len(eth_daily) == 1096
    assert len(dashboard["eth"]["weekly"]) == 156

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    out_path = OUT_DIR / "dashboard.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(dashboard, f, ensure_ascii=False, indent=1,
                  allow_nan=False)
        f.write("\n")

    for name, src in DOWNLOADS.items():
        shutil.copyfile(src, DOWNLOADS_DIR / name)
    for name, src in REPORT_COPIES.items():
        shutil.copyfile(src, REPORTS_DIR / name)

    # Preserve the report-relative figure/CSV/document links in one portable
    # bundle. Include curated public outputs only, never raw responses.
    bundle_paths = sorted(p for folder in (ANALYSIS, ROOT / "docs")
                          for p in folder.rglob("*") if p.is_file())
    with zipfile.ZipFile(REPORTS_DIR / "analysis-bundle.zip", "w",
                         compression=zipfile.ZIP_DEFLATED) as archive:
        for path in bundle_paths:
            entry = zipfile.ZipInfo(path.relative_to(ROOT).as_posix(),
                                    date_time=(2026, 10, 22, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(entry, path.read_bytes())

    print("wrote %s (%d products, %d stocks, %d eth days)" % (
        out_path.relative_to(ROOT), len(products), len(stocks),
        len(eth_daily)))
    print("copied %d download CSVs and %d reports" % (
        len(DOWNLOADS), len(REPORT_COPIES)))


if __name__ == "__main__":
    main()

