> 공개판 안내: 작성 당시 연구 기록입니다. 원가격·주가·벤치마크 원본과 복원 가능한 파일은 제외했습니다. 현재 공개 범위·실행법은 루트 README와 데이터 이용 안내를 따릅니다.

# ARIMA/SARIMA/ETS 모형 비교

집계원: `data/public/model_comparison.json` (asOf 2026-10-23, generated 2026-10-24, schema 1).
생성기: `scripts/write_model_comparison_report.py`. 원가격·원점별 예측·비밀값 없이 집계 점수만 읽는다. 빈칸은 --이며 0으로 채우지 않는다.

## 1. 고정 비교 규격

후보 5종 + 빈도 기준이다. 분류 2종(L2 다항 로지스틱 회귀, 깊이 제한 랜덤포레스트)은 과거 가격 특징을 쓰고, 시계열 3종은 같은 SKU의 로그가격만 쓴다.
외부 변수(주가·ETH·재고·출시)는 어떤 후보에도 넣지 않았다.

| 후보 | 규격 |
|---|---|
| ARIMA | 로그가격 ARIMA(1,1,0) + drift |
| SARIMA | SARIMA(1,1,0)(1,0,0,s), 주별 주기 52·월별 주기 12 |
| ETS | ETS(A,Ad,N) 로그가격, 초기 수준 고정·인접 추세, Kalman NaN 유지 |
| 분류 2종 | 기존 규약 그대로(분기 재학습·특징 중앙값+결측 표시자) |
| 기준 | 과거 방향 빈도(+1 보정) 확률 · 가격 유지 점예측 |

분기별 고정 파라미터다. 분류 모형은 분기 시작 전에 목표 기간까지 끝난 사례만으로 적합한다. 시계열 모형은 분기 시작 전에 관측된(available) 로그가격 전부로 적합하며 3개월 목표 성숙 조건을 두지 않는다. 같은 분기 원점들에는 `apply(refit=False)`로 분기 파라미터를 그대로 적용한다. 예측 분산은 잔차가 아니라 `get_forecast`의 실제 예측 분산을 쓴다. 결측 달력은 NaN으로 두며 칼만 필터 내부 예측을 관측으로 추가하지 않는다.
적합 최소 조건은 주별 52셀·관측 40개, 월별 12셀·관측 10개다. SARIMA는 2개 계절 주기 + 최근 두 주기 각 75% 관측을 추가로 요구한다. 국내 월간(7–22개월)은 연간 주기 두 주기를 못 채워 SARIMA 미산출이 정상이다.
방향 확률은 ±3% 기준의 가우시안 CDF다. 온도(0.5/1/2/4)는 2023–2024년 공통 과거 원점(2024년 말까지 성숙, 최소 24개·세 방향 포함)에서 로그손실 최소로만 고른다. 부족하면 기존 모형을 유지하고 시험 점수가 가장 낮은 모형으로 교체하지 않는다.
시험은 2025–2026년 동일 공통 원점 교집합(SKU별)이다. 후보별 전체 평가 가능 행 수(`allTestN`, 기존 분류 유효 평가 원점 universe 내)와 실패 사유를 함께 기록한다. 시계열 단독 예측(`standaloneTestN`, 집계에 있으면)은 기존 분류 비교가 없는 원점의 추가 산출로, 점수·선택에서 제외한다. 점예측은 시계열 모형의 로그정규 중앙값, 분류 모형의 방향별 중앙값 가중이다. MAE·RMSE는 변화율 분수를 %p로 표기하고, 80/95% 가격구간 커버리지는 온도 보정 전 원분포 구간(온도 적용 클래스 확률과 별개)이다.
2025–2026년을 이미 살펴본 뒤 후보를 확장한 회고 비교이며, 새 미관측 홀드아웃이나 실시간 성과가 아니다. 게이트(추천 사용 조건)는 기존과 동일하다.

## 2. 전체 요약

계열 35개(주별 14·월별 21), 선택 변경 2개, 게이트 통과 0개다. 공통 평가 행 합계 332개(JSON 기록값 332개), 선택 FULL 합계 394개다. 목표 기간이 겹치므로 행 수는 독립 표본 수가 아니며 비중첩 시간 구간을 함께 본다.
기존 스냅샷 FULL 합계 394개다.

선택이 바뀐 계열(과거 검증 기준, 시험 점수로 고르지 않음):

