"""Checks for the weekly stock normalization contract."""
import csv
import hashlib
import json
import math
from datetime import date, timedelta
from pathlib import Path
import unittest
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/processed/2026-10-22/stocks"
EXPECTED_COLUMNS = ["symbol", "company", "currency", "market", "week_start",
                    "week_end", "close", "adjusted_close", "return_log",
                    "return_fraction", "quote_date", "n_trading_days",
                    "adjustment_status", "source_file", "source_sha256"]
EXPECTED_WEEKS = [(date(2020, 1, 4) + timedelta(days=7 * k)).isoformat() for k in range(156)]
SYMBOLS = ["AMD", "INTC", "MU", "NVDA", "005930", "000660"]
def read_rows():
    with (OUT / "weekly_stocks.csv").open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))
class WeeklyStocksTest(unittest.TestCase):
    def test_columns_and_row_counts(self):
        rows = read_rows()
        self.assertEqual(len(rows), 936)
        self.assertEqual(list(rows[0].keys()), EXPECTED_COLUMNS)
        per_symbol = {}
        for r in rows:
            per_symbol.setdefault(r["symbol"], []).append(r)
        self.assertEqual(sorted(per_symbol), sorted(SYMBOLS))
        for symbol, group in per_symbol.items():
            self.assertEqual(len(group), 156, symbol)
            self.assertEqual([g["week_start"] for g in group], EXPECTED_WEEKS, symbol)
    def test_first_week_and_return_rule(self):
        rows = read_rows()
        for symbol in SYMBOLS:
            group = [r for r in rows if r["symbol"] == symbol]
            first = group[0]
            self.assertEqual(first["week_start"], "2020-01-04")
            self.assertEqual(first["week_end"], "2020-01-10")
            self.assertEqual(first["quote_date"], "2020-01-10")
            self.assertEqual(first["return_log"], "")
            self.assertEqual(first["return_fraction"], "")
            prev_adj = None
            for row in group:
                if row["adjusted_close"] == "":
                    self.assertEqual(row["return_log"], "")
                    self.assertEqual(row["return_fraction"], "")
                    prev_adj = None
                    continue
                adj = float(row["adjusted_close"])
                if prev_adj is None:
                    self.assertEqual(row["return_log"], "")
                    self.assertEqual(row["return_fraction"], "")
                else:
                    self.assertAlmostEqual(float(row["return_log"]), math.log(adj / prev_adj), places=9)
                    self.assertAlmostEqual(float(row["return_fraction"]), adj / prev_adj - 1.0, places=9)
                prev_adj = adj
    def test_quote_dates_inside_weeks_and_hashes(self):
        rows = read_rows()
        summary = json.loads((OUT / "quality_summary.json").read_text(encoding="utf-8"))
        self.assertEqual(summary["rows_total"], 936)
        for row in rows:
            self.assertTrue(row["week_start"] <= row["quote_date"] <= row["week_end"])
            self.assertGreaterEqual(int(row["n_trading_days"]), 1)
            self.assertIn(row["adjustment_status"], {"yahoo_adjclose", "yahoo_adjclose_excl_zero_volume_placeholders"})
            self.assertNotIn(row["adjusted_close"].strip().lower(), {"nan", "none"})
            digest = hashlib.sha256((ROOT / row["source_file"]).read_bytes()).hexdigest()
            self.assertEqual(row["source_sha256"], digest)
            self.assertEqual(row["source_sha256"], summary["symbols"][row["symbol"]]["source_sha256"])
    def test_last_session_mismatches_contract(self):
        summary = json.loads((OUT / "quality_summary.json").read_text(encoding="utf-8"))
        rows = read_rows()
        by_symbol_week = {(r["symbol"], r["week_end"]): r for r in rows}
        for symbol in ("005930", "000660"):
            cross = summary["symbols"][symbol]["naver_crosscheck"]
            self.assertEqual(cross["actual_session_data_missing_vs_naver"],
                             742 - summary["symbols"][symbol]["n_effective_trading_days"])
            self.assertEqual(cross["n_last_session_mismatches"],
                             len(cross["last_session_mismatches"]))
            for m in cross["last_session_mismatches"]:
                self.assertEqual(by_symbol_week[(symbol, m["week_end"])]["quote_date"],
                                 m["yahoo_selected_date"])
                self.assertNotEqual(m["naver_last_date"], m["yahoo_selected_date"])
if __name__ == "__main__":
    unittest.main()
