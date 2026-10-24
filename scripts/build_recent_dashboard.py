"""Build recent dashboard data: 2023-01-01..completed Friday 2026-10-16.
Inputs (read-only, never modified):
  data/processed/2026-10-21/overseas/weekly_prices.csv (utf-8-sig)
  data/verification/2026-10-23/timing/recent_markets.json (+ its raw files, for hashes)
Grid: Saturday-to-Friday calendar weeks, 2022-12-31..2026-10-10 (198 weeks),
week_end 2023-01-06..2026-10-16. Empty weeks kept as null; part
selected_quote_flags preserved (flagged=true, never silently removed).
Markets weekly = last valid exchange-local trading value within each Sat-Fri week.
Parts: B07STGGQ18 (CPU), B07MFZY2F2 (SSD). Markets: 7 recent series.
Correlations: 7 markets x 2 parts x 17 lags (-8..8) on log-returns + levels at
lag 0 = 252 rows. Log-returns only over immediately consecutive non-missing
calendar weeks. Lag k>0 pairs market return at week t with part return at
week t+k (market leads). Pearson only, no p-values, no significance claims.
Native currencies, no FX conversion (USD/KRW read separately).
Sensitivity: same correlations excluding flagged part-weeks (no silent removal).
Outputs (new files only):
  dashboard/dist/data/recent.json
  data/processed/2026-10-23/recent/{parts_weekly,markets_weekly,correlations,correlations_sensitivity}.csv
  data/processed/2026-10-23/recent/README.md
"""
from __future__ import annotations
import csv
import hashlib
import json
import math
import shutil
from datetime import date, timedelta
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
PARTS_CSV = ROOT / "data/processed/2026-10-21/overseas/weekly_prices.csv"
MARKETS_JSON = ROOT / "data/verification/2026-10-23/timing/recent_markets.json"
OUT_DIR = ROOT / "data/processed/2026-10-23/recent"
OUT_JSON = ROOT / "dashboard/dist/data/recent.json"
GRID_FIRST_START = date(2022, 12, 31)
GRID_LAST_END = date(2026, 10, 16)
PART_IDS = ["B07STGGQ18", "B07MFZY2F2"]
LAGS = list(range(-8, 9))
def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()
def grid():
    weeks = []
    s = GRID_FIRST_START
    while True:
        e = s + timedelta(days=6)
        if e > GRID_LAST_END:
            break
        weeks.append((s.isoformat(), e.isoformat()))
        s += timedelta(days=7)
    return weeks
def pearson(xs, ys):
    n = len(xs)
    if n < 2:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx <= 0 or syy <= 0:
        return None
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    return sxy / math.sqrt(sxx * syy)
def log_returns(vals):
    rets = {}
    for i in range(1, len(vals)):
        a, b = vals[i - 1], vals[i]
        if a is not None and b is not None and a > 0 and b > 0:
            rets[i] = math.log(b / a)
    return rets
