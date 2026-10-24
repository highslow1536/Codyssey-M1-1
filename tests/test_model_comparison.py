"""Sidecar verification for scripts/compare_forecast_models.py.
Scope: synthetic fixtures plus shape checks of the published aggregate
model_comparison.json when present. These tests never read raw price or
stock sources; only code and aggregate forecast artifacts are used.
Run: .venv/bin/python -m unittest tests/test_model_comparison.py
"""
import json
import math
import unittest
from datetime import date, timedelta
from unittest import mock
import numpy as np
from scipy.stats import norm as sp_norm
import scripts.build_forecast as bf
import scripts.compare_forecast_models as cmp
# ----------------------------------------------------------------------------
# Synthetic fixtures (Fridays; 2022-01-07 is a Friday).
# ----------------------------------------------------------------------------
def weekly_points(start, n, price=100.0, growth=0.002, gaps=()):
    pts = []
    d = start
    for k in range(n):
        p = None if k in gaps else round(price * ((1.0 + growth) ** k), 4)
        pts.append({"date": d.isoformat(), "price": p,
                    "quoteDate": d.isoformat() if p is not None else None})
        d += timedelta(days=7)
    return pts
def weekly_samples(points, series_id="SYN", y_cycle=(0, 1, 2)):
    samples = []
    for k, p in enumerate(points):
        if p["price"] is None:
            continue
        d = date.fromisoformat(p["date"])
        t = bf.target_date(d, "weekly")
        samples.append({"id": series_id, "origin": p["date"], "available": p["date"],
                        "target": t.isoformat(), "targetAvailable": t.isoformat(),
                        "price": p["price"], "y": y_cycle[k % len(y_cycle)],
                        "change": 0.01, "missingFeatures": 0,
                        "classMedians": [-0.05, 0.0, 0.05]})
    return samples
def sel_row(origin, y, probs, target_available="2024-12-01"):
    return {"id": "S", "origin": origin, "available": origin,
            "target": "2024-04-01", "targetAvailable": target_available,
            "price": 100.0, "y": y, "change": 0.01,
            "probabilities": list(probs), "classMedians": [-0.05, 0.0, 0.05],
            "missingFeatures": 0, "baseline": [1.0 / 3.0] * 3, "driftChange": 0.0}
def sharp(y):
    p = [0.05, 0.05, 0.05]
    p[y] = 0.9
    return p
def selection_rows(n, origins, probs_fn, target_available="2024-12-01"):
    return [sel_row(o, i % 3, probs_fn(i % 3), target_available)
            for i, o in enumerate(origins)]
# ----------------------------------------------------------------------------
class PrefixAvailabilityTest(unittest.TestCase):
    def test_weekly_prefix_strictly_before_cutoff(self):
        pts = weekly_points(date(2022, 12, 16), 5)
        self.assertEqual([p["date"] for p in pts],
                         ["2022-12-16", "2022-12-23", "2022-12-30", "2023-01-06", "2023-01-13"])
        prefix = cmp.prefix_before(pts, "weekly", "2023-01-01")
        self.assertEqual([p["date"] for p in prefix],
                         ["2022-12-16", "2022-12-23", "2022-12-30"])
    def test_monthly_bucket_known_only_next_month(self):
        pts = [{"date": "2023-02-01", "price": 100.0, "quoteDate": None},
               {"date": "2023-03-01", "price": 101.0, "quoteDate": None},
               {"date": "2023-04-01", "price": 102.0, "quoteDate": None}]
        self.assertEqual(cmp.observation_available(pts[1], "monthly"), "2023-04-01")
        prefix = cmp.prefix_before(pts, "monthly", "2023-04-01")
        self.assertEqual([p["date"] for p in prefix], ["2023-02-01"])
    def test_appending_in_quarter_prices_does_not_change_prefix(self):
        pts = weekly_points(date(2022, 10, 7), 20)
        before = cmp.prefix_before(pts, "weekly", "2023-01-01")
        extended = pts + weekly_points(date(2023, 2, 24), 8, price=1.0)
        after = cmp.prefix_before(extended, "weekly", "2023-01-01")
        self.assertEqual([p["date"] for p in before], [p["date"] for p in after])
