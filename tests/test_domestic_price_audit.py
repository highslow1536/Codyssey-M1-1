"""Reconcile the domestic audit outputs directly to the frozen source rows."""

import csv
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from audit_price_history import indexed
from probe_price_history import PERIODS, PRODUCTS

RAW = ROOT / "data/feasibility/2026-10-21"
OUTPUT = ROOT / "data/processed/2026-10-21/domestic"


def read_csv(name):
    with (OUTPUT / name).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


class DomesticAuditTest(unittest.TestCase):
    def test_exact_eight_products_have_explicit_price_basis(self):
        rows = read_csv("products.csv")
        self.assertEqual(len(rows), 8)
        self.assertEqual({r["product_code"] for r in rows}, {code for _, code, _ in PRODUCTS})
        for row in rows:
            self.assertEqual(row["currency"], "KRW")
            self.assertEqual(row["historical_field"], "minPrice")
            self.assertEqual(row["shipping_basis"], "unknown")
            self.assertEqual(row["cash_card_basis"], "unknown")

    def test_all_discrepancies_match_raw_including_source_only_and_internal(self):
        expected = set()
        for _, code, _ in PRODUCTS:
            pc = json.loads((RAW / "desktop/raw" / f"{code}.json").read_text())
            series = {"mobile": {}, "desktop": {}}
            for months in PERIODS:
                mobile = json.loads((RAW / "raw" / f"{code}_{months}m.json").read_text())
                series["mobile"][months] = indexed(mobile["graphDataList"], months)
                series["desktop"][months] = indexed(pc[str(months)]["result"], months, True)
                if months in (1, 3):
                    self.assertEqual(series["mobile"][months], series["desktop"][months])
            comparisons = [("cross_surface", f"mobile_{m}m", f"desktop_{m}m",
                            series["mobile"][m], series["desktop"][m]) for m in PERIODS]
            comparisons += [(f"{s}_internal", f"{s}_{a}m", f"{s}_{b}m", series[s][a], series[s][b])
                            for s in series for a, b in ((6, 12), (6, 24), (12, 24))]
            for scope, window_a, window_b, a, b in comparisons:
                for label in a.keys() | b.keys():
                    if scope.endswith("_internal") and (label not in a or label not in b):
                        continue  # Different query lengths intentionally cover different months.
                    if label not in b:
                        kind = "only_in_a"
                    elif label not in a:
                        kind = "only_in_b"
                    elif a[label] != b[label]:
                        kind = "value_mismatch"
                    else:
                        continue
                    expected.add((scope, code, window_a, window_b, label, str(a.get(label, "")), str(b.get(label, "")), kind))
        fields = ("scope", "product_code", "window_a", "window_b", "month_label", "price_a", "price_b", "kind")
        actual_rows = read_csv("discrepancies.csv")
        actual = {tuple(r[k] for k in fields) for r in actual_rows}
        self.assertEqual(actual, expected)
        self.assertEqual(len(actual_rows), len(actual))
        self.assertEqual(len(actual), 28)
        self.assertTrue(all(r["boundary_month"] == "true" for r in actual_rows))

    def test_saved_audit_hashes_still_match_sources(self):
        summary = json.loads((OUTPUT / "summary.json").read_text())
        self.assertEqual(len(summary["raw_hashes"]), 48)
        for relative_path, expected_hash in summary["raw_hashes"].items():
            self.assertEqual(hashlib.sha256((RAW / relative_path).read_bytes()).hexdigest(), expected_hash)
        for record in summary["evidence"]:
            self.assertEqual(hashlib.sha256((ROOT / record["file"]).read_bytes()).hexdigest(), record["sha256"])


if __name__ == "__main__":
    unittest.main()
