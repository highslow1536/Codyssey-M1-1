# 데이터 공개 범위와 취득·재현 안내

점검 2026-10-24 · [출처별 재배포 검토](../docs/data_redistribution.md) · [권리·변경 고지](../RIGHTS.md)

## 포함 자료

| 자료 | 공개 파일 | 원본·가공 구분 |
|---|---|---|
| Coin Metrics Community ETH | [지표별 원본 JSON](verification/2026-10-22/crypto/cm_eth_daily_raw.json), [수집 기록](verification/2026-10-22/crypto/cm_fetch_manifest.json) | 2026-10-21에 저장한 지표별 응답 묶음. CC BY-NC 4.0 |
| ETH 일별·주별 | [일별 1,096행](processed/2026-10-22/crypto/eth_daily.csv), [주별 156행](processed/2026-10-22/crypto/eth_weekly.csv), [품질 요약](processed/2026-10-22/crypto/quality_summary.json) | 2020\~2022 선택·주 집계·변화율·수익 대용을 자체 계산. 라이선스·변경 표시 유지 |
| 공개 분석·화면 입력 | [대시보드 JSON](public/dashboard.json), [연도별 요약](public/eth_yearly_summary.csv), [입력 해시·집계](public/eth_analysis.json) | JSON의 series는 ETH만 포함. forecast는 부품 모형의 자체 오차 집계 |
| 자체 집계 결과 | [과거 상관](analysis/2026-10-22/correlations.csv), [시차별 상관](analysis/2026-10-22/lag_correlations.csv), [예측 점수](analysis/2026-10-23/forecast/forecast_metrics.csv) | 원가격·개별 예측 정답 행이 없는 통계. 원본의 공개 라이선스라는 뜻은 아님 |

Coin Metrics 출처: [공식 데이터 저장소](https://github.com/coinmetrics/data). 라이선스: [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/). 비영리·출처·라이선스 표시·변경 고지 조건을 지킨다. API 응답을 재수집하지 않고 보존한 원본으로 공개본을 만들었다.

## excluded

다음 자료는 로컬 연구에 사용했지만 공개 저장소에는 **값을 포함하지 않았다**. 미공개 파일은 0행 CSV나 합성 데이터로 대체하지 않았다.

| 제외 범위 | 공개하지 않은 이유 | 대신 제공하는 내용 |
|---|---|---|
| PriceHistory 원문·History.Price·주간 가격 | 비상업 개인 이용과 재배포 허가는 다름. 재배포·파생 이용의 허가 근거 미확인 | ASIN·SKU·원문 URL, 전처리 코드·설정, 관측 수·상관·검증 점수 |
| 다나와 PC/mobile·몰 견적·아카이브 가격 | 상품 가격 DB의 복제·가공·대량 재배포 허가 미확인 | 제품 식별자·선택 조건, 가격 기준·감사·동급 비교 로직 |
| Yahoo 주가와 ETH-USD | 공식 안내에서 재배포 금지. Coin Metrics ETH와 구분 | 심볼·기간·주 집계 코드, 자체 상관 통계. Yahoo 시계열을 CM 자료로 갈아 끼워 재현했다고 하지 않음 |
| 3DCenter·Tom's/eBay GPU 표 | 전체 조사표·기사·이미지·시계열 데이터셋의 재배포 허가 미확인 | 조사일·월 라벨 기준, 전후 비교 방법·자체 요약·출처 링크 |
| PassMark·TechPowerUp·TechSpot 벤치마크 | 공개 열람을 점수표·차트 재발행 허가로 볼 근거 없음 | 측정 조건·한계·원문 링크·계산 코드 |
| 기존 앱 JSON·다운로드·ZIP·원가격 곡선·견적 캡처 | 원문을 빼도 동일 값을 복원하거나 다시 내려받을 수 있음 | 전체 앱 소스와 허용 자료로 실행하는 별도 공개 화면 |

파일별 원래 경로·SHA-256·크기·제외 사유는 [excluded_inventory.csv](excluded_inventory.csv)에 있다. [source_catalog.json](source_catalog.json)은 출처 URL 색인이며, [references_omitted.json](references_omitted.json)은 문서에서 제외 파일 대신 이 안내로 연결한 항목이다. URL·해시는 데이터 이용 허가나 당시 원본의 재취득 보장이 아니다.

## 제한된 입력을 보유한 경우의 복원

1. 먼저 해당 제공자의 현재 조건과 필요한 서면 허가·계약을 확인한다. 이 저장소의 수집 코드가 실행 허가를 대신하지 않는다.
2. [출처별 문서](../docs/reproduction.md)와 코드의 입력 경로·JSON 필드·기간·SKU를 확인한다. 원래 경로는 제외 목록에 남겼다.
3. 합법적으로 보유한 같은 입력을 원래 경로에 배치하고 SHA-256을 대조한다. 과거 시점의 동일 바이트를 확보하지 못하면 **새 분석**으로 구분한다.
4. 전체 재현 순서는 [기존 전체 분석 절차](../docs/full_reproduction.md)를 참고한다. 이 절차는 공개본만으로 완료되지 않는다.

자동 수집 금지·이용 제한을 우회하거나, 누락을 보간·합성해 원래 결과와 같다고 표시하지 않는다. 과제는 원본 대신 수집 방법·코드·설명을 제공하는 방식도 허용하며, 공개본에는 별도로 실제 1,096점 ETH 시계열을 포함했다.
