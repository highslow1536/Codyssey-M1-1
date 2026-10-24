"""Dashboard data export tests: contract, source parity, strict JSON.

Reads dashboard/dist/data/dashboard.json and compares it against the
original derived CSVs. Only public derived data is involved; no raw
webpages are read here.
"""

import csv
import hashlib
import json
import math
import re
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dashboard/dist/data"
DASHBOARD_JSON = DIST / "dashboard.json"
DOWNLOADS = DIST / "downloads"
REPORTS = ROOT / "dashboard/dist/reports"

ORIGINALS = {
    "cpu_ssd_weekly.csv": "data/analysis/2026-10-22/aligned_weekly.csv",
    "stock_correlations.csv": "data/analysis/2026-10-22/correlations.csv",
    "stock_lags.csv": "data/analysis/2026-10-22/lag_correlations.csv",
    "gpu_snapshots.csv": "data/analysis/2026-10-22/gpu_mining/aligned_snapshots.csv",
    "gpu_monthly.csv": "data/analysis/2026-10-22/gpu_mining/aligned_monthly.csv",
    "gpu_correlations.csv": "data/analysis/2026-10-22/gpu_mining/correlations.csv",
    "gpu_changes.csv": "data/analysis/2026-10-22/gpu_mining/price_changes.csv",
    "eth_daily.csv": "data/processed/2026-10-22/crypto/eth_daily.csv",
}

REPORT_ORIGINALS = {
    "cpu-ssd.md": "data/analysis/2026-10-22/REPORT.md",
    "gpu-mining.md": "data/analysis/2026-10-22/gpu_mining/REPORT.md",
}

# A bare non-string NaN/Infinity token can only appear as a JSON value,
# i.e. right after ':' or '['. Quoted text is never matched.
NON_FINITE_VALUE_RE = re.compile(
    r"[:,\[]\s*(NaN|-Infinity\b|Infinity\b)")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def num(text):
    text = text.strip()
    if text == "":
        return None
    return float(text)


class DashboardContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = DASHBOARD_JSON.read_bytes().decode("utf-8")
        cls.data = json.loads(cls.raw)

    def test_top_level_contract(self):
        self.assertEqual(
            set(self.data),
            {"schemaVersion", "asOf", "range", "products", "stocks",
             "stockCorrelations", "stockLags", "gpu", "eth", "sources",
             "inputHashes"})
        self.assertEqual(self.data["schemaVersion"], 1)
        self.assertEqual(self.data["asOf"], "2026-10-22")
        self.assertEqual(self.data["range"],
                         {"start": "2020-01-01", "end": "2022-12-31"})
        self.assertEqual(set(self.data["gpu"]),
                         {"retail", "monthly", "weekly", "correlations",
                          "changes", "periods", "sensitivity"})
        self.assertEqual(set(self.data["eth"]), {"daily", "weekly"})
        for source in self.data["sources"]:
            self.assertEqual(set(source), {"name", "url", "scope"})
            self.assertTrue(source["url"].startswith("http"))

    def test_products_contract_and_coverage(self):
        products = self.data["products"]
        self.assertEqual([p["id"] for p in products],
                         ["B07STGGQ18", "B07MFZY2F2"])
        self.assertEqual([p["category"] for p in products], ["CPU", "SSD"])
        self.assertEqual([p["name"] for p in products],
                         ["AMD Ryzen 5 3600", "Samsung 970 EVO Plus 1TB"])
        self.assertTrue(all(p["currency"] == "USD" for p in products))
        self.assertEqual(
            [p["coverage"] for p in products],
            [{"weeks": 156, "observed": 148, "returns": 140},
             {"weeks": 156, "observed": 135, "returns": 122}])
        for product in products:
            weeks = product["weeks"]
            self.assertEqual(len(weeks), 156)
            dates = [w["date"] for w in weeks]
            self.assertEqual(dates, sorted(dates))
            self.assertEqual(len(set(dates)), 156)
            self.assertEqual(dates[0], "2020-01-10")
            self.assertEqual(dates[-1], "2022-12-30")
            for week in weeks:
                self.assertEqual(set(week),
                                 {"date", "price", "return", "quoteDate"})
                self.assertTrue(week["price"] is None or isinstance(
                    week["price"], (int, float)))
                self.assertTrue(week["return"] is None or isinstance(
                    week["return"], (int, float)))
            observed = sum(1 for w in weeks if w["price"] is not None)
            returns = sum(1 for w in weeks if w["return"] is not None)
            self.assertEqual(product["coverage"]["observed"], observed)
            self.assertEqual(product["coverage"]["returns"], returns)

    def test_stocks_unique_and_complete(self):
        stocks = self.data["stocks"]
        symbols = [s["symbol"] for s in stocks]
        self.assertEqual(len(symbols), 6)
        self.assertEqual(len(set(symbols)), 6)
        for symbol in ("005930", "000660", "AMD", "INTC", "NVDA", "MU"):
            self.assertIn(symbol, symbols)
            entry = next(s for s in stocks if s["symbol"] == symbol)
            self.assertIsInstance(entry["symbol"], str)
        currencies = {s["symbol"]: s["currency"] for s in stocks}
        self.assertEqual(currencies["005930"], "KRW")
        self.assertEqual(currencies["000660"], "KRW")
        for symbol in ("AMD", "INTC", "NVDA", "MU"):
            self.assertEqual(currencies[symbol], "USD")
        for stock in stocks:
            self.assertEqual(len(stock["weeks"]), 156)
            dates = [w["date"] for w in stock["weeks"]]
            self.assertEqual(dates, sorted(dates))
            self.assertEqual(len(set(dates)), 156)
            for week in stock["weeks"]:
                self.assertEqual(set(week), {"date", "price", "return"})

    def test_product_weeks_match_aligned_csv(self):
        rows = read_csv(ROOT / "data/analysis/2026-10-22/aligned_weekly.csv")
        lookup = {}
        for row in rows:
            key = (row["product_id"], row["week_end"])
            if key not in lookup:
                lookup[key] = row
        for product in self.data["products"]:
            for week in product["weeks"]:
                src = lookup[(product["id"], week["date"])]
                self.assertEqual(week["price"], num(src["component_price_usd"]))
                self.assertEqual(week["return"],
                                 num(src["component_return_log"]))
                expected_quote = src["component_quote_date"].strip() or None
                self.assertEqual(week["quoteDate"], expected_quote)
        cpu = next(p for p in self.data["products"]
                   if p["id"] == "B07STGGQ18")
        self.assertEqual(cpu["weeks"][0]["price"], 179)
        self.assertIsNone(cpu["weeks"][0]["return"])
        self.assertAlmostEqual(cpu["weeks"][1]["return"], 0.0)

    def test_stock_weeks_match_weekly_csv(self):
        rows = read_csv(
            ROOT / "data/processed/2026-10-22/stocks/weekly_stocks.csv")
        lookup = {}
        for row in rows:
            lookup[(row["symbol"], row["week_end"])] = row
        for stock in self.data["stocks"]:
            for week in stock["weeks"]:
                src = lookup[(stock["symbol"], week["date"])]
                self.assertEqual(week["price"], num(src["adjusted_close"]))
                self.assertEqual(week["return"], num(src["return_log"]))
        amd = next(s for s in self.data["stocks"] if s["symbol"] == "AMD")
        self.assertAlmostEqual(amd["weeks"][0]["price"], 48.1699981689)
        self.assertIsNone(amd["weeks"][0]["return"])
        self.assertAlmostEqual(amd["weeks"][1]["return"], 0.0557157642588)
        # Shared calendar with the component series: no synthetic dates.
        cpu_dates = [w["date"] for w in self.data["products"][0]["weeks"]]
        self.assertEqual([w["date"] for w in amd["weeks"]], cpu_dates)

    def test_stock_correlation_tables(self):
        correlations = self.data["stockCorrelations"]
        lags = self.data["stockLags"]
        self.assertEqual(len(correlations), 12)
        self.assertEqual(len(lags), 204)
        src_rows = read_csv(ROOT / "data/analysis/2026-10-22/correlations.csv")
        cpu_amd = next(r for r in src_rows
                       if r["product_id"] == "B07STGGQ18"
                       and r["symbol"] == "AMD")
        out = next(r for r in correlations
                   if r["product_id"] == "B07STGGQ18" and r["symbol"] == "AMD")
        self.assertEqual(out["company"], "Advanced Micro Devices, Inc.")
        self.assertAlmostEqual(out["return_pearson"],
                               float(cpu_amd["return_pearson"]))
        self.assertEqual(out["n_return"], 140)
        self.assertEqual(out["n_level"], 148)
        self.assertIsInstance(out["symbol"], str)
        lag_rows = read_csv(
            ROOT / "data/analysis/2026-10-22/lag_correlations.csv")
        self.assertEqual(len(lags), len(lag_rows))
        for key in ("product_id", "symbol", "lag_weeks", "pearson",
                    "spearman", "n"):
            if key in ("product_id", "symbol"):
                self.assertEqual(lags[0][key], lag_rows[0][key])
                continue
            self.assertEqual(lags[0][key] is None, lag_rows[0][key] == "")
            if lags[0][key] is not None:
                self.assertAlmostEqual(float(lags[0][key]),
                                       float(lag_rows[0][key]))

    def test_gpu_tables_counts_and_filters(self):
        gpu = self.data["gpu"]
        self.assertEqual(len(gpu["retail"]), 99)
        self.assertEqual(len(gpu["monthly"]), 108)
        self.assertEqual(len(gpu["weekly"]), 468)
        self.assertEqual(len(gpu["correlations"]), 234)
        self.assertEqual(len(gpu["changes"]), 15)
        self.assertEqual(len(gpu["periods"]), 18)
        self.assertEqual(len(gpu["sensitivity"]), 27)
        for table in ("retail", "weekly"):
            ids = {r["series_id"] for r in gpu[table]}
            self.assertEqual(ids, {"3070", "3080", "3090"})
            for row in gpu[table]:
                self.assertIsInstance(row["series_id"], str)
        monthly_ids = {r["gpu"] for r in gpu["monthly"]}
        self.assertEqual(monthly_ids, {"3070", "3080", "3090"})
        first = gpu["retail"][0]
        self.assertEqual(first["series_id"], "3070")
        self.assertEqual(first["observation_date"], "2021-01-17")
        self.assertEqual(first["value"], 769)
        self.assertEqual(first["unit"], "EUR")
        for row in gpu["changes"]:
            self.assertIsInstance(row["causal_effect"], bool)
        snapshots = read_csv(
            ROOT / "data/analysis/2026-10-22/gpu_mining/aligned_snapshots.csv")
        wanted = [r for r in snapshots if r["series_id"] in
                  ("3070", "3080", "3090")]
        self.assertEqual(len(gpu["retail"]), len(wanted))
        self.assertEqual(gpu["retail"][-1]["observation_date"],
                         wanted[-1]["observation_date"])

    def test_eth_contract_and_parity(self):
        daily = self.data["eth"]["daily"]
        weekly = self.data["eth"]["weekly"]
        self.assertEqual(len(daily), 1096)
        self.assertEqual(len(weekly), 156)
        first = daily[0]
        self.assertEqual(first["date"], "2020-01-01")
        self.assertAlmostEqual(first["price"], 129.963875)
        self.assertAlmostEqual(first["proxyA"], 0.973693)
        self.assertAlmostEqual(first["proxyB"], 0.946133)
        for key in ("powTerminated", "partial", "beaconMixed",
                    "burnIncluded"):
            self.assertIsInstance(first[key], bool)
            self.assertFalse(first[key])
        src = read_csv(
            ROOT / "data/processed/2026-10-22/crypto/eth_daily.csv")
        self.assertEqual([d["date"] for d in daily],
                         [r["date"] for r in src])
        mid = next(d for d in daily if d["date"] == "2021-08-05")
        src_mid = next(r for r in src if r["date"] == "2021-08-05")
        self.assertAlmostEqual(mid["price"], float(src_mid["price_usd"]))
        src_weekly = read_csv(
            ROOT / "data/processed/2026-10-22/crypto/eth_weekly.csv")
        self.assertEqual(len(weekly), len(src_weekly))
        self.assertAlmostEqual(weekly[0]["price_usd_last"],
                               float(src_weekly[0]["price_usd_last"]))

    def test_strict_json_numbers(self):
        self.assertIsNone(NON_FINITE_VALUE_RE.search(self.raw))
        parsed = json.loads(self.raw)
        json.dumps(parsed, allow_nan=False)

        def walk(value):
            if isinstance(value, float):
                self.assertTrue(math.isfinite(value))
            elif isinstance(value, dict):
                for item in value.values():
                    walk(item)
            elif isinstance(value, list):
                for item in value:
                    walk(item)

        walk(parsed)

    def test_downloads_and_reports_are_exact_copies(self):
        for name, rel in ORIGINALS.items():
            with self.subTest(download=name):
                self.assertTrue((DOWNLOADS / name).exists())
                self.assertEqual(sha256_file(DOWNLOADS / name),
                                 sha256_file(ROOT / rel))
        for name, rel in REPORT_ORIGINALS.items():
            with self.subTest(report=name):
                self.assertTrue((REPORTS / name).exists())
                self.assertEqual(sha256_file(REPORTS / name),
                                 sha256_file(ROOT / rel))

    def test_input_hashes_match_sources(self):
        for rel, digest in self.data["inputHashes"].items():
            with self.subTest(input=rel):
                self.assertEqual(sha256_file(ROOT / rel), digest)
        self.assertIn("data/analysis/2026-10-22/aligned_weekly.csv",
                      self.data["inputHashes"])

    def test_report_bundle_preserves_figures_and_csv(self):
        with zipfile.ZipFile(REPORTS / "analysis-bundle.zip") as bundle:
            self.assertIsNone(bundle.testzip())
            for rel in ("data/analysis/2026-10-22/REPORT.md",
                        "data/analysis/2026-10-22/figures/01_indexed_trends.png",
                        "data/analysis/2026-10-22/aligned_weekly.csv",
                        "data/analysis/2026-10-22/gpu_mining/REPORT.md",
                        "data/analysis/2026-10-22/gpu_mining/figures/03_merge_monthly_prices.png",
                        "docs/eth_mining_data_basis.md"):
                self.assertEqual(bundle.read(rel), (ROOT / rel).read_bytes())
            self.assertTrue(all(name.startswith(("data/analysis/2026-10-22/", "docs/"))
                                for name in bundle.namelist()))


if __name__ == "__main__":
    unittest.main()

