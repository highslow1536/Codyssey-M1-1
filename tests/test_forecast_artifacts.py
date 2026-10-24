"""Published probabilistic results must match the auditable inputs and scores."""
import csv
import hashlib
import json
from pathlib import Path
import unittest
import numpy as np
from scripts import build_forecast as f


class ForecastArtifacts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=json.loads((f.WEB/'forecast.json').read_text())

    def test_sources_match_actual_bytes(self):
        for name,expected in self.data['inputHashes'].items():
            with self.subTest(name=name):
                self.assertEqual(hashlib.sha256((f.ROOT/name).read_bytes()).hexdigest(),expected)

    def test_no_unknown_future_or_invalid_probabilities_in_published_backtests(self):
        total=0
        for s in self.data['series']:
            for r in s['backtests']:
                total+=1
                self.assertLess(r['trainThrough'],r['fitCutoff'])
                self.assertLessEqual(r['targetAvailable'],f.AS_OF.isoformat())
                self.assertEqual(f.label(r['actualChange']),r['actualClass'])
                self.assertAlmostEqual(sum(r['probabilities']),1)
                self.assertAlmostEqual(sum(r['baseline']),1)
                self.assertTrue(all(0<=p<=1 for p in r['probabilities']))
                self.assertEqual(r['target'],f.target_date(f.date.fromisoformat(r['origin']),s['frequency']).isoformat())
            self.assertEqual(s['evaluation']['n'],len(s['backtests']))
        self.assertEqual(total,self.data['totals']['backtests'])

    def test_published_scores_are_recomputed_from_saved_probability_rows(self):
        for s in self.data['series']:
            rows=s['backtests'];e=s['evaluation']
            if not rows:continue
            self.assertAlmostEqual(e['brier'],np.mean([f.brier(r['probabilities'],r['actualClass']) for r in rows]))
            self.assertAlmostEqual(e['baselineBrier'],np.mean([f.brier(r['baseline'],r['actualClass']) for r in rows]))
            self.assertEqual(e['nonoverlapN'],f.nonoverlap_count(rows))
            self.assertEqual(e['originsN'],len(set(r['origin'] for r in rows)))

    def test_archive_conflict_partial_month_and_floor_remain_excluded_with_reasons(self):
        with (f.OUT/'excluded_observations.csv').open(encoding='utf-8-sig') as fp:
            rows=list(csv.DictReader(fp))
        reasons=[r['reason'] for r in rows]
        self.assertEqual(reasons.count('partial_month'),21)
        self.assertEqual(reasons.count('archive_price_basis_conflict_quarantined'),1)
        self.assertEqual(reasons.count('archived_quote_different_price_basis_not_training'),25)
        self.assertIn('absolute_floor',reasons)
        self.assertEqual(self.data['totals']['archiveQuotes'],25)
        self.assertEqual(self.data['totals']['quarantinedArchives'],1)

    def test_selection_data_never_uses_final_period_targets(self):
        with (f.OUT/'forecast_selection_predictions.csv').open(encoding='utf-8-sig') as fp:
            rows=list(csv.DictReader(fp))
        self.assertGreater(len(rows),0)
        for r in rows:
            self.assertLess(r['origin'],'2025-01-01')
            self.assertLess(r['trainThrough'],r['fitCutoff'])
            if r['selectionEligible']=='True':
                self.assertLessEqual(r['targetAvailable'],'2024-12-31')

    def test_downloads_are_exact_copies(self):
        for name in ['forecast_predictions.csv','forecast_weekly.csv','forecast_metrics.csv',
                     'forecast_domestic_archives.csv','excluded_observations.csv','forecast_selection_predictions.csv','forecast.json']:
            self.assertEqual((f.OUT/name).read_bytes(),(f.WEB/'downloads'/name).read_bytes())
        self.assertEqual((f.WEB/'forecast.json').read_bytes(),(f.OUT/'forecast.json').read_bytes())


if __name__=='__main__':unittest.main()
