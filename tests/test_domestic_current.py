"""Verify current-price shipping semantics and website data against saved evidence."""
import csv,hashlib,json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from collect_domestic_quotes import parse_pc,parse_mobile_series
from export_domestic_dashboard import build
RAW=ROOT/'data/verification/2026-10-23/domestic'
class DomesticCurrentTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.data=json.loads((ROOT/'dashboard/dist/data/domestic.json').read_text())
 def test_current_quotes_against_original_fields(self):
  observed=[]  # Public edition: compare the original expectation by SHA-256.
  for p in self.data['products']:
   raw=(RAW/'raw'/f"{p['id']}.html").read_bytes();q=parse_pc(raw.decode(),p['id'])
   observed.append(tuple(q[k] for k in ['productPrice','shipping','deliveredPrice']))
   self.assertEqual(p['quote']['sourceSha256'],hashlib.sha256(raw).hexdigest())
   self.assertEqual(q['deliveredPrice'],q['productPrice']+q['shipping'])
  self.assertEqual(hashlib.sha256(json.dumps(observed,separators=(',',':')).encode()).hexdigest(),'b85dab586270670a36b244814d2a033cac8756637cc0a3fcd75832e530d5fc5e')
 def test_hidden_footer_price_is_not_charged(self):
  s=(RAW/'raw/21694499.html').read_text();q=parse_pc(s,'21694499')
  self.assertIn('topFixDeliveryIncludeFee',s);self.assertEqual(q['deliveredPrice'],169220);self.assertNotEqual(q['deliveredPrice'],166320)
 def test_mobile_exact_product_cell_not_main_csr(self):
  for p in self.data['products']:
   raw=(RAW/'raw'/f"{p['id']}_mobile.html").read_bytes();value=parse_mobile_series(raw.decode('cp949',errors='replace'),p['id'])
   self.assertEqual(value,p['quote']['productPrice']);self.assertTrue(p['quote']['mobileCheck']['match']);self.assertIn('main_CSR_quote_not_observed',p['quote']['mobileCheck']['basis'])
 def test_active_peer_and_inactive_exclusion(self):
  p=self.data['marketReferences'][0];q=parse_pc((RAW/'raw/106710902_peer.html').read_text(),'106710902')
  self.assertEqual(q['deliveredPrice'],2022670);self.assertEqual(p['quote']['deliveredPrice'],q['deliveredPrice']);self.assertIsNone(self.data['excluded'][0]['productPrice'])
 def test_direct_gpu_pair_backed_by_performance_evidence(self):
  d=json.loads((ROOT/'data/verification/2026-10-23/performance/cpu_gpu.json').read_text());pair=d['gpu_1440p_raster']['confirmed_pair']
  self.assertEqual(self.data['products'][6]['performance']['gaming']['value'],pair['rtx_4060_fps']);self.assertEqual(self.data['products'][7]['performance']['gaming']['value'],pair['rtx_5070_ti_fps'])
 def test_export_reproducible_and_input_hashes_match(self):
  self.assertEqual(self.data,build())
  for path,digest in self.data['inputHashes'].items():self.assertEqual(hashlib.sha256((ROOT/path).read_bytes()).hexdigest(),digest)
 def test_download_and_observed_counts(self):
  with (ROOT/'dashboard/dist/data/downloads/domestic_current.csv').open(encoding='utf-8-sig') as f:rows=list(csv.DictReader(f))
  self.assertEqual(len(rows),8)
  for row,p in zip(rows,self.data['products']):self.assertEqual(int(row['delivered_price_krw']),p['quote']['deliveredPrice'])
  with (ROOT/'dashboard/dist/data/downloads/domestic_history.csv').open(encoding='utf-8-sig') as f:rows=list(csv.DictReader(f))
  self.assertEqual(sum(r['frequency']=='weekly_label' for r in rows),96)
  monthly=[r for r in rows if r['frequency']=='monthly_label'];self.assertEqual(sum(r['status']=='value_mismatch' for r in monthly),5);self.assertEqual(sum(r['status']=='mobile_only' for r in monthly),6)
  self.assertTrue(all(r['shipping_basis']=='unknown' for r in rows))
if __name__=='__main__':unittest.main()
