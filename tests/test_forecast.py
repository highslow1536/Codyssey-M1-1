"""Independent verification + regression tests for docs/forecast_protocol.md.

Scope: read-only. These tests never modify model sources, UI, or data.
They use synthetic fixtures plus (when present) read-only checks of the
audited outputs. Run: .venv/bin/python -m unittest tests/test_forecast.py
"""
import csv
import json
import math
import unittest
from datetime import date, timedelta

import numpy as np

import scripts.build_forecast as bf


def weekly_points(start, n, price=100.0, growth=0.01, gaps=()):
    pts = []
    d = start
    for k in range(n):
        p = None if k in gaps else round(price * ((1.0 + growth) ** k), 4)
        pts.append({"date": d.isoformat(), "price": p,
                    "quoteDate": d.isoformat() if p is not None else None})
        d += timedelta(days=7)
    return pts


def monthly_points(start, n, price=1000.0, step=10.0, gaps=()):
    pts = []
    d = start
    for k in range(n):
        p = None if k in gaps else round(price + step * k, 4)
        pts.append({"date": d.isoformat(), "price": p, "quoteDate": None})
        d = bf.add_months(d, 1)
    return pts


def assert_features_equal(tc, a, b):
    tc.assertIsNotNone(a)
    tc.assertIsNotNone(b)
    tc.assertEqual(len(a), len(b))
    for x, y in zip(a, b):
        if isinstance(x, float) and isinstance(y, float) and math.isnan(x) and math.isnan(y):
            continue
        tc.assertAlmostEqual(float(x), float(y), places=9)


class TargetDateTest(unittest.TestCase):
    def test_weekly_is_first_friday_on_or_after_3mo(self):
        origins = [date(2023, 1, 6), date(2023, 1, 31), date(2023, 2, 28),
                   date(2024, 2, 29), date(2023, 5, 5), date(2023, 11, 3),
                   date(2024, 12, 27)]
        for o in origins:
            with self.subTest(origin=o.isoformat()):
                t = bf.target_date(o, "weekly")
                self.assertEqual(t.weekday(), 4)
                self.assertGreaterEqual(t, bf.add_months(o, 3))
                self.assertLess(t - timedelta(days=7), bf.add_months(o, 3))

    def test_weekly_interval_is_13_or_14_weeks(self):
        d = date(2021, 1, 1)
        d += timedelta(days=(4 - d.weekday()) % 7)
        cur = d
        checked = 0
        while cur <= date(2025, 12, 31):
            t = bf.target_date(cur, "weekly")
            delta = (t - cur).days
            self.assertGreaterEqual(delta, 91)
            self.assertLessEqual(delta, 98)
            self.assertEqual(delta % 7, 0)
            cur += timedelta(days=7)
            checked += 1
        self.assertGreater(checked, 200)

    def test_monthly_targets_exact_bucket_3mo_later(self):
        for o in [date(2023, 1, 1), date(2023, 2, 1), date(2023, 5, 1),
                  date(2024, 11, 1), date(2025, 12, 1)]:
            with self.subTest(origin=o.isoformat()):
                t = bf.target_date(o, "monthly")
                self.assertEqual((t.year, t.month, t.day),
                                 (bf.add_months(o, 3).year, bf.add_months(o, 3).month, 1))


class FeaturesLeakageTest(unittest.TestCase):
    def test_future_mutation_does_not_change_prefix_features(self):
        pts = weekly_points(date(2023, 1, 6), 12)
        before = bf.features(pts, 6, "weekly")
        self.assertIsNotNone(before)
        self.assertEqual(len(before), 9)
        mutated = [dict(p) for p in pts]
        for k in range(7, len(mutated)):
            mutated[k]["price"] = 99999.0
        after = bf.features(mutated, 6, "weekly")
        assert_features_equal(self, before, after)

    def test_appending_future_points_does_not_change_features(self):
        pts = weekly_points(date(2023, 1, 6), 12)
        before = bf.features(pts, 6, "weekly")
        extended = pts + weekly_points(date(2023, 3, 31), 8, price=1.0)
        after = bf.features(extended, 6, "weekly")
        assert_features_equal(self, before, after)

    def test_origin_change_does_change_features(self):
        pts = weekly_points(date(2023, 1, 6), 12)
        before = bf.features(pts, 6, "weekly")
        mutated = [dict(p) for p in pts]
        mutated[6]["price"] = mutated[6]["price"] * 1.5
        after = bf.features(mutated, 6, "weekly")
        self.assertFalse(all(
            (math.isnan(a) and math.isnan(b)) or abs(a - b) < 1e-9
            for a, b in zip(before, after)))

    def test_missing_origin_gives_no_features(self):
        pts = weekly_points(date(2023, 1, 6), 12, gaps=(6,))
        self.assertIsNone(bf.features(pts, 6, "weekly"))

    def test_monthly_feature_length_and_category(self):
        pts = monthly_points(date(2023, 1, 1), 12)
        x = bf.features(pts, 6, "monthly", "GPU")
        self.assertIsNotNone(x)
        self.assertEqual(len(x), 13)


