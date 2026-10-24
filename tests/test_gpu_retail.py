"""Check source/model identity, sparse calendar handling and real quote counts."""
import hashlib
import json
from pathlib import Path
import sys
import unittest

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from prepare_gpu_retail_prices import extract_current, euro_range


class GpuRetailTest(unittest.TestCase):
    def setUp(self):
        self.path = ROOT / "data/processed/2026-10-22/gpu_retail"
        self.observations = pd.read_csv(self.path / "observations.csv", dtype={"series_id": str})
        self.weekly = pd.read_csv(self.path / "weekly_retail.csv", dtype={"series_id": str})

    def test_retailer_minimum_excludes_list_price_and_wrong_model(self):
        first = extract_current(ROOT / "data/verification/2026-10-22/gpu/3dcenter_2022-01-02.html")
        self.assertEqual(first["3070"][0], 999)
        self.assertEqual(first["3080"][0], 1499)
        last = extract_current(ROOT / "data/feasibility/2026-10-21/alternatives/raw/3dcenter_2022_09_11.html")
        self.assertEqual(last["3080"][0], 799)  # 12GB is 849, Ti is 999.
        self.assertEqual(last["3090"][0], 1099)  # 3090 Ti is 1249.
        self.assertIsNone(euro_range("nix"))
        self.assertIsNone(euro_range("$499"))

    def test_true_observations_are_not_filled_into_missing_weeks(self):
        self.assertEqual(len(self.observations), 141)
        self.assertEqual(len(self.weekly), 6 * 156)
        for identity, n, weeks, returns in (("3070", 33, 32, 1), ("3080", 29, 29, 0), ("3090", 33, 32, 1)):
            obs = self.observations[self.observations.series_id == identity]
            w = self.weekly[self.weekly.series_id == identity].sort_values("week_end")
            self.assertEqual(obs.value.notna().sum(), n)
            self.assertEqual(w.value.notna().sum(), weeks)
            self.assertEqual(w.weekly_return_log.notna().sum(), returns)
            self.assertTrue(w.loc[w.week_end.str.startswith("2020"), "value"].isna().all())
            self.assertTrue(w.loc[w.week_end > "2022-09-16", "value"].isna().all())
            expected = np.log(w.value / w.value.shift(1))
            np.testing.assert_allclose(w.weekly_return_log, expected, equal_nan=True, atol=1e-11)

    def test_same_week_observations_keep_last_valid_price(self):
        row = self.weekly[(self.weekly.series_id == "3070") & (self.weekly.week_end == "2021-01-22")].iloc[0]
        self.assertEqual(row.observation_date, "2021-01-22")
        self.assertEqual(row.value, 729)
        row = self.weekly[(self.weekly.series_id == "3080") & (self.weekly.week_end == "2021-01-22")].iloc[0]
        self.assertEqual(row.observation_status, "source_no_quote")
        self.assertTrue(np.isnan(row.value))

    def test_source_hashes_and_row_provenance(self):
        inputs = json.loads((self.path / "sources.json").read_text())["input_sha256"]
        for path, expected in inputs.items():
            self.assertEqual(hashlib.sha256((ROOT / path).read_bytes()).hexdigest(), expected)
        for row in self.observations.itertuples():
            self.assertEqual(row.source_sha256, inputs[row.source_file])


if __name__ == "__main__":
    unittest.main()
