"""Reproducible timing evidence. Historical trend is not a forecast probability.

Monthly median drift is evaluated at rolling origins against no change. Price
definitions remain separate; no current shop quote is appended to source history.
"""
from __future__ import annotations
import csv
import hashlib
import json
import math
from datetime import date, timedelta
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[1]
AS_OF = '2026-10-23'
THRESHOLD = .03


def month_index(value):
    year, month = map(int, value[:7].split('-'))
    return year * 12 + month - 1


def valid(value):
    return isinstance(value, (int, float)) and math.isfinite(value) and value > 0


def check_points(points):
    dates = [p['date'] for p in points]
    if len(set(dates)) != len(dates) or dates != sorted(dates):
        raise ValueError('Dates must be unique and sorted')
    return points


def forecast_at(monthly_points, origin_index, horizon_months=1):
    """Median of the last 3 one-month log returns, multiplied by horizon.

    Prefix-only: target values cannot enter features. Missing/partial months in
    the four required input observations invalidate the forecast.
    """
    if origin_index < 3 or horizon_months < 1:
        return None
    prefix = monthly_points[max(0, origin_index - 3):origin_index + 1]
    if len(prefix) != 4 or any(p.get('partial') or not valid(p.get('price')) for p in prefix):
        return None
    if any(month_index(b['date']) - month_index(a['date']) != 1 for a, b in zip(prefix, prefix[1:])):
        return None
    returns = [math.log(b['price'] / a['price']) for a, b in zip(prefix, prefix[1:])]
    return median(returns) * horizon_months


def quantile(values, q):
    if not values:
        return None
    values = sorted(values)
    x = (len(values) - 1) * q
    lo = int(x)
    return values[lo] + (values[math.ceil(x)] - values[lo]) * (x - lo)


def analyze_history(weekly, monthly, horizon_weeks=4):
    if horizon_weeks not in (4, 8, 12):
        raise ValueError('Supported horizons: 4, 8, 12 weeks')
    check_points(weekly)
    check_points(monthly)
    h = horizon_weeks
    by_date = {p['date']: p for p in weekly}
    last = weekly[-1] if weekly else None

    def change(days):
        if not last or not valid(last.get('price')):
            return None
        previous = by_date.get((date.fromisoformat(last['date']) - timedelta(days=days)).isoformat())
        return last['price'] / previous['price'] - 1 if previous and valid(previous.get('price')) else None

    changes = []
    historical = []
    for p in weekly:
        if not valid(p.get('price')):
            continue
        for days, target in ((7, changes), (h * 7, historical)):
            earlier = by_date.get((date.fromisoformat(p['date']) - timedelta(days=days)).isoformat())
            if earlier and valid(earlier.get('price')):
                target.append({'date': p['date'], 'change': p['price'] / earlier['price'] - 1})
    recent = changes[-4:]
    # Non-overlapping horizon intervals have distinct calendar windows.
    independent = []
    for point in historical:
        if not independent or (date.fromisoformat(point['date']) - date.fromisoformat(independent[-1]['date'])).days >= h * 7:
            independent.append(point)
    comparisons = {'n': len(historical), 'independentN': len(independent),
                   **{name: sum(fn(p['change']) for p in historical) for name, fn in {
                       'up': lambda x: x > THRESHOLD, 'down': lambda x: x < -THRESHOLD,
                       'flat': lambda x: abs(x) <= THRESHOLD}.items()}}
    # Monthly is a separate sensitivity experiment, not a 4-week price target.
    complete = [p for p in monthly if not p.get('partial')]
    month_map = {month_index(p['date']): (i, p) for i, p in enumerate(complete)}
    last_month = complete[-1] if complete else None

    def monthly_change(months):
        if not last_month or not valid(last_month.get('price')):
            return None
        previous = month_map.get(month_index(last_month['date']) - months)
        return last_month['price'] / previous[1]['price'] - 1 if previous and valid(previous[1].get('price')) else None
    hm = h // 4
    backtests = []
    for i, origin in enumerate(complete):
        prediction = forecast_at(complete, i, hm)
        target = month_map.get(month_index(origin['date']) + hm)
        if prediction is None or not target or not valid(target[1].get('price')):
            continue
        # Every intervening calendar month must be present and valid.
        if any(month_index(origin['date']) + k not in month_map or
               not valid(month_map[month_index(origin['date']) + k][1].get('price')) for k in range(1, hm + 1)):
            continue
        actual = math.log(target[1]['price'] / origin['price'])
        backtests.append({'origin': origin['date'], 'target': target[1]['date'],
                          'predictedChange': math.expm1(prediction), 'actualChange': math.expm1(actual),
                          'error': abs(math.expm1(prediction) - math.expm1(actual)),
                          'naiveError': abs(math.expm1(actual))})
    independent_tests = []
    for row in backtests:
        if not independent_tests or month_index(row['origin']) - month_index(independent_tests[-1]['origin']) >= hm:
            independent_tests.append(row)
    mae = sum(r['error'] for r in backtests) / len(backtests) if backtests else None
    naive_mae = sum(r['naiveError'] for r in backtests) / len(backtests) if backtests else None
    skill = 1 - mae / naive_mae if naive_mae else None
    validation = {'model': '직전 3개월 로그 변화율 중앙값 × 개월 수',
                  'horizonMonths': hm, 'n': len(backtests), 'independentN': len(independent_tests),
                  'mae': mae, 'naiveMae': naive_mae, 'skill': skill,
                  'probabilityAvailable': False,
                  'reason': '검증된 확률모형 없음. 월간 방향 검증 표본이 작고, 주간·월간 집계 정의도 불명확합니다.',
                  'minimumIndependentForProbabilityReview': 30,
                  'backtests': backtests}
    values = [p['price'] for p in weekly if valid(p.get('price'))]
    return {'horizonWeeks': h, 'lastDate': last['date'] if last else None,
            'lastPrice': last.get('price') if last else None,
            'weeklyN': len(values), 'weeklyTotal': len(weekly),
            'monthlyN': sum(valid(p.get('price')) for p in complete),
            'monthlyPartialN': sum(bool(p.get('partial')) for p in monthly),
            'longTrend': {'asOf': last_month['date'] if last_month else None,
                          'threeMonth': monthly_change(3), 'sixMonth': monthly_change(6),
                          'twelveMonth': monthly_change(12)},
            'weeklyRange': {'min': min(values) if values else None, 'max': max(values) if values else None,
                            'q25': quantile(values, .25), 'median': quantile(values, .5)},
            'trend': {'oneWeek': change(7), 'fourWeek': change(28),
                      'twelveWeek': change(84), 'elevenWeek': change(77),
                      'upWeeks': sum(p['change'] > 0 for p in recent),
                      'downWeeks': sum(p['change'] < 0 for p in recent),
                      'flatWeeks': sum(p['change'] == 0 for p in recent), 'intervals': len(recent)},
            'historyComparisons': comparisons, 'validation': validation}


