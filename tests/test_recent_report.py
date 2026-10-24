"""Current-period clock/missing-data rules; no network, no price source needed."""
from datetime import date
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from build_recent_report import coverage, correlations, last_complete_friday, weeks_between


class RecentReportTest(unittest.TestCase):
    def test_current_friday_is_not_assumed_complete(self):
        self.assertEqual(last_complete_friday(date(2026,10,23)),date(2026,10,16))
        self.assertEqual(last_complete_friday(date(2026,10,25)),date(2026,10,23))

    def test_shared_calendar_includes_completed_week(self):
        w=weeks_between(date(2023,1,6),date(2026,10,23))
        self.assertEqual(len(w),199)
        self.assertEqual(w[0],'2023-01-06');self.assertEqual(w[-1],'2026-10-23')

    def test_missing_week_does_not_create_return(self):
        c=coverage([None,10,None,20,30,None],[None,'a',None,'b','c',None],list('123456'))
        self.assertEqual((c['observed'],c['beforeFirstObservation'],c['missingAfterFirst']),(3,1,2))
        self.assertEqual(c['returns'],1)
        self.assertEqual(c['periodChange'],2)
        self.assertEqual(c['lastQuoteDate'],'c')

    def test_empty_coverage_is_not_zero_change(self):
        c=coverage([None]*4,[None]*4,list('1234'))
        self.assertEqual(c['beforeFirstObservation'],4)
        self.assertIsNone(c['periodChange']);self.assertIsNone(c['lastWeek'])

    def test_recent_change_requires_both_calendar_endpoints(self):
        vals=[10]+[None]*12+[20]
        self.assertEqual(coverage(vals,[None]*14,list(range(14)))['recent13WeekChange'],1)
        vals[-1]=None
        self.assertIsNone(coverage(vals,[None]*14,list(range(14)))['recent13WeekChange'])

    def test_positive_lag_pairs_market_before_part(self):
        # Market returns a,b,c; part returns x,a,b,c one week later.
        markets=[dict(id='m',values=[1,2,6,3,3])]
        parts=[dict(id='p',values=[1,1.1,2.2,6.6,3.3])]
        r=correlations(parts,markets,[1])[0]
        self.assertEqual(r['n'],3);self.assertAlmostEqual(r['pearson'],1)

    def test_insufficient_pairs_remain_unscored(self):
        r=correlations([dict(id='p',values=[1,None,3])],
                       [dict(id='m',values=[1,2,3])],[0])[0]
        self.assertEqual(r['n'],0);self.assertIsNone(r['pearson'])
        self.assertEqual(r['status'],'insufficient_pairs')
        constant=correlations([dict(id='p',values=[1,1,1])],
                             [dict(id='m',values=[1,2,3])],[0])[0]
        self.assertEqual(constant['n'],2);self.assertIsNone(constant['pearson'])
        self.assertEqual(constant['status'],'zero_variance')

    def test_public_aggregate_contains_no_price_rows(self):
        p=ROOT/'data/public/recent_analysis.json'
        self.assertTrue(p.exists())
        d=json.loads(p.read_text())
        self.assertEqual(len(d['correlations']),len(d['parts'])*len(d['markets'])*17)
        def check(v):
            if isinstance(v,dict):
                self.assertFalse({'price','values','points','probabilities','backtests'}&set(v))
                for child in v.values():check(child)
            elif isinstance(v,list):
                for child in v:check(child)
        check(d)
        for s in d['parts']:
            self.assertEqual(s['sourceAgeDays'],(date.fromisoformat(d['asOf'])-date.fromisoformat(s['sourceLastQuoteDate'])).days)


if __name__=='__main__':unittest.main()
