> 공개판 안내: 작성 당시 연구 기록입니다. 원가격·주가·벤치마크 원본과 복원 가능한 파일은 제외했습니다. 현재 공개 범위·실행법은 루트 README와 데이터 이용 안내를 따릅니다.

# 3개월 PC 부품 가격 모형 검증 결과

가격 스냅샷 2026-10-23, 모델 비교 2026-10-24. ARIMA·SARIMA·ETS를 기존 로지스틱·랜덤포레스트와 비교했다. 구매 추천 기준 통과는 **0/35계열**이다. 새 후보는 2023–2024년 과거 선택 구간으로만 선택했다. 2025–2026년은 이미 결과를 열람한 회고 벤치마크이며 새 미관측 홀드아웃이 아니다.

## 반영한 선택과 점수의 범위

총 선택 모델 평가 394행, 후보 공통 평가 332행. 같은 3개월 목표가 겹치므로 독립 표본 수가 아니다. 아래는 선택 모델의 **전체 산출 가능 평가**이며, 후보별 우열 비교는 공개 집계 JSON의 공통 원점 점수를 사용한다.

| 계열 | 선택 모델 | 과거 선택 n | 전체 시험 n / 비중첩 | Brier / 빈도 기준 | 변화율 MAE / 유지 |
|---|---|---:|---:|---:|---:|
| US · AMD Ryzen 5 3600 | arima | 55 | 56 / 6 | 0.6441 / 0.6645 | 35.81%p / 35.78%p |
| US · Crucial DDR4-3200 16GB CT16G4DFRA32A | logistic | 0 | 20 / 3 | 1.2232 / 0.5741 | 40.54%p / 14.74%p |
| US · Samsung 970 EVO Plus 1TB | sarima | 76 | 53 / 6 | 0.5875 / 0.7041 | 21.99%p / 22.10%p |
| US · EVGA RTX 3090 FTW3 Ultra 24G-P5-3987-KR | logistic | 0 | 0 / 0 | — / — | — / — |
| IN · NVIDIA GeForce RTX 3070 8GB (Amazon.in listing) | logistic | 0 | 0 / 0 | — / — | — / — |
| US · EVGA RTX 3080 FTW3 Ultra Gaming (Renewed) | logistic | 0 | 23 / 4 | 1.1482 / 0.6770 | 23.40%p / 9.98%p |
| US · Samsung 990 Pro SSD 1TB PCIe 4.0 NVMe M.2 | logistic | 0 | 32 / 3 | 1.2832 / 0.5699 | 55.20%p / 47.76%p |
| US · WD_Black SN850X 1TB NVMe SSD (WDS100T2X0E) | logistic | 0 | 52 / 5 | 0.7765 / 0.6233 | 36.04%p / 37.67%p |
| US · SK Hynix Platinum P41 1TB PCIe NVMe Gen4 M.2 2280 | logistic | 0 | 20 / 5 | 1.3060 / 0.7345 | 50.04%p / 47.84%p |
| US · Crucial T500 1TB PCIe Gen4 NVMe Gaming SSD with heatsink | logistic | 0 | 0 / 0 | — / — | — / — |
| IN · AMD Ryzen 5 9600X 3.9 GHz | logistic | 0 | 0 / 0 | — / — | — / — |
| US · Gigabyte RTX 4060 Eagle OC 8G GV-N4060EAGLE OC-8GD | logistic | 0 | 0 / 0 | — / — | — / — |
| IN · Crucial 16GB DDR5-5600 CL46 CT16G56C46U5 desktop | logistic | 0 | 0 / 0 | — / — | — / — |
| IN · Crucial Pro 16GB DDR4-3200 CP16G4DFRA32A single module | logistic | 0 | 0 / 0 | — / — | — / — |
| KR · Ryzen 5 7500F | logistic | 0 | 7 / 3 | 1.3522 / 0.9611 | 24.23%p / 9.04%p |
| KR · Core i5-14400F | logistic | 0 | 7 / 3 | 0.9462 / 0.7733 | 16.14%p / 5.01%p |
| KR · Ryzen 5 7600 | logistic | 0 | 7 / 3 | 0.2540 / 0.4733 | 12.78%p / 8.98%p |
| KR · Ryzen 5 9600X | logistic | 0 | 7 / 3 | 1.4976 / 0.9785 | 22.01%p / 7.76%p |
| KR · MSI RTX 4060 8GB | logistic | 0 | 7 / 3 | 1.2425 / 0.7611 | 22.44%p / 6.10%p |
| KR · MSI RTX 5070 Ti 16GB | logistic | 0 | 7 / 3 | 0.6762 / 0.5733 | 18.81%p / 11.19%p |
| KR · PALIT 5070 Ti 16GB | logistic | 0 | 1 / 1 | 0.5193 / 1.0068 | 24.61%p / 20.34%p |
| KR · MSI 5070 Ti GAMING TRIO | logistic | 0 | 7 / 3 | 1.3115 / 0.8386 | 22.30%p / 10.51%p |
| KR · GIGABYTE 5070 Ti GAMING OC | logistic | 0 | 7 / 3 | 1.1874 / 0.8305 | 19.36%p / 5.94%p |
| KR · GALAX 5070 Ti BLACK 2X | logistic | 0 | 5 / 2 | 0.5782 / 0.6574 | 14.92%p / 11.66%p |
| KR · MSI RTX 5060 Ti 16GB | logistic | 0 | 7 / 3 | 0.9943 / 0.7386 | 21.27%p / 12.06%p |
| KR · MSI RTX 5060 8GB | logistic | 0 | 7 / 3 | 1.2642 / 0.8386 | 22.39%p / 11.10%p |
| KR · SAPPHIRE RX 9060 XT 16GB | logistic | 0 | 7 / 3 | 0.7291 / 0.6509 | 16.47%p / 11.05%p |
| KR · 삼성 DDR4-3200 16GB | logistic | 0 | 7 / 3 | 1.1508 / 0.7229 | 24.83%p / 15.95%p |
| KR · 삼성 DDR5-5600 16GB | logistic | 0 | 7 / 3 | 0.3092 / 0.3616 | 13.93%p / 13.86%p |
| KR · 삼성 990 PRO 1TB | logistic | 0 | 7 / 3 | 0.7742 / 0.6683 | 22.48%p / 17.89%p |
| KR · SK하이닉스 P41 1TB | logistic | 0 | 7 / 3 | 0.7843 / 0.5948 | 25.35%p / 20.22%p |
| KR · TeamGroup DDR4-3200 Elite 서린 16GB | logistic | 0 | 6 / 2 | 1.8096 / 0.8947 | 22.40%p / 5.02%p |
| KR · Crucial DDR5-5600 CL46 대원 16GB | logistic | 0 | 7 / 3 | 0.5897 / 0.4657 | 16.62%p / 17.02%p |
| KR · WD BLACK SN850X 1TB | logistic | 0 | 7 / 3 | 1.0637 / 0.5923 | 43.26%p / 38.27%p |
| KR · Crucial T500 대원 1TB | logistic | 0 | 7 / 3 | 0.3664 / 0.4045 | 19.72%p / 19.94%p |