# ----------------------------------------------------------------------------
class EligibilityTest(unittest.TestCase):
    def test_weekly_minimum_boundary(self):
        self.assertIsNone(cmp.eligibility(np.full(52, 4.6), "weekly", "arima"))
        self.assertEqual(cmp.eligibility(np.full(51, 4.6), "weekly", "arima"),
                         "insufficient_history")
        short = np.full(52, np.nan)
        short[:39] = 4.6
        self.assertEqual(cmp.eligibility(short, "weekly", "arima"), "insufficient_history")
    def test_monthly_minimum_boundary(self):
        self.assertIsNone(cmp.eligibility(np.full(12, 4.6), "monthly", "arima"))
        self.assertEqual(cmp.eligibility(np.full(11, 4.6), "monthly", "arima"),
                         "insufficient_history")
        short = np.full(12, np.nan)
        short[:9] = 4.6
        self.assertEqual(cmp.eligibility(short, "monthly", "arima"), "insufficient_history")
    def test_sarima_weekly_requires_two_dense_cycles(self):
        self.assertIsNone(cmp.eligibility(np.full(104, 4.6), "weekly", "sarima"))
        self.assertEqual(cmp.eligibility(np.full(103, 4.6), "weekly", "sarima"),
                         "fewer_than_two_seasonal_cycles")
        sparse_last = np.full(104, 4.6)
        sparse_last[-14:] = np.nan
        self.assertEqual(cmp.eligibility(sparse_last, "weekly", "sarima"),
                         "sparse_seasonal_cycles")
        sparse_prev = np.full(104, 4.6)
        sparse_prev[:14] = np.nan
        self.assertEqual(cmp.eligibility(sparse_prev, "weekly", "sarima"),
                         "sparse_seasonal_cycles")
    def test_sarima_cycle_coverage_boundary_is_75_percent(self):
        exact = np.full(104, 4.6)
        exact[-13:] = np.nan
        self.assertIsNone(cmp.eligibility(exact, "weekly", "sarima"))
    def test_nonseasonal_candidate_ignores_sparse_cycles(self):
        sparse = np.full(104, 4.6)
        sparse[-14:] = np.nan
        self.assertIsNone(cmp.eligibility(sparse, "weekly", "arima"))
        self.assertIsNone(cmp.eligibility(sparse, "weekly", "ets"))
    def test_sarima_monthly_cycles(self):
        self.assertIsNone(cmp.eligibility(np.full(24, 4.6), "monthly", "sarima"))
        self.assertEqual(cmp.eligibility(np.full(23, 4.6), "monthly", "sarima"),
                         "fewer_than_two_seasonal_cycles")
        sparse = np.full(24, 4.6)
        sparse[-4:] = np.nan
        self.assertEqual(cmp.eligibility(sparse, "monthly", "sarima"),
                         "sparse_seasonal_cycles")
