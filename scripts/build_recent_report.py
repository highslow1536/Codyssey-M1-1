"""Analyze the current refresh separately from the frozen forecast benchmark.

Public output contains coverage, descriptive changes and correlations only.
Private output retains weekly prices, quote dates and source hashes. No missing
week is filled; returns require two adjacent valid calendar weeks.
"""
from __future__ import annotations

import argparse
import csv
from datetime import date, timedelta
import hashlib
import json
from pathlib import Path

import numpy as np
import build_forecast as forecast
from build_recent_dashboard import log_returns, pearson

ROOT = Path(__file__).resolve().parents[1]
MARKET_NAMES = {'AMD':'AMD', 'INTC':'Intel', 'MU':'Micron', 'NVDA':'NVIDIA',
                '005930.KS':'삼성전자', '000660.KS':'SK하이닉스', 'ETH-USD':'ETH'}
SHORT_NAMES = ['Ryzen 3600', 'Crucial DDR4 16GB (US)', '970 EVO Plus 1TB',
               'RTX 3090 FTW3', 'RTX 3070 (IN)', 'RTX 3080 Renewed',
               '990 PRO 1TB', 'SN850X 1TB', 'P41 1TB', 'T500 1TB',
               'Ryzen 9600X (IN)', 'RTX 4060 Eagle', 'Crucial DDR5 16GB (IN)',
               'Crucial Pro DDR4 16GB (IN)']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def weeks_between(start, end):
    result = []
    while start <= end:
        result.append(start.isoformat())
        start += timedelta(days=7)
    return result


def last_complete_friday(as_of):
    return as_of - timedelta(days=(as_of.weekday()-4) % 7 or 7)


def coverage(values, quote_dates, weeks):
    valid = [i for i,v in enumerate(values) if v is not None]
    first = valid[0] if valid else len(values)
    return dict(observed=len(valid), total=len(values), returns=len(log_returns(values)),
                beforeFirstObservation=first,
                missingAfterFirst=len(values)-first-len(valid),
                firstWeek=weeks[first] if valid else None,
                lastWeek=weeks[valid[-1]] if valid else None,
                lastQuoteDate=quote_dates[valid[-1]] if valid else None,
                periodChange=(values[valid[-1]]/values[first]-1) if len(valid)>1 else None,
                recent13WeekChange=(values[-1]/values[-14]-1)
                    if len(values)>=14 and values[-1] is not None and values[-14] is not None else None)


def correlations(parts, markets, lags):
    rows = []
    for part in parts:
        pr = log_returns(part['values'])
        for market in markets:
            mr = log_returns(market['values'])
            for lag in lags:
                pairs = [(mr[t], pr[t+lag]) for t in mr if t+lag in pr]
                r = pearson([a for a,b in pairs], [b for a,b in pairs])
                rows.append(dict(partId=part['id'], marketId=market['id'], lagWeeks=lag,
                                 n=len(pairs), pearson=r,
                                 status='ok' if r is not None else 'insufficient_pairs' if len(pairs)<2 else 'zero_variance'))
    return rows


