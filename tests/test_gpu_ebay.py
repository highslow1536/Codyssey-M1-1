"""Tests for Tom\u0027s Hardware eBay monthly GPU extraction."""
import csv
import json
import math
from pathlib import Path
import unittest
ROOT = Path(__file__).resolve().parents[1]
PDIR = ROOT / "data/processed/2026-10-22/gpu_ebay"
VDIR = ROOT / "data/verification/2026-10-22/gpu_ebay"
def read_csv(name):
    with open(PDIR / name, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))
class GpuEbayTest(unittest.TestCase):
    def test_grid_shape_and_no_interpolation(self):
        grid = read_csv("monthly_grid_2020_2022.csv")
        self.assertEqual(len(grid), 108)
        months = sorted({r["month"] for r in grid})
        self.assertEqual(len(months), 36)
        self.assertEqual(months[0], "2020-01")
        self.assertEqual(months[-1], "2022-12")
        for r in grid:
            if r["ebay_avg_price_usd"] == "":
                self.assertNotEqual(r["price_missing_reason"], "")
                self.assertIn(r["month"][:4], ("2020", "2021", "2022"))
            else:
                self.assertGreater(float(r["ebay_avg_price_usd"]), 0)
                if r["qty_sold"] != "":
                    self.assertGreaterEqual(int(float(r["qty_sold"])), 0)
    def test_monthly_observations_count(self):
        obs = read_csv("monthly_observations.csv")
        self.assertEqual(len(obs), 48)
        keys = {(r["gpu_model"], r["sale_month"]) for r in obs}
        self.assertEqual(len(keys), 48)
        for gpu in ("RTX 3070", "RTX 3080_10GB", "RTX 3090"):
            self.assertEqual(sum(1 for r in obs if r["gpu_model"] == gpu), 16)
        self.assertTrue(all("Ti" not in r["gpu_label_source"] for r in obs))
        self.assertTrue(all("12GB" not in r["gpu_label_source"] for r in obs))
    def test_partial_excluded_from_grid(self):
        partials = read_csv("partial_oct01_15_2021.csv")
        self.assertEqual(len(partials), 3)
        grid = read_csv("monthly_grid_2020_2022.csv")
        oct21 = [r for r in grid if r["month"] == "2021-10"]
        self.assertEqual(len(oct21), 3)
        self.assertTrue(all(r["sale_period_type"] == "monthly" for r in oct21))
    def test_log_returns_adjacent_only(self):
        grid = read_csv("monthly_grid_2020_2022.csv")
        by_gpu = {}
        for r in grid:
            by_gpu.setdefault(r["gpu_model"], []).append(r)
        for gpu, rows in by_gpu.items():
            rows.sort(key=lambda x: x["month"])
            for i in range(1, len(rows)):
                cur, prev = rows[i], rows[i - 1]
                if cur["log_return_price"] != "":
                    p1 = float(cur["ebay_avg_price_usd"])
                    p0 = float(prev["ebay_avg_price_usd"])
                    self.assertAlmostEqual(float(cur["log_return_price"]), math.log(p1 / p0), places=9)
                else:
                    self.assertNotEqual(cur["return_missing_reason"], "")
    def test_no_weekly_confusion_and_headers_preserved(self):
        audits = read_csv("audit_tables.csv")
        self.assertGreaterEqual(len(audits), 16)
        for a in audits:
            if a.get("is_monthly_table") == "True":
                self.assertIn("ebay price", (a.get("price_header") or "").lower())
    def test_sources_and_manifest(self):
        manifest = json.loads((VDIR / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(len(manifest), 16)
        for m in manifest:
            self.assertEqual(len(m["sha256"]), 64)
            self.assertTrue((VDIR / m["file"]).exists())
        summary = json.loads((PDIR / "quality_summary.json").read_text(encoding="utf-8"))
        self.assertEqual(summary["n_observations_monthly"], 48)
        self.assertEqual(summary["n_grid_rows"], 108)
    def test_crosscheck_quality(self):
        x = read_csv("crosscheck_existing_csv.csv")
        self.assertGreaterEqual(len(x), 40)
        mism = [r for r in x if r["qty_match"] not in ("True", "TRUE", "true", "1")]
        self.assertEqual(mism, [])
if __name__ == "__main__":
    unittest.main()