class SamplesAndCutoffTest(unittest.TestCase):
    def test_monthly_available_is_conservative(self):
        pts = monthly_points(date(2023, 1, 1), 12)
        series = {"id": "KR_SYN", "frequency": "monthly", "category": "CPU",
                  "points": pts}
        samples, _ = bf.make_samples(series)
        by_origin = {s["origin"]: s for s in samples}
        s = by_origin["2023-04-01"]
        self.assertEqual(s["target"], "2023-07-01")
        self.assertEqual(s["available"], "2023-05-01")
        self.assertEqual(s["targetAvailable"], "2023-08-01")
        self.assertGreater(s["available"], s["origin"])
        self.assertGreater(s["targetAvailable"], s["target"])

    def test_weekly_available_is_origin_itself(self):
        pts = weekly_points(date(2023, 1, 6), 24)
        series = {"id": "US_SYN", "frequency": "weekly", "category": "GPU",
                  "points": pts}
        samples, _ = bf.make_samples(series)
        s = next(r for r in samples if r["origin"] == "2023-02-10")
        self.assertEqual(s["available"], "2023-02-10")
        self.assertEqual(s["targetAvailable"], s["target"])

    def test_mature_training_strict_cutoff(self):
        rows = [
            {"y": 1, "targetAvailable": "2024-01-01"},
            {"y": 0, "targetAvailable": "2024-04-01"},
            {"y": None, "targetAvailable": "2023-01-01"},
            {"y": 2, "targetAvailable": "2024-03-31"},
        ]
        out = bf.mature_training(rows, "2024-04-01")
        self.assertEqual(
            sorted(r["targetAvailable"] for r in out),
            ["2024-01-01", "2024-03-31"])

    def test_missing_target_is_not_interpolated(self):
        pts = weekly_points(date(2023, 1, 6), 24, gaps=(18,))
        series = {"id": "US_GAP", "frequency": "weekly", "category": "GPU",
                  "points": pts}
        samples, failures = bf.make_samples(series)
        self.assertGreaterEqual(failures.get("missing_target", 0), 1)
        for s in samples:
            if s["y"] is None and s["targetAvailable"] <= bf.AS_OF.isoformat():
                self.assertIsNone(s["change"])
        self.assertNotIn("unmatured_target", failures)

    def test_missing_origin_produces_no_sample(self):
        pts = weekly_points(date(2023, 1, 6), 24, gaps=(8,))
        series = {"id": "US_MISS", "frequency": "weekly", "category": "GPU",
                  "points": pts}
        samples, failures = bf.make_samples(series)
        origins = {s["origin"] for s in samples}
        self.assertNotIn(pts[8]["date"], origins)
        self.assertGreaterEqual(failures.get("missing_origin_or_features", 0), 1)

    def test_future_immature_targets_excluded(self):
        pts = monthly_points(date(2026, 6, 1), 5)
        series = {"id": "KR_NEW", "frequency": "monthly", "category": "CPU",
                  "points": pts}
        samples, failures = bf.make_samples(series)
        self.assertTrue(samples)
        for s in samples:
            self.assertIsNone(s["y"])
        self.assertGreaterEqual(failures.get("unmatured_target", 0), 1)
        self.assertEqual(bf.mature_training(samples, "2026-09-01"), [])

    def test_weekly_grid_never_carries_or_uses_incomplete_week(self):
        quotes = [{"timestamp": "2026-10-02", "date": date(2026, 10, 2),
                   "price": 100.0, "row": 0},
                  {"timestamp": "2026-10-09", "date": date(2026, 10, 9),
                   "price": 101.0, "row": 1},
                  {"timestamp": "2026-10-23", "date": date(2026, 10, 23),
                   "price": 102.0, "row": 2}]
        grid = bf.weekly_grid(quotes)
        dates = [p["date"] for p in grid]
        self.assertIn("2026-10-02", dates)
        self.assertIn("2026-10-09", dates)
        self.assertNotIn("2026-10-23", dates)

    def test_monthly_grid_excludes_partial_without_carry(self):
        monthly = [{"date": "2023-01", "price": 100.0},
                   {"date": "2023-02", "price": 101.0, "partial": True},
                   {"date": "2023-03", "price": 102.0}]
        grid = bf.monthly_grid(monthly)
        by_date = {p["date"]: p for p in grid}
        self.assertIsNone(by_date["2023-02-01"]["price"])
        self.assertEqual(by_date["2023-03-01"]["price"], 102.0)


