"""Requirements-based tests for scripts/analyze_recent_timing.py."""

"""Main contract: analyze_history(weekly, monthly, horizon_weeks=4) and
forecast_at(monthly_points, origin_index, horizon_months=1).
Monthly buckets are a single 2026-10-23 snapshot, so backtests are
retrospective, not as-of price reproduction. No month filling,
partial:true excluded, no price-definition change, no current-quote append.
Standard library only. Existing tests untouched.
"""
import copy
import datetime
import hashlib
import inspect
import json
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import analyze_recent_timing as mod


class LongHorizonTrendTest(unittest.TestCase):
    def test_complete_month_trend_excludes_partial_and_needs_exact_calendar_month(self):
        monthly = [{'date': '2026-01', 'price': 100}, {'date': '2026-04', 'price': 120},
                   {'date': '2026-07', 'price': 150}, {'date': '2026-08', 'price': 160},
                   {'date': '2026-09', 'price': 170}, {'date': '2026-10', 'price': 999, 'partial': True}]
        a = mod.analyze_history([], monthly, 12)
        self.assertEqual(a['longTrend']['asOf'], '2026-09')
        self.assertIsNone(a['longTrend']['threeMonth'])
        self.assertIsNone(a['longTrend']['sixMonth'])
        monthly.insert(2, {'date': '2026-06', 'price': 125})
        self.assertAlmostEqual(mod.analyze_history([], monthly, 12)['longTrend']['threeMonth'], .36)

TIMING = ROOT / "data/verification/2026-10-23/timing"
HISTORY_FILE = TIMING / "ram_ssd_history.json"
RAWDIR = TIMING / "ram_ssd_raw"
EXPECTED_IDS = ["11790199", "18911780", "18297002", "17001050",
                "14907467", "20369126", "17788487", "29666111"]


def load_history():
    with HISTORY_FILE.open(encoding="utf-8") as fh:
        return json.load(fh)


def make_weekly(n=12, start="2026-08-04", step=100, base=300000):
    d0 = datetime.date.fromisoformat(start)
    out = []
    for i in range(n):
        out.append({"date": (d0 + datetime.timedelta(days=7 * i)).isoformat(),
                    "price": base + step * i})
    return out


def make_monthly(dates, prices, partials=None):
    rows = []
    for i, pair in enumerate(zip(dates, prices)):
        flag = bool(partials[i]) if partials and i < len(partials) else False
        rows.append({"date": pair[0], "price": pair[1], "partial": flag})
    return rows


class RealSourceAvailabilityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.history = load_history()
        cls.by_id = {p["id"]: p for p in cls.history["products"]}

    def test_all_eight_skus_present(self):
        self.assertEqual(sorted(self.by_id), sorted(EXPECTED_IDS))
        for pid in EXPECTED_IDS:
            p = self.by_id[pid]
            self.assertIn(p["category"], ("RAM", "SSD"))
            self.assertEqual(p["sourceUrl"],
                             "https://prod.danawa.com/info/?pcode=" + pid)

    def test_sha256_matches_preserved_raw(self):
        for pid in EXPECTED_IDS:
            digest = hashlib.sha256(
                (RAWDIR / (pid + ".json")).read_bytes()).hexdigest()
            self.assertEqual(self.by_id[pid]["sha256"], digest, pid)

    def test_weekly_tuesday_shape_and_no_current_append(self):
        for pid in EXPECTED_IDS:
            weekly = self.by_id[pid]["weekly"]
            self.assertEqual(len(weekly), 12, pid)
            dates = [row["date"] for row in weekly]
            self.assertEqual(dates[0], "2026-08-04", pid)
            self.assertEqual(dates[-1], "2026-10-20", pid)
            for d in dates:
                self.assertEqual(datetime.date.fromisoformat(d).weekday(),
                                 1, (pid, d))

    def test_monthly_partial_and_retrospective_snapshot(self):
        for pid in EXPECTED_IDS:
            monthly = self.by_id[pid]["monthly"]
            self.assertEqual(len(monthly),
                             19 if pid == "14907467" else 23, pid)
            self.assertEqual(monthly[-1]["date"], "2026-10", pid)
            self.assertTrue(monthly[-1]["partial"], pid)
            self.assertTrue(all(row["partial"] is False
                                for row in monthly[:-1]), pid)

    def test_source_periods_match_raw_counts(self):
        for pid in EXPECTED_IDS:
            raw = json.loads(
                (RAWDIR / (pid + ".json")).read_text(encoding="utf-8"))
            sp = self.by_id[pid]["sourcePeriods"]
            for key in ("1m", "3m", "6m", "12m", "24m"):
                self.assertEqual(sp[key]["rows"],
                                 len(raw[key[:-1]]["result"]), (pid, key))


