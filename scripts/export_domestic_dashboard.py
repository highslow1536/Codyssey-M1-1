#!/usr/bin/env python3
"""Rebuild domestic UI data from saved evidence. Offline; no extrapolated quotes."""
import csv,hashlib,json,shutil
from expand_domestic_dashboard import expand,export_expanded
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'dashboard/dist/data'
def read(path):return json.loads((ROOT/path).read_text())
def build():
 h=read('data/processed/2026-10-23/domestic/history.json')
 q=read('data/processed/2026-10-23/domestic/quotes.json')
 refs=read('data/verification/2026-10-23/domestic/peers.json')
 cpu=read('data/verification/2026-10-23/performance/cpu_gpu.json')
 ssd=read('data/verification/2026-10-23/performance/ram_ssd.json')
 meta={
 '21694499':('Ryzen 5 7500F','6코어 12스레드 · AM5 · 멀티팩 정품','AM5/DDR5 전용. 현재 메인보드·메모리 교체 비용과 쿨러를 확인하세요.'),
 '76555634':('Core i5-14400F','10코어 16스레드 · LGA1700 · 밸류팩 정품','LGA1700/BIOS 확인. 메인보드에 따라 DDR4 또는 DDR5 중 하나만 지원합니다.'),
 '11790199':('삼성 DDR4-3200 16GB','16GB 단품 · DDR4-3200 · UDIMM','DDR4 슬롯 전용. DDR5 슬롯과 호환되지 않습니다. 정확한 PN·랭크·CL을 확인하세요.'),
 '18911780':('삼성 DDR5-5600 16GB','16GB 단품 · DDR5-5600 · UDIMM','DDR5 슬롯 전용. 보드·CPU 지원 속도와 혼용 시 동작 조건을 확인하세요.'),
 '18297002':('삼성 990 PRO 1TB','1TB · PCIe 4.0 ×4 · 방열판 미포함','M.2 2280 NVMe 슬롯·발열·장착 공간 확인. 실제 작업 성능은 순차 최대속도와 다릅니다.'),
 '17001050':('SK하이닉스 P41 1TB','1TB · PCIe 4.0 ×4 · Platinum P41','M.2 2280 NVMe 슬롯·발열·장착 공간 확인. 용량·TBW 외 실제 사용 부하도 고려하세요.'),
 '20740013':('MSI RTX 4060 8GB','VENTUS 2X BLACK OC · D6 8GB','보조전원·케이스 공간·출력 단자 확인. 판매처가 적어 이 SKU 가격을 4060 시세로 일반화할 수 없습니다.'),
 '76550837':('MSI RTX 5070 Ti 16GB','VENTUS 3X OC · D7 16GB','케이스 길이·보조전원·권장 PSU 확인. 기존 부품을 재사용할 수 있는지 확인하세요.')}
 products=[]
 for quote in q['quotes']:
  code=quote['id'];short,spec,compat=meta[code]
  products.append({'id':code,'category':quote['category'],'shortName':short,'spec':spec,'compatibility':compat,'quote':quote,'history':next(p for p in h['products'] if p['product_code']==code),'performance':{}})
 def pf(code):return next(p['performance'] for p in products if p['id']==code)
 for code,value in [('21694499',110),('76555634',100)]:
  pf(code)['cpuBridge']={'value':value,'unit':'추정 게임 지수','label':'게임 성능 간접추정','group':'cpu-bridge-1440p','kind':'estimate','sources':['cpu-techspot','cpu-toms'],'note':'7500F 대 13400F의 1440p +10%와 14400 대 13400 약 1% 이내를 서로 다른 리뷰에서 연결. 직접 측정 아님. 오차 범위는 산정 불가.'}
 for code,value in [('20740013',45),('76550837',116)]:
  pf(code)['gaming']={'value':value,'unit':'FPS','label':'Crimson Desert · High 1440p','group':'crimson-1440p-native','kind':'measured-single-game','sources':['gpu-techspot'],'note':'TechSpot 동일 조건의 단일 게임 실측. 업스케일링·프레임 생성 없음. 엔진 RT GI 포함. MSI OC 고유 FPS나 다종 게임 평균 아님.'}
 for code,readspeed,write,tbw in [('18297002',7450,6900,600),('17001050',7000,6500,750)]:
  pf(code).update(capacity={'value':1000,'unit':'GB','label':'명목 용량','group':'ssd-1tb','kind':'spec'},read={'value':readspeed,'unit':'MB/s','label':'제조사 순차 읽기 최대','group':'ssd-sequential-read-1tb','kind':'spec'},writeMBs=write,tbw=tbw,warrantyYears=5)
 for code,group,band in [('11790199','ddr4-16gb',25.6),('18911780','ddr5-16gb',44.8)]:
  pf(code).update(capacity={'value':16,'unit':'GB','label':'단품 용량','group':group,'kind':'spec'},bandwidthGBsTheoretical=band)
 sources=[
 {'id':'cpu-techspot','name':'TechSpot · 7500F vs 13400F','url':'https://www.techspot.com/review/2728-ryzen-7500f-vs-core-134/','published':'2023-09-18','scope':'CPU 간접추정의 첫 번째 근거 · 상대 CPU는 13400F'},
 {'id':'cpu-toms','name':'Tom’s Hardware · Core i5-14400 review','url':'https://www.tomshardware.com/pc-components/cpus/intel-core-i5-14400-cpu-review','published':None,'scope':'14400/13400 약 1% 내 게임 차이 · 별도 테스트 환경'},
 {'id':'gpu-techspot','name':'TechSpot · Crimson Desert 40 GPUs','url':'https://www.techspot.com/article/3104-crimson-desert-benchmark/','published':'2026-03-18','scope':'단일 게임 · High 1440p 네이티브 · 9800X3D/DDR5-6000 · 45/116 FPS'},
 {'id':'samsung','name':'Samsung · 990 PRO 공식 사양','url':'https://semiconductor.samsung.com/consumer-storage/internal-ssd/990-pro/','published':None,'scope':'1TB 최대 순차 읽기/쓰기 · 7450/6900 MB/s · 600 TBW · 5년'},
 {'id':'hynix','name':'SK hynix · Platinum P41 공식 사양','url':'https://ssd.skhynix.com/platinum_p41/','published':None,'scope':'1TB 최대 순차 읽기/쓰기 · 7000/6500 MB/s · 750 TBW · 5년'},
 {'id':'ram','name':'Samsung · DRAM 모듈','url':'https://semiconductor.samsung.com/dram/module/','published':None,'scope':'세대 사양 참고. 유통 SKU의 정확한 PN·CL·랭크 및 실측 성능 미확인'}]
 for s in sources:s['accessed']='2026-10-23'
 peer=refs['peers'][0]; reference={'id':peer['id'],'shortName':'PALIT 5070 Ti 16GB','category':'GPU','quote':peer,'performance':{'gaming':dict(pf('76550837')['gaming'],kind='same-chip-proxy',note='5070 Ti 칩 실측을 같은 칩 비교용으로만 공유. 이 보드 자체 FPS 실측은 아님.')}}
 paths=['data/processed/2026-10-23/domestic/history.json','data/processed/2026-10-23/domestic/quotes.json','data/verification/2026-10-23/domestic/peers.json','data/verification/2026-10-23/performance/cpu_gpu.json','data/verification/2026-10-23/performance/ram_ssd.json']
 result={'schemaVersion':1,'asOf':'2026-10-23','historicalAsOf':'2026-10-21','products':products,'marketReferences':[reference],'excluded':refs['excluded'],'sources':sources,'historyCounts':h['counts'],'inputHashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths},'rules':{'staleDays':7,'thinSellerCountBelow':3,'reviewTolerance':0.05,'historyQuantiles':[0.25,0.5],'note':'모든 문턱값은 보수적인 화면 분류 규칙이며 통계적 신뢰구간·미래 예측·구매 성공 확률이 아님.'}}
 return expand(result)

def main():
 d=build();OUT.mkdir(parents=True,exist_ok=True)
 export_expanded(d)
 (OUT/'domestic.json').write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
 download=OUT/'downloads';download.mkdir(exist_ok=True)
 with (download/'domestic_current.csv').open('w',encoding='utf-8-sig',newline='') as f:
  fields=['id','name','category','product_price_krw','shipping_krw','delivered_price_krw','displayed_sellers','collected_at_kst','source_url','pc_mobile_series_match']
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
  for p in d['products']:
   q=p['quote'];w.writerow(dict(zip(fields,[p['id'],p['shortName'],p['category'],q['productPrice'],q['shipping'],q['deliveredPrice'],q['displayedSellerCount'],q['collectedAt'],q['sourceUrl'],q['mobileCheck']['match']])))
 with (download/'domestic_history.csv').open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.writer(f);w.writerow(['id','category','frequency','date_label','pc_krw','mobile_krw','status','partial_month','snapshot_kst','shipping_basis'])
  for p in d['products']:
   for r in p['history']['weekly_3m']:w.writerow([p['id'],p['category'],'weekly_label',r['iso_date'],r['desktop_price'],r['mobile_price'],'matched',False,d['historicalAsOf'],'unknown'])
   for r in p['history']['monthly_comparison_24m']:w.writerow([p['id'],p['category'],'monthly_label',r['month_iso'],r['desktop_price'],r['mobile_price'],r['status'],r['partial_month'],d['historicalAsOf'],'unknown'])
 report=ROOT/'docs/domestic_value_methodology.md'
 if report.exists():shutil.copyfile(report,ROOT/'dashboard/dist/reports/domestic-value.md')
 print(f"Exported {len(d['products'])} domestic SKUs and {len(d['marketReferences'])} separate market reference")
if __name__=='__main__':main()
