> 공개판 안내: 작성 당시 연구 기록입니다. 원가격·주가·벤치마크 원본과 복원 가능한 파일은 제외했습니다. 현재 공개 범위·실행법은 루트 README와 데이터 이용 안내를 따릅니다.

> 원래 전체 스냅샷용 순서입니다. 공개판에는 필요한 부품·주가 원본이 없으므로 아래 전체 순서를 실행할 수 없습니다. 공개 자료만으로 실행하는 순서는 [공개판 재현 안내](reproduction.md)를 따릅니다. 수집 코드의 공개는 수집·재배포 허가가 아닙니다.

# 재현 안내 (오프라인)

저장된 원본으로 기존 제출 결과를 재현하는 절차다. 아래 명령은 모두 저장소 루트에서 실행한다. 저장된 대시보드 확인은 2절만으로 가능하며, 전체 재생성은 4절을 선택해 진행한다.

원본 스냅샷(`data/feasibility/2026-10-21/`, `data/verification/`)과 설정을 보존한다. 분석은 기존 파생물을 덮어쓰므로 전체 재생성 전에는 파생물을 별도 보관한다. 의존성 설치 이후에는 네트워크 수집이 필요 없다.

## 1. 기본 설치

과제의 실행 환경 요구는 Python **3.10 이상**이다. 이 프로젝트는 고정 의존성으로 검증한 **3.12.14**를 권장하며, 다른 Python 버전의 실행은 확인하지 않았다. Python 3.12를 설치한 뒤 가상환경과 분석 의존성을 준비한다.

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-analysis.txt
```

`requirements-analysis.txt`에 분석·그림·모형 의존성을 고정했다. Node.js는 3절의 JavaScript 검사에만 필요하며 확인된 버전은 **v24.19.0**이다.

## 2. 빠른 실행 (대시보드, 빌드 없음)

```bash
python3 -m http.server 8766 --bind 127.0.0.1 --directory dashboard/dist
```

브라우저에서 `http://127.0.0.1:8766/`을 연다. HTML·CSS·JavaScript 정적 파일을 그대로 제공하므로 별도 빌드나 npm 설치가 필요 없다.

## 3. 전체 검사

```bash
.venv/bin/python -m unittest discover -s tests -v
(cd dashboard && node --test tests/*.test.mjs)
```

두 번째 명령은 `dashboard/package.json`의 `npm test`와 동일하다. 괄호 안에서만 작업 폴더를 바꾸므로 실행 후에도 저장소 루트를 유지한다. 검사 결과는 각 명령의 출력에서 확인한다.

## 4. 선택적 전체 재현 (오프라인, 순서대로)

파생물(`data/processed/`, `data/analysis/`, `dashboard/dist/data/`, `dashboard/dist/reports/`)을 덮어쓴다. 원본 경로와 기본 설정을 그대로 사용하는 순서다.

### 4.1 2020\~2022년 가격·주가 상관

입력: `data/feasibility/2026-10-21/`(원본), `config/correlation_analysis.json`, `config/price_preprocessing.json`, `data/verification/2026-10-22/stocks/`(주가 원본).

```bash
.venv/bin/python scripts/audit_domestic_prices.py
.venv/bin/python scripts/preprocess_overseas_prices.py
.venv/bin/python scripts/prepare_weekly_stocks.py
.venv/bin/python scripts/analyze_price_stock_correlations.py
.venv/bin/python scripts/plot_price_stock_correlations.py
.venv/bin/python scripts/write_price_stock_report.py
```

출력: `data/processed/2026-10-21/{domestic,overseas}/`, `data/processed/2026-10-22/stocks/`, `data/analysis/2026-10-22/`(REPORT.md, CSV, figures).

### 4.2 GPU·채굴 붐

입력: `data/feasibility/2026-10-21/alternatives/raw/`, `data/verification/2026-10-22/{gpu,gpu_ebay,crypto}/`.