- AMD Ryzen 5 3600 (US_B07STGGQ18): forest T4.0 → arima T4.0 (선택 n=55, past_validation_only)
- Samsung 970 EVO Plus 1TB (US_B07MFZY2F2): forest T4.0 → sarima T2.0 (선택 n=76, past_validation_only)

## 3. 대표 3계열(그림 04 대응)

![대표 3계열의 후보별 Brier·변화율 MAE와 공통 평가 원점](assets/public/04_model_comparison.png)

그림 04는 아래 표의 Brier·변화율 MAE를 그린 것이다. 낮을수록 좋다. 같은 계열 안의 막대만 비교한다.

### AMD Ryzen 5 3600 (US·weekly)
선택 arima T4.0 (선택 n=55, past_validation_only), 기존 forest T4.0. 공통 평가 n=37 (비중첩 5, 2025-04-04–2026-07-03).

| 후보 | T | 상태 | n | Brier | 변화율 MAE | ECE |
|---|---:|---|---:|---:|---:|---:|
| L2 다항 로지스틱 회귀 | 4.0 | evaluated | 37 | 0.6615 | 32.6%p | 5.5%p |
| 깊이 제한 랜덤포레스트 | 4.0 | evaluated | 37 | 0.6661 | 32.6%p | 3.0%p |
| ARIMA(1,1,0) + drift | 4.0 | evaluated | 37 | 0.6658 | 32.8%p | 4.9%p |
| SARIMA(1,1,0)(1,0,0,s) | 4.0 | evaluated | 37 | 0.6655 | 31.7%p | 11.3%p |
| ETS(A,Ad,N) · log price | 2.0 | evaluated | 37 | 0.6572 | 32.0%p | 10.6%p |
| 과거 방향 빈도 / 가격 유지 | -- | evaluated | 37 | 0.7031 | 32.6%p | 9.7%p |

기존 스냅샷 FULL(참고용, forest T4.0, n=56, Brier 0.6613)은 과거 2후보 체계의 기록이다. 개선 판단은 같은 공통 원점 위의 기존-vs-선택 비교로만 읽는다:

| 비교(같은 공통 원점) | 모형 | Brier | 변화율 MAE |
|---|---|---:|---:|
| 기존 forest T4.0 | 깊이 제한 랜덤포레스트 | 0.6661 | 32.6%p |
| 선택 arima T4.0 | ARIMA(1,1,0) + drift | 0.6658 | 32.8%p |

### Samsung 970 EVO Plus 1TB (US·weekly)
선택 sarima T2.0 (선택 n=76, past_validation_only), 기존 forest T4.0. 공통 평가 n=53 (비중첩 6, 2025-01-03–2026-06-26).

| 후보 | T | 상태 | n | Brier | 변화율 MAE | ECE |
|---|---:|---|---:|---:|---:|---:|
| L2 다항 로지스틱 회귀 | 4.0 | evaluated | 53 | 0.6068 | 21.5%p | 27.2%p |
| 깊이 제한 랜덤포레스트 | 4.0 | evaluated | 53 | 0.6240 | 21.7%p | 27.3%p |
| ARIMA(1,1,0) + drift | 4.0 | evaluated | 53 | 0.6309 | 24.0%p | 27.7%p |
| SARIMA(1,1,0)(1,0,0,s) | 2.0 | evaluated | 53 | 0.5875 | 22.0%p | 24.8%p |
| ETS(A,Ad,N) · log price | 4.0 | evaluated | 53 | 0.6178 | 21.5%p | 27.0%p |
| 과거 방향 빈도 / 가격 유지 | -- | evaluated | 53 | 0.7041 | 22.1%p | 29.9%p |

기존 스냅샷 FULL(참고용, forest T4.0, n=53, Brier 0.6240)은 과거 2후보 체계의 기록이다. 개선 판단은 같은 공통 원점 위의 기존-vs-선택 비교로만 읽는다:

| 비교(같은 공통 원점) | 모형 | Brier | 변화율 MAE |
|---|---|---:|---:|
| 기존 forest T4.0 | 깊이 제한 랜덤포레스트 | 0.6240 | 21.7%p |
| 선택 sarima T2.0 | SARIMA(1,1,0)(1,0,0,s) | 0.5875 | 22.0%p |

### Ryzen 5 7500F (KR·monthly)
선택 logistic T1.0 (선택 n=0, incumbent_retained_insufficient_selection), 기존 logistic T1.0. 공통 평가 n=7 (비중첩 3, 2025-12-01–2026-06-01).