class ContractPresenceTest(unittest.TestCase):
    def test_signatures_and_defaults(self):
        sig_a = inspect.signature(mod.analyze_history)
        self.assertIn("weekly", sig_a.parameters)
        self.assertIn("monthly", sig_a.parameters)
        self.assertIn("horizon_weeks", sig_a.parameters)
        self.assertEqual(sig_a.parameters["horizon_weeks"].default, 4)
        sig_f = inspect.signature(mod.forecast_at)
        self.assertIn("monthly_points", sig_f.parameters)
        self.assertIn("origin_index", sig_f.parameters)
        self.assertIn("horizon_months", sig_f.parameters)
        self.assertEqual(sig_f.parameters["horizon_months"].default, 1)

    def test_horizons_only_4_8_12(self):
        weekly = make_weekly(12)
        monthly = make_monthly(["2026-05", "2026-06", "2026-07",
                                "2026-08", "2026-09", "2026-10"],
                               [100, 101, 102, 103, 104, 105])
        for h in (4, 8, 12):
            res = mod.analyze_history(weekly, monthly, horizon_weeks=h)
            self.assertEqual(res["horizonWeeks"], h)
        with self.assertRaises(ValueError):
            mod.analyze_history(weekly, monthly, horizon_weeks=3)
        with self.assertRaises(ValueError):
            mod.analyze_history(weekly, monthly, horizon_weeks=5)

    def test_validation_keys_all_present(self):
        weekly = make_weekly(12)
        monthly = make_monthly(["2026-01", "2026-02", "2026-03",
                                "2026-04", "2026-05", "2026-06"],
                               [100, 101, 102, 103, 104, 105])
        res = mod.analyze_history(weekly, monthly, horizon_weeks=4)
        for key in ("trend", "historyComparisons", "validation"):
            self.assertIn(key, res, key)
        for key in ("oneWeek", "fourWeek", "twelveWeek", "upWeeks",
                    "downWeeks", "flatWeeks", "intervals"):
            self.assertIn(key, res["trend"], key)
        for key in ("n", "independentN", "up", "down", "flat"):
            self.assertIn(key, res["historyComparisons"], key)
        for key in ("n", "mae", "naiveMae", "skill",
                    "independentN", "probabilityAvailable"):
            self.assertIn(key, res["validation"], key)
        self.assertIs(res["validation"]["probabilityAvailable"], False)


class ForecastPrefixOnlyTest(unittest.TestCase):
    def test_median_three_returns_times_horizon(self):
        g = 1.1
        prices = [100 * (g ** i) for i in range(6)]
        pts = make_monthly(["2026-05", "2026-06", "2026-07",
                            "2026-08", "2026-09", "2026-10"], prices)
        self.assertAlmostEqual(mod.forecast_at(pts, 3, horizon_months=1),
                               math.log(g), places=7)
        self.assertAlmostEqual(mod.forecast_at(pts, 3, horizon_months=2),
                               2 * math.log(g), places=7)

    def test_none_cases(self):
        pts = make_monthly(["2026-07", "2026-08", "2026-09", "2026-10"],
                           [200, 202, 205, 210])
        self.assertIsNone(mod.forecast_at(pts, 2, horizon_months=1))
        self.assertIsNone(mod.forecast_at(pts, 3, horizon_months=0))
        partial = make_monthly(["2026-07", "2026-08", "2026-09",
                                "2026-10"], [200, 202, 205, 210],
                               partials=[False, True, False, False])
        self.assertIsNone(mod.forecast_at(partial, 3, horizon_months=1))
        gapped = make_monthly(["2026-07", "2026-08", "2026-10",
                               "2026-11"], [200, 202, 205, 210])
        self.assertIsNone(mod.forecast_at(gapped, 3, horizon_months=1))

    def test_future_mutation_does_not_change_past_forecast(self):
        pts = make_monthly(["2026-05", "2026-06", "2026-07",
                            "2026-08", "2026-09", "2026-10"],
                           [100, 102, 101, 103, 105, 107])
        r1 = mod.forecast_at(pts, 3, horizon_months=1)
        pts[4]["price"] = 99999
        pts[5]["price"] = 1
        self.assertEqual(mod.forecast_at(pts, 3, horizon_months=1), r1)

    def test_target_only_mutation_does_not_change_prediction(self):
        pts = make_monthly(["2026-04", "2026-05", "2026-06",
                            "2026-07", "2026-08", "2026-09"],
                           [100, 102, 101, 103, 105, 107])
        r1 = mod.forecast_at(pts, 3, horizon_months=1)
        pts[4]["price"] = 7
        self.assertEqual(mod.forecast_at(pts, 3, horizon_months=1), r1)

    def test_inputs_not_mutated(self):
        weekly = make_weekly(12)
        monthly = make_monthly(["2026-06", "2026-07", "2026-08",
                                "2026-09"], [50, 51, 52, 53])
        w0 = copy.deepcopy(weekly)
        m0 = copy.deepcopy(monthly)
        mod.analyze_history(weekly, monthly, horizon_weeks=4)
        mod.forecast_at(monthly, 1, horizon_months=1)
        self.assertEqual(weekly, w0)
        self.assertEqual(monthly, m0)


