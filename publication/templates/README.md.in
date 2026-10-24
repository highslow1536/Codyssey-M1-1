# PC 부품 가격 관측소 · 과제 공개 제출판

**PC 부품의 과거 가격·주가 관계와 3개월 구매 시점 예측을 검증한 프로젝트**다. 가격 정의·결측·표본 수를 확인하고, 검증에 실패한 예측은 구매 신호로 쓰지 않는다.

제출 저장소: **[highslow1536/Codyssey-M1-1](https://github.com/highslow1536/Codyssey-M1-1)** · 문서·권리 점검 2026-10-24 · 분석 스냅샷 2026-10-21\~23 · 자동 갱신 없음

> **공개 범위:** 전체 Python·웹 코드와 공개용 문서, 자체 집계 결과, 재배포 조건을 확인한 ETH 자료를 포함한다. 부품 가격·Yahoo 주가·벤치마크 원본과 이를 복원하는 시계열·다운로드·기존 화면 캡처는 제외했다. 원래 전체 연구 자료는 별도로 보존했으며, 이 저장소만으로 모든 부품 분석을 다시 학습할 수는 없다. [출처별 조건](docs/data_redistribution.md) · [제외 파일·취득 안내](data/README.md)

## 평가자가 확인할 순서

1. [REPORT](REPORT.md): 분석 질문 5개, 자료·전처리·분석·시각화·인사이트·한계·AI 로그.
2. [제출 체크표](docs/submission_checklist.md): PDF 필수 요건과 근거, 원본 제외로 인한 재현 제한.
3. [공개 데이터](data/processed/2026-10-22/crypto/eth_daily.csv): 실제 ETH 일별 1,096점과 주별 156점, 라이선스·변경 내용 명시.
4. 아래 명령으로 공개 대시보드를 열어 연도·지표를 바꾸고 실제 n과 예측 검증 요약 확인.

## 1. 바로 실행하기

저장소 전체를 내려받은 뒤 루트에서 실행한다. 화면 보기에는 Python 표준 라이브러리만 필요하다.

```bash
python3 -m http.server 8766 --bind 127.0.0.1
```

**[http://127.0.0.1:8766/dashboard/public/](http://127.0.0.1:8766/dashboard/public/)** 을 연다. 종료는 `Ctrl+C`. HTML을 직접 열면 JSON을 읽을 수 없다. 포트가 사용 중이면 다른 번호를 쓴다. 이 주소는 로컬 실행 주소이며 배포된 웹 주소가 아니다.

![실제로 실행한 공개 ETH 대시보드](docs/assets/public/public_01_trend.png)

**화면 읽기.** 전체 범위는 2020-01-01부터 2022-12-31까지 1,096일이다. 연도와 ETH 가격/수익 대용 A·B를 선택한다. 가격과 대용은 단위가 달라 같은 축에 겹치지 않는다. 예측 검증 탭은 별도 부품 모형의 집계 결과이며 이 ETH 자료로 새로 학습한 결과가 아니다.

## 2. 무엇을 분석했는가?

![자료 정의·감사·분석·검증의 흐름](docs/assets/figures/01_analysis_flow.png)

| 질문 | 결과와 근거 | 한계 |
|---|---|---|
| 부품 가격은 장기간 어떻게 변했나? | 2020\~2022년과 2023\~2026년을 나눠 분석. 과거 유효 주 CPU 148·SSD 135, 최근 158·173 | 두 구형 SKU의 호가이며 전체 시장 지수가 아님. 원시 가격은 공개 제외 |
| 기업 주가와 함께 움직이나? | 같은 주 변화율 CPU–AMD r=-0.046(n=140), SSD–삼성 r=-0.023(n=122) | 수준 상관과 다름. 204개 시차 비교 중 보정 후 유의 결과 0개 |
| GPU 하락을 머지로 설명할 수 있나? | 확보한 소매 조사에서는 머지 이전부터 하락. eBay 전후 변화는 3070 -19.5%, 3080 -15.1%, 3090 -16.4% | 전후 각 2개월, 공급·신제품·환율 미통제. 인과 효과 아님 |
| 현재 동급 제품 비교가 유용한가? | 국내 8개를 비교군 포함 21개로 확장. 희소 견적의 순위 보류·동급 비교 기준 구현 | 실제 재고·판매량 미확인. 견적·벤치마크 수치표와 복원 가능한 캡처는 공개 제외 |
| 3개월 예측으로 지금 구매를 권할 수 있나? | 35계열·최종 평가 394행, 추천 사용 조건 통과 0개 | 목표가 겹치므로 독립 표본 394개가 아님. 현재 국내 구매 확률로 권하지 않음 |

![가격 수준과 변화율을 구분한 자체 상관 통계](data/analysis/2026-10-22/figures/02_correlations.png)

붉고 파란 칸은 원가격의 재배포가 아니라 분석으로 계산한 상관계수다. 각 칸의 실제 n과 다중 비교 한계를 함께 확인한다. [집계 CSV](data/analysis/2026-10-22/correlations.csv)

## 3. 공개 데이터로 직접 재현할 수 있는 분석

![ETH 일별 가격과 30일 이동평균](docs/assets/public/01_eth_trend.png)

Coin Metrics ETH 자료는 **CC BY-NC 4.0** 조건으로 제공한다. 2020\~2022년 일별 1,096점, 30일 이동평균 유효 1,067점이다. 날짜를 빠짐없이 정렬하고, 30개 날짜의 값이 모두 있을 때만 평균한다. GPU 가격을 대신하는 시계열은 아니다.

![ETH 주별 변화율](docs/assets/public/02_eth_weekly_returns.png)

토요일\~금요일 156주 중 인접 두 주가 있는 변화율은 **155개**다. 2021년 주별 변화율의 표본 표준편차는 **15.95%p**, 2022년은 **11.65%p**였다. 일별 가격의 완만한 추세와 큰 주별 변동을 구분한다. [연도별 집계](data/public/eth_yearly_summary.csv)

![고정 100 MH/s 환산 대용 A와 B](docs/assets/public/03_eth_proxies.png)

대용 A는 발행+수수료, B는 발행만으로 계산한다. **988일 유효**, 머지 전환일 1일과 종료 뒤 107일은 값이 없다. 이는 자료 누락 108일과 다른 상태다. London 이후 소각 수수료·Beacon 발행 혼입 때문에 실제 GPU 채굴 순이익이나 엄밀한 상·하한으로 해석하지 않는다.

## 4. 예측 결과는 얼마나 믿을 수 있는가?

![대표 3계열의 모형 오차와 단순 기준 비교](docs/assets/figures/04_forecast_validation.png)

Brier와 변화율 MAE는 **낮을수록 좋다.** 미국 SSD는 Brier가 약 11.4% 개선돼도 방향별 표본과 보정 조건을 통과하지 못했다. 국내 7500F도 기준보다 나빴다. 성공한 확률 모형처럼 표현하지 않고 [35계열 집계 점수](data/analysis/2026-10-23/forecast/forecast_metrics.csv)와 표본 한계를 공개한다.

## 5. 실행·검증 범위

분석 환경은 Python **3.12.14**, 고정 의존성은 [requirements-analysis.txt](requirements-analysis.txt)다. 과제의 Python 3.10 이상 조건을 충족하며 다른 버전의 호환성은 확인하지 않았다.

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-analysis.txt
.venv/bin/python -m unittest discover -s tests -p test_eth_mining.py -v
.venv/bin/python scripts/verify_public_submission.py
(cd dashboard && node --test tests/forecast-view.test.mjs)
```

공개판에서 실행하는 검사는 ETH 원본 해시·산식·머지 경계와 공개 파일 범위, 화면 표현 규칙이다(ETH 6개·JavaScript 8개 통과). 원래 전체 스냅샷에서는 Python 151개·JavaScript 43개를 통과했지만, **원본을 제외한 이 저장소에서 전체 151·43개가 실행된다고 주장하지 않는다.** 자세한 범위와 재생성 명령은 [재현 안내](docs/reproduction.md)에 있다.

## 6. 파일과 권리

```text
README.md / REPORT.md       # 공개 제출 안내와 상세 분석
scripts/ / config/ / tests/ # 전체 분석 코드·조건·원래 검사 및 공개판 검사
docs/                      # 방법론·재배포 검토·제출표·이미지
data/verification/.../crypto/ # 허용된 Coin Metrics 원본과 수집 기록
data/processed/.../crypto/  # ETH 일별·주별 자료와 가공 내역
data/analysis/             # 자체 상관·커버리지·예측 오차 집계
data/public/               # 공개 대시보드 입력·연도별 집계
data/excluded_inventory.csv # 공개 제외 파일의 경로·해시·이유 (값 없음)
dashboard/public/          # 공개 자료로 바로 실행하는 화면
dashboard/dist/            # 전체 앱 소스; index.full.html은 별도 허가 자료 필요
publication/templates/     # 공개 문서 생성용 원문 템플릿
PUBLICATION_MANIFEST.json  # 공개 파일별 SHA-256·크기·분류
```

ETH 원자료와 그 가공물에는 **비영리·출처·라이선스 링크·변경 표시** 조건이 적용된다. 전체 코드·문서에 같은 데이터 라이선스를 일괄 부여하지 않았다. [권리 구분](RIGHTS.md), [출처별 검토](docs/data_redistribution.md), [제외·취득 방법](data/README.md)을 확인한다. 저장소를 공개했다고 제한된 자료의 재수집·공개 허가가 생기지는 않는다.