class ProbabilityCalibrationTest(unittest.TestCase):
    def test_temperature_rows_sum_to_one(self):
        p = np.array([[0.2, 0.6, 0.2], [0.9, 0.05, 0.05], [1 / 3.0] * 3])
        for t in [0.5, 1.0, 2.0, 4.0]:
            q = bf.temperature(p, t)
            for row in q:
                self.assertAlmostEqual(float(row.sum()), 1.0, places=9)
                for v in row:
                    self.assertGreaterEqual(float(v), 0.0)
                    self.assertLessEqual(float(v), 1.0)

    def test_temperature_one_is_identity(self):
        p = np.array([[0.2, 0.6, 0.2], [0.7, 0.2, 0.1]])
        q = bf.temperature(p, 1.0)
        np.testing.assert_allclose(q, p, rtol=1e-9, atol=1e-12)

    def test_temperature_sharpens_and_flattens(self):
        p = np.array([[0.2, 0.6, 0.2]])
        sharp = bf.temperature(p, 0.5)
        flat = bf.temperature(p, 4.0)
        self.assertGreater(float(sharp[0].max()), 0.6)
        self.assertLess(float(flat[0].max()), 0.6)

    def test_label_thresholds(self):
        self.assertEqual(bf.label(0.03), 1)
        self.assertEqual(bf.label(-0.03), 1)
        self.assertEqual(bf.label(0.0301), 2)
        self.assertEqual(bf.label(-0.0301), 0)
        self.assertEqual(bf.label(0.0), 1)

    def test_brier_and_baseline(self):
        self.assertAlmostEqual(bf.brier([1.0, 0.0, 0.0], 0), 0.0, places=9)
        self.assertAlmostEqual(
            bf.brier([1 / 3.0] * 3, 0), 2 / 3.0, places=9)
        rows = [{"y": 0}, {"y": 1}, {"y": 1}, {"y": 2}]
        base = bf.frequency_baseline(rows)
        self.assertAlmostEqual(float(base.sum()), 1.0, places=9)
        counts = np.array([1, 2, 1]) + 1
        np.testing.assert_allclose(base, counts / counts.sum())


class TimeBlocksTest(unittest.TestCase):
    def _rows(self, origins, probs=None, base=None, y=1):
        rows = []
        for o in origins:
            t = bf.target_date(o, "weekly")
            rows.append({"origin": o.isoformat(), "available": o.isoformat(),
                         "targetAvailable": t.isoformat(),
                         "probabilities": probs or [0.2, 0.6, 0.2],
                         "baseline": base or [1 / 3.0] * 3, "y": y})
        return rows

    def test_nonoverlap_dedupes_same_origin(self):
        o = date(2023, 1, 6)
        t = bf.target_date(o, "weekly")
        rows = [{"origin": o.isoformat(), "available": o.isoformat(),
                 "targetAvailable": t.isoformat()},
                {"origin": o.isoformat(), "available": o.isoformat(),
                 "targetAvailable": t.isoformat()}]
        self.assertEqual(bf.nonoverlap_count(rows), 1)

    def test_nonoverlap_spaced_origins_all_count(self):
        origins = [date(2023, 1, 6), date(2023, 5, 12), date(2023, 9, 8)]
        self.assertEqual(bf.nonoverlap_count(self._rows(origins)), 3)

    def test_nonoverlap_overlapping_weeks_do_not_inflate(self):
        start = date(2023, 1, 6)
        origins = [start + timedelta(days=7 * k) for k in range(14)]
        n = bf.nonoverlap_count(self._rows(origins))
        self.assertGreaterEqual(n, 1)
        self.assertLess(n, len(origins))

    def test_block_ci_deterministic_and_bounded(self):
        start = date(2023, 1, 6)
        origins = [start + timedelta(days=7 * k) for k in range(32)]
        rows = self._rows(origins)
        ci1 = bf.block_improvement_ci(rows, "weekly")
        ci2 = bf.block_improvement_ci(rows, "weekly")
        self.assertIsNotNone(ci1)
        self.assertEqual(ci1, ci2)
        lo, hi = ci1
        self.assertLessEqual(lo, hi)

    def test_block_ci_none_when_too_short(self):
        start = date(2023, 1, 6)
        origins = [start + timedelta(days=7 * k) for k in range(4)]
        self.assertIsNone(bf.block_improvement_ci(self._rows(origins), "weekly"))


