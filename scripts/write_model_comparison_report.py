"""ARIMA/SARIMA/ETS offline model-comparison report renderer.

Public inputs only:
  data/public/model_comparison.json (aggregate scores + legacyEvaluation)
Writes:
  docs/model_comparison.md

No raw prices, no per-origin forecasts, no private snapshots, no secrets.
Missing scores render as -- and are never filled with 0. Winners are
computed from the JSON, never hardcoded. Re-run after the aggregate
or figures update.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "public" / "model_comparison.json"
OUT = ROOT / "docs" / "model_comparison.md"
FIG04 = "assets/public/04_model_comparison.png"
FIG05 = "assets/public/05_model_coverage.png"
REPS = ("US_B07STGGQ18", "US_B07MFZY2F2", "KR_21694499")
ORDER = ("logistic", "forest", "arima", "sarima", "ets", "baseline")


def f4(v):
    return "--" if v is None else f"{v:.4f}"


def pct1(v):
    return "--" if v is None else f"{v * 100:.1f}%p"


def inte(v):
    return "--" if v is None else str(v)


def model_map(series):
    return {m.get("candidate"): m for m in series.get("models", [])}


def fig_line(path, alt_missing):
    if (OUT.parent / path).exists():
        return f"![{alt_missing}]({path})"
    return f"![{alt_missing}]({path})\n\n*그림 파일은 모형 비교 산출 단계에서 생성 예정이며, 본 문서는 수치표가 정본이다.*"


def main():
    if not SRC.exists():
        raise SystemExit(f"aggregate source missing: {SRC}")
    d = json.loads(SRC.read_text())
    seq = d.get("series", [])
    by_id = {s.get("id"): s for s in seq}
    legacy = {s.get("id"): (s.get("legacyEvaluation") or {}) for s in seq}
    has_legacy = any(legacy.values())
    summary = d.get("summary", {})
    common_sum = sum((s.get("common") or {}).get("testN") or 0 for s in seq)
    full_sum = sum((s.get("selectedAllEvaluation") or {}).get("n") or 0 for s in seq)
    legacy_sum = sum((v.get("n") or 0) for v in legacy.values())
    changed = [s for s in seq if (s.get("selection") or {}).get("candidate") != (s.get("incumbent") or {}).get("candidate")]
    weekly = sum(1 for s in seq if s.get("frequency") == "weekly")
    monthly = sum(1 for s in seq if s.get("frequency") == "monthly")
    L = []
    L.append("# ARIMA/SARIMA/ETS 모형 비교")
    L.append("")
    L.append(f"집계원: `data/public/model_comparison.json` (asOf {d.get('asOf')}, generated {d.get('generatedAt')}, schema {d.get('schemaVersion')}).")
    L.append("생성기: `scripts/write_model_comparison_report.py`. 원가격·원점별 예측·비밀값 없이 집계 점수만 읽는다. 빈칸은 --이며 0으로 채우지 않는다.")
    L.append("")
    L.append("## 1. 고정 비교 규격")
    L.append("")
    L.append("후보 5종 + 빈도 기준이다. 분류 2종(L2 다항 로지스틱 회귀, 깊이 제한 랜덤포레스트)은 과거 가격 특징을 쓰고, 시계열 3종은 같은 SKU의 로그가격만 쓴다.")
    L.append("외부 변수(주가·ETH·재고·출시)는 어떤 후보에도 넣지 않았다.")
    L.append("")
    L.append("| 후보 | 규격 |")
    L.append("|---|---|")
    L.append("| ARIMA | 로그가격 ARIMA(1,1,0) + drift |")
    L.append("| SARIMA | SARIMA(1,1,0)(1,0,0,s), 주별 주기 52·월별 주기 12 |")
    L.append("| ETS | ETS(A,Ad,N) 로그가격, 초기 수준 고정·인접 추세, Kalman NaN 유지 |")
    L.append("| 분류 2종 | 기존 규약 그대로(분기 재학습·특징 중앙값+결측 표시자) |")
    L.append("| 기준 | 과거 방향 빈도(+1 보정) 확률 · 가격 유지 점예측 |")
    L.append("")
    L.append("분기별 고정 파라미터다. 분류 모형은 분기 시작 전에 목표 기간까지 끝난 사례만으로 적합한다. "
              "시계열 모형은 분기 시작 전에 관측된(available) 로그가격 전부로 적합하며 3개월 목표 성숙 조건을 두지 않는다. "
              "같은 분기 원점들에는 `apply(refit=False)`로 분기 파라미터를 그대로 적용한다. "
              "예측 분산은 잔차가 아니라 `get_forecast`의 실제 예측 분산을 쓴다. 결측 달력은 NaN으로 두며 칼만 필터 내부 예측을 관측으로 추가하지 않는다.")
    L.append("적합 최소 조건은 주별 52셀·관측 40개, 월별 12셀·관측 10개다. SARIMA는 2개 계절 주기 + 최근 두 주기 각 75% 관측을 추가로 요구한다. 국내 월간(7~22개월)은 연간 주기 두 주기를 못 채워 SARIMA 미산출이 정상이다.")
    L.append("방향 확률은 ±3% 기준의 가우시안 CDF다. 온도(0.5/1/2/4)는 2023~2024년 공통 과거 원점(2024년 말까지 성숙, 최소 24개·세 방향 포함)에서 로그손실 최소로만 고른다. "
              "부족하면 기존 모형을 유지하고 시험 점수가 가장 낮은 모형으로 교체하지 않는다.")
    L.append("시험은 2025~2026년 동일 공통 원점 교집합(SKU별)이다. 후보별 전체 평가 가능 행 수(`allTestN`, 기존 분류 유효 평가 원점 universe 내)와 실패 사유를 함께 기록한다. "
              "시계열 단독 예측(`standaloneTestN`, 집계에 있으면)은 기존 분류 비교가 없는 원점의 추가 산출로, 점수·선택에서 제외한다. "
              "점예측은 시계열 모형의 로그정규 중앙값, 분류 모형의 방향별 중앙값 가중이다. MAE·RMSE는 변화율 분수를 %p로 표기하고, 80/95% 가격구간 커버리지는 온도 보정 전 원분포 구간(온도 적용 클래스 확률과 별개)이다.")
    L.append("2025~2026년을 이미 살펴본 뒤 후보를 확장한 회고 비교이며, 새 미관측 홀드아웃이나 실시간 성과가 아니다. 게이트(추천 사용 조건)는 기존과 동일하다.")
    L.append("")
    L.append("## 2. 전체 요약")
    L.append("")
    L.append(f"계열 {summary.get('series')}개(주별 {weekly}·월별 {monthly}), 선택 변경 {summary.get('selectionChanged')}개, 게이트 통과 {summary.get('passed')}개다. "
              f"공통 평가 행 합계 {common_sum}개(JSON 기록값 {summary.get('commonTestRows')}개), 선택 FULL 합계 {full_sum}개다. "
              "목표 기간이 겹치므로 행 수는 독립 표본 수가 아니며 비중첩 시간 구간을 함께 본다.")
    if has_legacy:
        L.append(f"기존 스냅샷 FULL 합계 {legacy_sum}개다.")
    else:
        L.append("기존 스냅샷 FULL은 공개 집계에 아직 없어 --로 둔다. 집계가 갱신되면 생성기를 다시 실행한다.")
    if changed:
        L.append("")
        L.append("선택이 바뀐 계열(과거 검증 기준, 시험 점수로 고르지 않음):")
        L.append("")
        for s in changed:
            sel = s.get("selection") or {}
            inc = s.get("incumbent") or {}
            L.append(f"- {s.get('name')} ({s.get('id')}): {inc.get('candidate')} T{inc.get('temperature')} → {sel.get('candidate')} T{sel.get('temperature')} (선택 n={sel.get('n')}, {sel.get('status')})")
    else:
        L.append("선택이 바뀐 계열이 없다. 전부 기존 모형을 유지한다.")
    L.append("")
    L.append("## 3. 대표 3계열(그림 04 대응)")
    L.append("")
    L.append(fig_line(FIG04, "대표 3계열의 후보별 Brier·변화율 MAE와 공통 평가 원점"))
    L.append("")
    L.append("그림 04는 아래 표의 Brier·변화율 MAE를 그린 것이다. 낮을수록 좋다. 같은 계열 안의 막대만 비교한다.")
    for rid in REPS:
        s = by_id.get(rid)
        if s is None:
            L.append(f"\n### {rid}: 집계에 없음 (--)")
            continue
        mm = model_map(s)
        sel = s.get("selection") or {}
        inc = s.get("incumbent") or {}
        com = s.get("common") or {}
        L.append("")
        L.append(f"### {s.get('name')} ({s.get('region')}·{s.get('frequency')})")
        L.append(f"선택 {sel.get('candidate')} T{sel.get('temperature')} (선택 n={sel.get('n')}, {sel.get('status')}), 기존 {inc.get('candidate')} T{inc.get('temperature')}. "
                  f"공통 평가 n={com.get('testN')} (비중첩 {com.get('nonoverlapN')}, {com.get('from')}~{com.get('to')}).")
        L.append("")
        L.append("| 후보 | T | 상태 | n | Brier | 변화율 MAE | ECE |")
        L.append("|---|---:|---|---:|---:|---:|---:|")
        for c in ORDER:
            m = mm.get(c, {})
            e = m.get("evaluation") or {}
            L.append(f"| {m.get('name', c)} | {inte(m.get('temperature'))} | {m.get('status', '--')} | {inte(e.get('n'))} | {f4(e.get('brier'))} | {pct1(e.get('mae'))} | {pct1(e.get('ece'))} |")
        leg = legacy.get(rid) or {}
        L.append("")
        L.append(f"기존 스냅샷 FULL(참고용, {inc.get('candidate')} T{inc.get('temperature')}, n={inte(leg.get('n'))}, Brier {f4(leg.get('brier'))})은 과거 2후보 체계의 기록이다. "
                  "개선 판단은 같은 공통 원점 위의 기존-vs-선택 비교로만 읽는다:")
        L.append("")
        L.append("| 비교(같은 공통 원점) | 모형 | Brier | 변화율 MAE |")
        L.append("|---|---|---:|---:|")
        for label, cand in (("기존", inc.get("candidate")), ("선택", sel.get("candidate"))):
            m = mm.get(cand, {})
            e = m.get("evaluation") or {}
            L.append(f"| {label} {cand} T{m.get('temperature')} | {m.get('name', cand)} | {f4(e.get('brier'))} | {pct1(e.get('mae'))} |")
        if (sel.get("status") or "").startswith("incumbent_retained"):
            L.append("")
            L.append("선택 자료가 없어 기존 모형을 유지한다. 시험 구간에서 시계열 후보의 점수가 낮게 보여도 회고 조회일 뿐이며 모형 교체 근거가 아니다. 시험 구간 성적으로 선택하지 않는다.")
    L.append("")
    L.append("계절·시계열 모형이 자동으로 우월하지 않다. 35계열 중 선택 변경은 2개뿐이고 통과는 0개다. SARIMA 제외(월간)는 성능 열위가 아니라 자료 길이의 정상 결과다.")
    L.append("")
    L.append("## 4. 전체 35계열 커버리지(그림 05 대응)")
    L.append("")
    L.append(fig_line(FIG05, "35계열 공통 평가 n·FULL n과 선택 모형"))
    L.append("")
    L.append("공통 n은 후보 비교에 쓴 동일 원점 수, 기존 FULL n은 과거 스냅샷의 전체 평가 수, 선택 FULL n은 선택 모형의 전체 평가 수다. `forecast_metrics.csv`·`forecast.json`은 선택 FULL 기준으로 덮어썼다. "
              "공통 0은 비교 불가이며 원시 자료 없음을 뜻하지 않는다. 일부 계열은 시계열 단독 산출만 있고 공통 비교가 없을 수 있다(아래 단독 산출 목록 참조).")
    L.append("")
    L.append("| 계열 | 지역·빈도 | 선택 모형 | 공통 n | 기존 FULL n | 선택 FULL n | 비중첩 | 게이트 |")
    L.append("|---|---|---|---:|---:|---:|---:|---|")
    for s in seq:
        sel = s.get("selection") or {}
        com = s.get("common") or {}
        fall = s.get("selectedAllEvaluation") or {}
        leg = legacy.get(s.get("id")) or {}
        gt = s.get("gates") or {}
        L.append(f"| {s.get('name')} | {s.get('region')}·{s.get('frequency')} | {sel.get('candidate')} T{sel.get('temperature')} | "
                  f"{inte(com.get('testN'))} | {inte(leg.get('n'))} | {inte(fall.get('n'))} | {inte(com.get('nonoverlapN'))} | "
                  f"{'통과' if gt.get('passed') else '미통과'} |")
    if not has_legacy:
        L.append("")
        L.append("공개 집계에 기존 FULL이 아직 없어 기존 FULL 칸은 --다. 집계가 갱신되면 생성기를 다시 실행한다.")
    solo = []
    for s in seq:
        com = s.get("common") or {}
        if (com.get("testN") or 0) == 0:
            st = sum(((model_map(s).get(c) or {}).get("standaloneTestN") or 0) for c in ORDER)
            if st:
                solo.append(f"{s.get('name')} ({st}행)")
    if solo:
        L.append("")
        L.append("공통 비교 없이 시계열 단독 산출만 있는 계열(점수·선택 제외): " + "; ".join(solo) + ".")
    L.append("")
    L.append("## 5. 모형별 집계")
    L.append("")
    L.append("| 후보 | 산출 계열 | 공통 미산출 계열 | 공통 행 합계 | 전체 행 합계 | 단독 행 합계 | 주요 실패 사유 |")
    L.append("|---|---:|---:|---:|---:|---:|---|")
    for c in ORDER:
        ev = un = cn = fn = stn = 0
        fails = {}
        for s in seq:
            m = model_map(s).get(c, {})
            e = m.get("evaluation") or {}
            if m.get("status") == "evaluated" and e.get("n"):
                ev += 1
                cn += e.get("n") or 0
            else:
                un += 1
            fn += (m.get("allTestN") or 0)
            stn += (m.get("standaloneTestN") or 0)
            fl = m.get("failures") or {}
            if isinstance(fl, dict):
                for k, v in fl.items():
                    if isinstance(v, int):
                        fails[k] = fails.get(k, 0) + v
                    elif isinstance(v, dict):
                        fails[v.get("code", k)] = fails.get(v.get("code", k), 0) + 1
                    else:
                        fails[k] = fails.get(k, 0) + 1
        fnote = "; ".join(f"{k} {v}" for k, v in sorted(fails.items())) if fails else "--"
        L.append(f"| {c} | {ev} | {un} | {cn} | {fn if fn else '--'} | {stn if stn else '--'} | {fnote} |")
    L.append("")
    L.append("실패 집계는 2023년 이후 전체 롤링 요청(최신 미성숙 원점 포함) 기준이며, 공통·전체 평가 행 수와 분모가 다르다.")
    L.append("미산출은 공통 비교 불가이며 원시 자료 없음을 뜻하지 않는다. 단독 행은 기존 분류 비교가 없는 원점의 시계열 추가 산출로 점수·선택에서 제외한다.")
    L.append("")
    L.append("## 6. 제한·주의")
    L.append("")
    for item in d.get("limitations", []):
        L.append(f"- {item}")
    L.append("")
    L.append("방법 근거: [statsmodels SARIMAX](https://www.statsmodels.org/stable/generated/statsmodels.tsa.statespace.sarimax.SARIMAX.html), "
              "[statespace ExponentialSmoothing](https://www.statsmodels.org/stable/generated/statsmodels.tsa.statespace.exponential_smoothing.ExponentialSmoothing.html), "
              "[statespace missing data example](https://www.statsmodels.org/stable/examples/notebooks/generated/statespace_sarimax_internet.html), "
              "[FPP3 시계열 교차 검증](https://otexts.com/fpp3/tscv.html). 게이트 정의는 `docs/forecast_protocol.md`.")
    OUT.write_text("\n".join(L) + "\n")
    print(f"wrote {OUT} from {SRC}")


if __name__ == "__main__":
    main()
