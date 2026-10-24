# 공개 제출판 실행·재현 안내

이 문서는 GitHub 공개본 기준이다. 원래 전체 스냅샷은 재배포 제한으로 제외했다. **공개본으로 가능한 ETH 재현과 별도 허가 입력이 필요한 전체 분석을 구분한다.** [데이터 범위](../data/README.md) · [권리 검토](data_redistribution.md)

## 1. 화면 보기

루트에서 실행한다. Python 표준 라이브러리만 사용한다.

```bash
python3 -m http.server 8766 --bind 127.0.0.1
```

`http://127.0.0.1:8766/dashboard/public/`을 연다. 저장 JSON만 읽고 외부 API를 호출하지 않는다. `dashboard/dist/index.html`도 공개 화면으로 안내한다. 원래 앱 HTML은 `dashboard/dist/index.full.html`에 보존했으며 모든 분석 입력을 허가받아 복원한 뒤에만 실행할 수 있다.

## 2. 분석 환경

과제는 Python 3.10 이상을 요구한다. 검증한 환경은 **Python 3.12.14**, Node.js **24.19.0**이다.

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-analysis.txt
```

## 3. 공개본에서 실행하는 검사

```bash
.venv/bin/python -m unittest discover -s tests -p test_eth_mining.py -v
.venv/bin/python scripts/verify_public_submission.py
(cd dashboard && node --test tests/forecast-view.test.mjs)
(cd dashboard && node --test tests/model-comparison.test.mjs)
.venv/bin/python -m unittest discover -s tests -p test_model_comparison.py -v
.venv/bin/python -m unittest discover -s tests -p test_recent_report.py -v
```

ETH 검사는 6개로 원본 SHA-256, 일·주 그리드, 수익 대용 산식, 전환일·종료 뒤의 빈칸, 변화율 경계를 확인한다. JavaScript 검사는 실제 가격 파일을 읽지 않고 가상 시험 입력으로 화면의 확률·검증 표현 규칙을 확인한다. 시험용 가상 값은 실제 관측·분석 결과에 사용하지 않는다.

`verify_public_submission.py`는 공개 파일 해시·제외 범위·문서 링크·ETH 관측 수·모형 집계를 확인한다. 원래 전체 검사는 수정하거나 무시하도록 바꾸지 않았다. `python -m unittest discover -s tests` 또는 `node --test tests/*.test.mjs`는 공개하지 않은 원본·앱 JSON을 요구하므로 이 저장소만으로 통과하지 않는다.

## 4. ETH 분석 재생성

```bash
.venv/bin/python scripts/prepare_eth_mining.py
.venv/bin/python scripts/build_public_eth_analysis.py
```

둘 다 저장 파일만 읽는 오프라인 분석이다. 첫 명령은 `data/verification/2026-10-22/crypto/cm_eth_daily_raw.json`에서 `data/processed/2026-10-22/crypto/`를 덮어쓴다. 두 번째는 그 일·주별 CSV와 공개된 `forecast_metrics.csv`를 읽어 `data/public/`와 `docs/assets/public/`의 ETH PNG·SVG 3종을 만든다. 이 과정에서 가격 모형을 재학습하지 않는다.

그림은 macOS AppleGothic을 사용한다. 다른 운영체제에서는 한국어 글꼴을 지정해야 하며 줄바꿈·바이트가 달라질 수 있다. 검증은 파일 해시와 분석 수치의 동등성을 구분한다. 재생성으로 파일이 바뀌면 저장된 공개 manifest 해시도 다시 만들어야 한다.

## 5. 전체 PC 부품 분석은 별도 입력 필요

모든 Python 분석·수집 코드, 설정과 원래 검사를 보존했다. [기존 전체 분석 순서](full_reproduction.md)는 입력 복원 후 참고하는 기록이다. 가격·주가·성능의 데이터 정의가 다르므로 공개 ETH 자료로 대체해 원래 상관이나 예측을 재현했다고 표시하지 않는다.

- 입력의 원래 경로·해시: [제외 목록](../data/excluded_inventory.csv)
- 출처 URL: [색인](../data/source_catalog.json), 각 방법론 문서
- 현재 재배포 조건과 제외 이유: [권리 검토](data_redistribution.md)
- 공개 패키지 작성 코드: `scripts/build_public_submission.py`, 문서 템플릿: `publication/templates/*.in`

재수집이 필요한 경우 먼저 제공자 허가를 확인한다. 자동 수집이 제한된 출처를 이 실행 절차에서 조회하지 않는다. 제외 원본을 GitHub 이력이나 ZIP·앱 JSON에 다시 포함하지 않는다.

## 6. ARIMA·SARIMA·ETS 비교 재현

공개본에서는 `data/public/model_comparison.json`의 집계와 테스트용 가상 시계열로 비교 코드·확률 산식·미래 차단을 검증할 수 있다. 가상 값은 실제 결과를 생성하는 데 사용하지 않았다. `scripts/plot_model_comparison.py`와 `scripts/write_model_comparison_report.py`는 공개 집계만 읽어 비교 그림·보고서를 재생성한다.

실제 35개 계열의 재학습은 허가된 원가격 입력 복원 후 다음 순서로 실행한다.

```bash
.venv/bin/python scripts/build_forecast.py
.venv/bin/python scripts/compare_forecast_models.py
.venv/bin/python scripts/write_forecast_report.py
```

`statsmodels==0.14.6`을 고정했다. 비교 스크립트는 원본 가격을 네트워크에서 재수집하지 않는다. 최초 두 후보 결과를 `data/analysis/2026-10-24/model_comparison/legacy_forecast.json`에 보존하고, 새 선택을 전체 앱의 `forecast.json`·지표·예측 CSV에 반영한다. 후보별 원점 예측·캐시는 공개 제외하며 SHA-256 목록에만 기록한다. 재실행 캐시 키는 코드와 입력 그리드의 해시다.

2023–2024년으로 모형·온도를 선택하고 2025–2026년은 공통 원점 회고 비교에 사용한다. 이미 관찰한 기간이므로 새로운 홀드아웃 성능이라고 표현하지 않는다. [확장 규약](forecast_protocol.md) · [검증 결과와 한계](model_comparison.md)

## 7. 최근 2023–2026년 분석과 최신성 감사

2026-10-25에 해외 부품 14개·시장 7개·국내 단면 견적 8개를 기존 원본과 분리해 조회했다. 주간 분석은 2026-10-23 완료 주까지 199주이며, 출처의 실제 마지막 관측일은 제품마다 다르다. 수집일을 오늘 가격의 관측일로 바꾸지 않았다. [최근 결과](recent_analysis.md)

공개 집계만으로 그림을 다시 생성할 수 있다.

```bash
.venv/bin/python scripts/plot_recent_report.py
```

원자료와 주간 가격 행은 공개 제외다. 제공자 자료를 이용할 권한과 연구 입력이 있는 환경에서는 `scripts/refresh_report_sources.py --as-of 2026-10-25 --fetch`로 새 폴더에 한 번 수집하고 `scripts/build_recent_report.py --as-of 2026-10-25`로 분석한다. 기존 날짜의 manifest가 있으면 수집기는 덮어쓰기를 거부한다. 기존 3개월 예측 벤치마크를 다시 학습하거나 새 미래 성과를 검증한 작업과 구분한다.
