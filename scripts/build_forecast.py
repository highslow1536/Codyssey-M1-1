"""Offline, purged rolling-origin three-calendar-month probabilistic backtests.

Specification is fixed in docs/forecast_protocol.md; no network calls or tuning on
the final evaluation period. Missing prices/targets are never interpolated.
"""
from __future__ import annotations

import calendar
from collections import Counter, defaultdict
import csv
from datetime import date, datetime, timedelta
import hashlib
import json
import math
from pathlib import Path
import re
import shutil

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data/analysis/2026-10-23/forecast'
WEB = ROOT / 'dashboard/dist/data'
AS_OF = date(2026, 10, 23)
SEED = 20261023
CLASSES = ['하락', '보합', '상승']
CANDIDATES = ['logistic', 'forest']
NAMES = {'logistic': 'L2 다항 로지스틱 회귀', 'forest': '깊이 제한 랜덤포레스트'}
TEMPERATURES = [.5, 1., 2., 4.]


def add_months(d, n):
    m = d.year * 12 + d.month - 1 + n
    y, m = divmod(m, 12)
    return date(y, m + 1, min(d.day, calendar.monthrange(y, m + 1)[1]))


def target_date(d, frequency):
    t = add_months(d, 3)
    return t + timedelta(days=(4 - t.weekday()) % 7) if frequency == 'weekly' else date(t.year, t.month, 1)


