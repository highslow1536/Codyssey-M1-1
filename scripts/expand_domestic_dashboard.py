"""Join current market audits and primary benchmarks without changing historical inputs."""
import csv, hashlib, json
from pathlib import Path
from analyze_domestic_market import audit_quote

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'data/verification/2026-10-23/expanded'
def read(p):return json.loads(p.read_text())

def expand(d):
 cpu=read(BASE/'cpu_benchmarks.json');gpu=read(BASE/'gpu_benchmarks.json')
 candidates=read(BASE/'peer_candidates.json')['candidates'];other=read(BASE/'other_candidates.json')['candidates']
 meta={
 '90160715':('MSI 5070 Ti GAMING TRIO','5070 Ti · 16GB · OC','RTX 5070 Ti','gpu-upper',16),
 '76510673':('GIGABYTE 5070 Ti GAMING OC','5070 Ti · 16GB · OC','RTX 5070 Ti','gpu-upper',16),
 '99839876':('GALAX 5070 Ti BLACK 2X','5070 Ti · 16GB · OC','RTX 5070 Ti','gpu-upper',16),
 '81990338':('MSI RTX 5060 Ti 16GB','VENTUS 2X OC PLUS · 16GB','RTX 5060 Ti','gpu-entry',16),
 '90956033':('MSI RTX 5060 8GB','VENTUS 2X OC · 8GB','RTX 5060','gpu-entry',8),
 '91909571':('SAPPHIRE RX 9060 XT 16GB','PULSE OC · 16GB','RX 9060 XT','gpu-entry',16),
 '18718496':('Ryzen 5 7600','6코어 12스레드 · AM5 · 멀티팩 정품','Ryzen 5 7600','cpu',None),
 '62794079':('Ryzen 5 9600X','6코어 12스레드 · AM5 · 멀티팩 정품','Ryzen 5 9600X','cpu',None)}
 raw={p['id']:ROOT/'data/verification/2026-10-23/domestic/raw'/f"{p['id']}.html" for p in d['products']}
 raw['106710902']=ROOT/'data/verification/2026-10-23/domestic/raw/106710902_peer.html'
 for q in candidates:
  short,spec,chip,tier,vram=meta[q['id']]
  p={'id':q['id'],'category':q['category'],'shortName':short,'spec':spec,'quote':q,'performance':{},'chip':chip,'comparisonTier':tier,'vramGB':vram,
     'compatibility':'AM5·DDR5·BIOS·쿨러와 총 교체 비용을 확인하세요.' if q['category']=='CPU' else 'VRAM 요구량·보조전원·PSU·케이스 공간·AS 조건을 확인하세요.'}
  d['marketReferences'].append(p);raw[p['id']]=BASE/q['file']
 for x in other:
  p={k:v for k,v in x.items() if k in ['id','category','shortName','spec','quote']};p['performance']={}
  p['compatibility']='같은 세대의 UDIMM 슬롯 전용. CL·랭크·CPU 지원 속도와 혼용 조건을 확인하세요.' if p['category']=='RAM' else 'M.2 2280 NVMe·발열·보증을 확인하세요. 같은 용량은 같은 실제 성능을 뜻하지 않습니다.'
  d['marketReferences'].append(p);raw[p['id']]=ROOT/x['rawFile']
 allp=d['products']+d['marketReferences']
 mapping={'21694499':('Ryzen 5 7500F','cpu',None),'76555634':('Core i5-14400F','cpu',None),'20740013':('RTX 4060','gpu-entry',8),'76550837':('RTX 5070 Ti','gpu-upper',16),'106710902':('RTX 5070 Ti','gpu-upper',16)}
 cpu_names={'Ryzen 5 7500F':'AMD Ryzen 5 7500F','Core i5-14400F':'Intel Core i5-14400F','Ryzen 5 7600':'AMD Ryzen 5 7600','Ryzen 5 9600X':'AMD Ryzen 5 9600X'}
 cpu_urls={'21694499':cpu['common_bundle']['source_urls'][4],'76555634':cpu['common_bundle']['source_urls'][4],'18718496':cpu['common_bundle']['source_urls'][5],'62794079':cpu['common_bundle']['source_urls'][6]}
 gpu_names={'RTX 4060':'GeForce RTX 4060 8GB','RTX 5060':'GeForce RTX 5060 8GB','RTX 5060 Ti':'GeForce RTX 5060 Ti 16GB','RTX 5070 Ti':'GeForce RTX 5070 Ti 16GB','RX 9060 XT':'Sapphire RX 9060 XT Pulse 16GB (tested OC custom)'}
 for p in allp:
  p.setdefault('spec','RTX 5070 Ti · GAMINGPRO-SOC · 16GB')
  p.setdefault('compatibility','같은 GPU 칩도 쿨링·소음·전력 제한·AS가 다릅니다.')
  p['cohort']='original' if p in d['products'] else 'reference'
  if p['id'] in mapping:p['chip'],p['comparisonTier'],p['vramGB']=mapping[p['id']]
  p['marketAudit']=audit_quote(raw[p['id']].read_text(),p['quote'])
  assert p['marketAudit']['firstOfferReconciled'],p['id']
  p['quoteRawFile']=str(raw[p['id']].relative_to(ROOT))
  pf=p['performance']
  if p['category']=='CPU':
   row=next(x for x in cpu['common_bundle']['values'] if x['cpu']==cpu_names[p['chip']])
   for key,field,label,group in [('cpuMulti','cpu_mark','PassMark CPU Mark · 멀티','passmark-cpu-mark'),('cpuSingle','single_thread','PassMark Single Thread','passmark-single-thread')]:
    pf[key]={'value':row[field],'unit':'점','label':label,'group':group,'kind':'measured-aggregate','samples':row['samples'],'asOf':'2026-10-23','sources':['cpu-passmark'],'sourceUrl':cpu_urls[p['id']],
     'note':'서로 다른 PC의 사용자 제출 실측 평균. 보드·RAM·냉각·전력 설정 미통제. 게임 FPS·동일 실험실의 짝지은 비교가 아닙니다. 표본 수는 제출 건수이며 독립 사용자 수는 미확인입니다.'}
   p['socket']='LGA1700' if p['id']=='76555634' else 'AM5'
  if p['category']=='GPU':
   row=next(x for x in gpu['bundle_1440p']['cards'] if x['chip']==gpu_names[p['chip']])
   p['benchmarkCard']=row['chip']
   pf['gamingSuite']={'value':row['relative_index_1440p_vs_pulse100'],'unit':'성능점','label':'TechPowerUp · 1440p · 23종 상대성능','group':'tpu-9060xt-1440p-23','kind':'measured-suite','games':23,'published':'2025-06-21','sources':['gpu-tpu'],
    'note':'같은 리뷰·테스트 시스템의 네이티브 1440p, RT off, 업스케일·프레임 생성 없음. Pulse OC=100. The Last of Us 충돌 항목 제외. 칩/리뷰 카드 기준으로 다른 OC 보드의 고유 실측을 뜻하지 않습니다. 2025년 드라이버·게임 버전이며 최신 패치 미반영.'}
   if p['chip']=='RTX 5070 Ti' and 'gaming' not in pf:pf['gaming']=dict(d['products'][7]['performance']['gaming'],kind='same-chip-proxy')
  if p['category']=='RAM':
   gen='ddr4' if p['id'] in ['11790199','14907467'] else 'ddr5'
   pf['capacity']={'value':16,'unit':'GB','label':'같은 세대 · 단품 용량','group':gen+'-16gb','kind':'spec'};p['chip']=gen+'-16gb';p['marketGroup']=gen+'-16gb'
  if p['category']=='SSD':
   pf['capacity']={'value':1000,'unit':'GB','label':'PCIe 4.0 TLC/DRAM · 명목 1TB','group':'ssd-pcie4-tlc-dram-1tb','kind':'spec'};p['chip']=p['shortName'];p['marketGroup']='ssd-pcie4-tlc-dram-1tb'
  p.setdefault('marketGroup',p.get('chip'))
 d['sources'].extend([
  {'id':'cpu-passmark','name':'PassMark · CPU Mark / Single Thread 공식 집계','url':cpu['common_bundle']['source_urls'][4],'published':None,'accessed':'2026-10-23','scope':'2026-10-23 갱신 · 4개 판매 CPU · 제출 5,987 / 6,594 / 7,109 / 9,982건 · 게임 테스트 아님'},
  {'id':'gpu-tpu','name':'TechPowerUp · Sapphire RX 9060 XT Pulse OC 리뷰','url':gpu['source']['pages']['relative_performance'],'published':gpu['source']['publication_date'],'accessed':'2026-10-23','scope':'23종 상대성능 · 1440p 네이티브 · RT off · 9800X3D/DDR5-6200 · 카드별 드라이버 상이'}])
 paths=[BASE/x for x in ['cpu_benchmarks.json','gpu_benchmarks.json','peer_candidates.json','other_candidates.json']]+list(raw.values())+list((BASE/'cpu_raw').glob('*_browser.html'))+list((BASE/'gpu_raw').glob('*'))
 for path in paths:d['inputHashes'][str(path.relative_to(ROOT))]=hashlib.sha256(path.read_bytes()).hexdigest()
 cpu['common_bundle']['values']=[x for x in cpu['common_bundle']['values'] if x['cpu'] in cpu_names.values()]
 cpu['common_bundle']['pairwise_cpu_mark_pct_vs_7500F'].pop('r5_7600X_vs_7500F',None)
 gpu.pop('workspace',None);gpu.pop('assignee_scope',None)
 d['benchmarks']={'cpu':cpu['common_bundle'],'gpu':gpu}
 d['rules'].update(anchorSellerCountAtLeast=10,anchorKnownStoreCountAtLeast=3,outlierPremium=0.20,outlierMinimumPeers=3,defaultQuoteStatistic='top3Median',parityAggregation='median within chip then median across chips')
 return d