```bash
.venv/bin/python scripts/prepare_gpu_retail_prices.py
.venv/bin/python scripts/prepare_gpu_ebay_monthly.py
.venv/bin/python scripts/prepare_eth_mining.py
.venv/bin/python scripts/analyze_gpu_mining.py
.venv/bin/python scripts/plot_gpu_mining.py
.venv/bin/python scripts/write_gpu_mining_report.py
```

출력: `data/processed/2026-10-22/{gpu_retail,gpu_ebay,crypto}/`, `data/analysis/2026-10-22/gpu_mining/`.

### 4.3 국내·최근 시장·예측 (2026-10-23)

4.1\~4.2의 파생물이 준비된 상태에서 아래 순서로 실행한다. `analyze_recent_timing.py`와 `build_forecast.py`가 `domestic.json`을 읽으므로 국내 내보내기가 먼저다. 국내 가격 감사와 비교 제품 확장은 `export_domestic_dashboard.py`가 내부에서 처리한다.

```bash
.venv/bin/python scripts/collect_domestic_quotes.py
.venv/bin/python scripts/prepare_domestic_history.py
.venv/bin/python scripts/export_domestic_dashboard.py
.venv/bin/python scripts/analyze_recent_timing.py
.venv/bin/python scripts/build_recent_dashboard.py
.venv/bin/python scripts/plot_report_recent_prices.py
.venv/bin/python scripts/build_forecast.py
.venv/bin/python scripts/write_forecast_report.py
.venv/bin/python scripts/export_dashboard_data.py
```

- `collect_domestic_quotes.py`는 위처럼 인자 없이 실행하면 저장된 `data/verification/2026-10-23/domestic/manifest.json`과 `raw/`만 가공한다. `--fetch`는 새 수집 옵션이므로 기존 결과 재현에는 붙이지 않는다.
- 국내·최근 시장 입력: `data/feasibility/2026-10-21/`, `data/verification/2026-10-23/{domestic,expanded,performance,timing}/`, `data/processed/2026-10-21/overseas/weekly_prices.csv`.
- 출력: `data/processed/2026-10-23/{domestic,recent}/`, `dashboard/dist/data/{domestic,recent,timing,forecast,dashboard}.json`, `data/analysis/2026-10-23/{forecast,figures}/`, `dashboard/dist/data/downloads/`, `dashboard/dist/reports/`.

`plot_report_recent_prices.py`는 통합 리포트의 2023\~2026년 가격 그림(PNG·SVG)을 만든다. 이 단계는 앞에서 만든 `data/processed/2026-10-23/recent/parts_weekly.csv`만 읽는다. 루트 `README.md`와 통합 `REPORT.md`는 수동 편집 문서이며 생성 스크립트가 덮어쓰지 않는다.

`build_forecast.py`의 `load_sources()`에서 확인한 예측 입력은 다음과 같다. 추가 해외·국내 아카이브 자료가 없으면 건너뛰는 구현이므로, 같은 대상 범위를 재현하려면 색인 JSON과 참조 원본을 함께 보관한다.

| 입력 | 저장 경로·역할 |
| --- | --- |
| 기존 해외 6개 계열 | `data/feasibility/2026-10-21/alternatives/{requests.json,extra_gpu_requests.json}`과 `raw/`의 각 `raw_file` |
| 추가 해외 8개 계열 | `data/verification/2026-10-23/forecast/overseas_extended/series.json`의 `observations`를 가공하고, 각 `rawFile` 원본의 SHA-256을 확인한다. 저장 원본은 같은 폴더의 `raw/overseas_*_prices.json`이다. |
| 국내 월간 학습 | `data/verification/2026-10-23/timing/{cpu_gpu_history.json,ram_ssd_history.json}`과 각 `rawFile` 원본. 제품 이름은 `dashboard/dist/data/domestic.json`에서 읽는다. |
| 국내 아카이브 참고 관측 | `data/verification/2026-10-23/forecast/domestic_extended/extended_history.json`과 각 `wayback_anchors[].raw_file`에 지정된 `raw/wayback_*.html`. SHA-256·가격 기준을 확인하며 월간 학습 자료와 연결하지 않는다. |

