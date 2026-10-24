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
