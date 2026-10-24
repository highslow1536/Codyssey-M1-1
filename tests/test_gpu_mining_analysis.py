"""Guard against inflated time-series samples and misleading event comparisons."""
import hashlib
import json
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from analyze_gpu_mining import OUT, PROCESSED, align_snapshots, monthly_crypto


class GpuMiningAnalysisTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.daily = pd.read_csv(PROCESSED / "crypto/eth_daily.csv")
        cls.snap = pd.read_csv(OUT / "aligned_snapshots.csv", dtype={"series_id": str})
        cls.monthly = pd.read_csv(OUT / "aligned_monthly.csv", dtype={"gpu": str})
        cls.corr = pd.read_csv(OUT / "correlations.csv", dtype={"series_id": str})

    def test_alignment_excludes_quote_day_and_requires_all_seven_days(self):
        obs = pd.DataFrame([{"series_id": "x", "observation_date": "2022-09-14", "value": 100},
                            {"series_id": "x", "observation_date": "2022-09-16", "value": 99}])
        out = align_snapshots(obs, self.daily)
        first = out.iloc[0]
        self.assertEqual(first.crypto_window_start, "2022-09-07")
        self.assertEqual(first.crypto_window_end, "2022-09-13")
        expected = self.daily[self.daily.date.between("2022-09-07", "2022-09-13")].price_usd.mean()
        self.assertAlmostEqual(first.eth_price_7d, expected)
        self.assertTrue(np.isnan(out.iloc[1].fees_included_proxy_7d))
        self.assertEqual(out.iloc[1].fees_included_proxy_n_days, 6)
        self.assertFalse(np.isnan(out.iloc[1].eth_price_7d))

    def test_actual_intervals_are_not_weekly_returns(self):
        expected_counts = {"3070": (33, 32), "3080": (29, 28), "3090": (33, 32)}
        for identity, (levels, changes) in expected_counts.items():
            group = self.snap[(self.snap.series_id == identity) & self.snap.value.notna()].sort_values("observation_date")
            self.assertEqual(len(group), levels)
            self.assertEqual(group.gpu_interval_logchange.notna().sum(), changes)
            expected_days = pd.to_datetime(group.observation_date).diff().dt.days
            np.testing.assert_allclose(group.interval_days, expected_days, equal_nan=True)
            self.assertGreater(group.interval_days.median(), 7)
        weekly = pd.read_csv(OUT / "aligned_weekly.csv", dtype={"series_id": str})
        self.assertEqual(len(weekly), 936)
        for identity, count in {"3070": 1, "3080": 0, "3090": 1}.items():
            self.assertEqual(weekly[weekly.series_id == identity].weekly_return_log.notna().sum(), count)

    def test_monthly_grid_and_merge_month(self):
        self.assertEqual(len(self.monthly), 108)
        for _, group in self.monthly.groupby("gpu"):
            self.assertEqual(len(group), 36)
            self.assertEqual(group.price_usd.notna().sum(), 16)
            self.assertEqual(group.gpu_return_log.notna().sum(), 15)
            self.assertTrue(group[group.month.str.startswith("2020")].price_usd.isna().all())
            september = group[group.month == "2022-09"].iloc[0]
            self.assertTrue(np.isfinite(september.gpu_return_log))
            self.assertTrue(np.isfinite(september.eth_price_mean))
            self.assertTrue(np.isnan(september.fees_included_proxy_mean))
            self.assertEqual(september.fees_included_proxy_n_days, 14)
        crypto = monthly_crypto(self.daily)
        self.assertEqual(crypto.eth_price_mean.notna().sum(), 36)
        self.assertEqual(crypto.fees_included_proxy_mean.notna().sum(), 32)

    def test_correlation_pair_counts(self):
        for identity in ("3070", "3080", "3090"):
            subset = self.corr[(self.corr.series_id == identity) & (self.corr.dataset == "ebay_monthly")]
            for metric, nlevel, nchange in (("eth_price", 16, 15), ("fees_included_proxy", 12, 11),
                                           ("fees_excluded_proxy", 12, 11)):
                self.assertEqual(subset[(subset.crypto_metric == metric) & (subset.method == "monthly_levels")].iloc[0].n, nlevel)
                self.assertEqual(subset[(subset.crypto_metric == metric) & (subset.method == "adjacent_month_logchange")].iloc[0].n, nchange)

    def test_event_comparison_is_two_real_months_each_side(self):
        changes = pd.read_csv(OUT / "price_changes.csv", dtype={"series_id": str})
        for identity, group in self.monthly.groupby("gpu"):
            row = changes[(changes.series_id == identity) & (changes.comparison == "premerge_Jul_Aug_vs_postmerge_Oct_Nov")].iloc[0]
            before = group[group.month.isin(["2022-07", "2022-08"])].price_usd.mean()
            after = group[group.month.isin(["2022-10", "2022-11"])].price_usd.mean()
            self.assertEqual((row.n_before, row.n_after), (2, 2))
            self.assertAlmostEqual(row.before_value, before)
            self.assertAlmostEqual(row.after_value, after)
            self.assertAlmostEqual(row.change_fraction, after / before - 1)
            self.assertFalse(row.causal_effect)

    def test_all_analysis_input_hashes_match(self):
        metadata = json.loads((OUT / "analysis_metadata.json").read_text())
        for relative, digest in metadata["input_sha256"].items():
            self.assertEqual(hashlib.sha256((ROOT / relative).read_bytes()).hexdigest(), digest, relative)


if __name__ == "__main__":
    unittest.main()
