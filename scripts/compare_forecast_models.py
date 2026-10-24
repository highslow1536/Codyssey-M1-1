"""Offline expansion of the frozen three-month benchmark; never tune on test.

Private per-origin forecasts stay in data/analysis. Only non-reconstructive
per-series aggregate scores are exported to data/public for redistribution.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date
import hashlib
import json
import math
from pathlib import Path
import shutil
import warnings

import numpy as np
from scipy.stats import norm
from statsmodels.tsa.statespace.sarimax import SARIMAX
from statsmodels.tsa.statespace.exponential_smoothing import ExponentialSmoothing

try:
    from scripts import build_forecast as bf
except ModuleNotFoundError:
    import build_forecast as bf

ROOT = bf.ROOT
OUT = ROOT / 'data/analysis/2026-10-24/model_comparison'
MODELS = ['logistic', 'forest', 'arima', 'sarima', 'ets']
NAMES = {**bf.NAMES, 'arima': 'ARIMA(1,1,0) + drift',
         'sarima': 'SARIMA(1,1,0)(1,0,0,s)', 'ets': 'ETS(A,Ad,N) · log price',
         'baseline': '과거 방향 빈도 / 가격 유지'}
TS_MODELS = ['arima', 'sarima', 'ets']


def observation_available(point, frequency):
    d = date.fromisoformat(point['date'])
    return bf.add_months(d, 1).isoformat() if frequency == 'monthly' else point['date']


def prefix_before(points, frequency, cutoff):
    return [p for p in points if observation_available(p, frequency) < cutoff]


def eligibility(values, frequency, candidate):
    seasonal = 52 if frequency == 'weekly' else 12
    minimum_grid, minimum_observed = (52, 40) if frequency == 'weekly' else (12, 10)
    if len(values) < minimum_grid or np.isfinite(values).sum() < minimum_observed:
        return 'insufficient_history'
    if candidate == 'sarima':
        if len(values) < 2 * seasonal:
            return 'fewer_than_two_seasonal_cycles'
        # Coverage of each of the last two calendar cycles, not compressed data.
        if any(np.isfinite(values[-k*seasonal:len(values)-(k-1)*seasonal]).sum() < math.ceil(.75*seasonal)
               for k in (1, 2)):
            return 'sparse_seasonal_cycles'
    return None


def log_values(points):
    return np.asarray([math.log(p['price']) if bf.valid_price(p['price']) else np.nan for p in points])


def fit_price_model(values, frequency, candidate):
    if candidate == 'ets':
        adjacent = np.diff(values)
        trend = float(np.nanmedian(adjacent)) if np.isfinite(adjacent).any() else 0.
        model = ExponentialSmoothing(values, trend=True, damped_trend=True,
                                     initialization_method='known', initial_level=float(values[np.isfinite(values)][0]),
                                     initial_trend=trend)
    else:
        period = 52 if frequency == 'weekly' else 12
        model = SARIMAX(values, order=(1, 1, 0),
                        seasonal_order=(1, 0, 0, period) if candidate == 'sarima' else (0, 0, 0, 0),
                        trend='n' if candidate == 'sarima' else 'c',
                        enforce_stationarity=True, enforce_invertibility=True)
    recorded = []
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        fitted = model.fit(disp=False, maxiter=100, cov_type='none')
        if not fitted.mle_retvals.get('converged', False):
            # Fixed deterministic retry, never selected according to forecast scores.
            fitted = model.fit(start_params=fitted.params, disp=False, maxiter=200, cov_type='none')
        recorded = sorted({type(w.message).__name__ for w in caught})
    if not fitted.mle_retvals.get('converged', False):
        raise ValueError('nonconverged_fit')
    if not np.isfinite(fitted.params).all() or not math.isfinite(fitted.llf):
        raise ValueError('nonfinite_fit')
    return fitted, recorded


def distribution(mu, variance, price):
    """Conditional Gaussian log-price distribution, not calibrated certainty."""
    if not all(math.isfinite(v) for v in (mu, variance, price)) or variance <= 0 or price <= 0:
        raise ValueError('invalid_predictive_distribution')
    sd = math.sqrt(variance)
    lower = norm.cdf((math.log(price * .97) - mu) / sd)
    upper = norm.cdf((math.log(price * 1.03) - mu) / sd)
    p = np.clip([lower, upper - lower, 1 - upper], 1e-12, 1)
    p /= p.sum()
    # Fail visibly instead of silently clipping explosive point forecasts.
    point = math.exp(mu) / price - 1
    intervals = {}
    for coverage in (.8, .95):
        z = norm.ppf((1 + coverage) / 2)
        intervals[str(int(coverage * 100))] = [math.exp(mu-z*sd)/price-1, math.exp(mu+z*sd)/price-1]
    if not np.isfinite([point] + [v for pair in intervals.values() for v in pair]).all():
        raise ValueError('nonfinite_price_forecast')
    return p.tolist(), point, intervals


def rolling_price_predictions(series, samples, candidate):
    points, frequency = series['points'], series['frequency']
    groups = defaultdict(list)
    for sample in samples:
        if sample['available'] >= '2023-01-01':
            groups[bf.quarter(sample['available'])].append(sample)
    results, failures, fits = [], Counter(), []
    by_date = {p['date']: i for i, p in enumerate(points)}
    for cutoff, targets in sorted(groups.items()):
        prefix = prefix_before(points, frequency, cutoff)
        values = log_values(prefix)
        reason = eligibility(values, frequency, candidate)
        if reason:
            failures[reason] += len(targets)
            fits.append({'cutoff': cutoff, 'status': 'excluded', 'reason': reason,
                         'gridN': len(prefix), 'observedN': int(np.isfinite(values).sum()),
                         'requestedOriginsN': len(targets)})
            continue
        try:
            fitted, warning_names = fit_price_model(values, frequency, candidate)
        except (ValueError, np.linalg.LinAlgError, FloatingPointError, OverflowError) as exc:
            reason = str(exc) if str(exc) in ('nonconverged_fit', 'nonfinite_fit') else type(exc).__name__
            failures[reason] += len(targets)
            fits.append({'cutoff': cutoff, 'status': 'failed', 'reason': reason,
                         'gridN': len(prefix), 'observedN': int(np.isfinite(values).sum()),
                         'requestedOriginsN': len(targets)})
            continue
        fits.append({'cutoff': cutoff, 'trainThrough': observation_available(prefix[-1], frequency),
                     'gridN': len(prefix), 'observedN': int(np.isfinite(values).sum()),
                     'warnings': warning_names, 'converged': True, 'status': 'converged',
                     'requestedOriginsN': len(targets)})
        for sample in targets:
            i = by_date[sample['origin']]
            assert observation_available(points[i], frequency) == sample['available']
            horizon = ((date.fromisoformat(sample['target'])-date.fromisoformat(sample['origin'])).days // 7
                       if frequency == 'weekly' else 3)
            try:
                # Apply fixed quarter parameters to the prefix through this origin.
                # Internal Kalman predictions at NaN dates are never observations.
                with warnings.catch_warnings():
                    warnings.simplefilter('ignore', category=RuntimeWarning)
                    # statsmodels 0.14's ETS clone omits known initialization
                    # arguments; supply the SAME quarter initialization explicitly.
                    init = ({'initial_level': fitted.model._initial_level,
                             'initial_trend': fitted.model._initial_trend}
                            if candidate == 'ets' else {})
                    current = fitted.apply(log_values(points[:i+1]), refit=False, copy_initialization=True, **init)
                    forecast = current.get_forecast(steps=horizon)
                mu = float(np.asarray(forecast.predicted_mean)[-1])
                variance = float(np.asarray(forecast.var_pred_mean)[-1])
                p, point, intervals = distribution(mu, variance, sample['price'])
            except (ValueError, np.linalg.LinAlgError, FloatingPointError, OverflowError) as exc:
                failures[str(exc) if str(exc) == 'invalid_predictive_distribution' else type(exc).__name__] += 1
                continue
            r = {k: v for k, v in sample.items() if k != 'x'}
            results.append({**r, 'candidate': candidate, 'probabilities': p, 'predictedChange': point,
                            'actualChange': sample['change'], 'actualClass': sample['y'],
                            'intervals': intervals, 'logMean': mu, 'logVariance': variance,
                            'trainN': int(np.isfinite(values).sum()), 'trainThrough': fits[-1]['trainThrough'],
                            'fitCutoff': cutoff, 'stateThrough': sample['available']})
    return results, dict(failures), fits


def calibrated(rows, t):
    out = []
    for row in rows:
        r = dict(row)
        r['probabilities'] = bf.temperature(r['probabilities'], t).tolist()
        if r['candidate'] not in TS_MODELS:
            r['predictedChange'] = float(np.dot(r['probabilities'], r['classMedians']))
        r.update(actualClass=r['y'], actualChange=r['change'])
        out.append(r)
    return out


def is_selection(r):
    return r['origin'] < '2025-01-01' and r['targetAvailable'] <= '2024-12-31' and r['y'] is not None


def common_rows(predictions, phase, candidates=None):
    predicate = is_selection if phase == 'selection' else lambda r: r['origin'] >= '2025-01-01' and r['y'] is not None
    maps = {c: {r['origin']: r for r in rows if predicate(r)} for c, rows in predictions.items()
            if candidates is None or c in candidates}
    active = [c for c, rows in maps.items() if rows]
    origins = set.intersection(*(set(maps[c]) for c in active)) if active else set()
    return {c: [maps[c][o] for o in sorted(origins)] for c in active}, active


def select_model(predictions, incumbent):
    eligible = [c for c, rows in predictions.items()
                if sum(is_selection(r) for r in rows) >= 24]
    paired, active = common_rows(predictions, 'selection', eligible)
    example = next(iter(paired.values()), [])
    n = len(example)
    if n < 24 or len({r['y'] for r in example}) < 3:
        return {**incumbent, 'status': 'incumbent_retained_insufficient_selection', 'n': n,
                'validationLogLoss': None, 'reason': '같은 과거 원점 24개·세 방향 결과가 부족해 기존 선택 유지',
                'comparisonCandidates': active, 'options': []}, paired
    options = []
    for candidate, rows in paired.items():
        for t in bf.TEMPERATURES:
            p = bf.temperature([r['probabilities'] for r in rows], t)
            loss = -float(np.mean([math.log(p[i, r['y']]) for i, r in enumerate(rows)]))
            options.append({'candidate': candidate, 'temperature': t, 'n': n, 'logLoss': loss})
    winner = min(options, key=lambda r: (r['logLoss'], MODELS.index(r['candidate']), r['temperature']))
    return {**winner, 'status': 'past_validation_only', 'validationLogLoss': winner['logLoss'],
            'reason': '2023–2024년 공통 원점 로그손실 최소; 2025–2026년 점수로 선택하지 않음',
            'comparisonCandidates': active, 'options': options}, paired


def scores(rows, frequency):
    e = bf.evaluate(rows, frequency)
    e['rmse'] = float(np.sqrt(np.mean([(r['predictedChange']-r['change'])**2 for r in rows]))) if rows else None
    intervals = [r for r in rows if r.get('intervals')]
    e['intervalN'] = len(intervals)
    for size in (80, 95):
        e[f'interval{size}Coverage'] = (float(np.mean([r['intervals'][str(size)][0] <= r['change'] <= r['intervals'][str(size)][1]
                                                   for r in intervals])) if intervals else None)
    return e


def cached_price_predictions(series, samples, candidate):
    cache = OUT / 'cache'
    cache.mkdir(parents=True, exist_ok=True)
    source = Path(__file__).read_bytes()
    key = hashlib.sha256(source + json.dumps([series['points'], series['frequency'], candidate], sort_keys=True).encode()).hexdigest()
    path = cache / (series['id'] + '_' + candidate + '.json')
    if path.exists():
        stored = json.loads(path.read_text())
        if stored['key'] == key:
            return stored['rows'], stored['failures'], stored['fits']
    rows, failures, fits = rolling_price_predictions(series, samples, candidate)
    path.write_text(json.dumps({'key': key, 'rows': rows, 'failures': failures, 'fits': fits}, allow_nan=False))
    return rows, failures, fits


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    legacy_path = bf.OUT / 'forecast.json'
    # A stable source snapshot retains the prior two-model benchmark.
    legacy_snapshot = OUT / 'legacy_forecast.json'
    if not legacy_snapshot.exists():
        shutil.copyfile(legacy_path, legacy_snapshot)
    legacy = json.loads(legacy_snapshot.read_text())
    sources, _, hashes = bf.load_sources()
    samples_by_id = {s['id']: bf.make_samples(s)[0] for s in sources}
    domestic = [r for s in sources if s['region'] == 'KR' for r in samples_by_id[s['id']]]
    panel = {c: bf.rolling_predictions(domestic, 'monthly', c) for c in ('logistic', 'forest')}
    aggregates, audit, selected_results = [], [], []
    for original in legacy['series']:
        s = next(s for s in sources if s['id'] == original['id'])
        samples = samples_by_id[s['id']]
        candidates = {c: ([r for r in panel[c] if r['id'] == s['id']] if s['region'] == 'KR'
                          else bf.rolling_predictions(samples, s['frequency'], c)) for c in ('logistic', 'forest')}
        failures, fit_audit, standalone_counts = {}, {}, {}
        reference = {r['origin']: r for r in candidates['logistic']}
        for c in TS_MODELS:
            rows, failures[c], fit_audit[c] = cached_price_predictions(s, samples, c)
            standalone_counts[c] = sum(r['origin'] >= '2025-01-01' and r['y'] is not None
                                       and r['origin'] not in reference for r in rows)
            # Baselines and evaluation universe are exactly those of the existing model.
            candidates[c] = [{**r, 'baseline': reference[r['origin']]['baseline'],
                              'driftChange': reference[r['origin']]['driftChange']}
                             for r in rows if r['origin'] in reference]
        incumbent = {k: original['selection'][k] for k in ('candidate', 'temperature')}
        choice, validation = select_model(candidates, incumbent)
        common, active = common_rows(candidates, 'test')
        example = next(iter(common.values()), [])
        model_metrics = []
        for c in MODELS:
            t = choice['temperature'] if choice['candidate'] == c else incumbent['temperature'] if incumbent['candidate'] == c else 1.
            # Each contender's temperature is selected only on the SAME validation dates.
            options = [r for r in choice['options'] if r['candidate'] == c]
            if options:
                t = min(options, key=lambda r: (r['logLoss'], r['temperature']))['temperature']
            selected_val = calibrated(validation.get(c, []), t)
            selected_test = calibrated(common.get(c, []), t)
            reasons = []
            if c == 'sarima' and s['frequency'] == 'monthly':
                reasons.append('국내 완료 월 최대 22개: 연간 12개월 주기의 2회 반복에 미달')
            if not selected_test:
                reasons.append('공통 평가 가능한 예측 없음; 0점으로 해석하지 않음')
                if standalone_counts.get(c, 0):
                    reasons.append(f'시계열 단독 산출 {standalone_counts[c]}건 중 기존 분류 모형과 비교 가능한 공통 원점 없음')
            model_metrics.append({'candidate': c, 'name': NAMES[c], 'temperature': t,
                                  'status': 'evaluated' if selected_test else 'unavailable', 'reasons': reasons,
                                  'failures': failures.get(c, {}),
                                  'selection': scores(selected_val, s['frequency']),
                                  'evaluation': scores(selected_test, s['frequency']),
                                  'standaloneTestN': standalone_counts.get(c),
                                  'allTestN': sum(r['origin'] >= '2025-01-01' and r['y'] is not None for r in candidates[c])})
        baseline_rows = [{**r, 'candidate': 'baseline', 'probabilities': r['baseline'], 'predictedChange': 0., 'intervals': None}
                         for r in example]
        model_metrics.append({'candidate': 'baseline', 'name': NAMES['baseline'], 'status': 'evaluated' if example else 'unavailable',
                              'reasons': [], 'failures': {}, 'selection': {}, 'evaluation': scores(baseline_rows, s['frequency'])})
        selected_full = calibrated([r for r in candidates[choice['candidate']] if r['origin'] >= '2025-01-01'], choice['temperature'])
        e = scores(selected_full, s['frequency'])
        updated = dict(original)
        updated.update(selection=choice, evaluation=e, gates=bf.gates(e, s['frequency']), backtests=selected_full)
        if choice['candidate'] in TS_MODELS:
            latest_rows, _, _ = cached_price_predictions(s, samples, choice['candidate'])
            latest = max(latest_rows, key=lambda r: r['origin']) if latest_rows else None
            if latest:
                latest = calibrated([latest], choice['temperature'])[0]
                updated['forecast'] = {'origin': latest['origin'], 'availableAt': latest['available'], 'target': latest['target'],
                    'quoteDate': next(p['quoteDate'] for p in s['points'] if p['date'] == latest['origin']),
                    'price': latest['price'], 'probabilities': latest['probabilities'], 'model': NAMES[choice['candidate']],
                    'temperature': choice['temperature'], 'trainN': latest['trainN'], 'trainThrough': latest['trainThrough'],
                    'available': True, 'missingFeatures': latest['missingFeatures'], 'predictedChange': latest['predictedChange'],
                    'intervals': latest['intervals']}
            else:
                updated['forecast'] = None
        elif choice['candidate'] != incumbent['candidate'] or choice['temperature'] != incumbent['temperature']:
            updated['forecast'] = bf.latest_forecast(s, samples, choice, domestic if s['region'] == 'KR' else samples)
        if s['frequency'] == 'monthly':
            updated['gates']['passed'] = False
            updated['gates']['reasons'].append('완료 월 버킷으로 오늘부터 3개월 구매 판단과 목표가 다름')
        f = updated['forecast']
        if not f:
            updated['gates']['passed'] = False
            updated['gates']['reasons'].append('최신 예측 산출 불가')
        elif (bf.AS_OF-date.fromisoformat(f.get('quoteDate') or f['origin'])).days > (14 if s['frequency'] == 'weekly' else 62):
            updated['gates']['passed'] = False
            updated['gates']['reasons'].append('최신 원점이 오래되어 현재 구매 신호로 사용할 수 없음')
        paired_selected = next(m['evaluation'] for m in model_metrics if m['candidate'] == choice['candidate'])
        aggregates.append({'id': s['id'], 'name': s['name'], 'region': s['region'], 'frequency': s['frequency'],
                           'coverage': original['coverage'], 'incumbent': incumbent,
                           'legacyEvaluation': original['evaluation'], 'selection': choice,
                           'common': {'selectionN': choice['n'], 'testN': len(example), 'nonoverlapN': bf.nonoverlap_count(example),
                                      'from': min((r['origin'] for r in example), default=None),
                                      'to': max((r['origin'] for r in example), default=None), 'candidates': active},
                           'models': model_metrics, 'selectedEvaluation': paired_selected,
                           'selectedAllEvaluation': e, 'gates': updated['gates']})
        selected_results.append(updated)
        audit.extend({**r, 'temperature': next(m.get('temperature', 1) for m in model_metrics if m['candidate'] == c)}
                     for c, rows in candidates.items() for r in rows)
        (OUT / (s['id'] + '_fits.json')).write_text(json.dumps(fit_audit, indent=2))
        print(s['id'], 'common test', len(example), 'selection', choice['n'], 'chosen', choice['candidate'],
              'failures', failures, flush=True)
    limitations = [
        '2025–2026년 결과를 이미 살펴본 뒤 후보를 확장한 회고 비교입니다. 새 미관측 홀드아웃이나 실시간 성과가 아닙니다.',
        '모형·온도는 2023–2024년 공통 과거 원점에서만 선택합니다. 선택 표본 부족 시 기존 모형을 유지하며 시험 점수의 최저 모형으로 교체하지 않습니다.',
        '국내 7–22개월 자료는 연간 계절성 두 주기도 충족하지 않습니다. SARIMA 제외를 성능 열위로 읽지 않습니다.',
        '각 SKU에서 산출 가능한 후보의 공통 원점만 비교하므로 기존 전체 평가보다 n이 작습니다. 후보별 전체 평가 가능 행 수와 실패 사유를 함께 기록합니다.',
        '전체 평가 allTestN도 기존 분류 모형이 산출한 평가 원점 범위 안의 수입니다. 그 밖에서 시계열 모형만 산출한 사례는 standaloneTestN에 기록하며 점수 비교·교체 근거에 쓰지 않습니다.',
        '3개월 목표가 겹치므로 n은 독립 표본 수가 아닙니다. 비중첩 시간 구간 수를 함께 봅니다.',
        '달력의 결측은 NaN으로 유지합니다. 칼만 필터의 내부 상태 예측은 관측 가격이나 정답으로 추가하지 않습니다.',
        'SARIMA는 주별 52주 주기 가정의 제한된 고정 차수 후보입니다. 모든 차수·계절주기·ETS 변형의 우열을 검증한 것은 아닙니다.',
        'ARIMA·SARIMA·ETS는 로그가격의 가우시안 예측 분포를 가정합니다. 확률 온도는 클래스 확률에만 적용하며 80/95% 가격구간은 원분포 구간입니다. 급변·두꺼운 꼬리·매개변수 추정 불확실성을 충분히 반영하지 못할 수 있습니다.',
        '분류 모형은 국내 패널/해외 SKU 학습이고 시계열 모형은 각 SKU의 관측 가격을 학습합니다. 학습 대상과 이용 가능한 정답 정보가 다르지만 예측 시점과 목표·평가 원점은 동일합니다.',
        '수렴 실패·이력 부족·결측이 많은 주기를 제외한 공통 표본에는 선택 편향이 남습니다. 미산출은 0점이 아닙니다.',
        '실패 사유별 건수는 2023년 이후 전체 산출 요청 원점 수이며, 선택·시험뿐 아니라 최신 미성숙 목표의 요청도 포함합니다. allTestN과 분모가 다릅니다.',
        '관측 스냅샷은 2026-10-23으로 고정되어 있습니다. 자동 갱신·미래 주가·ETH·재고·출시 정보는 사용하지 않습니다.'
    ]
    comparison = {'schemaVersion': 1, 'asOf': bf.AS_OF.isoformat(), 'generatedAt': '2026-10-24',
                  'protocol': {'selection': '2023–2024 origins, targets available by 2024-12-31',
                               'test': '2025–2026 matured targets; retrospective expansion',
                               'horizon': '3 calendar months; weekly first Friday on/after, monthly +3 buckets',
                               'comparison': 'per-SKU exact common origins', 'selectionMetric': 'logLoss',
                               'orders': {c: NAMES[c] for c in TS_MODELS}, 'seasonalPeriods': {'weekly': 52, 'monthly': 12}},
                  'summary': {'series': len(aggregates),
                              'selectionChanged': sum(s['selection']['candidate'] != s['incumbent']['candidate'] for s in aggregates),
                              'passed': sum(s['gates']['passed'] for s in aggregates),
                              'commonTestRows': sum(s['common']['testN'] for s in aggregates)},
                  'models': [{'id': c, 'name': NAMES[c]} for c in MODELS+['baseline']],
                  'series': aggregates, 'limitations': limitations}
    encoded = json.dumps(comparison, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    for path in (OUT/'model_comparison.json', ROOT/'data/public/model_comparison.json', bf.WEB/'model_comparison.json'):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(encoded)
    (OUT/'candidate_predictions.json').write_text(json.dumps(audit, ensure_ascii=False, allow_nan=False))
    new_document = {**legacy, 'series': selected_results, 'modelComparison': './data/model_comparison.json',
                    'limitations': legacy['limitations']+limitations,
                    'totals': {**legacy['totals'], 'backtests': sum(s['evaluation']['n'] for s in selected_results),
                               'passed': sum(s['gates']['passed'] for s in selected_results)}}
    for path in (legacy_path, bf.WEB/'forecast.json', bf.WEB/'downloads/forecast.json'):
        path.write_text(json.dumps(new_document, ensure_ascii=False, indent=2, allow_nan=False)+'\n')
    fields = ['id','name','n','originsN','nonoverlapN','from','to','brier','baselineBrier','brierSkill','logLoss',
              'baselineLogLoss','accuracy','ece','mae','naiveMae','driftMae','passed','reasons']
    rows = [{'id':s['id'],'name':s['name'], **s['evaluation'], 'passed': s['gates']['passed'],
             'reasons': '; '.join(s['gates']['reasons'])} for s in selected_results]
    bf.write_csv(bf.OUT/'forecast_metrics.csv', rows, fields)
    shutil.copyfile(bf.OUT/'forecast_metrics.csv', bf.WEB/'downloads/forecast_metrics.csv')
    predictions = [r for s in selected_results for r in s['backtests']]
    flat = [{**r, 'p_down': r['probabilities'][0], 'p_flat': r['probabilities'][1], 'p_up': r['probabilities'][2],
             'base_down': r['baseline'][0], 'base_flat': r['baseline'][1], 'base_up': r['baseline'][2]} for r in predictions]
    bf.write_csv(bf.OUT/'forecast_predictions.csv', flat,
                 ['id','origin','available','target','targetAvailable','fitCutoff','trainThrough','trainN','candidate',
                  'missingFeatures','price','actualClass','actualChange','predictedChange','driftChange',
                  'p_down','p_flat','p_up','base_down','base_flat','base_up'])
    shutil.copyfile(bf.OUT/'forecast_predictions.csv', bf.WEB/'downloads/forecast_predictions.csv')
    (OUT/'source_hashes.json').write_text(json.dumps(hashes, indent=2)+'\n')
    print(json.dumps(comparison['summary']), flush=True)
    return comparison


if __name__ == '__main__':
    build()