## 방법과 자료의 한계

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

- 국내 아카이브 26건 중 25건은 별도 참고용, 1건은 일반·현금 가격 충돌로 격리했다. 월간 minPrice와 이어 붙이지 않는다.
- 신규 해외 8계열 원문 3,065점과 기존 6계열의 가격 정의·국가·통화를 분리한다. 국내는 최대 완료 월 22개이며 연간 SARIMA를 제외했다.
- 국내 최신 목표는 2026-09→2026-12 월간 버킷이며 2026-10-23 현재 결제 가격에서 3개월 뒤의 국내 가격을 예측한 것이 아니다.

## 재현·감사

`python scripts/build_forecast.py` → `python scripts/compare_forecast_models.py` → `python scripts/write_forecast_report.py`. 별도 허가 원본이 필요한 오프라인 절차다. 공개 집계만으로 원모델을 재학습할 수 없다.

- 상세 비교 규약: `docs/forecast_protocol.md`; 결과 설명: `docs/model_comparison.md`.
- 공개 통계: `data/public/model_comparison.json`, `data/public/model_comparison_metrics.csv`.
- 비공개 연구 감사: `data/analysis/2026-10-24/model_comparison/candidate_predictions.json`, SKU별 적합 기록과 원본 해시.
- `forecast_predictions.csv`, `forecast_metrics.csv`, `forecast.json`은 새 선택 모델을 반영했다. 최초 두 후보의 결과는 `legacy_forecast.json`에 보존했다.
- 최초 두 후보 선택 감사는 `forecast_selection_predictions.csv`; 확장 후보 선택 옵션·온도 점수는 공개 JSON의 `selection.options`에 있다.