def valid_price(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and v > 0


def label(change):
    return 2 if change > .03 + 1e-12 else 0 if change < -.03 - 1e-12 else 1


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize_quotes(observations, series_id, minimum=5):
    """No neighbour/future-based flags. USD <$5 is a predeclared floor sensitivity.

    The inherited known $1.47 CPU error is excluded by a fixed absolute floor,
    with an entirely unfiltered run exported separately for sensitivity.
    """
    accepted, excluded, seen = [], [], {}
    for i, r in enumerate(observations):
        ts = str(r.get('date', r.get('x', '')))
        try:
            d = date.fromisoformat(ts[:10])
        except ValueError:
            excluded.append({'series': series_id, 'row': i, 'date': ts, 'price': r.get('price', r.get('y')), 'reason': 'invalid_date'})
            continue
        v = r.get('price', r.get('y'))
        reason = 'nonpositive_or_nonfinite' if not valid_price(v) else 'future_quote' if d > AS_OF else 'absolute_floor' if v < minimum else None
        if reason:
            excluded.append({'series': series_id, 'row': i, 'date': ts, 'price': v, 'reason': reason})
            continue
        # Identical timestamps with conflicting prices must be audited, not silently selected.
        if ts in seen and seen[ts] != v:
            raise ValueError(f'Conflicting timestamp: {series_id} {ts}')
        if ts in seen:
            excluded.append({'series': series_id, 'row': i, 'date': ts, 'price': v, 'reason': 'duplicate_timestamp'})
            continue
        seen[ts] = v
        accepted.append({'timestamp': ts, 'date': d, 'price': float(v), 'row': i})
    return sorted(accepted, key=lambda x: x['timestamp']), excluded


def weekly_grid(quotes):
    if not quotes:
        return []
    selected = {}
    for q in quotes:
        end = q['date'] + timedelta(days=(4 - q['date'].weekday()) % 7)
        if end < AS_OF:  # only completed weeks, never use this incomplete Friday
            selected[end] = q
    if not selected:
        return []
    d, end, points = min(selected), AS_OF - timedelta(days=(AS_OF.weekday() - 4) % 7 or 7), []
    while d <= end:
        q = selected.get(d)
        points.append({'date': d.isoformat(), 'price': q['price'] if q else None,
                       'quoteDate': q['date'].isoformat() if q else None})
        d += timedelta(days=7)
    return points


def monthly_grid(monthly):
    source = {r['date']: r for r in monthly if not r.get('partial') and valid_price(r.get('price'))}
    if not source:
        return []
    d = date.fromisoformat(min(source) + '-01')
    end = date(AS_OF.year, AS_OF.month, 1)
    points = []
    while d < end:
        r = source.get(d.strftime('%Y-%m'))
        points.append({'date': d.isoformat(), 'price': r['price'] if r else None, 'quoteDate': None})
        d = add_months(d, 1)
    return points


def features(points, i, frequency, category='CPU'):
    """Only prefix data; deliberately no whole-series quantile/outlier statistics."""
    if not valid_price(points[i]['price']):
        return None
    p = points[i]['price']
    window = 12 if frequency == 'weekly' else 6
    min_points = 4
    prefix = points[max(0, i - window + 1):i + 1]
    observed = [r['price'] for r in prefix if valid_price(r['price'])]
    if i < (4 if frequency == 'weekly' else 3) or len(observed) < min_points:
        return None
    lags = (1, 4, 12, 26) if frequency == 'weekly' else (1, 2, 3, 6)
    changes = [math.log(p / points[i - k]['price']) if i >= k and valid_price(points[i-k]['price']) else np.nan for k in lags]
    returns = [math.log(b['price'] / a['price']) for a, b in zip(prefix, prefix[1:]) if valid_price(a['price']) and valid_price(b['price'])]
    extra = [math.log(p / float(np.median(observed))), float(np.std(returns)) if len(returns) >= 2 else np.nan,
             math.log(max(observed) / min(observed)), len(observed) / window,
             (date.fromisoformat(points[i]['date']) - date.fromisoformat(points[0]['date'])).days / 365.25]
    # Categories used only in the homogeneous domestic minPrice monthly panel.
    if frequency == 'monthly':
        extra.extend(float(category == c) for c in ['CPU', 'RAM', 'SSD', 'GPU'])
    return changes + extra


def make_samples(series):
    points, frequency = series['points'], series['frequency']
    lookup = {p['date']: p for p in points}
    samples, failures = [], Counter()
    for i, point in enumerate(points):
        x = features(points, i, frequency, series['category'])
        if x is None:
            failures['missing_origin_or_features'] += 1
            continue
        d = date.fromisoformat(point['date'])
        t = target_date(d, frequency)
        target = lookup.get(t.isoformat())
        # Monthly source bucket is not known before the month has completed.
        available = add_months(d, 1) if frequency == 'monthly' else d
        target_available = add_months(t, 1) if frequency == 'monthly' else t
        change = target['price'] / point['price'] - 1 if target and valid_price(target['price']) else None
        if change is None:
            failures['unmatured_target' if target_available > AS_OF else 'missing_target'] += 1
        samples.append({'id': series['id'], 'origin': d.isoformat(), 'available': available.isoformat(),
                        'target': t.isoformat(), 'targetAvailable': target_available.isoformat(),
                        'price': point['price'], 'x': x, 'y': label(change) if change is not None else None,
                        'change': change, 'missingFeatures': sum(not math.isfinite(z) for z in x)})
    return samples, dict(failures)


def sufficient(rows, frequency):
    counts = Counter(r['y'] for r in rows)
    return len(rows) >= (80 if frequency == 'weekly' else 48) and all(counts[c] >= 5 for c in range(3)) and (frequency == 'weekly' or len({r['origin'] for r in rows}) >= 6)


def mature_training(samples, cutoff):
    # Strictly before the quarter start: origin/target at cutoff is not yet known.
    return [r for r in samples if r['y'] is not None and r['targetAvailable'] < cutoff]


def fit_model(rows, candidate):
    model = make_pipeline(SimpleImputer(strategy='median', add_indicator=True, keep_empty_features=True),
                          StandardScaler(),
                          LogisticRegression(C=1, max_iter=1200, random_state=SEED) if candidate == 'logistic' else
                          RandomForestClassifier(n_estimators=120, max_depth=3, min_samples_leaf=12, random_state=SEED, n_jobs=1))
    model.fit([r['x'] for r in rows], [r['y'] for r in rows])
    return model


def temperature(probabilities, t):
    p = np.clip(np.asarray(probabilities, dtype=float), 1e-12, 1)
    logits = np.log(p) / t
    e = np.exp(logits - logits.max(axis=-1, keepdims=True))
    return e / e.sum(axis=-1, keepdims=True)


def frequency_baseline(rows):
    counts = np.bincount([r['y'] for r in rows], minlength=3) + 1
    return counts / counts.sum()


def quarter(d):
    d = date.fromisoformat(d)
    return date(d.year, (d.month - 1) // 3 * 3 + 1, 1).isoformat()


def rolling_predictions(samples, frequency, candidate):
    output = []
    groups = defaultdict(list)
    for r in samples:
        if r['y'] is not None and r['available'] >= '2023-01-01':
            groups[quarter(r['available'])].append(r)
    for cutoff, test in sorted(groups.items()):
        training = mature_training(samples, cutoff)
        if not sufficient(training, frequency):
            continue
        model, base = fit_model(training, candidate), frequency_baseline(training)
        p = model.predict_proba([r['x'] for r in test])
        class_medians = [float(np.median([r['change'] for r in training if r['y'] == c])) for c in range(3)]
        for r, probs in zip(test, p):
            # Model classes always 0,1,2 after the minimum-class check.
            last_change = r['x'][2]  # 12 weeks/3 calendar buckets, a separate naive drift comparator
            scale = ((date.fromisoformat(r['target'])-date.fromisoformat(r['origin'])).days/84
                     if frequency=='weekly' else 1.)
            drift = math.expm1(last_change*scale) if math.isfinite(last_change) else 0.
            output.append({**{k: v for k, v in r.items() if k != 'x'}, 'candidate': candidate,
                           'probabilities': probs.tolist(), 'baseline': base.tolist(),
                           'classMedians': class_medians, 'driftChange': drift,
                           'trainN': len(training), 'trainThrough': max(r['targetAvailable'] for r in training),
                           'fitCutoff': cutoff})
    return output


def choose_model(predictions, frequency):
    options = []
    if frequency == 'weekly':
        for candidate, rows in predictions.items():
            val = [r for r in rows if r['origin'] < '2025-01-01' and r['targetAvailable'] <= '2024-12-31']
            if len(val) < 24 or len({r['y'] for r in val}) < 3:
                continue
            for t in TEMPERATURES:
                p = temperature([r['probabilities'] for r in val], t)
                loss = -float(np.mean([math.log(p[i, r['y']]) for i, r in enumerate(val)]))
                options.append((loss, CANDIDATES.index(candidate), t, candidate, len(val)))
    if not options:
        return {'status': 'fixed_unselected', 'candidate': 'logistic', 'temperature': 1., 'n': 0, 'validationLogLoss': None}
    loss, _, t, candidate, n = min(options)
    return {'status': 'past_validation_only', 'candidate': candidate, 'temperature': t, 'n': n, 'validationLogLoss': loss,
            'candidates':[{'candidate':c,'temperature':temp,'n':size,'logLoss':score}
                          for score,_,temp,c,size in options]}


def apply_temperature(rows, t):
    result = []
    for row in rows:
        r = dict(row)
        r['probabilities'] = temperature(r['probabilities'], t).tolist()
        r['predictedChange'] = float(np.dot(r['probabilities'], r['classMedians']))
        r['actualClass'] = r['y']
        r['actualChange'] = r['change']
        result.append(r)
    return result


def brier(p, y):
    return float(sum((v - float(i == y)) ** 2 for i, v in enumerate(p)))


def nonoverlap_count(rows):
    # One time interval per origin, never multiply independent periods by SKU.
    by_origin = {r['origin']: r for r in rows}
    until, n = '', 0
    for origin, r in sorted(by_origin.items()):
        if r['available'] >= until:
            n += 1
            until = r['targetAvailable']
    return n


def block_improvement_ci(rows, frequency):
    if not rows:
        return None
    origin_scores = defaultdict(list)
    for r in rows:
        origin_scores[r['origin']].append(brier(r['baseline'], r['y']) - brier(r['probabilities'], r['y']))
    first, last = min(origin_scores), max(origin_scores)
    d, end = date.fromisoformat(first), date.fromisoformat(last)
    step = timedelta(days=7) if frequency == 'weekly' else None
    grid = []
    while d <= end:
        values = origin_scores.get(d.isoformat(), [])
        grid.append(float(np.mean(values)) if values else np.nan)
        d = d + step if step else add_months(d, 1)
    width = 14 if frequency == 'weekly' else 3
    if len(grid) < 2 * width:
        return None
    a, rng, means = np.asarray(grid), np.random.default_rng(SEED), []
    for _ in range(1000):
        starts = rng.integers(0, len(a) - width + 1, size=math.ceil(len(a)/width))
        draws = np.concatenate([a[s:s+width] for s in starts])[:len(a)]
        if np.any(np.isfinite(draws)):
            means.append(float(np.nanmean(draws)))
    return np.quantile(means, [.025, .975]).tolist() if means else None


def wilson(hits, n):
    if not n:
        return [None, None]
    p, z = hits / n, 1.959963984540054
    den = 1 + z*z/n
    c = (p + z*z/(2*n)) / den
    h = z * math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / den
    return [max(0, c-h), min(1, c+h)]


def evaluate(rows, frequency):
    empty = {'n': 0, 'originsN': 0, 'nonoverlapN': 0, 'from': None, 'to': None,
             'brier': None, 'baselineBrier': None, 'brierSkill': None, 'logLoss': None,
             'baselineLogLoss': None, 'accuracy': None, 'ece': None, 'mae': None,
             'naiveMae': None, 'driftMae': None, 'improvementCI': None, 'classCounts': [0,0,0], 'reliability': []}
    if not rows:
        return empty
    bs = float(np.mean([brier(r['probabilities'], r['y']) for r in rows]))
    baseline = float(np.mean([brier(r['baseline'], r['y']) for r in rows]))
    reliability, weighted = [], 0.
    for c in range(3):
        for lo, hi in [(0,.2),(.2,.4),(.4,.6),(.6,.8),(.8,1.000001)]:
            group = [r for r in rows if lo <= r['probabilities'][c] < hi]
            if not group:
                continue
            n, hits = len(group), sum(r['y'] == c for r in group)
            p = float(np.mean([r['probabilities'][c] for r in group]))
            lower, upper = wilson(hits, n)
            reliability.append({'class': c, 'binLow':lo, 'binHigh':min(1.,hi), 'n': n, 'predicted': p, 'observed': hits/n, 'low': lower, 'high': upper})
            weighted += n * abs(p - hits/n)
    return {**empty, 'n': len(rows), 'originsN': len({r['origin'] for r in rows}),
            'nonoverlapN': nonoverlap_count(rows), 'from': min(r['origin'] for r in rows),
            'to': max(r['origin'] for r in rows), 'brier': bs, 'baselineBrier': baseline,
            'brierSkill': 1-bs/baseline if baseline else None,
            'logLoss': -float(np.mean([math.log(max(1e-12, r['probabilities'][r['y']])) for r in rows])),
            'baselineLogLoss': -float(np.mean([math.log(r['baseline'][r['y']]) for r in rows])),
            'accuracy': float(np.mean([int(np.argmax(r['probabilities'])) == r['y'] for r in rows])),
            'ece': weighted / (3*len(rows)),
            'mae': float(np.mean([abs(r['predictedChange']-r['change']) for r in rows])),
            'naiveMae': float(np.mean([abs(r['change']) for r in rows])),
            'driftMae': float(np.mean([abs(r['driftChange']-r['change']) for r in rows])),
            'improvementCI': block_improvement_ci(rows, frequency),
            'classCounts': [sum(r['y']==c for r in rows) for c in range(3)], 'reliability': reliability}


def gates(e, frequency):
    reasons = []
    required = 52 if frequency == 'weekly' else 12
    if e['originsN'] < required:
        reasons.append(f"검증 원점 {e['originsN']}개로 최소 {required}개 미달")
    if e['nonoverlapN'] < 8:
        reasons.append(f"비중첩 시간 구간 {e['nonoverlapN']}개로 최소 8개 미달")
    if min(e['classCounts']) < 10:
        reasons.append('일부 방향의 실제 결과가 10개 미만')
    if not e['improvementCI'] or e['improvementCI'][0] <= 0:
        reasons.append('기준 대비 Brier 개선의 95% 구간 하한이 0 이하이거나 산출 불가')
    if e['logLoss'] is None or e['logLoss'] >= e['baselineLogLoss']:
        reasons.append('로그손실이 과거 빈도 기준보다 개선되지 않음')
    if e['ece'] is None or e['ece'] > .1:
        reasons.append('보정 구간의 평균 확률·실제 빈도 차이가 10%p 초과이거나 평가 불가')
    return {'passed': not reasons, 'reasons': reasons}


def latest_forecast(series, samples, selection, training_samples):
    if not samples:
        return None
    latest = max(samples, key=lambda r: r['origin'])
    # Latest model may use all labels known strictly before this origin's availability.
    training = mature_training(training_samples, latest['available'])
    if not sufficient(training, series['frequency']):
        return None
    model = fit_model(training, selection['candidate'])
    p = temperature(model.predict_proba([latest['x']])[0], selection['temperature']).tolist()
    return {'origin': latest['origin'], 'availableAt': latest['available'], 'target': latest['target'],
            'quoteDate':next(p['quoteDate'] for p in series['points'] if p['date']==latest['origin']),
            'price': latest['price'], 'probabilities': p, 'model': NAMES[selection['candidate']],
            'temperature': selection['temperature'], 'trainN': len(training),
            'trainThrough': max(r['targetAvailable'] for r in training), 'available': True,
            'missingFeatures': latest['missingFeatures']}


def load_sources(minimum=5):
    base = ROOT / 'data/feasibility/2026-10-21/alternatives'
    records = json.loads((base/'requests.json').read_text())['pricehistory_products']
    records += json.loads((base/'extra_gpu_requests.json').read_text())
    series, exclusions, input_hashes = [], [], {}
    for r in records:
        f = base/'raw'/r['raw_file']
        data = json.loads(f.read_text())
        region = 'US' if r['store']=='amazon.com' else 'IN'
        category = 'GPU' if r['category'].startswith('GPU') else r['category']
        sid = region+'_'+r['asin']
        quotes, excluded = normalize_quotes(data['History']['Price'], sid, minimum if r['currency']=='USD' else 0)
        points = weekly_grid(quotes)
        input_hashes[str(f.relative_to(ROOT))] = sha(f)
        series.append({'id': sid, 'category': category, 'name': r['name'], 'region': region,
                       'currency': r['currency'], 'condition': 'renewed' if 'RENEWED' in r['category'] else 'new',
                       'frequency': 'weekly', 'sourceUrl': r['product_url'], 'rawFile': str(f.relative_to(ROOT)),
                       'points': points, 'rawN': len(data['History']['Price']), 'excludedN': len(excluded),
                       'limitations': ['원문은 불규칙한 Amazon 등록 호가이며 실제 거래·배송·세금·재고는 미확인입니다.',
                                       '원문 시간대 미확인. 표시 날짜를 그대로 주에 배정했습니다.',
                                       '해외 개별 SKU의 확률을 국내 제품의 구매 추천으로 이전하지 않습니다.']})
        exclusions.extend(excluded)
    extended = ROOT/'data/verification/2026-10-23/forecast/overseas_extended/series.json'
    if extended.exists():
        input_hashes[str(extended.relative_to(ROOT))] = sha(extended)
        extension_document=json.loads(extended.read_text())
        for r in extension_document['series']:
            quotes, excluded = normalize_quotes(r['observations'], r['id'], minimum if r['currency']=='USD' else 0)
            f = ROOT/r['rawFile']
            if not f.exists():
                f = extended.parent/r['rawFile']
            assert sha(f) == r['sha256'], f'Hash mismatch {f}'
            input_hashes[str(f.relative_to(ROOT))] = sha(f)
            series.append({k:v for k,v in r.items() if k not in ['observations','sha256']} | {
                'rawFile':str(f.relative_to(ROOT)),
                'frequency':'weekly', 'points':weekly_grid(quotes), 'rawN':len(r['observations']),
                'excludedN':len(excluded), 'priceBasis':extension_document.get('priceBasis'),
                'limitations':r.get('limitations',[]) + ['해외 확률을 국내 SKU 추천으로 대체하지 않습니다.',
                 'Amazon/Flipkart 등록 호가. 배송비·세금·판매자·재고·실제 거래 여부 미확인.',r.get('same_sku_note','포장·세부 옵션의 국내 SKU 일치 여부 미확인')]})
            exclusions.extend(excluded)
    domestic = json.loads((WEB/'domestic.json').read_text())
    products = {p['id']:p for p in domestic['products']+domestic['marketReferences']}
    for filename in ['cpu_gpu_history.json','ram_ssd_history.json']:
        f = ROOT/'data/verification/2026-10-23/timing'/filename
        input_hashes[str(f.relative_to(ROOT))] = sha(f)
        for r in json.loads(f.read_text())['products']:
            raw = ROOT/r['rawFile']
            assert sha(raw)==r['sha256'], f'Hash mismatch {raw}'
            input_hashes[str(raw.relative_to(ROOT))]=sha(raw)
            for i,point in enumerate(r['monthly']):
                if point.get('partial'):
                    exclusions.append({'series':'KR_'+r['id'],'row':i,'date':point['date'],
                                       'price':point['price'],'reason':'partial_month'})
            series.append({'id':'KR_'+r['id'], 'domesticId':r['id'], 'category':r['category'],
                           'name':products[r['id']]['shortName'], 'region':'KR', 'currency':'KRW', 'condition':'new',
                           'frequency':'monthly', 'sourceUrl':r['sourceUrl'], 'rawFile':r['rawFile'],
                           'points':monthly_grid(r['monthly']), 'rawN':len(r['monthly']),
                           'excludedN':sum(bool(p.get('partial')) for p in r['monthly']),
                           'limitations':['국내 동일 가격 정의 21개 SKU 패널 학습. 제품별 단독 모형이 아닙니다.',
                                           '학습 행은 SKU×월이며 동일 칩 보드와 공통 수요 충격을 공유합니다. 행 수가 독립 경기 구간 수는 아닙니다.',
                                           '원문 월간 minPrice는 월평균·월말가·배송/할인 포함 기준이 확인되지 않았습니다.',
                                           '부분월 제외. 완료 월에서 3개월 뒤의 버킷 예측이며 오늘부터 3개월 예측이 아닙니다.',
                                           '현재 배송 포함 3몰 중앙값과 연결하거나 미래 원화 견적으로 표시하지 않습니다.']})
    archive_file=ROOT/'data/verification/2026-10-23/forecast/domestic_extended/extended_history.json'
    if archive_file.exists():
        input_hashes[str(archive_file.relative_to(ROOT))]=sha(archive_file)
        archive=json.loads(archive_file.read_text())
        for product in archive['products']:
            selected=next(s for s in series if s.get('domesticId')==product['id'])
            selected['archivedObservations']=[]
            selected['quarantinedArchives']=[]
            for a in product['wayback_anchors']:
                f=ROOT/a['raw_file']
                assert sha(f)==a['sha256'],f'Archive hash mismatch {f}'
                input_hashes[str(f.relative_to(ROOT))]=sha(f)
                text=f.read_text(errors='replace')  # archived pages have mixed Korean encodings; numeric attributes are ASCII
                hidden=re.search(r'id="min_price_'+product['id']+r'"\s+value="(\d+)"',text)
                assert hidden and int(hidden.group(1))==a['ordinary_lowest_krw']
                assert a['same_sku'] and a['same_sku_title_match']
                # All accepted archive points require a second structured price.
                # 2020 DDR4's hidden value is the cash price, unlike OG ordinary.
                if a['lowprice_json_ld']!=a['ordinary_lowest_krw']:
                    selected['quarantinedArchives'].append({**a,'exclusionReason':'일반·현금 가격 기준 충돌 또는 JSON-LD 재확인 불가'})
                    exclusions.append({'series':'KR_'+product['id'],'row':a['archive_timestamp'],
                                       'date':a['anchor_date'],'price':a['ordinary_lowest_krw'],
                                       'reason':'archive_price_basis_conflict_quarantined'})
                    continue
                selected['archivedObservations'].append(a)
                exclusions.append({'series':'KR_'+product['id'],'row':a['archive_timestamp'],
                                   'date':a['anchor_date'],'price':a['ordinary_lowest_krw'],
                                   'reason':'archived_quote_different_price_basis_not_training'})
    return series, exclusions, input_hashes


def run(series,selection_audit=None):
    samples_by_id, failures = {}, {}
    for s in series:
        samples_by_id[s['id']], failures[s['id']] = make_samples(s)
    domestic = [r for s in series if s['region']=='KR' for r in samples_by_id[s['id']]]
    domestic_rows = rolling_predictions(domestic, 'monthly', 'logistic') if domestic else []
    results, all_predictions = [], []
    for s in series:
        samples = samples_by_id[s['id']]
        if s['region']=='KR':
            choice = {'status':'fixed_unselected','candidate':'logistic','temperature':1.,'n':0,'validationLogLoss':None}
            predictions = [r for r in domestic_rows if r['id']==s['id']]
            training_samples = domestic
        else:
            candidates = {c:rolling_predictions(samples, s['frequency'], c) for c in CANDIDATES}
            if selection_audit is not None:
                for candidate,rows in candidates.items():
                    selection_audit.extend({**r,'selectionEligible':r['targetAvailable']<='2024-12-31'}
                                           for r in rows if r['origin']<'2025-01-01')
            choice = choose_model(candidates, s['frequency'])
            predictions = candidates[choice['candidate']]
            training_samples = samples
        final = apply_temperature([r for r in predictions if r['origin'] >= '2025-01-01'], choice['temperature'])
        e = evaluate(final, s['frequency'])
        g = gates(e, s['frequency'])
        f = latest_forecast(s, samples, choice, training_samples)
        if s['frequency']=='monthly':
            g['passed']=False
            g['reasons'].append('완료 월 버킷 예측으로 오늘부터 3개월 구매 판단과 목표가 다름')
        if f and (AS_OF-date.fromisoformat(f.get('quoteDate') or f['origin'])).days > (14 if s['frequency']=='weekly' else 62):
            g['passed']=False
            g['reasons'].append('최신 원점이 오래되어 현재 구매 신호로 사용할 수 없음')
        if not f:
            g['passed']=False
            g['reasons'].append('최신 학습 표본 또는 원점 특징 부족으로 현재 확률 미산출')
        p = s['points']
        observed=[r for r in p if valid_price(r['price'])]
        out = {k:v for k,v in s.items() if k not in ['rawN','excludedN']}
        out.update({'coverage':{'rawN':s['rawN'],'observed':len(observed),'total':len(p),
                                'first':observed[0]['date'] if observed else None,
                                'last':observed[-1]['date'] if observed else None,'excludedN':s['excludedN']},
                    'selection':choice,'evaluation':e,'gates':g,'forecast':f,'backtests':final,
                    'sampleExclusions':failures[s['id']]})
        results.append(out)
        all_predictions.extend(final)
        print(s['id'],s['name'], 'observed',len(observed),'test',e['n'],'origins',e['originsN'],
              'BSS',round(e['brierSkill'],3) if e['brierSkill'] is not None else None,'passed',g['passed'],flush=True)
    return results, all_predictions


def write_csv(path, rows, fields):
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    downloads=WEB/'downloads';downloads.mkdir(exist_ok=True)
    series, exclusions, hashes = load_sources()
    selection_audit=[]
    results, predictions = run(series,selection_audit)
    sensitivity=[]
    # Repeat the prespecified pipeline with no absolute floor; only affected SKU.
    raw_series, _, _ = load_sources(minimum=0)
    for raw in raw_series:
        original=next(s for s in series if s['id']==raw['id'])
        if raw['excludedN'] != original['excludedN']:
            raw_result,_=run([raw])
            sensitivity.append({'id':raw['id'],'withFloor':next(r for r in results if r['id']==raw['id'])['evaluation'],
                                'withoutFloor':raw_result[0]['evaluation'],
                                'withoutFloorForecast':raw_result[0]['forecast']})
    document={'schemaVersion':1,'asOf':AS_OF.isoformat(),'protocolUrl':'./data/downloads/forecast_protocol.md',
              'series':results,'inputHashes':hashes,'sensitivity':sensitivity,
              'totals':{'series':len(results),'observed':sum(s['coverage']['observed'] for s in results),
                        'backtests':len(predictions),'passed':sum(s['gates']['passed'] for s in results),
                        'archiveQuotes':sum(len(s.get('archivedObservations',[])) for s in results),
                        'quarantinedArchives':sum(len(s.get('quarantinedArchives',[])) for s in results)},
              'limitations':['현재 조회한 이력 스냅샷의 회고 검증이며 당시 수집본에 의한 실시간 실험은 아닙니다.',
                             '중첩된 3개월 정답·동일 경기 구간을 독립 표본으로 보지 않습니다.',
                             'Wilson 구간은 보정 빈도의 기술 통계이며 시간 의존성을 반영한 보정 보증 구간이 아닙니다.',
                             '수집 관측이 있는 주만 대상으로 하므로 품절·추적 중단과 관련된 결측 선택 편향이 남습니다.',
                             '원자료 날짜/가격은 보간하지 않습니다. 결측 특징의 학습 집합 중앙값 대체와 구분합니다.']}
    encoded=json.dumps(document,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
    (OUT/'forecast.json').write_text(encoded);(WEB/'forecast.json').write_text(encoded)
    flat=[]
    for r in predictions:
        flat.append({**r,'p_down':r['probabilities'][0],'p_flat':r['probabilities'][1],'p_up':r['probabilities'][2],
                     'base_down':r['baseline'][0],'base_flat':r['baseline'][1],'base_up':r['baseline'][2]})
    fields=['id','origin','available','target','targetAvailable','fitCutoff','trainThrough','trainN','candidate',
            'missingFeatures','price','actualClass','actualChange','predictedChange','driftChange',
            'p_down','p_flat','p_up','base_down','base_flat','base_up']
    write_csv(OUT/'forecast_predictions.csv',flat,fields)
    audit_rows=[{**r,'p_down':r['probabilities'][0],'p_flat':r['probabilities'][1],
                 'p_up':r['probabilities'][2],'base_down':r['baseline'][0],
                 'base_flat':r['baseline'][1],'base_up':r['baseline'][2]} for r in selection_audit]
    write_csv(OUT/'forecast_selection_predictions.csv',audit_rows,
              ['id','origin','available','target','targetAvailable','fitCutoff','trainThrough','trainN',
               'candidate','selectionEligible','change','y','p_down','p_flat','p_up','base_down','base_flat','base_up'])
    write_csv(OUT/'forecast_weekly.csv',[{'id':s['id'],'frequency':s['frequency'],'region':s['region'],
              'currency':s['currency'],**p} for s in results for p in s['points']],
              ['id','frequency','region','currency','date','price','quoteDate'])
    write_csv(OUT/'forecast_metrics.csv',[{'id':s['id'],'name':s['name'],**s['evaluation'],
              'passed':s['gates']['passed'],'reasons':'; '.join(s['gates']['reasons'])} for s in results],
              ['id','name','n','originsN','nonoverlapN','from','to','brier','baselineBrier','brierSkill','logLoss',
               'baselineLogLoss','accuracy','ece','mae','naiveMae','driftMae','passed','reasons'])
    write_csv(OUT/'excluded_observations.csv',exclusions,['series','row','date','price','reason'])
    for name in ['forecast_predictions.csv','forecast_weekly.csv','forecast_metrics.csv','excluded_observations.csv','forecast_selection_predictions.csv','forecast.json']:
        shutil.copyfile(OUT/name,downloads/name)
    archive_rows=[{'series':s['id'],**a,'status':'reference_only_not_model'} for s in results for a in s.get('archivedObservations',[])]
    archive_rows += [{'series':s['id'],**a,'raw_extracted_price':a['ordinary_lowest_krw'],
                      'ordinary_lowest_krw':None,'status':'quarantined_price_basis_conflict'}
                     for s in results for a in s.get('quarantinedArchives',[])]
    write_csv(OUT/'forecast_domestic_archives.csv',archive_rows,
              ['series','anchor_date','ordinary_lowest_krw','cash_lowest_krw','delivered_krw','status',
               'raw_extracted_price','evidence_meta_ordinary_krw','source_url','sha256','exclusionReason'])
    shutil.copyfile(OUT/'forecast_domestic_archives.csv',downloads/'forecast_domestic_archives.csv')
    shutil.copyfile(ROOT/'docs/forecast_protocol.md',downloads/'forecast_protocol.md')
    (OUT/'source_hashes.json').write_text(json.dumps(hashes,indent=2)+'\n')
    print(json.dumps(document['totals']))


if __name__=='__main__':
    main()
