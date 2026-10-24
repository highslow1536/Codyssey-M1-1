> 공개판 안내: 작성 당시 연구 기록입니다. 원가격·주가·벤치마크 원본과 복원 가능한 파일은 제외했습니다. 현재 공개 범위·실행법은 루트 README와 데이터 이용 안내를 따릅니다.

### 주가 주별 정규화의 가격 기준 (2020-2022)

이 문서는 상관/시차 분석에 들어가는 6종 주가 주별 테이블의 가격 기준 선택과
검증 결과를 정리한다.

### 1. 대상과 출처

주별 테이블은 2020-01-04(토)부터 2022-12-30(금)까지 토~금 156주 그리드를 쓰며,
종목마다 156행, 전체 936행이다. 6종 모두 Yahoo Finance chart 일별 조회를
1차 입력으로 썼다. 미국 4종은 기존 스냅샷을 재사용했고, 한국 2종은
Naver 수정기준 미확인 문제를 피하려고 같은 방식의 Yahoo 조회를 새로 받았다.

| symbol | Yahoo 심볼 | 회사 | 통화 | 시장 | 로컬 원본 |
| --- | --- | --- | --- | --- | --- |
| AMD | AMD | Advanced Micro Devices, Inc. | USD | NasdaqGS | data/feasibility/2026-10-21/alternatives/raw/yahoo_AMD.json |
| INTC | INTC | Intel Corporation | USD | NasdaqGS | data/feasibility/2026-10-21/alternatives/raw/yahoo_INTC.json |
| MU | MU | Micron Technology, Inc. | USD | NasdaqGS | data/feasibility/2026-10-21/alternatives/raw/yahoo_MU.json |
| NVDA | NVDA | NVIDIA Corporation | USD | NasdaqGS | data/feasibility/2026-10-21/alternatives/raw/yahoo_NVDA.json |
| 005930 | 005930.KS | Samsung Electronics Co., Ltd. | KRW | KSE | data/verification/2026-10-22/stocks/yahoo_005930.KS.json |
| 000660 | 000660.KS | SK hynix Inc. | KRW | KSE | data/verification/2026-10-22/stocks/yahoo_000660.KS.json |

요청 URL 형식은 6종 공통으로
https://query1.finance.yahoo.com/v8/finance/chart/{심볼}?period1=1577836800&period2=1672531200&interval=1d&events=div%7Csplit
이다. 한국 2종은 2026-10-22(KST) 공개 GET으로 HTTP 200을 받아
data/verification/2026-10-22/stocks/에 새 raw로 저장했다. Naver 원종가 파일은
교차 확인용으로만 쓰고 주별 테이블에는 쓰지 않았다.

### 2. adjusted_close의 보이는 의미와 미확인 부분