| 후보 | T | 상태 | n | Brier | 변화율 MAE | ECE |
|---|---:|---|---:|---:|---:|---:|
| L2 다항 로지스틱 회귀 | 1.0 | evaluated | 7 | 1.3522 | 24.2%p | 52.7%p |
| 깊이 제한 랜덤포레스트 | 1.0 | evaluated | 7 | 1.1661 | 22.1%p | 45.9%p |
| ARIMA(1,1,0) + drift | 1.0 | evaluated | 7 | 0.5571 | 7.3%p | 31.8%p |
| SARIMA(1,1,0)(1,0,0,s) | 1.0 | unavailable | 0 | -- | -- | -- |
| ETS(A,Ad,N) · log price | 1.0 | evaluated | 7 | 0.5491 | 8.7%p | 32.6%p |
| 과거 방향 빈도 / 가격 유지 | -- | evaluated | 7 | 0.9611 | 9.0%p | 41.2%p |

기존 스냅샷 FULL(참고용, logistic T1.0, n=7, Brier 1.3522)은 과거 2후보 체계의 기록이다. 개선 판단은 같은 공통 원점 위의 기존-vs-선택 비교로만 읽는다:

| 비교(같은 공통 원점) | 모형 | Brier | 변화율 MAE |
|---|---|---:|---:|
| 기존 logistic T1.0 | L2 다항 로지스틱 회귀 | 1.3522 | 24.2%p |
| 선택 logistic T1.0 | L2 다항 로지스틱 회귀 | 1.3522 | 24.2%p |

선택 자료가 없어 기존 모형을 유지한다. 시험 구간에서 시계열 후보의 점수가 낮게 보여도 회고 조회일 뿐이며 모형 교체 근거가 아니다. 시험 구간 성적으로 선택하지 않는다.

계절·시계열 모형이 자동으로 우월하지 않다. 35계열 중 선택 변경은 2개뿐이고 통과는 0개다. SARIMA 제외(월간)는 성능 열위가 아니라 자료 길이의 정상 결과다.

## 4. 전체 35계열 커버리지(그림 05 대응)

![35계열 공통 평가 n·FULL n과 선택 모형](assets/public/05_model_coverage.png)

공통 n은 후보 비교에 쓴 동일 원점 수, 기존 FULL n은 과거 스냅샷의 전체 평가 수, 선택 FULL n은 선택 모형의 전체 평가 수다. `forecast_metrics.csv`·`forecast.json`은 선택 FULL 기준으로 덮어썼다. 공통 0은 비교 불가이며 원시 자료 없음을 뜻하지 않는다. 일부 계열은 시계열 단독 산출만 있고 공통 비교가 없을 수 있다(아래 단독 산출 목록 참조).