# ----------------------------------------------------------------------------
class DistributionTest(unittest.TestCase):
    def test_tight_bands_match_exact_cdf_and_concentrate_flat(self):
        mu, var, price = math.log(100.0), 0.0001, 100.0
        sd = math.sqrt(var)
        lo = (math.log(price * 0.97) - mu) / sd
        hi = (math.log(price * 1.03) - mu) / sd
        expected = [sp_norm.cdf(lo), sp_norm.cdf(hi) - sp_norm.cdf(lo), 1.0 - sp_norm.cdf(hi)]
        p, point, _iv = cmp.distribution(mu, var, price)
        self.assertAlmostEqual(sum(p), 1.0, places=9)
        for actual, exp in zip(p, expected):
            self.assertAlmostEqual(actual, exp, places=9)
        self.assertGreater(p[1], p[0])
        self.assertGreater(p[1], p[2])
        self.assertAlmostEqual(point, 0.0, places=9)
    def test_wide_bands_match_exact_cdf_with_heavy_tails(self):
        mu, var, price = math.log(100.0), 0.01, 100.0
        sd = math.sqrt(var)
        lo = (math.log(price * 0.97) - mu) / sd
        hi = (math.log(price * 1.03) - mu) / sd
        expected = [sp_norm.cdf(lo), sp_norm.cdf(hi) - sp_norm.cdf(lo), 1.0 - sp_norm.cdf(hi)]
        p, point, _iv = cmp.distribution(mu, var, price)
        self.assertAlmostEqual(sum(p), 1.0, places=9)
        for actual, exp in zip(p, expected):
            self.assertAlmostEqual(actual, exp, places=9)
        self.assertGreater(p[0], p[1])
        self.assertGreater(p[2], p[1])
        self.assertAlmostEqual(point, 0.0, places=9)
    def test_intervals_nest_and_contain_median(self):
        _p, point, iv = cmp.distribution(math.log(100.0), 0.04, 100.0)
        self.assertGreater(iv["80"][0], iv["95"][0])
        self.assertLess(iv["80"][1], iv["95"][1])
        self.assertLessEqual(iv["80"][0], point)
        self.assertGreaterEqual(iv["80"][1], point)
        self.assertLessEqual(iv["95"][0], point)
        self.assertGreaterEqual(iv["95"][1], point)
    def test_upward_drift_puts_mass_up(self):
        p, point, _iv = cmp.distribution(math.log(110.0), 0.01, 100.0)
        self.assertGreater(p[2], p[0])
        self.assertGreater(p[2], p[1])
        self.assertAlmostEqual(point, 0.10, places=9)
    def test_wider_variance_flattens_classes(self):
        tight, _p1, _i1 = cmp.distribution(math.log(110.0), 0.0001, 100.0)
        wide, _p2, _i2 = cmp.distribution(math.log(110.0), 1.0, 100.0)
        self.assertGreater(max(tight), max(wide))
    def test_invalid_distribution_raises(self):
        for mu, var, price in [(math.log(100.0), 0.0, 100.0),
                               (math.log(100.0), -1.0, 100.0),
                               (float("nan"), 0.01, 100.0),
                               (math.log(100.0), 0.01, 0.0),
                               (math.log(100.0), 0.01, -5.0)]:
            with self.subTest(mu=mu, var=var, price=price):
                with self.assertRaises(ValueError):
                    cmp.distribution(mu, var, price)
