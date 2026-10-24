"""Prevent calendar compression, lag-sign inversions and unsupported precision."""

from datetime import date, timedelta
import hashlib
import json
from pathlib import Path
import sys
import unittest

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from analyze_price_stock_correlations import (bootstrap_ci, circular_shift_pvalue,
    consecutive_returns, fdr_adjust, lag_pair, pearson, spearman)


class CorrelationRulesTest(unittest.TestCase):
    def test_missing_and_constant_are_not_zero_correlation(self):
        coefficient, n = pearson([1, np.nan, 3], [3, 2, 1])
        self.assertEqual(n, 2)
        self.assertTrue(np.isnan(coefficient))
        self.assertTrue(np.isnan(pearson([1, 1, 1], [1, 2, 3])[0]))
        self.assertAlmostEqual(pearson([1, 2, 3], [6, 4, 2])[0], -1)

    def test_positive_lag_means_stock_leads(self):
        stock = np.random.default_rng(19).normal(size=40)
        price = np.r_[np.nan, np.nan, stock[:-2]]
        r, n = pearson(*lag_pair(price, stock, 2))
        self.assertAlmostEqual(r, 1)
        self.assertEqual(n, 38)
        reverse, _ = pearson(*lag_pair(stock, price, -2))
        self.assertAlmostEqual(reverse, 1)

    def test_shift_occurs_before_pairwise_missing_drop(self):
        price = np.array([10., np.nan, 30., 40., 50.])
        stock = np.array([1., 2., 3., 4., 5.])
        a, b = lag_pair(price, stock, 1)
        self.assertEqual(pearson(a, b)[1], 3)
        np.testing.assert_array_equal(b, [1, 2, 3, 4])
        self.assertTrue(np.isnan(a[0]))

    def test_no_return_across_missing_week(self):
        values = consecutive_returns([100, np.nan, 121, 133.1, 133.1])
        self.assertTrue(np.isnan(values[:3]).all())
        self.assertAlmostEqual(values[3], np.log(1.1))
        self.assertEqual(values[4], 0)

    def test_spearman_uses_pairwise_ties(self):
        self.assertAlmostEqual(spearman(np.array([1, 1, 3, np.nan]), np.array([1, 2, 3, 9])), np.sqrt(3) / 2)

    def test_resampling_is_reproducible_and_shift_p_never_zero(self):
        x = np.arange(1., 21.)
        y = x * 2
        ci = bootstrap_ci(x, y, 4, 300, 19)
        self.assertEqual(ci, bootstrap_ci(x, y, 4, 300, 19))
        self.assertAlmostEqual(ci[0], 1)
        self.assertAlmostEqual(ci[1], 1)
        p, count = circular_shift_pvalue(x, y, 0)
        self.assertEqual(count, 19)
        self.assertEqual(p, .05)

    def test_fdr_restores_original_order_and_keeps_missing(self):
        result = fdr_adjust([.04, .01, .03, np.nan])
        np.testing.assert_allclose(result[:3], [.04, .03, .04])
        self.assertTrue(np.isnan(result[3]))
        self.assertTrue(np.all(fdr_adjust([.04, .01, .03], True) >= result[:3]))


class AnalysisReconciliationTest(unittest.TestCase):
    def setUp(self):
        self.output = ROOT / "data/analysis/2026-10-22"
        self.aligned = pd.read_csv(self.output / "aligned_weekly.csv", dtype={"product_id": str, "symbol": str})

    def test_aligned_pair_counts_and_first_boundary(self):
        self.assertEqual(len(self.aligned), 2 * 6 * 156)
        self.assertFalse(self.aligned.duplicated(["product_id", "symbol", "week_end"]).any())
        summary = pd.read_csv(self.output / "correlations.csv", dtype={"product_id": str, "symbol": str})
        for _, row in summary.iterrows():
            pair = self.aligned[(self.aligned.product_id == row.product_id) & (self.aligned.symbol == row.symbol)]
            self.assertEqual(len(pair), 156)
            self.assertEqual(int(pair.return_pair_available.sum()), int(row.n_return))
            self.assertEqual(int(pair.level_pair_available.sum()), int(row.n_level))
            self.assertTrue(np.isnan(pair.iloc[0].component_return_log))
            self.assertTrue(np.isnan(pair.iloc[0].stock_return_log))

    def test_every_lag_uses_actual_calendar_dates(self):
        results = pd.read_csv(self.output / "lag_correlations.csv", dtype={"product_id": str, "symbol": str})
        self.assertEqual(len(results), 204)
        for _, row in results.iterrows():
            pair = self.aligned[(self.aligned.product_id == row.product_id) & (self.aligned.symbol == row.symbol)]
            stock = dict(zip(pair.week_end, pair.stock_return_log))
            values = []
            for observation in pair.itertuples():
                target = (date.fromisoformat(observation.week_end) - timedelta(weeks=int(row.lag_weeks))).isoformat()
                a, b = observation.component_return_log, stock.get(target, np.nan)
                if np.isfinite(a) and np.isfinite(b):
                    values.append((a, b))
            self.assertEqual(len(values), int(row.n))
            x, y = np.array(values).T
            self.assertAlmostEqual(np.corrcoef(x, y)[0, 1], row.pearson, places=10)

    def test_analysis_input_hashes_match(self):
        metadata = json.loads((self.output / "analysis_metadata.json").read_text())
        for path, expected in metadata["input_sha256"].items():
            self.assertEqual(hashlib.sha256((ROOT / path).read_bytes()).hexdigest(), expected)

    def test_missing_last_session_also_invalidates_next_return(self):
        scenarios = pd.read_csv(self.output / "sensitivity.csv", dtype={"product_id": str, "symbol": str})
        scenario = "exclude_stock_last_session_mismatch_and_next_week"
        exclusions = {
            "005930": {"2022-03-04", "2022-03-11"},
            "000660": {"2022-03-04", "2022-03-11", "2022-03-18"},
        }
        selected = scenarios[scenarios.scenario == scenario]
        self.assertEqual(len(selected), 4)
        for row in selected.itertuples():
            pair = self.aligned[(self.aligned.product_id == row.product_id) &
                                (self.aligned.symbol == row.symbol)]
            keep = ~pair.week_end.isin(exclusions[row.symbol])
            valid = keep & pair.component_return_log.notna() & pair.stock_return_log.notna()
            self.assertEqual(int(valid.sum()), row.n)
            self.assertAlmostEqual(np.corrcoef(pair.loc[valid, "component_return_log"],
                                              pair.loc[valid, "stock_return_log"])[0, 1],
                                   row.pearson, places=10)


if __name__ == "__main__":
    unittest.main()