추가 해외 `rawFile`은 저장소 루트 기준으로 먼저 찾고, 없으면 `series.json`이 있는 폴더 기준으로 찾는다. 국내 `rawFile`과 아카이브 `raw_file`은 저장소 루트 기준이다. 폴더 구조를 보존하고 참조 파일을 함께 옮겨야 한다.

예측 결과는 `forecast_predictions.csv`(최종 평가), `forecast_selection_predictions.csv`(후보 선택), `forecast_metrics.csv`(점수), `forecast_weekly.csv`(주·월 가격), `forecast_domestic_archives.csv`(아카이브·격리), `excluded_observations.csv`(제외 사유), `forecast.json`·`source_hashes.json`으로 남는다. 검증 규격은 [forecast_protocol.md](forecast_protocol.md)에 고정되어 있다.

### 4.4 문서용 이미지 재생성

저장된 입력과 분석 결과가 이미 있으면 4.1\~4.3을 다시 실행할 필요 없이 아래 명령만 실행한다.

```bash
.venv/bin/python scripts/plot_documentation_figures.py
```

출력은 `docs/assets/figures/`의 PNG·SVG 각 6개와 입력 SHA-256·표시 수치 목록인 `manifest.json`이다. 원본 수집·모형 학습·대시보드 내보내기는 하지 않는다. 기존 분석 CSV와 문서만 읽는다. 한국어 렌더링은 macOS의 AppleGothic을 사용하므로 다른 운영체제에서는 스크립트의 `FONT_PATH`를 설치된 한국어 폰트 경로로 변경한다.

`docs/assets/screenshots/`의 다섯 PNG는 실제 로컬 앱을 캡처한 화면으로 위 명령이 생성하지 않는다. 촬영 경로·기준일과 기존 분석 그림의 위치는 [이미지 안내](assets/README.md)에 있다. 루트 README·REPORT도 자동 생성 대상이 아니다.

## 5. 새 수집은 별도 스냅샷으로

네트워크 수집기는 기존 결과 재현에 필요 없다. 새 자료가 필요하면 기존 스냅샷과 분리해 수집한다.

- `scripts/probe_price_history.py`, `scripts/probe_alternative_sources.py`
- `scripts/collect_domestic_quotes.py --fetch`, `scripts/collect_domestic_extended.py`, `scripts/collect_forecast_overseas.py`, `scripts/collect_recent_markets.py`, `scripts/collect_gpu_retail_sources.py`
- 새 수집은 새 날짜 폴더를 사용한다. 출력 경로가 고정된 수집기는 먼저 별도 경로로 조정해야 한다. 기존 `data/feasibility/2026-10-21/`, `data/verification/` 원본은 덮어쓰지 않는다.

## 6. 입력 경로 주의사항

- 읽기 전용(원본): `data/feasibility/2026-10-21/`, `data/verification/`, `config/*.json`. 이 폴더들에 쓰기가 일어나면 감사 기준이 달라진다.
- 덮어쓰는 파생물: `data/processed/`, `data/analysis/`, `dashboard/dist/data/`, `dashboard/dist/reports/`.
- 국내 월간 `minPrice`의 집계 정의는 미확인이다. 해외 W-FRI 주간 자료와 바로 결합하지 않는다. 시장·통화·상품이 다른 계열을 하나의 시계열로 합치지 않는다(`data/processed/2026-10-23/domestic/NOTES.md`, 루트 README).
- 최근 `parts_weekly.csv`에는 전체 기간에서 계산한 첫 행의 `log_return`이 남아 있다. 최근 분석은 198주 내부의 인접 가격으로 다시 계산하므로, 구간 밖 2022년 마지막 주에서 넘어온 값은 제외한다. 비어 있지 않은 열 개수 136·158개와 구간 안의 유효 변화율 135·157개를 구분한다.
- 전체 재생성 전에는 파생물을 별도 보관한다. 다수 스크립트는 기본 출력 경로가 고정되어 있다.