def main():
    weeks = grid()
    assert len(weeks) == 198, len(weeks)
    assert weeks[0] == ("2022-12-31", "2023-01-06")
    assert weeks[-1] == ("2026-10-10", "2026-10-16")
    wstarts = [w[0] for w in weeks]
    wends = [w[1] for w in weeks]
    idx = {ws: i for i, ws in enumerate(wstarts)}
    with open(PARTS_CSV, encoding="utf-8-sig", newline="") as f:
        prd = csv.DictReader(f)
        pcols = prd.fieldnames
        prows = [r for r in prd if r["product_id"] in PART_IDS and r["week_start"] in idx and r["week_end"] == wends[idx[r["week_start"]]]]
    assert len(prows) == 2 * 198, len(prows)
    by_part = {}
    for r in prows:
        by_part.setdefault(r["product_id"], {})[r["week_start"]] = r
    for pid in PART_IDS:
        assert len(by_part[pid]) == 198, (pid, len(by_part[pid]))
    mdoc = json.loads(MARKETS_JSON.read_text(encoding="utf-8"))
    assert mdoc["asOf"] == "2026-10-22", mdoc["asOf"]
    mseries = {s["id"]: s for s in mdoc["series"]}
    assert len(mseries) == 7, len(mseries)
    for s in mseries.values():
        raw = json.loads((ROOT / s['rawFile']).read_text())
        meta = raw['chart']['result'][0]['meta']
        s['exchangeTimezoneName'] = meta['exchangeTimezoneName']
        s['market'] = meta.get('fullExchangeName', meta.get('exchangeName', ''))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUT_DIR / "parts_weekly.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=pcols, lineterminator="\n")
        w.writeheader()
        for pid in PART_IDS:
            for ws in wstarts:
                w.writerow(by_part[pid][ws])
    mweek_cols = ["week_start", "week_end", "id", "name", "kind", "currency", "priceBasis", "market", "exchangeTimezoneName", "price", "quote_date", "n_daily_points", "source_file", "source_sha256"]
    mrows = []
    mvals = {}
    for mid, s in mseries.items():
        by_date = {}
        for p in s["points"]:
            if "2022-12-31" <= p["date"] <= "2026-10-22":
                by_date[p["date"]] = p["price"]
        vals = []
        for ws, we in weeks:
            in_w = sorted(d for d in by_date if ws <= d <= we)
            if in_w:
                qd = in_w[-1]
                vals.append(by_date[qd])
                mrows.append({"week_start": ws, "week_end": we, "id": mid, "name": s["name"], "kind": "crypto" if mid == "ETH-USD" else "stock", "currency": s["currency"], "priceBasis": s["priceBasis"], "market": s["market"], "exchangeTimezoneName": s["exchangeTimezoneName"], "price": repr(float(by_date[qd])), "quote_date": qd, "n_daily_points": len(in_w), "source_file": s["rawFile"], "source_sha256": s["sha256"]})
            else:
                vals.append(None)
                mrows.append({"week_start": ws, "week_end": we, "id": mid, "name": s["name"], "kind": "crypto" if mid == "ETH-USD" else "stock", "currency": s["currency"], "priceBasis": s["priceBasis"], "market": s["market"], "exchangeTimezoneName": s["exchangeTimezoneName"], "price": "", "quote_date": "", "n_daily_points": 0, "source_file": s["rawFile"], "source_sha256": s["sha256"]})
        mvals[mid] = vals
    with open(OUT_DIR / "markets_weekly.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=mweek_cols, lineterminator="\n")
        w.writeheader()
        w.writerows(mrows)
    pvals = {}
    pinfo = {}
    for pid in PART_IDS:
        r0 = by_part[pid][wstarts[0]]
        vals = []
        flags = []
        qds = []
        for ws in wstarts:
            r = by_part[pid][ws]
            v = r["price_usd"]
            vals.append(float(v) if v not in ("", None) else None)
            flags.append(bool(r["selected_quote_flags"]))
            qds.append(r["quote_date"] or None)
        pvals[pid] = vals
        pinfo[pid] = {"name": r0["product_name"], "category": r0["category"], "currency": r0["currency"], "sourceUrl": r0["source_url"], "flags": flags, "quote_dates": qds}
    series = []
    for pid in PART_IDS:
        pts = []
        for i, (ws, we) in enumerate(weeks):
            v = pvals[pid][i]
            pt = {"date": we, "value": v, "quoteDate": pinfo[pid]["quote_dates"][i], "flagged": pinfo[pid]["flags"][i]}
            pts.append(pt)
        obs = [i for i, v in enumerate(pvals[pid]) if v is not None]
        rets = log_returns(pvals[pid])
        series.append({"id": pid, "name": pinfo[pid]["name"], "kind": "part", "category": pinfo[pid]["category"], "currency": pinfo[pid]["currency"], "priceBasis": "sourceQuote", "sourceUrl": pinfo[pid]["sourceUrl"], "points": pts, "coverage": {"observed": len(obs), "total": 198, "returns": len(rets), "first": weeks[obs[0]][1] if obs else None, "last": weeks[obs[-1]][1] if obs else None}})
    for mid, s in mseries.items():
        vals = mvals[mid]
        pts = []
        for i, (ws, we) in enumerate(weeks):
            mr = [r for r in mrows if r["id"] == mid and r["week_start"] == ws][0]
            pts.append({"date": we, "value": vals[i], "quoteDate": mr["quote_date"] or None})
        obs = [i for i, v in enumerate(vals) if v is not None]
        rets = log_returns(vals)
        daily = s["points"]
        series.append({"id": mid, "name": s["name"], "kind": "crypto" if mid == "ETH-USD" else "stock", "currency": s["currency"], "priceBasis": s["priceBasis"], "sourceUrl": s["sourceUrl"], "points": pts, "coverage": {"observed": len(obs), "total": 198, "returns": len(rets), "first": weeks[obs[0]][1] if obs else None, "last": weeks[obs[-1]][1] if obs else None}, "dailyCoverage": {"n": len(daily), "first": daily[0]["date"] if daily else None, "last": daily[-1]["date"] if daily else None}})
    def corr_rows(drop_flagged):
        rows = []
        for pid in PART_IDS:
            pv = pvals[pid]
            if drop_flagged:
                pv = [None if pinfo[pid]["flags"][i] else v for i, v in enumerate(pv)]
            pr = log_returns(pv)
            for mid in mseries:
                mv = mvals[mid]
                mr = log_returns(mv)
                xs = [a for a, b in zip(pv, mv) if a is not None and b is not None]
                ys = [b for a, b in zip(pv, mv) if a is not None and b is not None]
                r0 = pearson(xs, ys)
                rows.append({"partId": pid, "marketId": mid, "part_currency": pinfo[pid]["currency"], "market_currency": mseries[mid]["currency"], "mode": "levels", "lag_weeks": 0, "pearson": r0, "n": len(xs)})
                for k in LAGS:
                    pairs = [(mr[t], pr[t + k]) for t in mr if (t + k) in pr]
                    xs2 = [a for a, b in pairs]
                    ys2 = [b for a, b in pairs]
                    rk = pearson(xs2, ys2) if len(pairs) >= 2 else None
                    rows.append({"partId": pid, "marketId": mid, "part_currency": pinfo[pid]["currency"], "market_currency": mseries[mid]["currency"], "mode": "returns", "lag_weeks": k, "pearson": rk, "n": len(pairs)})
        return rows
    primary = corr_rows(False)
    sens = corr_rows(True)
    assert len(primary) == 7 * 2 * (17 + 1) == 252, len(primary)
    assert len(sens) == 252
    ccols = ["partId", "marketId", "part_currency", "market_currency", "mode", "lag_weeks", "pearson", "n"]
    for name, rows in (("correlations.csv", primary), ("correlations_sensitivity.csv", sens)):
        with open(OUT_DIR / name, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=ccols, lineterminator="\n")
            w.writeheader()
            for r in rows:
                rr = dict(r)
                rr["pearson"] = "" if rr["pearson"] is None else repr(rr["pearson"])
                w.writerow(rr)
    jcorr = [{k: r[k] for k in ("partId", "marketId", "mode", "lag_weeks", "pearson", "n")} for r in primary]
    for r in jcorr:
        r["pearson"] = None if r["pearson"] == "" else r["pearson"]
    input_hashes = {str(PARTS_CSV.relative_to(ROOT)): sha256_of(PARTS_CSV), str(MARKETS_JSON.relative_to(ROOT)): sha256_of(MARKETS_JSON)}
    for s in mdoc["series"]:
        input_hashes[s["rawFile"]] = sha256_of(ROOT / s["rawFile"])
    sources = {"parts": str(PARTS_CSV.relative_to(ROOT)) + " (utf-8-sig, filtered to 198 Sat-Fri weeks, empty weeks and selected_quote_flags kept)", "markets": str(MARKETS_JSON.relative_to(ROOT)) + " (daily 2023-01-01..2026-10-22; weekly = last valid trading value per Sat-Fri week, capped at week ending 2026-10-16)", "grid": "Saturday-to-Friday, 2022-12-31..2026-10-10 starts (198 weeks)"}
    limitations = [
        "토~금 완료 주만 비교합니다. 시장 일별 자료는 10월 22일까지지만 주별 비교는 10월 16일까지입니다.",
        "빈 주는 null로 남겼습니다. 원문 이상치 표시는 보존했으며 이 구간의 표시된 이상치는 0건입니다.",
        "로그 변화율은 바로 이웃한 두 주가 모두 유효할 때만 계산합니다. 양의 시차는 시장이 부품보다 앞서는 방향입니다.",
        "Pearson 상관은 기술 통계입니다. 다중 시차를 탐색했고 통계적 유의성이나 인과·예측력을 검증하지 않았습니다.",
        "USD·KRW 원통화 자료입니다. 환율의 영향을 통제하지 못했습니다.",
        "해외 부품은 미국 Amazon의 구형 SKU 호가이며 국내 신제품 가격을 대표하지 않습니다.",
        "Yahoo의 배당·분할 수정주가를 사용했습니다. 조정 배율을 독립적으로 재계산하지 않았습니다.",
        "거래일은 현지 날짜를 보존했으나 한국·미국 시장 마감과 부품 원본의 관측 시각은 완전히 일치하지 않습니다.",
        "ETH는 머지 이후 가격만 비교합니다. 2023년 이후 ETH 채굴 수익성 자료로 해석하지 않습니다.",
    ]
    doc = {"schemaVersion": 1, "asOf": "2026-10-23", "start": "2023-01-01", "weeklyEnd": "2026-10-16", "series": series, "correlations": jcorr, "sources": sources, "limitations": limitations, "inputHashes": input_hashes}
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# recent (2023-01-01..2026-10-16 weekly)", "", "Grid: Saturday-to-Friday, 198 weeks (starts 2022-12-31..2026-10-10).", "Daily market data runs to 2026-10-22, but weekly stops at the last completed Friday 2026-10-16.", "", "## weekly coverage (observed / 198 weeks, returns = consecutive-week log-returns)"]
    for s in series:
        c = s["coverage"]
        extra = ""
        if "dailyCoverage" in s:
            d = s["dailyCoverage"]
            extra = ", daily n=%s %s..%s" % (d["n"], d["first"], d["last"])
        lines.append("- %s (%s): weekly %d/198, returns %d, %s..%s%s" % (s["id"], s["currency"], c["observed"], c["returns"], c["first"], c["last"], extra))
    nnull = sum(1 for r in primary if r["pearson"] is not None)
    lines += ["", "## correlations", "- rows: %d (= 7 markets x 2 parts x 17 return-lags + 14 levels-at-0); non-null pearson: %d" % (len(primary), nnull), "- sensitivity (flagged weeks dropped): identical here, 0 flagged part-weeks in range.", "- native currencies, no FX; USD/KRW pairs read separately; no p-values."]
    (OUT_DIR / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    downloads = ROOT / 'dashboard/dist/data/downloads'
    for name in ('parts_weekly', 'markets_weekly', 'correlations', 'correlations_sensitivity'):
        shutil.copyfile(OUT_DIR / (name + '.csv'), downloads / ('recent_' + name + '.csv'))
    print(json.dumps({"json": str(OUT_JSON.relative_to(ROOT)), "csvs": sorted(p.name for p in OUT_DIR.glob("*.csv")), "weeks": 198, "corr_rows": len(primary), "coverage": {s["id"]: s["coverage"] for s in series}}, ensure_ascii=False, indent=2))
if __name__ == "__main__":
    main()

