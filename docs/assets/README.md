# 공개 문서 이미지

공개본은 **원가격을 복원할 수 있는 가격 곡선·견적 막대·벤치마크 표·기존 앱 캡처를 제외**한다. 원래 연구에서 작성한 통계·설명도와 허용된 ETH 데이터의 자체 그래프만 남겼다. [재배포 검토](../data_redistribution.md)

| 포함 파일 | 근거·해석 |
|---|---|
| `figures/01_analysis_flow.png`, `05_forecast_timeline.png`와 SVG | 자체 분석·미래 정보 차단 절차를 설명하는 개념도 |
| `figures/02_observation_coverage.png`와 SVG | 실제 관측 주와 전체 달력 수의 자체 집계 |
| `figures/04_forecast_validation.png`와 SVG | [공개 모형 점수](../../data/analysis/2026-10-23/forecast/forecast_metrics.csv). 원가격·사례별 정답은 없음 |
| `data/analysis/2026-10-22/figures/02_correlations.*`, `04_lag_correlations.*`, `05_missing_coverage.*` | 수준·변화율·시차 상관과 실제 n, 관측 수의 자체 통계. 원가격 시계열 재배포가 아님 |
| `data/analysis/2026-10-22/gpu_mining/figures/04_observation_coverage.*` | GPU와 ETH의 서로 다른 관측 빈도·해당 없음 상태 |
| [ETH 추이](public/01_eth_trend.png) · [SVG](public/01_eth_trend.svg) | Coin Metrics CC BY-NC 4.0, 일별 1,096점·30일 이동평균 1,067점 |
| [ETH 주별 변화율](public/02_eth_weekly_returns.png) · [SVG](public/02_eth_weekly_returns.svg) | 156주 중 155개 인접 변화율 |
| [ETH 수익 대용](public/03_eth_proxies.png) · [SVG](public/03_eth_proxies.svg) | 988일 유효, 부분일·PoW 종료 뒤는 빈칸 |
| [공개 전체 화면](public/public_01_trend.png), [기간·지표 변경](public/public_02_proxy_2022.png), [검증 요약](public/public_03_validation.png) | 2026-10-24 실제 로컬 실행 화면. 공개 ETH 값·집계 점수만 표시 |

ETH 3종 재생성:

```bash
.venv/bin/python scripts/build_public_eth_analysis.py
```

캡처는 위 명령이 생성하지 않는다. 문서 사진은 실제 공개 화면을 촬영했으며 합성 UI가 아니다. 원래 문서 그림을 만드는 `plot_documentation_figures.py`는 제외된 국내 견적·개별 예측 행을 요구하므로 공개본만으로 모든 그림을 재생성할 수 없다. 공개하지 않은 그림은 [제외 목록](../../data/excluded_inventory.csv)에 남겼다.

ETH 자료·가공 그림에는 [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/) 조건과 [Coin Metrics](https://github.com/coinmetrics/data) 출처·변경 표시를 유지한다. 자체 통계·설명도에 이 라이선스를 일괄 부여한 것은 아니다. [권리 구분](../../RIGHTS.md)
