> 공개판 안내: 작성 당시 연구 기록입니다. 원가격·주가·벤치마크 원본과 복원 가능한 파일은 제외했습니다. 현재 공개 범위·실행법은 루트 README와 데이터 이용 안내를 따릅니다.

# ETH PoW 채굴 수익성 대용 지표 — 데이터 근거 문서

## 0. 한 줄 요약

- 실제 카드별·실측 채굴 수익성은 확보하지 못했다. 아래 산출물은 **가정별 대용 proxy 2종**이다.
- A) **수수료 전액 포함 대용**: `(IssTotNtv + FeeTotNtv) × PriceUSD` 를 100MH/s로 환산. London(2021-08-05) 이후에는 광부가 받지 못한 소각 base fee도 더하므로 **수수료 수입을 과대평가**한다.
- B) **수수료 제외 대용**: `IssTotNtv × PriceUSD` 를 100MH/s로 환산. 수수료를 전부 빼고, MEV를 빠뜨리며, Beacon(합의레이어) 스테이킹 발행량이 포함되어 **엄밀한 하한이 아니다**.
- 어느 쪽도 실제 광부 매출의 상한·하한을 보장하지 않는다. London 전후 비교를 실제 순이익 차이로 말하면 안 된다.

## 1. 확보한 지표 (공개 자료만)

| 지표 | 단위 | 출처 정의 |
|---|---|---|
| PriceUSD | USD | 다음날 00:00 UTC 기준 고정 종가 (Coin Metrics fixing/reference rate) |
| HashRate | TH/s (ETH) | 일간 평균 해시레이트. ETH 산식 = `(DiffMean / BlkIntMean) / 1e12` |
| FeeTotNtv | ETH | 해당 일에 지불된 수수료 전액 합. 신규 발행을 제외한다 |
| IssTotNtv | ETH | 해당 일에 신규 발행된 네이티브 단위 전액 합 |
| IssTotUSD | USD | 신규 발행분의 USD 가치 합 |

