"""Checks for the cases that could create spurious stock/price correlations."""

import csv
from datetime import date
import hashlib
import json
import math
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from preprocess_overseas_prices import (friday, normalize, previous_complete_friday,
                                      returns, weekly)

CONFIG = json.loads((ROOT / "config/price_preprocessing.json").read_text())
RECORD = {"asin": "test", "category": "CPU", "name": "test CPU", "currency": "USD",
          "store": "amazon.com", "product_url": "https://example.test/price",
          "source_file": "test.json", "source_sha256": "test-hash"}


def fixture(points, quarantine=None):
    config = {**CONFIG, "quarantine": quarantine or [], "snapshot_date": "2020-02-05"}
    source = {"History": {"Price": [{"x": d, "y": p} for d, p in points]}}
    observations = normalize(source, RECORD, config)
    return observations, weekly(observations, RECORD, config)


def read_csv(name):
    with (ROOT / "data/processed/2026-10-21/overseas" / name).open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


class WeeklyRulesTest(unittest.TestCase):
    def test_calendar_and_incomplete_current_week(self):
        self.assertEqual(friday(date(2020, 1, 10)), date(2020, 1, 10))
        self.assertEqual(friday(date(2020, 1, 11)), date(2020, 1, 17))
        self.assertEqual(previous_complete_friday(date(2026, 10, 21)), date(2026, 10, 16))
        self.assertEqual(previous_complete_friday(date(2026, 10, 16)), date(2026, 10, 9))

    def test_missing_week_blocks_return_and_preserves_real_zero_change(self):
        _, rows = fixture([("2020-01-10 12:00:00", 10), ("2020-01-24 12:00:00", 20),
                           ("2020-01-31 12:00:00", 20)])
        self.assertEqual(rows[1]["price_usd"], "")
        self.assertEqual(rows[2]["log_return"], "")
        self.assertEqual(rows[2]["return_missing_reason"], "previous_week_missing")
        self.assertEqual(rows[3]["log_return"], 0)
        self.assertEqual(rows[3]["return_missing_reason"], "")

    def test_multiple_same_day_observations_use_latest_timestamp(self):
        _, rows = fixture([("2020-01-10 16:00:00", 11), ("2020-01-10 08:00:00", 10)])
        self.assertEqual(rows[0]["price_usd"], 11)
        self.assertEqual(rows[0]["n_quote_days"], 1)
        self.assertEqual(rows[0]["n_quotes_used"], 2)

    def test_quarantine_uses_only_earlier_quote_from_same_week(self):
        rule = {"asin": "test", "timestamp": "2020-01-10 12:00:00", "price": 1,
                "reason": "unverified_extreme_quote", "note": "fixture"}
        _, rows = fixture([("2020-01-09 12:00:00", 100), ("2020-01-10 12:00:00", 1)], [rule])
        self.assertEqual(rows[0]["price_usd"], 100)
        self.assertEqual(rows[0]["raw_last_price_usd"], 1)
        self.assertEqual(rows[0]["quote_age_days"], 1)
        _, empty = fixture([("2020-01-10 12:00:00", 1)], [rule])
        self.assertEqual(empty[0]["price_usd"], "")
        self.assertEqual(empty[0]["n_quarantined"], 1)

    def test_invalid_prices_do_not_become_zero(self):
        observations, rows = fixture([("2020-01-10 12:00:00", 0),
                                      ("2020-01-17 12:00:00", float("nan")),
                                      ("2020-01-24 12:00:00", True)])
        self.assertTrue(all(o["status"] == "quarantined" for o in observations))
        self.assertTrue(all(r["price_usd"] == "" for r in rows))

    def test_duplicates_and_changed_manual_rules_fail_loudly(self):
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            fixture([("2020-01-10 12:00:00", 100)] * 2)
        rule = {"asin": "test", "timestamp": "2020-01-10 12:00:00", "price": 1,
                "reason": "unverified_extreme_quote", "note": "fixture"}
        with self.assertRaisesRegex(ValueError, "price changed"):
            fixture([("2020-01-10 12:00:00", 2)], [rule])

    def test_core_return_is_reset_instead_of_leaking_prior_window(self):
        _, rows = fixture([("2020-01-03 12:00:00", 100), ("2020-01-10 12:00:00", 110)])
        self.assertAlmostEqual(rows[1]["log_return"], math.log(1.1))
        core = [r.copy() for r in rows if r["week_start"] >= "2020-01-01"]
        returns(core)
        self.assertEqual(core[0]["log_return"], "")

    def test_statistical_warning_alone_does_not_delete_observation(self):
        points = [(f"2020-01-{day:02d} 12:00:00", 100) for day in range(4, 10)]
        observations, rows = fixture(points + [("2020-01-10 12:00:00", 30)])
        self.assertEqual(observations[-1]["status"], "accepted")
        self.assertTrue(observations[-1]["statistical_flags"])
        self.assertEqual(rows[0]["price_usd"], 30)