| 계열 | 지역·빈도 | 선택 모형 | 공통 n | 기존 FULL n | 선택 FULL n | 비중첩 | 게이트 |
|---|---|---|---:|---:|---:|---:|---|
| AMD Ryzen 5 3600 | US·weekly | arima T4.0 | 37 | 56 | 56 | 5 | 미통과 |
| Crucial DDR4-3200 16GB CT16G4DFRA32A | US·weekly | logistic T1.0 | 20 | 20 | 20 | 3 | 미통과 |
| Samsung 970 EVO Plus 1TB | US·weekly | sarima T2.0 | 53 | 53 | 53 | 6 | 미통과 |
| EVGA RTX 3090 FTW3 Ultra 24G-P5-3987-KR | US·weekly | logistic T1.0 | 0 | 0 | 0 | 0 | 미통과 |
| NVIDIA GeForce RTX 3070 8GB (Amazon.in listing) | IN·weekly | logistic T1.0 | 0 | 0 | 0 | 0 | 미통과 |
| EVGA RTX 3080 FTW3 Ultra Gaming (Renewed) | US·weekly | logistic T1.0 | 23 | 23 | 23 | 4 | 미통과 |
| Samsung 990 Pro SSD 1TB PCIe 4.0 NVMe M.2 | US·weekly | logistic T1.0 | 32 | 32 | 32 | 3 | 미통과 |
| WD_Black SN850X 1TB NVMe SSD (WDS100T2X0E) | US·weekly | logistic T1.0 | 52 | 52 | 52 | 5 | 미통과 |
| SK Hynix Platinum P41 1TB PCIe NVMe Gen4 M.2 2280 | US·weekly | logistic T1.0 | 15 | 20 | 20 | 3 | 미통과 |
| Crucial T500 1TB PCIe Gen4 NVMe Gaming SSD with heatsink | US·weekly | logistic T1.0 | 0 | 0 | 0 | 0 | 미통과 |
| AMD Ryzen 5 9600X 3.9 GHz | IN·weekly | logistic T1.0 | 0 | 0 | 0 | 0 | 미통과 |
| Gigabyte RTX 4060 Eagle OC 8G GV-N4060EAGLE OC-8GD | US·weekly | logistic T1.0 | 0 | 0 | 0 | 0 | 미통과 |
| Crucial 16GB DDR5-5600 CL46 CT16G56C46U5 desktop | IN·weekly | logistic T1.0 | 0 | 0 | 0 | 0 | 미통과 |
| Crucial Pro 16GB DDR4-3200 CP16G4DFRA32A single module | IN·weekly | logistic T1.0 | 0 | 0 | 0 | 0 | 미통과 |
| Ryzen 5 7500F | KR·monthly | logistic T1.0 | 7 | 7 | 7 | 3 | 미통과 |
| Core i5-14400F | KR·monthly | logistic T1.0 | 4 | 7 | 7 | 2 | 미통과 |
| Ryzen 5 7600 | KR·monthly | logistic T1.0 | 7 | 7 | 7 | 3 | 미통과 |
| Ryzen 5 9600X | KR·monthly | logistic T1.0 | 7 | 7 | 7 | 3 | 미통과 |
| MSI RTX 4060 8GB | KR·monthly | logistic T1.0 | 7 | 7 | 7 | 3 | 미통과 |
| MSI RTX 5070 Ti 16GB | KR·monthly | logistic T1.0 | 4 | 7 | 7 | 2 | 미통과 |
| PALIT 5070 Ti 16GB | KR·monthly | logistic T1.0 | 1 | 1 | 1 | 1 | 미통과 |
| MSI 5070 Ti GAMING TRIO | KR·monthly | logistic T1.0 | 1 | 7 | 7 | 1 | 미통과 |
| GIGABYTE 5070 Ti GAMING OC | KR·monthly | logistic T1.0 | 4 | 7 | 7 | 2 | 미통과 |
| GALAX 5070 Ti BLACK 2X | KR·monthly | logistic T1.0 | 5 | 5 | 5 | 2 | 미통과 |
| MSI RTX 5060 Ti 16GB | KR·monthly | logistic T1.0 | 1 | 7 | 7 | 1 | 미통과 |
| MSI RTX 5060 8GB | KR·monthly | logistic T1.0 | 1 | 7 | 7 | 1 | 미통과 |
| SAPPHIRE RX 9060 XT 16GB | KR·monthly | logistic T1.0 | 1 | 7 | 7 | 1 | 미통과 |
| 삼성 DDR4-3200 16GB | KR·monthly | logistic T1.0 | 4 | 7 | 7 | 2 | 미통과 |
| 삼성 DDR5-5600 16GB | KR·monthly | logistic T1.0 | 7 | 7 | 7 | 3 | 미통과 |
| 삼성 990 PRO 1TB | KR·monthly | logistic T1.0 | 7 | 7 | 7 | 3 | 미통과 |
| SK하이닉스 P41 1TB | KR·monthly | logistic T1.0 | 7 | 7 | 7 | 3 | 미통과 |
| TeamGroup DDR4-3200 Elite 서린 16GB | KR·monthly | logistic T1.0 | 4 | 6 | 6 | 2 | 미통과 |
| Crucial DDR5-5600 CL46 대원 16GB | KR·monthly | logistic T1.0 | 7 | 7 | 7 | 3 | 미통과 |
| WD BLACK SN850X 1TB | KR·monthly | logistic T1.0 | 7 | 7 | 7 | 3 | 미통과 |
| Crucial T500 대원 1TB | KR·monthly | logistic T1.0 | 7 | 7 | 7 | 3 | 미통과 |

공통 비교 없이 시계열 단독 산출만 있는 계열(점수·선택 제외): NVIDIA GeForce RTX 3070 8GB (Amazon.in listing) (78행); Crucial T500 1TB PCIe Gen4 NVMe Gaming SSD with heatsink (90행); AMD Ryzen 5 9600X 3.9 GHz (30행); Gigabyte RTX 4060 Eagle OC 8G GV-N4060EAGLE OC-8GD (70행); Crucial 16GB DDR5-5600 CL46 CT16G56C46U5 desktop (50행); Crucial Pro 16GB DDR4-3200 CP16G4DFRA32A single module (84행).

## 5. 모형별 집계