weekly_stocks.csv의 수익률은 Yahoo adjclose 계열로만 계산한다. adjclose는
보이는 그대로 배당과 분할을 소급 반영한 수정 종가이며, 같은 날 close는 분할만
소급 반영된 값이다. 산식 자체를 독립 재계산하지는 않았으므로 과도하게 확정하지 않는다.
정의와 관측, 미수행을 구분한다. (a) 정의: Yahoo의 자체 설명에 따르면 조정 종가는
적용 가능한 모든 분할과 배당 분배를 반영한 값이며, 분할·배당 승수를 CRSP 기준에 따라
적용한다([Yahoo 도움말 SLN28256 'What is the adjusted close?'](https://in.help.yahoo.com/kb/adjusted-close-sln28256.html)).
Yahoo Finance 히스토리 페이지도 Close는 분할 조정값, Adj Close는 분할·배당 분배
조정값으로 표시한다(예: https://ca.finance.yahoo.com/quote/AMD.TO/history/).
(b) 관측: 페이로드 events의 배당·분할 목록과 adjclose/close 비율 패턴이 이 설명과
어긋나지 않는다. (c) 미수행: 승수의 독립 재계산.
아래 기업행사 목록을 quality_summary.json에 그대로 남겼으니
점프 해석 전에 반드시 대조해야 한다.

- AMD: 배당 0건, 분할 0건.
- INTC: 분기 배당 12건 (0.33 x 4, 0.348 x 4, 0.365 x 4).
- MU: 배당 6건. 2021-09-30에 0.10으로 시작해 2022년 0.115로 인상.
- NVDA: 소액 배당 12건 (0.004) + 2021-07-20 4:1 분할.
- 005930: 배당 12건 (354 x 3, 2020-12-29 1932, 361 x 8). 분할 없음.
- 000660: 배당 6건 (1170, 1540, 300 x 4). 분할 없음.

NVDA 주의점: Yahoo close/adjclose 레벨은 조회 시점까지의 분할이 모두 소급
반영된 표시값이라 명목 거래가와 직접 비교하면 안 된다. 2021년 4:1 분할에 더해
2024년 6월 10:1 분할이 구간 밖에서 한 번 더 있었고, 그래서 2020년 초 close가
한 자릿수(예: 2020-01-02 5.9977)로 표시된다. 비율 기반 수익률에는 상수 배율이
약분되므로 영향이 없으며, 분할 전후 주간 수익률도 adjclose 기준이라 연속이다.

### 3. 일자 산정과 주별 규칙

일자는 각 거래소 시간대 기준으로 timestamp를 변환했다. 미국 4종은
exchangeTimezoneName America/New_York, 한국 2종은 Asia/Seoul이며,
스냅샷 meta 값이 기대와 일치함을 확인했다.

- 매주 토~금 달력주에서 유효 거래일 중 마지막 날을 고른다.
- 유효 거래일은 거래량 > 0이면서 close와 adjclose가 모두 있는 날이다.
- 해당 주에 유효 거래일이 없으면 빈 행으로 두고 이월하지 않는다.
  (이번 구간에서는 빈 주가 0개였다.)
- 수익률은 바로 앞 달력주에도 adjusted_close가 있을 때만
  log(adj_t / adj_prev)와 단순비율(adj_t / adj_prev - 1)을 기록한다.
- 첫 주(2020-01-04~10, 대표일 2020-01-10)는 변화율이 빈값이다.
- CSV에서 숫자 공란은 결측을 뜻한다.

### 4. 거래일 검증과 한국 자료 교차 확인

중복: 6종 모두 timestamp 중복 0, 일자 중복 0.
결측: 미국 4종은 원본 756행이 전부 유효하고 유효일 최대 간격 4일이다.
한국 2종은 원본 740행 중 거래량 0인 평탄 행을 신뢰할 수 없는 이월 표시로 보고
제외했다(005930 13일, 000660 15일). 실제 비거래일로 단정하지 않는다. Naver에
같은 날짜의 실제 거래가 있기 때문이다. 유효일은 005930 727일, 000660 725일이며
최대 간격 6일이다. Naver 742행 대비 실제 세션 자료가 005930 15개, 000660 17개
부족하다(내역: Yahoo에 전혀 없는 2022-01-03·2022-05-09 2세션 + 거래량 0 이월 표시
13/15일). 제외된 주에도 같은 주 다른 유효일이 있어 주별 대표일은 선정됐다.
다만 아래 대표일 불일치 주에서는 Naver 마지막일과 Yahoo 선정일이 하루 이상 어긋난다.

Naver 교차 확인: Naver 파일(005930 742행, 000660 742행)과 비교하면
2022-01-03과 2022-05-09 두 세션이 Yahoo에 없고, 거래량 0 이월 표시일에는
Naver 실종가와 Yahoo 이월 표시가가 다르다. 유효 거래일끼리는 반올림 종가가
전부 일치해(불일치 0건) Yahoo 유효 종가를 쓰는 선택이 깨지지 않는다.
Naver 종가는 기업행사 조정 기준이 확인되지 않아 수익률 계산에 쓰지 않았다.
Naver 마지막일과 Yahoo 선정일이 다른 주는 quality_summary.json의
last_session_mismatches에 week_end 목록으로 남겼다. 민감도 분석에서는
해당 주와 바로 다음 주를 제외하고 비교한다.
- 005930 불일치 1주: week_end 2022-03-04
  (Naver 마지막일 2022-03-04, Yahoo 선정일 2022-03-03).
  제외 범위: 2022-03-04, 2022-03-11.
- 000660 불일치 2주: week_end 2022-03-04, 2022-03-11
  (2022-03-04: Naver 2022-03-04 vs Yahoo 2022-03-03,
   2022-03-11: Naver 2022-03-11 vs Yahoo 2022-03-08).
  제외 범위: 2022-03-04, 2022-03-11, 2022-03-18.

### 5. 통화와 비교 제약

미국 4종은 USD, 한국 2종은 KRW를 그대로 유지했다. 6종 표준 비교에서 환율
효과는 조정하지 않았으므로, 후속 해석에서는 통화 다름을 제약으로 명시해야
한다. 원화 종목과 달러 종목의 수익률 숫자 비교는 환율 움직임을 섞은 채로
읽히며, 가격 레벨 비교는 통화 단위가 달라 직접 비교가 성립하지 않는다.

### 6. 행수와 원본 해시

weekly_stocks.csv는 936행(헤더 제외)이며 종목당 156행, 종목당 수익률 155개,
첫 주 공란 규칙을 만족한다. 행별 source_sha256은 아래 원본 해시와 일치한다.

- yahoo_AMD.json: 9ce04c820e4c709b1aa5de1daae370c939645f2f6d6940fa124ea559f9969b6e
- yahoo_INTC.json: 35dc52aa11d402734b194397c1d3bd257c796cba63d85ba6021f70e6c0af1c05
- yahoo_MU.json: 922e44c507c503d80c5d7deac1268df62928d2cbbdbd173f878a9fc3372f73f6
- yahoo_NVDA.json: 64250c9d807d8d9a9924688676c4a53c010e32a54dd41453f72e29d2cee8d3df
- yahoo_005930.KS.json: 87287d2953d2f3b26c79891564e356af81062bfebdf9793d6fbdac2ba04456fe
- yahoo_000660.KS.json: 53ae64bd84217971b5f614bb6392209d80c1801ac862b7556617a0ee1597a35b
- naver_005930.txt(교차 확인용): a283a54a37145fe012b774b412e0ea6db24736e87758ef2066641717da205081
- naver_000660.txt(교차 확인용): ff11a473d87addae5f74e055c5b3f50c82a1d913e24d412af25a8a4112452bd0

### 7. 산출물 목록

- scripts/prepare_weekly_stocks.py (재현 스크립트)
- data/verification/2026-10-22/stocks/yahoo_005930.KS.json (신규 raw)
- data/verification/2026-10-22/stocks/yahoo_000660.KS.json (신규 raw)
- data/processed/2026-10-22/stocks/weekly_stocks.csv (936행)
- data/processed/2026-10-22/stocks/sources.json (출처와 필드 의미)
- data/processed/2026-10-22/stocks/quality_summary.json (검증 수치와 기업행사 목록)
- tests/test_weekly_stocks.py (그리드·수익률 규칙·해시 검사)
- docs/stock_data_basis.md (이 문서)