def build():
    base = ROOT / 'data/verification/2026-10-23/timing'
    files = [base / 'cpu_gpu_history.json', base / 'ram_ssd_history.json']
    products = []
    for path in files:
        batch = json.loads(path.read_text())
        for p in batch['products']:
            if any(row['date'] > AS_OF for row in p['weekly']):
                raise ValueError('Future observation')
            p['analysis'] = {str(h): analyze_history(p['weekly'], p['monthly'], h) for h in (4, 8, 12)}
            products.append(p)
    domestic = json.loads((ROOT / 'dashboard/dist/data/domestic.json').read_text())
    all_ids = {p['id'] for p in domestic['products'] + domestic['marketReferences']}
    if {p['id'] for p in products} != all_ids or len(products) != len(all_ids):
        raise ValueError('Domestic history must cover every quoted SKU exactly once')
    output = {'schemaVersion': 1, 'asOf': AS_OF, 'products': products,
              'forecastStatus': 'unvalidated_probabilities_withheld',
              'rules': {'trendThreshold': .03, 'flatBand': .03, 'quoteFreshDays': 7,
                        'defaultHorizonWeeks': 12, 'defaultUrgency': 'flexible'},
              'limitations': ['주간은 화요일 원문 관측. 배송·카드·쿠폰·평균/최저/종가 집계 정의 미확인.',
                              '월간과 주간 값·현재 3몰 배송 포함 중앙값은 같은 가격 정의로 검증되지 않아 연결하지 않습니다.',
                              '최근 추세를 이용한 행동 규칙이며 미래 방향의 확률 예측이 아닙니다.',
                              '현재는 2026-10-23 저장 스냅샷. 자동 갱신·가격 알림 발송은 구현하지 않았습니다.',
                              '월간 검증의 전체 오차는 중첩 표본을 포함합니다. 독립 표본 수도 따로 표시합니다.'],
              'methodSources': [{'name': '시계열 순차 검증', 'url': 'https://otexts.com/fpp3/tscv.html'},
                                {'name': '확률 보정과 검증', 'url': 'https://scikit-learn.org/stable/modules/calibration.html'}],
              'inputHashes': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}
    dest = ROOT / 'dashboard/dist/data/timing.json'
    dest.write_text(json.dumps(output, ensure_ascii=False, separators=(',', ':')))
    downloads = ROOT / 'dashboard/dist/data/downloads'
    with (downloads / 'domestic_timing_history.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['product_id', 'frequency', 'date', 'price_krw', 'partial', 'source_url'])
        writer.writeheader()
        for p in products:
            for frequency in ('weekly', 'monthly'):
                for row in p[frequency]:
                    writer.writerow({'product_id': p['id'], 'frequency': frequency, 'date': row['date'],
                                     'price_krw': row['price'], 'partial': row.get('partial', False), 'source_url': p['sourceUrl']})
    with (downloads / 'domestic_timing_validation.csv').open('w', encoding='utf-8-sig', newline='') as f:
        fields = ['product_id', 'horizon_months', 'origin', 'target', 'predictedChange', 'actualChange', 'error', 'naiveError']
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for p in products:
            for analysis in p['analysis'].values():
                for row in analysis['validation']['backtests']:
                    writer.writerow({'product_id': p['id'], 'horizon_months': analysis['validation']['horizonMonths'], **row})
    print(json.dumps({'products': len(products), 'weeklyN': sum(p['analysis']['4']['weeklyN'] for p in products),
                      'maxValidationN': max(p['analysis']['4']['validation']['n'] for p in products), 'output': str(dest)}))


if __name__ == '__main__':
    build()