## 7. ZIP·생성 메타데이터와 수치 비교

`export_dashboard_data.py`는 `data/analysis/2026-10-22/`와 `docs/`를 묶어 `dashboard/dist/reports/analysis-bundle.zip`을 재생성한다. ZIP 항목 순서를 정렬하고 항목 시각을 `2026-10-22 00:00:00`으로 고정하므로, 원본 파일의 수정시각만 달라져 ZIP이 변하는 구조는 아니다.

다만 2026-10-22 계열 분석 그림은 SVG 생성 시각을 고정하지 않아 다시 만들면 내부 메타데이터가 달라질 수 있다. 문서용 6종은 SVG 날짜·ID 해시를 고정하고, 최근 가격 그림은 날짜를 제거하고 ID 해시를 고정한다. 포함 문서·그림 바이트가 바뀌면 ZIP 바이트와 해시도 달라진다. ZIP 전체 해시 차이만으로 분석 수치가 달라졌다고 판단하지 않는다.

앱의 `analysis-bundle.zip`은 기존 분석의 보조 다운로드다. 루트 `README.md`·`REPORT.md`와 모든 분석 코드·최근 자료를 담은 전체 과제 제출본이 아니며, 이번 문서 점검에서 다시 내보내지 않았다. **과제 제출은 프로젝트 파일을 기준으로 하고 이 ZIP만 제출하지 않는다.** 포함 범위는 [제출 체크표](submission_checklist.md)를 따른다.

수치 재현은 같은 입력 해시·설정을 전제로 CSV/JSON의 날짜·제품 식별자·가격·결측·표본 수·예측·점수를 비교한다. JSON의 `run_date_kst`·`generated_date_kst` 같은 실행일과 그림 메타데이터는 수치와 구분한다. 내보낸 다운로드 CSV는 해당 실행에서 생성한 원본 CSV의 바이트 복사본이다.


## 2026-10-24 ARIMA·SARIMA·ETS 확장 비교

허가된 원본을 복원한 연구 환경에서는 기존 build_forecast.py 뒤에 compare_forecast_models.py와 write_forecast_report.py를 실행한다. 공개 집계만으로 실제 가격 모형을 재학습할 수는 없다. 공개 집계의 그림·상세 설명은 plot_model_comparison.py와 write_model_comparison_report.py로 다시 생성한다. [고정 규약](forecast_protocol.md), [결과와 한계](model_comparison.md)를 함께 확인한다.

## 2026-10-25 최근 동향 재수집·분석

원래 예측 벤치마크 입력·결과를 바꾸지 않고 새 경로를 사용한다. 수집기는 같은 날짜의 manifest가 있으면 덮어쓰기를 거부한다.

```bash
.venv/bin/python scripts/refresh_report_sources.py --as-of 2026-10-25 --fetch
.venv/bin/python scripts/build_recent_report.py --as-of 2026-10-25
.venv/bin/python -m unittest discover -s tests -p test_recent_report.py -v
```

입력은 `data/verification/2026-10-25/report_refresh/`, 원가격 주간 CSV·비공개 곡선은 `data/analysis/2026-10-25/recent/`에 보존한다. 공개 출력은 `data/public/recent_analysis.json`, `recent_coverage.csv`, `recent_correlations.csv`, `source_freshness.json`과 `docs/recent_analysis.md`다. `scripts/plot_recent_report.py`는 공개 집계만으로 그림을 재생성한다. 수집일·실제 관측일·주간 날짜를 구분하고 10월 24일 호가는 아직 끝나지 않은 다음 주로 남긴다.