| 후보 | 산출 계열 | 공통 미산출 계열 | 공통 행 합계 | 전체 행 합계 | 단독 행 합계 | 주요 실패 사유 |
|---|---:|---:|---:|---:|---:|---|
| logistic | 28 | 7 | 332 | 394 | -- | -- |
| forest | 28 | 7 | 332 | 394 | -- | -- |
| arima | 26 | 9 | 326 | 350 | 297 | insufficient_history 599; nonconverged_fit 3 |
| sarima | 6 | 29 | 212 | 212 | 58 | fewer_than_two_seasonal_cycles 446; insufficient_history 599; sparse_seasonal_cycles 427 |
| ets | 26 | 9 | 326 | 353 | 297 | insufficient_history 599 |
| baseline | 28 | 7 | 332 | -- | -- | -- |

실패 집계는 2023년 이후 전체 롤링 요청(최신 미성숙 원점 포함) 기준이며, 공통·전체 평가 행 수와 분모가 다르다.
미산출은 공통 비교 불가이며 원시 자료 없음을 뜻하지 않는다. 단독 행은 기존 분류 비교가 없는 원점의 시계열 추가 산출로 점수·선택에서 제외한다.

## 6. 제한·주의

- 2025–2026년 결과를 이미 살펴본 뒤 후보를 확장한 회고 비교입니다. 새 미관측 홀드아웃이나 실시간 성과가 아닙니다.
- 모형·온도는 2023–2024년 공통 과거 원점에서만 선택합니다. 선택 표본 부족 시 기존 모형을 유지하며 시험 점수의 최저 모형으로 교체하지 않습니다.
- 국내 7–22개월 자료는 연간 계절성 두 주기도 충족하지 않습니다. SARIMA 제외를 성능 열위로 읽지 않습니다.
- 각 SKU에서 산출 가능한 후보의 공통 원점만 비교하므로 기존 전체 평가보다 n이 작습니다. 후보별 전체 평가 가능 행 수와 실패 사유를 함께 기록합니다.
- 전체 평가 allTestN도 기존 분류 모형이 산출한 평가 원점 범위 안의 수입니다. 그 밖에서 시계열 모형만 산출한 사례는 standaloneTestN에 기록하며 점수 비교·교체 근거에 쓰지 않습니다.
- 3개월 목표가 겹치므로 n은 독립 표본 수가 아닙니다. 비중첩 시간 구간 수를 함께 봅니다.
- 달력의 결측은 NaN으로 유지합니다. 칼만 필터의 내부 상태 예측은 관측 가격이나 정답으로 추가하지 않습니다.
- SARIMA는 주별 52주 주기 가정의 제한된 고정 차수 후보입니다. 모든 차수·계절주기·ETS 변형의 우열을 검증한 것은 아닙니다.
- ARIMA·SARIMA·ETS는 로그가격의 가우시안 예측 분포를 가정합니다. 확률 온도는 클래스 확률에만 적용하며 80/95% 가격구간은 원분포 구간입니다. 급변·두꺼운 꼬리·매개변수 추정 불확실성을 충분히 반영하지 못할 수 있습니다.
- 분류 모형은 국내 패널/해외 SKU 학습이고 시계열 모형은 각 SKU의 관측 가격을 학습합니다. 학습 대상과 이용 가능한 정답 정보가 다르지만 예측 시점과 목표·평가 원점은 동일합니다.
- 수렴 실패·이력 부족·결측이 많은 주기를 제외한 공통 표본에는 선택 편향이 남습니다. 미산출은 0점이 아닙니다.
- 실패 사유별 건수는 2023년 이후 전체 산출 요청 원점 수이며, 선택·시험뿐 아니라 최신 미성숙 목표의 요청도 포함합니다. allTestN과 분모가 다릅니다.
- 관측 스냅샷은 2026-10-23으로 고정되어 있습니다. 자동 갱신·미래 주가·ETH·재고·출시 정보는 사용하지 않습니다.

방법 근거: [statsmodels SARIMAX](https://www.statsmodels.org/stable/generated/statsmodels.tsa.statespace.sarimax.SARIMAX.html), [statespace ExponentialSmoothing](https://www.statsmodels.org/stable/generated/statsmodels.tsa.statespace.exponential_smoothing.ExponentialSmoothing.html), [statespace missing data example](https://www.statsmodels.org/stable/examples/notebooks/generated/statespace_sarimax_internet.html), [FPP3 시계열 교차 검증](https://otexts.com/fpp3/tscv.html). 게이트 정의는 `docs/forecast_protocol.md`.