class MissingMonthNoSkipTest(unittest.TestCase):
    def test_gap_pair_not_counted_as_adjacent(self):
        full_weekly = make_weekly(12)
        gapped_weekly = [w for i, w in enumerate(full_weekly) if i != 5]
        steady = make_monthly(["2026-01", "2026-02", "2026-03",
                               "2026-04", "2026-05", "2026-06"],
                              [100, 101, 102, 103, 104, 105])
        rg_w = mod.analyze_history(gapped_weekly, steady, horizon_weeks=4)
        rf_w = mod.analyze_history(full_weekly, steady, horizon_weeks=4)
        self.assertLess(rg_w["historyComparisons"]["n"],
                        rf_w["historyComparisons"]["n"])
        hc = rg_w["historyComparisons"]
        self.assertEqual(hc["n"], hc["up"] + hc["down"] + hc["flat"])
        full = make_monthly(["2026-01", "2026-02", "2026-03",
                             "2026-04", "2026-05", "2026-06"],
                            [100, 101, 102, 103, 104, 105])
        gapped = make_monthly(["2026-01", "2026-02", "2026-04",
                               "2026-05", "2026-06", "2026-07"],
                              [100, 101, 103, 104, 105, 106])
        rg = mod.analyze_history(full_weekly, gapped, horizon_weeks=4)
        rf = mod.analyze_history(full_weekly, full, horizon_weeks=4)
        self.assertGreater(rf["validation"]["n"], 0)
        self.assertLess(rg["validation"]["n"], rf["validation"]["n"])

    def test_gap_forecast_does_not_peek_at_neighbor(self):
        gapped = make_monthly(["2026-01", "2026-02", "2026-03",
                               "2026-04", "2026-06", "2026-07"],
                              [100, 101, 102, 103, 105, 106])
        r1 = mod.forecast_at(gapped, 3, horizon_months=1)
        gapped[4]["price"] = 99999
        gapped[5]["price"] = 1
        self.assertEqual(mod.forecast_at(gapped, 3, horizon_months=1), r1)


class PartialMonthTargetBanTest(unittest.TestCase):
    def test_partial_never_a_backtest_target(self):
        weekly = make_weekly(12)
        flagged = make_monthly(
            ["2026-05", "2026-06", "2026-07", "2026-08", "2026-09",
             "2026-10"], [100, 101, 102, 103, 104, 105],
            partials=[False, False, False, False, False, True])
        dropped = make_monthly(["2026-05", "2026-06", "2026-07",
                                "2026-08", "2026-09"],
                               [100, 101, 102, 103, 104])
        r_flag = mod.analyze_history(weekly, flagged, horizon_weeks=4)
        r_drop = mod.analyze_history(weekly, dropped, horizon_weeks=4)
        targets = [b["target"]
                   for b in r_flag["validation"]["backtests"]]
        self.assertNotIn("2026-10", targets)
        self.assertEqual(r_flag["validation"]["n"],
                         r_drop["validation"]["n"])
        self.assertEqual(r_flag["historyComparisons"]["n"],
                         r_drop["historyComparisons"]["n"])

    def test_partial_target_price_change_does_not_leak(self):
        pts = make_monthly(["2026-05", "2026-06", "2026-07",
                            "2026-08", "2026-09"],
                           [100, 101, 102, 103, 104],
                           partials=[False, False, False, False, True])
        r1 = mod.forecast_at(pts, 3, horizon_months=1)
        pts[4]["price"] = 99999
        self.assertEqual(mod.forecast_at(pts, 3, horizon_months=1), r1)