def write_csv(path, rows):
    with path.open('w', encoding='utf-8-sig', newline='') as handle:
        writer=csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader(); writer.writerows(rows)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--as-of', type=date.fromisoformat, required=True)
    args=ap.parse_args()
    snapshot=ROOT/'data/verification'/args.as_of.isoformat()/'report_refresh'
    manifest_path=snapshot/'manifest.json'
    manifest=json.loads(manifest_path.read_text())
    records={r['id']:r for r in manifest['records']}
    if any(r['status']!='ok' for r in records.values()):
        raise SystemExit('Refresh has failures; do not silently substitute old data as current.')
    forecast.AS_OF=args.as_of
    old_series,_,_=forecast.load_sources()
    old_series=[s for s in old_series if s['frequency']=='weekly']
    mdoc=json.loads((snapshot/'markets.json').read_text())
    evidence_end=min(date.fromisoformat(s['lastDate']) for s in mdoc['series'])
    end=min(last_complete_friday(args.as_of), evidence_end-timedelta(days=(evidence_end.weekday()-4)%7))
    weeks=weeks_between(date(2023,1,6),end)
    parts=[]; markets=[]; private_rows=[]
    hashes={str(manifest_path.relative_to(ROOT)):sha(manifest_path)}
    for source,short in zip(old_series,SHORT_NAMES,strict=True):
        rec=records[source['id']]; path=ROOT/rec['rawFile']
        if sha(path)!=rec['sha256']: raise ValueError('Changed refresh raw input')
        hashes[str(path.relative_to(ROOT))]=sha(path)
        raw=json.loads(path.read_text())
        quotes,excluded=forecast.normalize_quotes(raw['History']['Price'],source['id'],5 if source['currency']=='USD' else 0)
        by_week={p['date']:p for p in forecast.weekly_grid(quotes)}
        vals=[by_week.get(w,{}).get('price') for w in weeks]
        dates=[by_week.get(w,{}).get('quoteDate') for w in weeks]
        part=dict(id=source['id'],name=source['name'],shortName=short,category=source['category'],
                  currency=source['currency'],region=source['region'],condition=source['condition'],
                  sourceUrl=source['sourceUrl'],sourceLastQuoteDate=rec['lastDate'],
                  sourceAgeDays=(args.as_of-date.fromisoformat(rec['lastDate'])).days,
                  excludedN=len(excluded),coverage=coverage(vals,dates,weeks),values=vals)
        parts.append(part)
        for w,v,qd in zip(weeks,vals,dates):
            private_rows.append(dict(id=part['id'],weekEnd=w,quoteDate=qd,price=v,
                                     currency=part['currency'],source_sha256=rec['sha256']))
    for s in mdoc['series']:
        path=ROOT/s['rawFile']
        if sha(path)!=s['sha256']: raise ValueError('Changed market raw input')
        hashes[str(path.relative_to(ROOT))]=sha(path)
        by_date={p['date']:p['price'] for p in s['points']}
        vals=[]; dates=[]
        for w in weeks:
            begin=(date.fromisoformat(w)-timedelta(days=6)).isoformat()
            days=sorted(d for d in by_date if begin<=d<=w)
            vals.append(by_date[days[-1]] if days else None); dates.append(days[-1] if days else None)
        market=dict(id=s['id'],name=MARKET_NAMES[s['id']],currency=s['currency'],
                    priceBasis=s['priceBasis'],sourceUrl=s['sourceUrl'],
                    dailyN=s['nValid'],dailyLast=s['lastDate'],
                    coverage=coverage(vals,dates,weeks),values=vals)
        markets.append(market)
        for w,v,qd in zip(weeks,vals,dates):
            private_rows.append(dict(id=s['id'],weekEnd=w,quoteDate=qd,price=v,
                                     currency=s['currency'],source_sha256=s['sha256']))
    rows=correlations(parts,markets,range(-8,9))
    public=dict(schemaVersion=1,asOf=args.as_of.isoformat(),checkedAt=manifest['checkedAt'],
                firstWeek=weeks[0],lastWeek=weeks[-1],calendarWeeks=len(weeks),
                parts=[{k:v for k,v in s.items() if k!='values'} for s in parts],
                markets=[{k:v for k,v in s.items() if k!='values'} for s in markets],
                correlations=rows,refreshSummary=manifest['summary'],inputHashes=hashes,
                limitations=['해외 14개 리스팅의 호가이며 국내 현재가·전체 시장 지수가 아닙니다. 통화·지역·보드·신품/리퍼 조건이 다릅니다.',
                '완료된 토–금 달력을 유지합니다. 첫 관측 전과 이후 결측을 구분하며 결측을 보간·이월하지 않습니다.',
                '최근 13주 변화는 기술통계이며 달력 3개월 예측과 다릅니다. 양 끝 주에 실제 관측이 없으면 미산출입니다.',
                '로그 변화율은 연속 두 주가 있을 때만 계산합니다. 양의 시차는 시장이 부품을 앞서는 방향입니다.',
                '상관은 탐색 기술통계입니다. 다중비교 유의성·인과관계·예측력을 검증하지 않았고, 통화·환율·시차·신제품·재고를 통제하지 않았습니다.',
                '국내 8개는 새로 조회한 단면 견적입니다. 월간 이력에 새 관측으로 붙이거나 구형 해외 제품으로 대체하지 않았습니다.',
                '3개월 모델 비교는 2026-10-23 스냅샷으로 고정했습니다. 새 수집을 새 미래 검증 성과로 세지 않습니다.',
                '2022년 머지 이후 ETH는 가격만 분석하며 PoW 채굴 수익 대용을 연장하지 않습니다.'])
    out=ROOT/'data/analysis'/args.as_of.isoformat()/'recent';out.mkdir(parents=True,exist_ok=True)
    write_csv(out/'weekly_prices.csv',private_rows)
    pubdir=ROOT/'data/public';pubdir.mkdir(exist_ok=True)
    (pubdir/'recent_analysis.json').write_text(json.dumps(public,ensure_ascii=False,indent=2)+'\n')
    write_csv(pubdir/'recent_correlations.csv',rows)
    write_csv(pubdir/'recent_coverage.csv',[dict(id=s['id'],name=s['name'],currency=s['currency'],
          **s['coverage']) for s in public['parts']+public['markets']])
    # Metadata only: no current quotes, historical rows or session headers.
    safe_keys=('id','name','category','kind','currency','sourceUrl','status','n','firstDate','lastDate',
               'previousLastWeeklyObservation','sourceUpdatedOn','displayedSellerCount','historicalObservationAdded')
    freshness=dict(asOf=public['asOf'],checkedAt=public['checkedAt'],summary=manifest['summary'],
                   records=[{k:r[k] for k in safe_keys if k in r} for r in records.values()])
    (pubdir/'source_freshness.json').write_text(json.dumps(freshness,ensure_ascii=False,indent=2)+'\n')
    write_report(public,freshness)
    plot(public,parts,markets,weeks,out)
    print(json.dumps(dict(weeks=len(weeks),parts=len(parts),markets=len(markets),
                         correlations=len(rows),sameWeekPairs=len(parts)*len(markets)),ensure_ascii=False))