# ----------------------------------------------------------------------------
class CommonRowsSelectTest(unittest.TestCase):
    def test_selection_excludes_test_future_rows(self):
        rows = selection_rows(30, [(date(2024, 1, 1) + timedelta(days=i)).isoformat()
                                   for i in range(30)], sharp)
        future = [sel_row("2025-02-01", 2, sharp(2), "2025-05-01")]
        paired, active = cmp.common_rows({"logistic": rows, "forest": rows + future},
                                         "selection")
        self.assertEqual(sorted(active), ["forest", "logistic"])
        self.assertEqual(len(paired["logistic"]), 30)
        self.assertEqual(len(paired["forest"]), 30)
    def test_test_phase_excludes_unmatured_and_old_rows(self):
        mature = [sel_row("2025-02-01", 1, sharp(1), "2025-05-01")]
        unmatured = [dict(sel_row("2025-03-01", 1, sharp(1), "2025-06-01"), y=None)]
        old = [sel_row("2024-06-01", 0, sharp(0), "2024-09-01")]
        paired, active = cmp.common_rows({"arima": mature + unmatured + old}, "test")
        self.assertEqual(active, ["arima"])
        self.assertEqual([r["origin"] for r in paired["arima"]], ["2025-02-01"])
    def test_common_origins_are_exact_intersection(self):
        base = [(date(2024, 1, 1) + timedelta(days=i)).isoformat() for i in range(30)]
        a = selection_rows(30, base, sharp)
        extra = ["2024-12-%02d" % d for d in range(1, 6)]
        b = selection_rows(30, base[5:] + extra, sharp)
        paired, _active = cmp.common_rows({"logistic": a, "forest": b}, "selection")
        self.assertEqual(len(paired["logistic"]), 25)
        self.assertEqual([r["origin"] for r in paired["logistic"]],
                         [r["origin"] for r in paired["forest"]])
    def test_winner_uses_selection_only_and_test_future_ignored(self):
        origins = [(date(2024, 1, 1) + timedelta(days=i)).isoformat() for i in range(30)]
        flat = [1.0 / 3.0] * 3
        predictions = {
            "logistic": selection_rows(30, origins, sharp),
            "forest": selection_rows(30, origins, lambda _y: flat),
        }
        for i in range(5):
            predictions["logistic"].append(sel_row("2025-0%d-01" % (i + 1), 0, sharp(2),
                                                  "2025-0%d-01" % (i + 4)))
            predictions["forest"].append(sel_row("2025-0%d-01" % (i + 1), 2, sharp(2),
                                                "2025-0%d-01" % (i + 4)))
        choice, _paired = cmp.select_model(predictions, {"candidate": "forest",
                                                         "temperature": 1.0})
        self.assertEqual(choice["status"], "past_validation_only")
        self.assertEqual(choice["candidate"], "logistic")
        self.assertEqual(choice["n"], 30)
    def test_candidate_below_24_selection_rows_is_excluded(self):
        origins = [(date(2024, 1, 1) + timedelta(days=i)).isoformat() for i in range(30)]
        predictions = {
            "logistic": selection_rows(30, origins, sharp),
            "forest": selection_rows(30, origins, sharp),
            "ets": selection_rows(5, origins[:5], sharp),
        }
        choice, _paired = cmp.select_model(predictions, {"candidate": "logistic",
                                                        "temperature": 1.0})
        self.assertNotIn("ets", choice["comparisonCandidates"])
        self.assertEqual(choice["candidate"], "logistic")
    def test_short_common_selection_retains_incumbent(self):
        base_a = [(date(2024, 1, 1) + timedelta(days=i)).isoformat() for i in range(30)]
        base_b = [(date(2024, 3, 1) + timedelta(days=i)).isoformat() for i in range(30)]
        predictions = {
            "logistic": selection_rows(30, base_a, sharp),
            "forest": selection_rows(30, base_b, sharp),
        }
        choice, _paired = cmp.select_model(predictions, {"candidate": "forest",
                                                         "temperature": 2.0})
        self.assertEqual(choice["status"], "incumbent_retained_insufficient_selection")
        self.assertEqual(choice["candidate"], "forest")
        self.assertEqual(choice["temperature"], 2.0)
        self.assertLess(choice["n"], 24)
        self.assertEqual(choice["options"], [])
    def test_missing_class_retains_incumbent(self):
        origins = [(date(2024, 1, 1) + timedelta(days=i)).isoformat() for i in range(30)]
        rows = [sel_row(o, i % 2, sharp(i % 2)) for i, o in enumerate(origins)]
        choice, _paired = cmp.select_model({"logistic": rows, "forest": rows},
                                            {"candidate": "logistic", "temperature": 1.0})
        self.assertEqual(choice["status"], "incumbent_retained_insufficient_selection")
        self.assertEqual(choice["candidate"], "logistic")
    def test_tie_break_is_deterministic_model_order(self):
        origins = [(date(2024, 1, 1) + timedelta(days=i)).isoformat() for i in range(30)]
        rows = selection_rows(30, origins, sharp)
        choice, _paired = cmp.select_model({"forest": list(rows), "logistic": list(rows)},
                                            {"candidate": "forest", "temperature": 1.0})
        self.assertEqual(choice["candidate"], "logistic")
        self.assertIn(choice["temperature"], bf.TEMPERATURES)
# ----------------------------------------------------------------------------
class CalibratedTest(unittest.TestCase):
    def test_ts_point_median_preserved(self):
        row = {"candidate": "ets", "probabilities": [0.2, 0.5, 0.3],
               "predictedChange": 0.07, "y": 1, "change": 0.05}
        for t in bf.TEMPERATURES:
            with self.subTest(temperature=t):
                out = cmp.calibrated([dict(row)], t)[0]
                self.assertEqual(out["predictedChange"], 0.07)
                self.assertAlmostEqual(sum(out["probabilities"]), 1.0, places=9)
                self.assertEqual(out["actualClass"], 1)
                self.assertEqual(out["actualChange"], 0.05)
    def test_classifier_point_is_probability_weighted_class_median(self):
        row = {"candidate": "logistic", "probabilities": [0.2, 0.5, 0.3],
               "predictedChange": 999.0, "classMedians": [-0.04, 0.0, 0.06],
               "y": 2, "change": 0.05}
        out = cmp.calibrated([dict(row)], 1.0)[0]
        self.assertAlmostEqual(out["predictedChange"], 0.2 * -0.04 + 0.5 * 0.0 + 0.3 * 0.06,
                               places=9)
        self.assertEqual(out["actualClass"], 2)
