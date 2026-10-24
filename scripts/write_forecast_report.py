"""Render the measured forecast scores and acquisition limits without new fitting."""
import csv
from datetime import date
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/analysis/2026-10-23/forecast'
WEB=ROOT/'dashboard/dist/data/downloads'


def main():
    data=json.loads((OUT/'forecast.json').read_text())
    comparison=ROOT/'data/public/model_comparison.json'
    if comparison.exists() and data.get('modelComparison'):
        write_expanded(data,json.loads(comparison.read_text()))
        return
    series=data['series']
    new=[s for s in series if '__' in s['id']]
    def score(v):return '—' if v is None else f'{v:.4f}'
    def pp(v):return '—' if v is None else f'{v*100:.1f}%p'
    lines=[
        '# 3개월 PC 부품 가격 확률 모형 검증 결과',
        '',
        '기준일: 2026-10-23. 실제 가격 이력을 늘려 확률 모형을 학습·검증하고 대시보드에 연결했다. **이번에 검증한 모형 중 구매 추천 사용 기준을 통과한 계열은 0개**다. 확률 숫자가 생성됐다는 이유로 신뢰할 만한 미래 확률이라고 판단하지 않는다.',
        '',
        '## 실제 확장한 데이터',
        '',
        f'- 신규 해외 {len(new)}개 계열 **{sum(s["coverage"]["rawN"] for s in new):,}개 원문 관측**을 확보했다. 기존 자료 6개와 별도로 보존한다. 국가·통화·신품/리퍼·용량·히트싱크 옵션을 구분했다.',
        '- 국내 9개 제품의 과거 아카이브 **26건**을 확보했다. 교차 확인된 **25건(2021-11~2024-11)**을 별도 맥락 자료로 표시하고, 2020-11 DDR4 한 건은 일반·현금 기준 충돌로 격리했다. 원문·추출값·사유를 보존했다.',
        '- 국내 아카이브는 일반 최저가 스냅샷이고 기존 차트는 집계 정의가 불명확한 월간 minPrice다. 이어 붙이거나 보간해 학습 기간을 늘리지 않았다. 국내 연속 이력은 여전히 최대 완료 월 22개이며, 오늘부터 3개월 뒤에 대응하는 연속 주간 자료는 미확보다.',
        '',
        '| 신규 해외 계열 | 통화 | 관측 주 / 전체 달력 주 | 실제 관측 주 범위 |',
        '|---|---|---:|---|',
    ]
    for s in new:
        c=s['coverage']
        lines.append(f'| [{s["name"]}]({s["sourceUrl"]}) | {s["currency"]} | {c["observed"]} / {c["total"]} | {c["first"]} ~ {c["last"]} |')
    lines += [
        '',
        '토~금 주의 마지막 실제 호가를 사용한다. 전체 그리드는 현재 완료 주 2026-10-16까지여서 추적 중단 뒤 결측도 포함한다. 원문 날짜의 주가 완료했는지와 관측 최초/최후 날짜 안에서 7일 전체가 관측됐는지는 다르다. 소스별 매니페스트의 완전 포함 주 수와 위 수치는 기준이 다르며, 위 표가 실제 모형 입력 수다. 실제로 매일 조사했거나 거래가 체결됐다는 뜻은 아니다.',
        '',
        '## 모형과 검증',
        '',
        '- 하락: -3% 미만, 보합: ±3% 이내, 상승: +3% 초과. 주간 목표는 달력 3개월 뒤 이상인 첫 금요일(13~14주), 월간 목표는 정확히 3개 달 뒤 동일 버킷이다.',
        '- 해외는 SKU별 L2 다항 로지스틱 회귀·깊이 제한 랜덤포레스트를 분기별 학습했다. 2023~2024년 중 정답까지 2024년에 확보 가능한 예측만으로 후보·확률 온도를 선택하고 2025~2026년에서 최종 평가했다. 선택 자료가 모자란 제품은 사전 고정 로지스틱·온도 1이다.',
        '- 국내는 동일 가격 정의 21개 SKU 월간 패널의 고정 로지스틱 모형이다. 같은 칩 보드와 공통 시기 충격을 공유하므로 SKU×월 행 수가 독립 표본 수는 아니다. 시점별 모든 SKU의 미래 정답을 함께 차단한다.',
        '- 각 학습은 정답 목표 기간이 분기 시작 전에 종료한 자료만 쓴다. 특징은 과거 가격만 사용한다. 결측 특징의 중앙값은 해당 학습 집합에서만 구하고 결측 표시자를 추가한다. 가격·목표를 이월하거나 보간하지 않는다. 주가·ETH의 미래 값은 사용하지 않는다.',
        '- 현재 조회한 이력의 회고 검증이다. 당시 공개됐던 수집본을 복원한 실시간 검증은 아니다. 공급 단절·품절과 결측의 연관, 소스의 사후 수정은 통제하지 못했다.',
        '',
        'Brier는 세 방향의 제곱오차 합(0~2), 기준은 같은 학습 자료의 발생 빈도(+1 보정)다. 낮을수록 좋다. 가격 변화의 점 예측은 학습 구간 방향별 변화율 중앙값을 확률로 가중한 값이며 별도 회귀가 아니다. MAE 단위는 변화율의 %p다.',
        '',
        '| 계열 | 최종 시험 n | 서로 다른 원점 / 비중첩 시간 | 모형 Brier | 기준 Brier | 변화율 MAE / 유지 MAE |',
        '|---|---:|---:|---:|---:|---:|',
    ]
    for s in series:
        e=s['evaluation']
        lines.append(f'| {s["region"]} · {s["name"]} | {e["n"]} | {e["originsN"]} / {e["nonoverlapN"]} | {score(e["brier"])} | {score(e["baselineBrier"])} | {pp(e["mae"])} / {pp(e["naiveMae"])} |')
    lines += [
        '',
        f'전체 예측·정답 행은 **{data["totals"]["backtests"]}건**이다. 제품과 시기를 공유하므로 독립 표본으로 합산하지 않는다.',
        '',
        '미국 Ryzen 3600은 Brier 0.6613 대 기준 0.6645로 거의 차이가 없고, 개선 95% 블록 구간은 0을 포함한다. 미국 970 EVO Plus는 Brier가 약 11.4% 개선됐지만 세 방향의 검증 수가 8/4/41개로 불균형하며 보정의 평균 차이가 약 27.3%p다. 국내 7500F는 7회(비중첩 3개)에서 Brier가 약 40.7% 나빴고, 변화율 MAE는 24.2%p 대 유지 기준 9.0%p다. 이 결과로 매수·대기를 권하지 않는다.',
        '',
        '공개 조건은 점수·로그손실 개선, 3개월 시간 블록의 95% 개선 하한 >0, 보정 차이 ≤10%p, 세 클래스 각각 10개, 주간 52/월간 12개 원점 및 비중첩 시간 8개다. 2025~2026년 최종 평가 범위 자체도 8개의 3개월 구간을 충분히 담지 못한다. 학습·선택에 쓴 옛 자료를 독립 평가로 재사용해 이를 채우지 않았다. 낮은 Brier만으로 확률 보정이나 안정성을 입증하지 않는다.',
        '',
        '## 대시보드 반영과 미해결 범위',
        '',
        '- `#forecast`: 35개 가격 계열 선택, 실험 확률, 정확한 원점·목표, 학습 마감, Brier·로그손실·MAE, 보정 점 그래프, 실제/예측 변화 그래프, 미관측을 유지한 장기 가격, 국내 아카이브 별도 점 그래프, 전체 예측·선택·제외 내역 다운로드.',
        '- `#domestic`: 3개월 계획은 새 검증 결과를 우선한다. 실패한 모형이나 단순 단기 추세로 지금 사거나 대기하라고 권하지 않는다. 견적 이상·희소 판매처·오래된 데이터의 확인은 우선한다.',
        '- 국내 최신 예측은 2026-09 완료 버킷 → 2026-12 버킷이다. **2026-10-23부터 3개월 뒤인 2027-01의 국내 가격 예측이 아니다.** 현재 배송 포함 3몰 중앙값의 미래 견적으로 환산하지 않았다. 해외 모형의 확률도 국내로 이전하지 않았다.',
        '- 따라서 사용자가 원한 실용적 현재 국내 3개월 구매 신호는 아직 검증하지 못했다. 동일 가격 정의로 더 긴 국내 주간 이력과 시간상 독립된 검증 기간이 필요하다. 자동 수집·정기 재학습은 이번에 설치하지 않았다.',
        '',
        '## 재현과 감사 자료',
        '',
        'Python 3.12에서 `pip install -r requirements-analysis.txt`, `python scripts/build_forecast.py`, `python scripts/write_forecast_report.py` 순으로 실행한다. 저장 원본을 읽는 오프라인 분석으로 네트워크 조회가 필요 없다. 신규 수집기는 기존 원본을 덮어쓰지 않는 별도 스냅샷을 사용한다.',
        '',
        '- `forecast_predictions.csv`: 최종 평가의 모든 원점·목표·학습 마감·확률·기준 확률·정답.',
        '- `forecast_selection_predictions.csv`: 선택 이전 후보별 예측과 선택 가능 여부. 후보·온도별 손실은 JSON의 selection.candidates.',
        '- `forecast_weekly.csv`: 주/월 원가격 그리드. 파일의 frequency 열로 구분하며 결측은 빈칸.',
        '- `forecast_metrics.csv`: 계열별 점수·추천 사용 실패 이유.',
        '- `forecast_domestic_archives.csv`: 25개 참고 관측 + 1개 격리. 격리 행은 일반가 칸을 비우고 원문 추출값을 별도 열에 보존.',
        '- `excluded_observations.csv`: USD $5 미만 오류, 21개 부분월, 다른 가격 정의의 아카이브 및 충돌 사유. $5 하한 없이 재실행한 CPU 민감도도 JSON에 보존.',
        '- `forecast.json`: 확률·모든 최종 사례·보정 구간·입력 SHA-256. 원본/다운로드 복사본 일치와 미래 차단은 자동 테스트로 검사.',
        '',
        '방법 근거: [시계열 교차 검증](https://otexts.com/fpp3/toolbox.html#time-series-cross-validation), [scikit-learn 확률 보정](https://scikit-learn.org/stable/modules/calibration.html). 자세한 고정 기준은 `docs/forecast_protocol.md`.',
        '',
    ]
    (OUT/'REPORT.md').write_text('\n'.join(lines))
    shutil.copyfile(OUT/'REPORT.md',WEB/'forecast_report.md')