class SavedDataReconciliationTest(unittest.TestCase):
    def test_outputs_reference_unchanged_inputs(self):
        summary = json.loads((ROOT / "data/processed/2026-10-21/overseas/quality_summary.json").read_text())
        for relative_path, expected_hash in summary["input_sha256"].items():
            self.assertEqual(hashlib.sha256((ROOT / relative_path).read_bytes()).hexdigest(), expected_hash)

    def test_original_snapshot_hashes_match_previous_audit(self):
        base = ROOT / "data/feasibility/2026-10-21/alternatives"
        expected = json.loads((base / "validation.json").read_text())["raw_file_sha256"]
        for label in ("cpu", "ssd"):
            for suffix in (".html", "_prices.json"):
                path = base / "raw" / f"pricehistory_{label}{suffix}"
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), expected[path.name])

    def test_every_raw_quote_accounted_and_core_counts_match(self):
        audit = read_csv("observations_audit.csv")
        excluded = read_csv("excluded_records.csv")
        summary = json.loads((ROOT / "data/processed/2026-10-21/overseas/quality_summary.json").read_text())
        self.assertEqual(len(audit), 2225)
        self.assertEqual(len(excluded), 2)
        for product, stats in summary["products"].items():
            original = [r for r in audit if r["product_id"] == product]
            accepted = [r for r in original if r["status"] == "accepted"]
            self.assertEqual(len(original), stats["raw_price_rows"])
            self.assertEqual(len(accepted), stats["accepted_rows"])
            self.assertEqual(sum(not r["core_exclusion_reason"] for r in accepted),
                             stats["analysis_2020_2022"]["quote_rows_used"])

    def test_weekly_quotes_and_returns_reconcile_independently(self):
        audit = read_csv("observations_audit.csv")
        for filename in ("weekly_prices.csv", "weekly_2020_2022.csv"):
            previous = {}
            rows = read_csv(filename)
            for row in rows:
                selected = sorted((a for a in audit if a["product_id"] == row["product_id"]
                    and a["status"] == "accepted" and row["week_start"] <= a["source_date"] <= row["week_end"]),
                    key=lambda a: a["source_timestamp"])
                self.assertEqual(int(row["n_quotes_used"]), len(selected))
                self.assertEqual(row["price_usd"], selected[-1]["price"] if selected else "")
                self.assertEqual(row["imputed"], "0")
                if selected:
                    self.assertEqual(row["quote_timestamp"], selected[-1]["source_timestamp"])
                    self.assertLessEqual(int(row["quote_age_days"]), 6)
                before = previous.get(row["product_id"])
                if not before or not row["price_usd"] or not before["price_usd"]:
                    self.assertEqual(row["log_return"], "")
                else:
                    self.assertAlmostEqual(float(row["log_return"]),
                        math.log(float(row["price_usd"]) / float(before["price_usd"])))
                previous[row["product_id"]] = row


if __name__ == "__main__":
    unittest.main()