# ----------------------------------------------------------------------------
class _FakeState:
    def __init__(self, mu, var):
        self.mu = mu
        self.var = var
    def get_forecast(self, steps):
        m = mock.Mock()
        m.predicted_mean = np.asarray([self.mu] * steps)
        m.var_pred_mean = np.asarray([self.var] * steps)
        return m
class _FakeFitted:
    def __init__(self, mu=4.6, var=0.01):
        self.mu = mu
        self.var = var
        self.apply_calls = []
    def apply(self, values, refit=False, copy_initialization=True):
        assert refit is False
        self.apply_calls.append(np.asarray(values, dtype=float))
        return _FakeState(self.mu, self.var)
def fake_fit_factory(calls, fitted_list, fail_on=(), mu=4.6, var=0.01):
    def _fit(values, frequency, candidate):
        snapshot = np.asarray(values, dtype=float).copy()
        calls.append((snapshot, frequency, candidate))
        if len(calls) in fail_on:
            raise ValueError("nonconverged_fit")
        fitted = _FakeFitted(mu=mu, var=var)
        fitted_list.append(fitted)
        return fitted, []
    return _fit
# ----------------------------------------------------------------------------
class QuarterFreezeLeakageTest(unittest.TestCase):
    def setUp(self):
        self.points = weekly_points(date(2022, 1, 7), 90)
        self.samples = weekly_samples(self.points)
        self.series = {"id": "SYN", "frequency": "weekly", "points": self.points}
    def run_rolling(self, **kwargs):
        calls, fitted_list = [], []
        with mock.patch.object(cmp, "fit_price_model",
                               side_effect=fake_fit_factory(calls, fitted_list, **kwargs)):
            rows, failures, fits = cmp.rolling_price_predictions(self.series, self.samples,
                                                                "arima")
        return rows, failures, fits, calls, fitted_list
    def test_fit_uses_strict_prefix_once_per_quarter(self):
        rows, failures, _fits, calls, _fitted = self.run_rolling()
        self.assertEqual(failures, {})
        cutoffs = sorted({bf.quarter(s["available"]) for s in self.samples
                          if s["available"] >= "2023-01-01"})
        self.assertGreaterEqual(len(cutoffs), 2)
        self.assertEqual(len(calls), len(cutoffs))
        for (vals, freq, cand), cutoff in zip(calls, cutoffs):
            self.assertEqual(freq, "weekly")
            self.assertEqual(cand, "arima")
            self.assertEqual(len(vals), len(cmp.prefix_before(self.points, "weekly", cutoff)))
        self.assertEqual(len(calls[0][0]), 52)
        for r in rows:
            self.assertEqual(r["fitCutoff"], bf.quarter(r["available"]))
            self.assertLess(r["trainThrough"], r["fitCutoff"])
            self.assertEqual(r["stateThrough"], r["available"])
            self.assertAlmostEqual(sum(r["probabilities"]), 1.0, places=9)
        total = sum(1 for s in self.samples if s["available"] >= "2023-01-01")
        self.assertEqual(len(rows) + sum(failures.values()), total)
    def test_in_quarter_data_extends_state_without_refit(self):
        _rows, _failures, _fits, calls, fitted_list = self.run_rolling()
        apply_lens = [len(a) for f in fitted_list for a in f.apply_calls]
        self.assertTrue(apply_lens)
        self.assertGreater(max(apply_lens), len(calls[0][0]))
        self.assertEqual(len(calls[0][0]), 52)
    def test_mutating_in_quarter_prices_leaves_quarter_fit_unchanged(self):
        _rows, _failures, _fits, calls, _fitted = self.run_rolling()
        first_fit = calls[0][0].copy()
        mutated = [dict(p) for p in self.points]
        for p in mutated:
            if "2023-01-01" <= p["date"] < "2023-04-01" and p["price"] is not None:
                p["price"] = round(p["price"] * 2.0, 4)
        series2 = {"id": "SYN", "frequency": "weekly", "points": mutated}
        samples2 = weekly_samples(mutated)
        calls2, fitted2 = [], []
        with mock.patch.object(cmp, "fit_price_model",
                               side_effect=fake_fit_factory(calls2, fitted2)):
            cmp.rolling_price_predictions(series2, samples2, "arima")
        np.testing.assert_array_equal(calls2[0][0], first_fit)
    def test_fit_failure_is_recorded_not_scored(self):
        rows, failures, _fits, _calls, _fitted = self.run_rolling(fail_on=(1,))
        self.assertIn("nonconverged_fit", failures)
        self.assertGreater(failures["nonconverged_fit"], 0)
        self.assertTrue(rows)
    def test_invalid_predictive_variance_is_recorded(self):
        rows, failures, _fits, _calls, _fitted = self.run_rolling(var=0.0)
        self.assertEqual(rows, [])
        self.assertIn("invalid_predictive_distribution", failures)
