"""Validate expanded evidence, especially shipping and benchmark/retail identity boundaries."""
import csv,hashlib,json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from analyze_domestic_market import audit_quote,parse_offers,Tree
from collect_domestic_quotes import parse_pc
class ExpandedEvidenceTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.d=json.loads((ROOT/'dashboard/dist/data/domestic.json').read_text());cls.all=cls.d['products']+cls.d['marketReferences']
 def test_all_quotes_reparse_and_expanded_candidates_are_actually_broadly_listed(self):
  self.assertEqual(len(self.all),21);self.assertEqual(len({p['id'] for p in self.all}),21)
  for p in self.all:
   raw=(ROOT/p['quoteRawFile']).read_bytes();q=parse_pc(raw.decode(),p['id']);a=audit_quote(raw.decode(),q)
   self.assertEqual(hashlib.sha256(raw).hexdigest(),p['quote']['sourceSha256'])
   self.assertEqual(p['marketAudit'],a)
   self.assertTrue(a['firstOfferReconciled'])
   for k in ['productPrice','shipping','deliveredPrice','displayedSellerCount']:self.assertEqual(q[k],p['quote'][k])
   if p['cohort']=='reference':
    self.assertGreaterEqual(q['displayedSellerCount'],10);self.assertGreaterEqual(a['distinctDisplayedStoresWithShipping'],3)
    self.assertNotIn('history',p);self.assertNotIn('mobileCheck',p['quote'])
 def test_delivery_tooltip_cash_and_missing_delivery_do_not_create_free_shipping(self):
  def li(s,v,delivery,extra=''):return f'<li class="list-item"><div class="box__logo">{s}</div><p class="text__num">{v}</p><div class="box__delivery">{delivery}</div>{extra}</li>'
  source='<ul class="list__mall-price">'+li('A',100,'3,000원<span>무료배송 조건 안내</span>')+li('A',90,'무료배송')+li('B',50,'문의')+li('C',40,'무료배송','<span class="badge__cash">현금</span>')+li('D',200,'무료배송')+'</ul>'
  offers=parse_offers(source);self.assertEqual(offers[0]['shipping'],3000);self.assertIsNone(offers[2]['shipping']);self.assertTrue(offers[3]['cashOnly'])
  a=audit_quote(source,{'productPrice':100,'deliveredPrice':3100});self.assertEqual(a['distinctDisplayedStoresWithShipping'],2);self.assertIsNone(a['top3DeliveredMedian'])
 def test_median_quote_uses_store_totals_rather_than_summary_product_sort(self):
  p=next(p for p in self.all if p['id']=='29666111');a=p['marketAudit']
  self.assertEqual(p['quote']['deliveredPrice'],401460);self.assertEqual(a['top3DeliveredMedian'],398970)
  self.assertLess(a['top3DeliveredMedian'],p['quote']['deliveredPrice']);self.assertEqual(a['top3DeliveredHigh'],401460)
 def test_cpu_scores_and_samples_match_saved_live_primary_dom(self):
  base=ROOT/'data/verification/2026-10-23/expanded/cpu_raw'
  pairs=[('passmark_14400F_7500F_browser.html',[('5837','76555634'),('5648','21694499')]),('passmark_7500F_7600_browser.html',[('5172','18718496')]),('passmark_7500F_9600X_browser.html',[('6199','62794079')])]
  for filename,ids in pairs:
   parser=Tree();parser.feed((base/filename).read_text());nodes=list(parser.root.walk())
   self.assertIn('As of 23rd of October 2026',parser.root.text())
   sample=next(n for n in nodes if n.tag=='tr' and n.text().startswith('# of Samples'))
   vals=[n.text() for n in sample.children if getattr(n,'tag',None)=='td']
   for source_id,retail_id in ids:
    p=next(p for p in self.all if p['id']==retail_id)
    for prefix,key in [('tr-rating-','cpuMulti'),('tr-threadRating-','cpuSingle')]:
     row=next(n for n in nodes if n.attrs.get('id')==prefix+source_id)
     self.assertIn(f"{p['performance'][key]['value']:,}",row.text());self.assertIn(str(p['performance'][key]['samples']),vals)
 def test_gpu_primary_chart_identity_and_count_not_oc_board_or_fps_substitution(self):
  b=self.d['benchmarks']['gpu'];self.assertEqual(len(b['suite']['games']),24)
  self.assertIn('23 games',b['suite']['tlou_note']);self.assertIn('NOT absolute FPS',b['suite']['metric_types']['relative_index'])
  for row in b['files']['raw']:
   p=ROOT/'data/verification/2026-10-23/expanded/gpu_raw'/row['file'];self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(),row['sha256'])
  pulse=next(p for p in self.all if p['id']=='91909571');self.assertEqual(pulse['performance']['gamingSuite']['value'],100)
  self.assertEqual(next(p for p in self.all if p['id']=='20740013')['performance']['gamingSuite']['value'],69)
  for p in self.all:
   if p['category']=='GPU':self.assertEqual(p['performance']['gamingSuite']['games'],23)
 def test_downloads_contain_actual_21_quotes_and_deduplicated_benchmark_rows(self):
  folder=ROOT/'dashboard/dist/data/downloads'
  with (folder/'domestic_expanded.csv').open(encoding='utf-8-sig') as f:rows=list(csv.DictReader(f))
  self.assertEqual(len(rows),21);self.assertEqual(sum(r['cohort']=='original' for r in rows),8)
  with (folder/'domestic_benchmarks.csv').open(encoding='utf-8-sig') as f:rows=list(csv.DictReader(f))
  self.assertEqual(sum(r['kind']=='measured-aggregate' for r in rows),8)
  self.assertEqual(sum(r['kind']=='measured-suite' for r in rows),8)
  self.assertTrue(any(r['retail_quote_available']=='False' for r in rows))
if __name__=='__main__':unittest.main()