def write_expanded(data,comparison):
    def score(v):return '—' if v is None else f'{v:.4f}'
    def pp(v):return '—' if v is None else f'{v*100:.2f}%p'
    lines=['# 3개월 PC 부품 가격 모형 검증 결과', '',
        '가격 스냅샷 2026-10-23, 모델 비교 2026-10-24. ARIMA·SARIMA·ETS를 기존 로지스틱·랜덤포레스트와 비교했다. '
        f'구매 추천 기준 통과는 **{data["totals"]["passed"]}/{len(data["series"])}계열**이다. '
        '새 후보는 2023–2024년 과거 선택 구간으로만 선택했다. 2025–2026년은 이미 결과를 열람한 회고 벤치마크이며 새 미관측 홀드아웃이 아니다.', '',
        '## 반영한 선택과 점수의 범위', '',
        f'총 선택 모델 평가 {data["totals"]["backtests"]}행, 후보 공통 평가 {comparison["summary"]["commonTestRows"]}행. '
        '같은 3개월 목표가 겹치므로 독립 표본 수가 아니다. 아래는 선택 모델의 **전체 산출 가능 평가**이며, '
        '후보별 우열 비교는 공개 집계 JSON의 공통 원점 점수를 사용한다.', '',
        '| 계열 | 선택 모델 | 과거 선택 n | 전체 시험 n / 비중첩 | Brier / 빈도 기준 | 변화율 MAE / 유지 |',
        '|---|---|---:|---:|---:|---:|']
    for s in data['series']:
        e=s['evaluation']
        lines.append(f'| {s["region"]} · {s["name"]} | {s["selection"]["candidate"]} | {s["selection"]["n"]} | '
            f'{e["n"]} / {e["nonoverlapN"]} | {score(e["brier"])} / {score(e["baselineBrier"])} | {pp(e["mae"])} / {pp(e["naiveMae"])} |')
    lines += ['', '## 방법과 자료의 한계', '',
        *['- '+s for s in comparison['limitations']], '',
        '- 국내 아카이브 26건 중 25건은 별도 참고용, 1건은 일반·현금 가격 충돌로 격리했다. 월간 minPrice와 이어 붙이지 않는다.',
        '- 신규 해외 8계열 원문 3,065점과 기존 6계열의 가격 정의·국가·통화를 분리한다. 국내는 최대 완료 월 22개이며 연간 SARIMA를 제외했다.',
        '- 국내 최신 목표는 2026-09→2026-12 월간 버킷이며 2026-10-23 현재 결제 가격에서 3개월 뒤의 국내 가격을 예측한 것이 아니다.', '',
        '## 재현·감사', '',
        '`python scripts/build_forecast.py` → `python scripts/compare_forecast_models.py` → '
        '`python scripts/write_forecast_report.py`. 별도 허가 원본이 필요한 오프라인 절차다. 공개 집계만으로 원모델을 재학습할 수 없다.', '',
        '- 상세 비교 규약: `docs/forecast_protocol.md`; 결과 설명: `docs/model_comparison.md`.',
        '- 공개 통계: `data/public/model_comparison.json`, `data/public/model_comparison_metrics.csv`.',
        '- 비공개 연구 감사: `data/analysis/2026-10-24/model_comparison/candidate_predictions.json`, SKU별 적합 기록과 원본 해시.',
        '- `forecast_predictions.csv`, `forecast_metrics.csv`, `forecast.json`은 새 선택 모델을 반영했다. 최초 두 후보의 결과는 `legacy_forecast.json`에 보존했다.',
        '- 최초 두 후보 선택 감사는 `forecast_selection_predictions.csv`; 확장 후보 선택 옵션·온도 점수는 공개 JSON의 `selection.options`에 있다.', '']
    (OUT/'REPORT.md').write_text('\n'.join(lines))
    shutil.copyfile(OUT/'REPORT.md',WEB/'forecast_report.md')


if __name__=='__main__':main()