def write_report(d,freshness):
    lines=['# 최근 부품·주가 분석과 최신성 감사','',
           f"확인 기준: **{d['asOf']} KST**. 최근 분석 달력: **{d['firstWeek']}–{d['lastWeek']} ({d['calendarWeeks']}주)**.",
           '수집일·실제 호가일·주간 대표 날짜·예측 검증 기간을 구분한다. 공개판은 원가격 곡선 없이 자체 집계만 제공한다.','',
           '![최근 14개 부품의 관측 범위와 7개 시장의 동시 변화율 상관](assets/public/06_recent_analysis.png)','',
           '## 1. 실제 확보 범위','',
           '| 계열 | 시장·통화 | 유효 주 / 달력 | 인접 변화율 n | 주간 마지막 / 실제 호가 | 원출처 최신일 | 경과 일수 |',
           '|---|---|---:|---:|---|---|---:|']
    for s in d['parts']:
        c=s['coverage'];lines.append(f"| {s['shortName']} | {s['region']}·{s['currency']} | {c['observed']} / {c['total']} | {c['returns']} | {c['lastWeek']} / {c['lastQuoteDate']} | {s['sourceLastQuoteDate']} | {s['sourceAgeDays']} |")
    lines+=['','원출처 최신일이 주간 마지막보다 늦을 수 있다. 10월 24일(토) 호가는 아직 완료되지 않은 다음 주에 속하므로 10월 23일 주간 분석에 넣지 않았다. 첫 관측 이전에는 미출시·미등록·미추적을 구분할 수 없으므로 이후 결측과 따로 표시한다.','',
            '| 시장 | 일별 n | 실제 마지막 거래/관측일 | 유효 주 / 달력 | 변화율 n |','|---|---:|---|---:|---:|']
    for s in d['markets']:
        c=s['coverage'];lines.append(f"| {s['name']} | {s['dailyN']} | {s['dailyLast']} | {c['observed']} / {c['total']} | {c['returns']} |")
    lines+=['','## 2. 부품–주가·ETH 동시 변화율 상관','',
            '같은 토–금 달력의 로그 변화율 Pearson r이다. 괄호는 실제 짝 수 n이며 제품 수를 독립 표본으로 합산하지 않는다. 시차 ±8주 전체 탐색표는 [CSV](../data/public/recent_correlations.csv)에 공개한다. p값·유의성·예측 신호를 주장하지 않는다. 인도 RTX 3070은 짝 수가 있어도 부품 변화율의 분산이 0이어서 상관계수를 계산할 수 없다(미산출은 r=0이 아님).','',
            '| 부품 | '+' | '.join(s['name'] for s in d['markets'])+' |',
            '|---|'+'---:|'*len(d['markets'])]
    lookup={(r['partId'],r['marketId']):r for r in d['correlations'] if r['lagWeeks']==0}
    for s in d['parts']:
        cells=[]
        for m in d['markets']:
            r=lookup[s['id'],m['id']];cells.append(f"{r['pearson']:+.3f} ({r['n']})" if r['pearson'] is not None else f"미산출 ({r['n']})")
        lines.append('| '+s['shortName']+' | '+' | '.join(cells)+' |')
    lines+=['','## 3. 최신 조회가 의미하는 것','',
            f"{d['checkedAt']}에 해외 14개·시장 7개·국내 단면 8개를 다시 조회했다. 요청 성공과 현재 날짜까지의 이력 확보는 별개다.",
            'Ryzen 3600은 2026-10-06, 970 EVO Plus는 2026-09-26에서 원출처 호가가 멈췄다. 이 두 구형 SKU만으로 현재 전체 PC 시장을 해석하지 않는다. 최근 제품의 이력·국내 현재 견적·검증된 미래 예측은 별도 근거다.',
            '국내 견적의 sourceUpdatedOn은 미확인이다. 재조회 시점의 노출 견적이며 판매자의 재고·결제 가능 상태를 확인한 거래 가격이 아니다. 원견적 값과 원가격 시계열은 재배포 조건 미확인으로 공개 제외한다.',
            '2020–2022년은 과거 채굴 붐 설명에, 2023–2026년은 최근 동향·상관 탐색에 사용한다. 두 기간의 계수를 서로 바꿔 인용하거나 2020–2022년의 204시차 보정 결과를 최근 기간에 적용하지 않는다.','',
            '## 4. 한계와 재현','']
    lines += ['- '+s for s in d['limitations']]
    lines+=['','공개 집계: [최근 분석 JSON](../data/public/recent_analysis.json) · [관측 수 CSV](../data/public/recent_coverage.csv) · [조회 메타데이터](../data/public/source_freshness.json).',
            '수집: `scripts/refresh_report_sources.py --as-of 2026-10-25 --fetch` (새 경로에 한 번). 분석: `scripts/build_recent_report.py --as-of 2026-10-25` (저장된 원본이 있는 연구 환경).',
            '공개판에서는 `scripts/plot_recent_report.py`로 집계 그림만 재생성할 수 있다. 기존 3개월 모델 비교·확률 보정·구매 추천 기준은 바꾸지 않았다.']
    (ROOT/'docs/recent_analysis.md').write_text('\n'.join(lines)+'\n')


def plot(d,parts,markets,weeks,out):
    from plot_recent_report import plot_public
    plot_public(d)
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(4,4,figsize=(17,13))
    for ax,s in zip(axes.flat,parts):
        ax.plot([date.fromisoformat(w) for w in weeks],
                [v if v is not None else np.nan for v in s['values']],color='#166e58',linewidth=1)
        ax.set_title(s['shortName']+' · '+s['currency'],fontsize=10)
        ax.tick_params(axis='x',labelrotation=30,labelsize=8);ax.grid(alpha=.15)
    for ax in list(axes.flat)[len(parts):]:ax.set_visible(False)
    fig.suptitle('최근 해외 부품별 원가격 · 결측 주를 연결하지 않음',fontsize=19)
    fig.tight_layout(rect=(0,0,1,.96));fig.savefig(out/'price_trends.png',dpi=130);plt.close(fig)


if __name__=='__main__':main()
