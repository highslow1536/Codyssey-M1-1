> 공개판 안내: 작성 당시 연구 기록입니다. 원가격·주가·벤치마크 원본과 복원 가능한 파일은 제외했습니다. 현재 공개 범위·실행법은 루트 README와 데이터 이용 안내를 따릅니다.

# GPU eBay 월별 데이터 근거

기준일 2026-10-22. Tom Hardware 원문 p11~p26에서
RTX 3070 / RTX 3080-10GB / RTX 3090 월별 평균가격과 QTY Sold만 추출했다.
공개 HTML만 사용했고, secrets/.env/개인자료는 사용하지 않았다.
메인 결합에는 원문 확인 16개월(2021-09~2022-12)만 사용한다.

## 원문 범위와 판매기간 확인

- p11 Dec 2022 ~ p22 Jan 2022, p23 Dec 2021, p24 Nov 2021, p25 Oct 2021,
  p26 Sep 2021(월간) + Oct 1-15(부분월).
- 판정은 title 판매월 표기와 표 head 가격열 + p26 본문으로 했다.
- 월간표와 주별자료를 혼동하지 않았다. head는 모두 월간 가격열이다.
- p26 Table0(Oct 1-15)은 그리드에서 제외하고 partial 파일로만 보존했다.
- Dec 2020~Mar 2021은 p38 확인 결과 이미지 차트만 있어 숫자 복원하지 않았다.

## 기존 csv 대조 (일괄 오프셋 단정 없음)

- 대조는 건별로만 본다: source sale_month vs 기존 Month 라벨.
- 48건 중 45건이 기존 csv와 가격 일치, 수량 45/45 일치, 라벨 45/45 일치했다.
- 예: 3070 Oct 2021 1144/2411, 3080 2022-09 585/1520, 3090 Dec 2021 2918/1295은
  sale_month와 기존 Month가 동일 표기다. 이 구간에서는 1달 오프셋이 확인되지 않았다.
- 미일치 3건은 Sep 2021 3GPU로 기존 csv에 해당 월 자체가 없다.
- Nov2023=Oct2023 같은 다른 구간 사례를 이 16개월에 일괄 적용하지 않았다.

## 2022-09 merge-mixed 처리

- 2022-09는 부분월이 아니라 merge 전후 혼합월이다. 월간 총계 집계는 정상이다.
- sale_period_type=monthly_merge_mixed, is_merge_mixed_flag=1로만 표시한다.
- 월변화율은 정상 계산한다: GPU별 16개월 -> 15개, 전체 45개 유효.
- 전후 이벤트 비교에서만 9월을 제외한다: Jul-Aug vs Oct-Nov, Q2 vs Q4.
- exclude_from_event_compare=1인 행이 그 제외 대상이다.

## 산출물과 확정 열

- monthly_grid_2020_2022.csv 108행(36x3), 가격 있음 48행, 변화율 45행.
- monthly_observations.csv 48행, partial_oct01_15_2021.csv 3행.
- audit_tables.csv 33개, crosscheck_existing_csv.csv 45행.

그리드 확정 열:

- gpu_model, gpu_label_source, month, sale_period_label, sale_period_type
- source_page, source_url, source_title, source_sha256, table_index
- table_header_price, table_header_qty
- ebay_avg_price_usd, qty_sold (결측 공란, 0/보간 없음)
- price_missing_reason, qty_missing_reason
- is_merge_mixed_flag, merge_note, exclude_from_event_compare
- log_return_price, return_missing_reason

## 재현

- python3 scripts/prepare_gpu_ebay_monthly.py (stdlib만, 네트워크 없음).
- python3 -m unittest tests.test_gpu_ebay -v.