def export_expanded(d):
 out=ROOT/'dashboard/dist/data/downloads'
 with (out/'domestic_expanded.csv').open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.writer(f);w.writerow(['id','name','category','cohort','chip','product_krw','shipping_krw','delivered_summary_krw','median3_product_krw','median3_delivered_krw','displayed_sellers','known_shipping_storefronts','reconciled','collected_at','source_url','quote_sha256'])
  for p in d['products']+d['marketReferences']:
   q=p['quote'];a=p['marketAudit'];w.writerow([p['id'],p['shortName'],p['category'],p['cohort'],p['chip'],q['productPrice'],q['shipping'],q['deliveredPrice'],a['top3ProductMedian'],a['top3DeliveredMedian'],q['displayedSellerCount'],a['distinctDisplayedStoresWithShipping'],a['firstOfferReconciled'],q['collectedAt'],q['sourceUrl'],q['sourceSha256']])
 with (out/'domestic_benchmarks.csv').open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.writer(f);w.writerow(['chip','metric','value','unit','kind','submission_n','game_n','as_of_or_published','source_url','retail_quote_available'])
  for p in [p for p in d['products']+d['marketReferences'] if p['category']=='CPU']:
   for k in ['cpuMulti','cpuSingle']:
    m=p['performance'][k];w.writerow([p['chip'],k,m['value'],m['unit'],m['kind'],m['samples'],'',m['asOf'],m['sourceUrl'],True])
  for row in d['benchmarks']['gpu']['bundle_1440p']['cards']:
   available=any(p.get('benchmarkCard')==row['chip'] for p in d['products']+d['marketReferences'])
   w.writerow([row['chip'],'relative_index_1440p',row['relative_index_1440p_vs_pulse100'],'Pulse OC=100','measured-suite','',23,'2025-06-21',d['sources'][-1]['url'],available])