class GatesThresholdsTest(unittest.TestCase):
    def _good_eval(self, freq="weekly"):
        return {"n": 60, "originsN": 60 if freq == "weekly" else 14,
                "nonoverlapN": 9, "from": "2025-01-01", "to": "2026-01-01",
                "brier": 0.5, "baselineBrier": 0.6, "brierSkill": 0.2,
                "logLoss": 0.8, "baselineLogLoss": 1.0, "accuracy": 0.6,
                "ece": 0.05, "mae": 1.0, "naiveMae": 2.0, "driftMae": 1.5,
                "improvementCI": [0.01, 0.1], "classCounts": [15, 20, 25],
                "reliability": []}

    def test_sufficient_minimums(self):
        weekly_ok = [{"y": c} for c in ([0] * 5 + [1] * 5 + [2] * 70)]
        self.assertTrue(bf.sufficient(weekly_ok, "weekly"))
        self.assertFalse(bf.sufficient(weekly_ok[:79], "weekly"))
        self.assertFalse(bf.sufficient([{"y": 1}] * 100, "weekly"))
        monthly_ok = [{"y": c, "origin": "2023-%02d-01" % (1 + (i % 6))} for i, c in
                      enumerate([0] * 6 + [1] * 6 + [2] * 36)]
        self.assertTrue(bf.sufficient(monthly_ok, "monthly"))
        self.assertFalse(bf.sufficient(monthly_ok[:47], "monthly"))
        few_origins = [dict(r, origin="2023-01-01") for r in monthly_ok]
        self.assertFalse(bf.sufficient(few_origins, "monthly"))

    def test_gates_pass_and_each_failure(self):
        self.assertTrue(bf.gates(self._good_eval("weekly"), "weekly")["passed"])
        for key, val in [("originsN", 51), ("nonoverlapN", 7)]:
            with self.subTest(key=key):
                e = self._good_eval("weekly")
                e[key] = val
                g = bf.gates(e, "weekly")
                self.assertFalse(g["passed"])
                self.assertTrue(g["reasons"])
        e = self._good_eval("weekly")
        e["classCounts"] = [9, 20, 31]
        self.assertFalse(bf.gates(e, "weekly")["passed"])
        e = self._good_eval("weekly")
        e["improvementCI"] = [-0.01, 0.1]
        self.assertFalse(bf.gates(e, "weekly")["passed"])
        e = self._good_eval("weekly")
        e["logLoss"] = 1.2
        self.assertFalse(bf.gates(e, "weekly")["passed"])
        e = self._good_eval("weekly")
        e["ece"] = 0.11
        self.assertFalse(bf.gates(e, "weekly")["passed"])
        e = self._good_eval("monthly")
        e["originsN"] = 11
        self.assertFalse(bf.gates(e, "monthly")["passed"])


class AuditReadTest(unittest.TestCase):
    def test_protocol_doc_present(self):
        p = bf.ROOT / "docs" / "forecast_protocol.md"
        self.assertTrue(p.exists())
        text = p.read_text()
        for phrase in ["3%", "Wilson", "Laplace", "Brier"]:
            self.assertIn(phrase, text)

    def test_prediction_audit_columns_when_outputs_exist(self):
        out = bf.OUT / "forecast_predictions.csv"
        if not out.exists():
            self.skipTest("forecast outputs not built yet")
        with out.open(encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            required = ["id", "origin", "available", "target", "targetAvailable",
                        "fitCutoff", "trainThrough", "trainN", "candidate",
                        "missingFeatures", "price", "actualClass", "actualChange",
                        "p_down", "p_flat", "p_up", "base_down", "base_flat", "base_up"]
            for col in required:
                self.assertIn(col, reader.fieldnames)
            n = sum(1 for _ in reader)
            self.assertGreater(n, 0)

    def test_source_hashes_readable_when_present(self):
        p = bf.OUT / "source_hashes.json"
        if not p.exists():
            self.skipTest("forecast outputs not built yet")
        hashes = json.loads(p.read_text())
        self.assertTrue(hashes)
        for key, value in hashes.items():
            self.assertEqual(len(value), 64)
            int(value, 16)


if __name__ == "__main__":
    unittest.main()