# ----------------------------------------------------------------------------
# Real (unmocked) ETS smoke test over a gappy calendar grid. Exercises the
# real fit plus the fitted.apply clone path with NaN calendar dates. The
# statsmodels 0.14 clone omits known-initialization arguments, so a
# regression on that path raises ValueError and yields zero rows.
# ----------------------------------------------------------------------------
class RealEtsMissingCalendarTest(unittest.TestCase):
    def setUp(self):
        gaps = (10, 11, 40, 61, 62, 63)
        self.points = weekly_points(date(2022, 1, 7), 80, gaps=gaps)
        self.samples = weekly_samples(self.points)
        self.series = {"id": "SYN-ETS", "frequency": "weekly", "points": self.points}
    def test_ets_produces_rows_over_missing_weeks(self):
        rows, failures, fits = cmp.rolling_price_predictions(self.series, self.samples, "ets")
        self.assertTrue(rows, "ETS produced no rows: apply/clone path likely regressed")
        for r in rows:
            self.assertAlmostEqual(sum(r["probabilities"]), 1.0, places=9)
            for v in r["probabilities"]:
                self.assertGreaterEqual(v, 0.0)
                self.assertLessEqual(v, 1.0)
            iv = r["intervals"]
            self.assertLessEqual(iv["80"][0], r["predictedChange"])
            self.assertGreaterEqual(iv["80"][1], r["predictedChange"])
            self.assertLessEqual(iv["95"][0], iv["80"][0])
            self.assertGreaterEqual(iv["95"][1], iv["80"][1])
            self.assertEqual(r["fitCutoff"], bf.quarter(r["available"]))
            self.assertLess(r["trainThrough"], r["fitCutoff"])
            self.assertTrue(math.isfinite(r["logMean"]))
            self.assertTrue(math.isfinite(r["logVariance"]))
        self.assertTrue(fits)
        for f in fits:
            self.assertTrue(f["converged"])
            self.assertGreaterEqual(f["observedN"], 40)
        total = sum(1 for s in self.samples if s["available"] >= "2023-01-01")
        self.assertEqual(len(rows) + sum(failures.values()), total)
    def test_ets_result_matches_distribution_contract(self):
        rows, _failures, _fits = cmp.rolling_price_predictions(self.series, self.samples, "ets")
        self.assertTrue(rows)
        r = rows[0]
        p, point, _iv = cmp.distribution(r["logMean"], r["logVariance"], r["price"])
        self.assertAlmostEqual(point, r["predictedChange"], places=9)
        for a, b in zip(p, r["probabilities"]):
            self.assertAlmostEqual(a, b, places=9)