class DuplicateDateTest(unittest.TestCase):
    def test_analyze_rejects_duplicate_or_unsorted(self):
        weekly = make_weekly(12)
        weekly[5]["date"] = weekly[4]["date"]
        monthly = make_monthly(["2026-07", "2026-08", "2026-09"],
                               [1, 2, 3])
        with self.assertRaises(ValueError):
            mod.analyze_history(weekly, monthly, horizon_weeks=4)
        monthly2 = make_monthly(["2026-07", "2026-07", "2026-09"],
                                [1, 2, 3])
        with self.assertRaises(ValueError):
            mod.analyze_history(make_weekly(12), monthly2, horizon_weeks=4)
        nodup = make_monthly(["2026-09", "2026-07", "2026-08"],
                             [1, 2, 3])
        with self.assertRaises(ValueError):
            mod.analyze_history(make_weekly(12), nodup, horizon_weeks=4)

    def test_forecast_neutralizes_duplicate_prefix(self):
        pts = make_monthly(["2026-07", "2026-08", "2026-08", "2026-09"],
                           [200, 202, 203, 205])
        self.assertIsNone(mod.forecast_at(pts, 3, horizon_months=1))


class TwelveWeeklyProbabilityBanTest(unittest.TestCase):
    def test_probability_not_available_with_twelve_weekly(self):
        res = mod.analyze_history(
            make_weekly(12),
            make_monthly(["2026-05", "2026-06", "2026-07", "2026-08"],
                         [1, 2, 3, 4]), horizon_weeks=4)
        v = res["validation"]
        self.assertIs(v["probabilityAvailable"], False)
        for banned in ("probability", "p_up", "hitRate", "confidence"):
            if banned in v:
                self.assertIsNone(v[banned], banned)

    def test_trend_counts_and_skill_consistent(self):
        weekly = make_weekly(12, step=100)
        monthly = make_monthly(["2026-01", "2026-02", "2026-03",
                                "2026-04", "2026-05", "2026-06"],
                               [100, 101, 102, 103, 104, 105])
        res = mod.analyze_history(weekly, monthly, horizon_weeks=4)
        t = res["trend"]
        self.assertEqual(t["intervals"], 4)
        self.assertEqual(t["upWeeks"] + t["downWeeks"] + t["flatWeeks"],
                         t["intervals"])
        self.assertEqual(t["upWeeks"], t["intervals"])
        self.assertEqual(t["downWeeks"], 0)
        hc = res["historyComparisons"]
        self.assertEqual(hc["n"], hc["up"] + hc["down"] + hc["flat"])
        self.assertLessEqual(hc["independentN"], hc["n"])
        v = res["validation"]
        self.assertEqual(v["n"], 2)
        if v["mae"] is not None and v["naiveMae"] not in (None, 0):
            self.assertAlmostEqual(v["skill"],
                                   1 - v["mae"] / v["naiveMae"], places=9)


class MissingValuePreservedTest(unittest.TestCase):
    def test_none_and_zero_skipped_not_filled(self):
        weekly = make_weekly(12)
        monthly = make_monthly(["2026-05", "2026-06", "2026-07",
                                "2026-08"], [100, None, 102, 103])
        res = mod.analyze_history(weekly, monthly, horizon_weeks=4)
        self.assertLessEqual(res["validation"]["n"], 1)
        monthly0 = make_monthly(["2026-05", "2026-06", "2026-07",
                                 "2026-08"], [100, 0, 102, 103])
        res0 = mod.analyze_history(weekly, monthly0, horizon_weeks=4)
        self.assertLessEqual(res0["validation"]["n"], 1)


if __name__ == "__main__":
    unittest.main()
