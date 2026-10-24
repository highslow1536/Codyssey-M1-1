"""Research-only audit: recompute reported scores from saved candidate rows.

The public repository excludes these price-reconstructive candidate rows.
Run only after restoring the authorized research snapshot.
"""
from collections import defaultdict
import json
import unittest

from scripts import compare_forecast_models as cm


class ComparisonArtifactTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads((cm.ROOT/'data/public/model_comparison.json').read_text())
        rows = json.loads((cm.OUT/'candidate_predictions.json').read_text())
        cls.rows = defaultdict(lambda: defaultdict(list))
        for row in rows:
            cls.rows[row['id']][row['candidate']].append(row)

    def test_every_origin_respects_clock_and_has_valid_target(self):
        for series in self.data['series']:
            for rows in self.rows[series['id']].values():
                for r in rows:
                    self.assertLess(r['trainThrough'], r['fitCutoff'])
                    self.assertLessEqual(r['fitCutoff'], r['available'])
                    self.assertLessEqual(r['targetAvailable'], cm.bf.AS_OF.isoformat())
                    self.assertEqual(r['target'], cm.bf.target_date(cm.date.fromisoformat(r['origin']), series['frequency']).isoformat())
                    self.assertAlmostEqual(sum(r['probabilities']), 1.)

    def test_selection_recomputed_from_past_only(self):
        for series in self.data['series']:
            choice, _ = cm.select_model(self.rows[series['id']], series['incumbent'])
            self.assertEqual(choice, series['selection'])

    def test_all_common_metrics_recomputed_from_exact_same_origins(self):
        for series in self.data['series']:
            common, active = cm.common_rows(self.rows[series['id']], 'test')
            self.assertEqual(active, series['common']['candidates'])
            origin_sets = [set(r['origin'] for r in rows) for rows in common.values()]
            self.assertTrue(all(s == origin_sets[0] for s in origin_sets))
            for model in series['models']:
                if model['candidate'] == 'baseline':
                    continue
                rows = cm.calibrated(common.get(model['candidate'], []), model['temperature'])
                actual = cm.scores(rows, series['frequency'])
                with self.subTest(series=series['id'], model=model['candidate']):
                    self.assertEqual(actual, model['evaluation'])

    def test_selected_full_metrics_and_model_match_app(self):
        app = json.loads((cm.bf.WEB/'forecast.json').read_text())
        for series in self.data['series']:
            actual = next(s for s in app['series'] if s['id'] == series['id'])
            self.assertEqual(actual['selection'], series['selection'])
            self.assertEqual(actual['evaluation'], series['selectedAllEvaluation'])
            self.assertEqual(actual['gates'], series['gates'])


if __name__ == '__main__':
    unittest.main()