# ----------------------------------------------------------------------------
class AggregateArtifactsTest(unittest.TestCase):
    PATHS = [bf.ROOT / "data/public/model_comparison.json",
             cmp.OUT / "model_comparison.json"]
    def load_present(self):
        found = []
        for p in self.PATHS:
            if p.exists():
                try:
                    found.append((p, json.loads(p.read_text())))
                except (ValueError, OSError):
                    continue
        return found
    def test_aggregate_shape_when_present(self):
        found = self.load_present()
        if not found:
            self.skipTest("model comparison benchmark not built yet; main owns the rerun")
        for path, doc in found:
            with self.subTest(path=str(path)):
                self.assertIn("series", doc)
                self.assertIn("limitations", doc)
                self.assertTrue(doc["limitations"])
                self.assertTrue(all(isinstance(lim, str) for lim in doc["limitations"]))
                summary = doc.get("summary", {})
                for key in ("series", "passed", "commonTestRows"):
                    self.assertIn(key, summary)
                for s in doc["series"]:
                    self.assertIn("id", s)
                    self.assertIn("selection", s)
                    self.assertIn("common", s)
                    self.assertIn("models", s)
                    self.assertIn("selectionN", s["common"])
                    self.assertIn("testN", s["common"])
                    self.assertIn("candidates", s["common"])
                    for m in s["models"]:
                        self.assertIn("candidate", m)
                        self.assertIn("failures", m)
                        self.assertIsInstance(m["failures"], dict)
    def test_out_and_public_copies_agree(self):
        out_p = cmp.OUT / "model_comparison.json"
        pub_p = bf.ROOT / "data/public/model_comparison.json"
        if not (out_p.exists() and pub_p.exists()):
            self.skipTest("benchmark copies not both present")
        out = json.loads(out_p.read_text())
        pub = json.loads(pub_p.read_text())
        self.assertEqual(out["summary"], pub["summary"])
        self.assertEqual(len(out["series"]), len(pub["series"]))
        for a, b in zip(out["series"], pub["series"]):
            with self.subTest(series=a["id"]):
                self.assertEqual(a["id"], b["id"])
                self.assertEqual(a["selection"], b["selection"])
                self.assertEqual(a["common"], b["common"])
                self.assertEqual(a["selectedAllEvaluation"], b["selectedAllEvaluation"])
                for ma, mb in zip(a["models"], b["models"]):
                    self.assertEqual(ma["candidate"], mb["candidate"])
                    self.assertEqual(ma["evaluation"], mb["evaluation"])
                    self.assertEqual(ma["failures"], mb["failures"])
    def test_paired_scores_match_common_origins(self):
        found = self.load_present()
        if not found:
            self.skipTest("model comparison benchmark not built yet; main owns the rerun")
        _path, doc = found[0]
        for s in doc["series"]:
            with self.subTest(series=s["id"]):
                chosen = s["selection"]["candidate"]
                models = {m["candidate"]: m for m in s["models"]}
                self.assertIn(chosen, models)
                self.assertEqual(models[chosen]["evaluation"]["n"], s["common"]["testN"])
                self.assertEqual(s["selection"]["n"], s["common"]["selectionN"])
                self.assertEqual(s["selectedAllEvaluation"]["n"], models[chosen]["allTestN"])
                self.assertGreaterEqual(models[chosen]["allTestN"], s["common"]["testN"])
        self.assertEqual(doc["summary"]["commonTestRows"],
                         sum(s["common"]["testN"] for s in doc["series"]))
    def test_pinned_2026_10_24_rerun_outcomes(self):
        found = self.load_present()
        if not found:
            self.skipTest("model comparison benchmark not built yet; main owns the rerun")
        _path, doc = found[0]
        self.assertEqual(doc["summary"],
                         {"series": 35, "selectionChanged": 2, "passed": 0, "commonTestRows": 332})
        by_id = {s["id"]: s for s in doc["series"]}
        self.assertEqual(by_id["US_B07STGGQ18"]["selection"]["candidate"], "arima")
        self.assertEqual(by_id["US_B07MFZY2F2"]["selection"]["candidate"], "sarima")
        self.assertEqual(sum(s["common"]["testN"] for s in doc["series"]), 332)
        self.assertEqual(sum(s["selectedAllEvaluation"]["n"] for s in doc["series"]), 394)
if __name__ == "__main__":
    unittest.main()
