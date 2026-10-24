"""Tests for the domestic dashboard history export helper.

Every assertion reconciles data/processed/2026-10-23/domestic/history.json
directly against the frozen raw responses: no deletion, no duplication,
no relabelling. Covers spot labels, the incomplete-month flag, the export
rules (no appended current price, no outlier removal, ISO display rules)
and source hashes. Standard library only.
"""

import csv
import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import prepare_domestic_history as helper

RAW = ROOT / "data/feasibility/2026-10-21"
OUTPUT = ROOT / "data/processed/2026-10-23/domestic"


def load_history():
    with (OUTPUT / "history.json").open(encoding="utf-8") as handle:
        return json.load(handle)


def raw_mobile(code, months):
    with (RAW / "raw" / ("%s_%dm.json" % (code, months))).open(encoding="utf-8") as handle:
        return json.load(handle)["graphDataList"]


def raw_desktop(code, months):
    with (RAW / "desktop" / "raw" / (code + ".json")).open(encoding="utf-8") as handle:
        return json.load(handle)[str(months)]["result"]


def desktop_label(row):
    return row.get("Fulldate", row["date"])


def products_csv():
    path = ROOT / "data/processed/2026-10-21/domestic/products.csv"
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


class DomesticHistoryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.history = load_history()
        cls.by_code = {p["product_code"]: p for p in cls.history["products"]}

    def test_eight_products_with_unconfirmed_basis(self):
        rows = products_csv()
        self.assertEqual(len(self.history["products"]), 8)
        self.assertEqual(
            [p["product_code"] for p in self.history["products"]],
            [r["product_code"] for r in rows],
        )
        for product in self.history["products"]:
            self.assertEqual(product["currency"], "KRW")
            self.assertEqual(product["historical_field"], "minPrice")
            self.assertEqual(product["price_basis"], "source_label_lowest_price_trend")
            self.assertEqual(product["shipping_basis"], "unknown")
            self.assertEqual(product["cash_card_basis"], "unknown")
            self.assertEqual(product["coupon_basis"], "unknown")
            self.assertEqual(product["aggregation_basis"], "unconfirmed")
            self.assertEqual(product["weekly_aggregation"], "unknown")

    def test_weekly_3m_matches_raw_both_surfaces(self):
        total = 0
        for code, product in self.by_code.items():
            mob = raw_mobile(code, 3)
            desk = raw_desktop(code, 3)
            weekly = product["weekly_3m"]
            self.assertEqual(len(weekly), 12, code)
            self.assertEqual(len(weekly), len(mob), code)
            self.assertEqual(len(weekly), len(desk), code)
            for seq, row in enumerate(weekly):
                mrow = mob[seq]
                drow = desk[seq]
                self.assertEqual(row["seq"], seq)
                self.assertEqual(row["label_mobile"], mrow["date"].replace(".", "-")[-5:])
                self.assertEqual(row["label_desktop"], desktop_label(drow).replace(".", "-")[-5:])
                self.assertEqual(row["desktop_fulldate"], drow["Fulldate"])
                self.assertEqual(row["mobile_price"], mrow["minPrice"])
                self.assertEqual(row["desktop_price"], drow["minPrice"])
                self.assertTrue(row["match"], (code, row))
            total += len(weekly)
        self.assertEqual(total, 96)

    def test_monthly_24m_arrays_preserve_raw_values(self):
        mobile_total = 0
        desktop_total = 0
        for code, product in self.by_code.items():
            mob = raw_mobile(code, 24)
            desk = raw_desktop(code, 24)
            exported_m = product["monthly_mobile_24m"]
            exported_d = product["monthly_desktop_24m"]
            self.assertEqual(
                [(r["label"], r["price"]) for r in exported_m],
                [(r["date"].replace(".", "-"), r["minPrice"]) for r in mob],
                code,
            )
            self.assertEqual(
                [(r["label"], r["price"]) for r in exported_d],
                [(desktop_label(r), r["minPrice"]) for r in desk],
                code,
            )
            mobile_total += len(exported_m)
            desktop_total += len(exported_d)
        self.assertEqual(mobile_total, 185)
        self.assertEqual(desktop_total, 179)
        counts = self.history["counts"]
        self.assertEqual(counts["weekly_unique_rows_total"], 96)
        self.assertEqual(counts["monthly_mobile_24m_rows_total"], 185)
        self.assertEqual(counts["monthly_desktop_24m_rows_total"], 179)

    def test_monthly_comparison_marks_status_without_merging(self):
        only_a = 0
        only_b = 0
        for code, product in self.by_code.items():
            mob = {r["date"].replace(".", "-"): r["minPrice"] for r in raw_mobile(code, 24)}
            desk = {desktop_label(r): r["minPrice"] for r in raw_desktop(code, 24)}
            comp = product["monthly_comparison_24m"]
            self.assertEqual(len(comp), len(set(mob) | set(desk)), code)
            self.assertEqual(
                [r["month_label"] for r in comp],
                list(mob) + [label for label in desk if label not in mob],
                code,
            )
            for row in comp:
                label = row["month_label"]
                in_m = label in mob
                in_d = label in desk
                if in_m and in_d and mob[label] == desk[label]:
                    self.assertEqual(row["status"], "matched", (code, label))
                elif in_m and in_d:
                    self.assertEqual(row["status"], "value_mismatch", (code, label))
                elif in_m:
                    self.assertEqual(row["status"], "mobile_only", (code, label))
                    only_a += 1
                else:
                    self.assertEqual(row["status"], "desktop_only", (code, label))
                    only_b += 1
                if in_m:
                    self.assertEqual(row["mobile_price"], mob[label], (code, label))
                else:
                    self.assertIsNone(row["mobile_price"], (code, label))
                if in_d:
                    self.assertEqual(row["desktop_price"], desk[label], (code, label))
                else:
                    self.assertIsNone(row["desktop_price"], (code, label))
        self.assertEqual(only_a, 6)
        self.assertEqual(only_b, 0)

    def test_spot_labels_known_boundary_months(self):
        comp216 = {r["month_label"]: r for r in self.by_code["21694499"]["monthly_comparison_24m"]}
        self.assertEqual(comp216["24-11"]["status"], "mobile_only")
        self.assertEqual(comp216["24-11"]["mobile_price"], 176590)
        self.assertIsNone(comp216["24-11"]["desktop_price"])
        self.assertEqual(comp216["24-12"]["status"], "value_mismatch")
        self.assertEqual(comp216["24-12"]["mobile_price"], 214990)
        self.assertEqual(comp216["24-12"]["desktop_price"], 223020)
        comp5070 = {r["month_label"]: r for r in self.by_code["76550837"]["monthly_comparison_24m"]}
        self.assertTrue(all(r["status"] == "matched" for r in comp5070.values()))

    def test_partial_current_month_flagged(self):
        for code, product in self.by_code.items():
            comp = {r["month_label"]: r for r in product["monthly_comparison_24m"]}
            self.assertIn("26-10", comp, code)
            for label, row in comp.items():
                self.assertEqual(row["partial_month"], label == "26-10", (code, label))
                self.assertEqual(row["month_iso"], "20" + label, (code, label))
            mobiles = {r["label"]: r for r in product["monthly_mobile_24m"]}
            self.assertIn("26-10", mobiles, code)

    def test_no_appended_current_price_row(self):
        for code, product in self.by_code.items():
            mob3 = raw_mobile(code, 3)
            last = product["weekly_3m"][-1]
            self.assertEqual(last["mobile_price"], mob3[-1]["minPrice"], code)
            self.assertEqual(last["label_mobile"], mob3[-1]["date"].replace(".", "-")[-5:], code)
            self.assertEqual(len(product["weekly_3m"]), len(mob3), code)
            self.assertEqual(len(product["monthly_mobile_24m"]), len(raw_mobile(code, 24)), code)
            self.assertEqual(len(product["monthly_desktop_24m"]), len(raw_desktop(code, 24)), code)

    def test_labels_not_renamed_to_observed_weeks(self):
        dump = json.dumps(self.history)
        self.assertNotIn("FRI", dump)
        for code, product in self.by_code.items():
            for row in product["weekly_3m"]:
                self.assertRegex(row["label_mobile"], "^[0-9]{2}-[0-9]{2}$", (code, row))
                self.assertRegex(row["label_desktop"], "^[0-9]{2}-[0-9]{2}$", (code, row))
                self.assertRegex(row["desktop_fulldate"], "^[0-9]{2}-[0-9]{2}-[0-9]{2}$", (code, row))
            for row in product["monthly_mobile_24m"] + product["monthly_desktop_24m"]:
                self.assertRegex(row["label"], "^[0-9]{2}-[0-9]{2}$", (code, row))

    def test_no_verified_minimum_or_representative_claim(self):
        def walk(node):
            if isinstance(node, dict):
                for key, value in node.items():
                    self.assertNotIn("representative", key)
                    self.assertNotIn("typical", key)
                    self.assertNotIn("average", key)
                    walk(value)
            elif isinstance(node, list):
                for item in node:
                    walk(item)
        walk(self.history)
        sem = self.history["price_semantics"]
        self.assertEqual(sem["aggregation_basis"], "unconfirmed")
        self.assertEqual(sem["weekly_aggregation"], "unknown")

    def test_known_spike_values_preserved(self):
        code = "20740013"
        mob = {r["date"].replace(".", "-"): r["minPrice"] for r in raw_mobile(code, 24)}
        exported = {r["label"]: r["price"] for r in self.by_code[code]["monthly_mobile_24m"]}
        self.assertIn("25-11", exported)
        self.assertEqual(exported["25-11"], mob["25-11"])
        desk = {desktop_label(r): r["minPrice"] for r in raw_desktop(code, 24)}
        exported_d = {r["label"]: r["price"] for r in self.by_code[code]["monthly_desktop_24m"]}
        self.assertIn("25-11", exported_d)
        self.assertEqual(exported_d["25-11"], desk["25-11"])

    def test_iso_display_rules(self):
        for code, product in self.by_code.items():
            for row in product["weekly_3m"]:
                self.assertEqual(row["iso_date"], "20" + row["desktop_fulldate"], (code, row))
                self.assertTrue(row["iso_year_inferred"], (code, row))
                self.assertRegex(row["iso_date"], "^2026-[0-9]{2}-[0-9]{2}$", (code, row))

    def test_source_hashes_and_counts_match_raw(self):
        sources = self.history["sources"]
        self.assertEqual(len(sources), 48)
        for entry in sources:
            path = ROOT / entry["file"]
            self.assertTrue(path.is_file(), entry["file"])
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(entry["sha256"], digest, entry["file"])
        cited = self.history["audit_consistency"]["cited"]
        self.assertEqual(cited["cross_surface_value_mismatches"], 13)
        self.assertEqual(cited["cross_surface_mobile_only_rows"], 6)
        self.assertEqual(cited["cross_surface_desktop_only_rows"], 0)
        self.assertEqual(cited["desktop_internal_mismatches"], 9)
        self.assertEqual(cited["mobile_internal_mismatches"], 0)

    def test_build_history_returns_written_document(self):
        built = helper.build_history()
        on_disk = load_history()
        strip = lambda d: {k: v for k, v in d.items() if k != "generated_date_kst"}
        self.assertEqual(strip(built), strip(on_disk))


if __name__ == "__main__":
    unittest.main()