- 확보 경로: Coin Metrics community API (`/v4/timeseries/asset-metrics`, assets=eth, frequency=1d, 2020-01-01~2023-01-01) + 원본 보존 `data/verification/2026-10-22/crypto/cm_eth_daily_raw.json`.
- GitHub 공개 CSV(`coinmetrics/data` `csv/eth.csv`) 헤더를 1회 조회로 확인: 노출 지표는 community API와 동일한 32종. `RevUSD/RevNtv`, 소각량(`FeeBurn*`), 우선순위 수수료(`FeePrio*/FeeTip*`), 광부/엉클 내역 지표는 **어느 쪽에도 없다**.
- community API에 `RevUSD` 를 직접 요청하면 `forbidden` 을 반환한다. 실제 광부 매출(RevUSD)은 무료 공개 범위에 없다.
- [공식 발행량 정의](https://gitbook-docs.coinmetrics.io/network-data/network-data-overview/supply/supply-issuance)는 Beacon 출범 이후 머지 이전에도 ETH 발행량에 채굴 보상과 스테이킹 보상이 함께 포함된다고 명시한다. 따라서 2020-12-01 이후 두 대용 지표 모두 순수 채굴 보상이 아니다. `beacon_issuance_included=1`로 표시한다. ETH_CL `IssContNtv` 분리 시계열을 공개 API에 요청했으나 HTTP 403으로 확보하지 못해 빼지 못했다.

### 후보 소스 확인 결과 (각 1회 정상 GET, 차단 시 우회 없음)

- BitinfoCharts `ethereum-mining_profitability.html`: Cloudflare 챌린지 페이지(약 5.8KB)만 반환. 우회하지 않고 종료.
- Etherscan `chart/blockreward`: 페이지 1회분에는 차트 데이터 배열이 내장되어 있지 않다(`dataArray = []`, 후속 XHR 필요). 추가 호출 없이 종료.
- 결론: 실제 광부 보상(보상+수수료) 시계열의 공개 직접 확보는 실패. 위 A/B 대용으로 진행한다.

## 2. 타임스탬프 경계 (CoinMetrics 일자 의미)

- API `time` 값(예: `2020-01-01T00:00:00Z`)은 **해당 일 00:00 UTC 구간의 시작**을 가리킨다.
- [공식 Price 정의](https://gitbook-docs.coinmetrics.io/network-data/network-data-overview/market/price)에 따르면 PriceUSD 일별 값은 **그 날의 끝(다음날 00:00 UTC) 기준 종가**다. 날짜 라벨을 그대로 유지한다.
- 메인 결합은 GPU 관측일 D의 전날까지 **D-7~D-1의 7개 원본 날짜 값**을 평균한다. 독일 가격의 정확한 장중 시각이 일정하지 않으므로 장중 선행성을 검증한 것은 아니다. 날짜 창을 ±1일 옮긴 민감도도 별도 계산한다.

## 3. 수수료 소각 (London / EIP-1559, 2021-08-05)

- London 업그레이드는 2021-08-05 이더리움 메인넷에 적용됐고, EIP-1559가 base fee 소각을 도입했다.
- 소각되는 base fee와 달리 **miner에게 가는 것은 priority fee(팁)뿐**이다. 따라서 London 이후 `FeeTotNtv` = 팁 + 소각된 base fee이며, 이를 전부 광부 보상으로 합산하는 A안은 소각분만큼 과대하다.
- 소각량을 빼려면 `FeeBurn*` 계열이 필요하지만 무료 범위에 없어 보정 불가. `london_burn_overincluded=1` 플래그로 과대포함 구간(수익값 존재 + date ≥ 2021-08-05)을 표시한다.

## 4. Merge 경계 (2022-09-15)

- 이더리움 Merge는 2022-09-15 완료됐고, 그 순간부터 기존 PoW 채굴은 유효한 블록 생성 수단이 아니다.
- 실측 확인: community HashRate는 **2022-09-14가 마지막**이고 09-15부터 값이 없다. IssTotNtv도 09-14 약 13997 ETH → 09-15 약 1559 ETH로 붕괴(PoW 블록·엉클 보상 종료, PoS 발행만 잔류)한다.
- 처리: 2022-09-15는 **부분일**로 수익 계산에서 제외(가격만 유지). 2022-09-16 이후는 PoW 수익성 **해당없음**(결측과 구분, 0으로 채우지 않음). PoS 발행량은 proxy에 절대 섞지 않는다.

## 5. 산식

- A안 일별: `rev_usd_per100mh_gross = (IssTotNtv + FeeTotNtv) × PriceUSD / (HashRate_THS × 1e6) × 100`.
- B안 일별: `iss_usd_per100mh = IssTotNtv × PriceUSD / (HashRate_THS × 1e6) × 100`.
- 일별 파일의 7일 후행평균(`*_7d`): 당일 포함 직전 7일 전부 값이 있을 때만 평균, 하나라도 없으면 빈칸. 메인 GPU 결합은 **D-1 행의 7일 평균과 같은 창(D-7~D-1)**을 원본 일별 값에서 다시 계산한다.
- 전기 시나리오: 200W × 24h = 4.8kWh/일 → 0.10 USD/kWh는 0.48 USD/일, 0.20 USD/kWh는 0.96 USD/일. **고정 가정이며 실제 RTX 실측이 아니다.** `net_*` = gross − 전기료(참고용, A안 기준이므로 실제 순이익이 아님).
- 무보간: 빈칸은 빈칸으로 둔다. 수익 반환율(return)은 만들지 않는다(가격 return만 weekly에, 인접 달력주 조건).

## 6. Weekly / Monthly 규칙

- Weekly: 기존 주가 그리드와 동일(토~금, week_end 2020-01-10~2022-12-30, 156주). `rev_*_week_mean` 은 해당 주 수익값 존재일 평균. Merge 포함 주는 `mixed`(2022-09-10~16주: n_rev_days=5, 마지막 수익일 09-14), 이후 15주는 `terminated`(수익 빈칸, 가격은 유지). 가격 return은 바로 전 달력주 가격 존재 시에만.
- Monthly(메인 결합용 정의, 본 산출물에 파일 없음): 일별 crypto의 **해당 달 전체 평균**. 2022-09월 PoW 월간값은 Merge 혼합이므로 **월간 결측**으로 둔다. GPU 월간(eBay)과 맞출 때는 같은 달 일별 평균을 쓴다.
- GPU 불규칙 관측(독일 33시점/3080은 29시점) 결합: 위 창으로 수준과 실제 관측 간 로그 변화율을 계산한다. 인접 달력주 변화율 표본은 3070/3080/3090 순서로 **1/0/1개**라 주별 상관·회귀는 계산하지 않는다.

## 7. 산출 파일

- `data/processed/2026-10-22/crypto/eth_daily.csv` — 1096행(2020-01-01~2022-12-31), 23열. 대용 지표 계산 가능 988일(2020-01-01~2022-09-14), 부분일 1일, PoW 종료 107일, 미관측 0일.
- `data/processed/2026-10-22/crypto/eth_weekly.csv` — 156행, 21열. active 140주 / mixed 1주 / terminated 15주.
- `data/processed/2026-10-22/crypto/quality_summary.json`, `sources.json` — 집계치와 출처.
- 원본: `data/verification/2026-10-22/crypto/cm_eth_daily_raw.json` (SHA256 `095b9879d729c5fbfc39832609eb6bc2af6ec1e58ab5a47ca775850ebc0bacf9`), `cm_fetch_manifest.json`.
- 재현: `python3 scripts/prepare_eth_mining.py` (표준라이브러리만), 검증 `python3 -m unittest tests.test_eth_mining` (6건 통과).

## 8. 남은 한계 (메인 보고서에 그대로 인용 가능)

1. 실제 카드별·실측 채굴 수익성을 확보하지 못했다. A/B 모두 대용이다.
2. A안은 London 이후 소각분을 과대포함한다. B안은 수수료·MEV를 빠뜨리며 엄밀한 하한이 아니다.
3. 두 지표 모두 Beacon 출범 이후 스테이킹 발행량이 섞인다. 별도 분리 자료를 확보하지 못해 보정하지 못했다. 두 지표가 비슷한 상관을 보여도 실측 채굴 수익성을 검증한 것이 아니다.
4. 전기료는 고정 가정이다. 실제 카드 전력·요금·다운타임·풀 수수료·난이도 급변 반영 없음.
5. 가격은 일 마감 고정가라 장중 변동·슬리피지를 반영하지 않는다.

## 9. 공식 정의·이벤트 근거

- [Coin Metrics HashRate: ETH 단위와 산식](https://gitbook-docs.coinmetrics.io/network-data/network-data-overview/mining/hash-rate)
- [Coin Metrics 총수수료](https://gitbook-docs.coinmetrics.io/network-data/network-data-overview/fees-and-revenue/fees)
- [이더리움 공식 포크 연혁: Beacon·London](https://ethereum.org/ethereum-forks/)
- [EIP-1559: base fee 소각·priority fee 지급](https://eips.ethereum.org/EIPS/eip-1559)
- [이더리움 공식 Merge 설명: 2022-09-15 PoW 종료](https://ethereum.org/roadmap/merge/)
