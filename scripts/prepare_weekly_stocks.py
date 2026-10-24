"""Prepare Saturday-Friday weekly stock closes for 2020-01-04 to 2022-12-30.
Read-only over existing Yahoo chart snapshots; never modifies raw inputs.
Weekly rule: last effective trading day of each Sat-Fri calendar week.
No carry-forward: a week without an effective trading day stays empty.
Returns use adjusted closes only when the immediately preceding calendar
week also has an adjusted close; the first grid week has no return.
Effective trading day = volume > 0 with non-null close and adjclose.
Zero-volume flat rows (present in the KSE snapshots) are excluded as
untrusted carried-forward rows, NOT as confirmed non-trading days:
Naver shows real trading on those dates.
"""
from __future__ import annotations
import csv
import hashlib
import json
import math
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
ROOT = Path(__file__).resolve().parents[1]
GRID_START = date(2020, 1, 4)
GRID_END = date(2022, 12, 30)
PERIOD1 = 1577836800
PERIOD2 = 1672531200
SYMBOLS = [
    {"symbol": "AMD", "yahoo_symbol": "AMD", "company": "Advanced Micro Devices, Inc.",
     "raw": "data/feasibility/2026-10-21/alternatives/raw/yahoo_AMD.json"},
    {"symbol": "INTC", "yahoo_symbol": "INTC", "company": "Intel Corporation",
     "raw": "data/feasibility/2026-10-21/alternatives/raw/yahoo_INTC.json"},
    {"symbol": "MU", "yahoo_symbol": "MU", "company": "Micron Technology, Inc.",
     "raw": "data/feasibility/2026-10-21/alternatives/raw/yahoo_MU.json"},
    {"symbol": "NVDA", "yahoo_symbol": "NVDA", "company": "NVIDIA Corporation",
     "raw": "data/feasibility/2026-10-21/alternatives/raw/yahoo_NVDA.json"},
    {"symbol": "005930", "yahoo_symbol": "005930.KS", "company": "Samsung Electronics Co., Ltd.",
     "raw": "data/verification/2026-10-22/stocks/yahoo_005930.KS.json",
     "naver_raw": "data/feasibility/2026-10-21/alternatives/raw/naver_005930.txt"},
    {"symbol": "000660", "yahoo_symbol": "000660.KS", "company": "SK hynix Inc.",
     "raw": "data/verification/2026-10-22/stocks/yahoo_000660.KS.json",
     "naver_raw": "data/feasibility/2026-10-21/alternatives/raw/naver_000660.txt"},
]
COLUMNS = ["symbol", "company", "currency", "market", "week_start", "week_end",
           "close", "adjusted_close", "return_log", "return_fraction",
           "quote_date", "n_trading_days", "adjustment_status",
           "source_file", "source_sha256"]
def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()
def chart_url(ysym):
    return ("https://query1.finance.yahoo.com/v8/finance/chart/" + ysym
            + "?period1=" + str(PERIOD1) + "&period2=" + str(PERIOD2)
            + "&interval=1d&events=div%7Csplit")
def parse_naver_closes(path):
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    rows = re.findall(r'\["(\d{8})",\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+)', text)
    return {m[0]: int(m[4]) for m in rows}
def week_grid():
    weeks = []
    start = GRID_START
    while start <= GRID_END:
        weeks.append((start, start + timedelta(days=7)))
        start += timedelta(days=7)
    fixed = [(s, s + timedelta(days=6)) for s, _ in weeks]
    return fixed
def load_symbol(cfg):
    raw_path = ROOT / cfg["raw"]
    digest = sha256_of(raw_path)
    payload = json.loads(raw_path.read_text(encoding="utf-8"))
    result = payload["chart"]["result"][0]
    meta = result["meta"]
    tzname = meta["exchangeTimezoneName"]
    tz = ZoneInfo(tzname)
    stamps = result["timestamp"]
    quote = result["indicators"]["quote"][0]
    adj = result["indicators"]["adjclose"][0]["adjclose"]
    closes = quote["close"]
    volumes = quote["volume"]
    daily = []
    for i, ts in enumerate(stamps):
        day = datetime.fromtimestamp(ts, tz=tz).date().isoformat()
        daily.append({"date": day, "close": closes[i],
                      "adjusted": adj[i] if adj else None,
                      "volume": volumes[i] if volumes else None})
    dup_ts = len(stamps) - len(set(stamps))
    dates = [d["date"] for d in daily]
    dup_dates = len(dates) - len(set(dates))
    effkeys = set()
    effective = []
    for d in daily:
        if d["volume"] is not None and d["volume"] > 0 and d["close"] is not None and d["adjusted"] is not None:
            effective.append(d)
            effkeys.add(id(d))
    excluded = [d["date"] for d in daily if id(d) not in effkeys]
    events = result.get("events", {}) or {}
    dividends = [{"date": datetime.fromtimestamp(v["date"], tz=tz).date().isoformat(),
                  "amount": v["amount"]} for v in events.get("dividends", {}).values()]
    dividends.sort(key=lambda x: x["date"])
    splits = [{"date": datetime.fromtimestamp(v["date"], tz=tz).date().isoformat(),
               "splitRatio": v.get("splitRatio")} for v in events.get("splits", {}).values()]
    splits.sort(key=lambda x: x["date"])
    by_date = {d["date"]: d for d in effective}
    return {"meta": meta, "tzname": tzname, "digest": digest, "daily": daily,
            "effective": effective, "by_date": by_date, "excluded": excluded,
            "dup_ts": dup_ts, "dup_dates": dup_dates,
            "dividends": dividends, "splits": splits}
def main():
    weeks = week_grid()
    assert len(weeks) == 156, len(weeks)
    assert weeks[0][0].isoformat() == "2020-01-04"
    assert weeks[-1][1].isoformat() == "2022-12-30"
    out_dir = ROOT / "data/processed/2026-10-22/stocks"
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    per_symbol = {}
    sources = {"grid": {"week_start": "2020-01-04", "week_end": "2022-12-30",
                          "convention": "Saturday-to-Friday", "n_weeks": 156},
               "symbols": {}}
    for cfg in SYMBOLS:
        info = load_symbol(cfg)
        meta = info["meta"]
        eff_dates = sorted(info["by_date"])
        max_gap = 0
        for a, b in zip(eff_dates, eff_dates[1:]):
            gap = (date.fromisoformat(b) - date.fromisoformat(a)).days
            max_gap = max(max_gap, gap)
        week_rows = []
        for ws, we in weeks:
            in_week = [d for d in eff_dates if ws.isoformat() <= d <= we.isoformat()]
            if in_week:
                pick = in_week[-1]
                rec = info["by_date"][pick]
                week_rows.append({"week_start": ws.isoformat(), "week_end": we.isoformat(),
                                  "close": rec["close"], "adjusted": rec["adjusted"],
                                  "quote_date": pick, "n": len(in_week)})
            else:
                week_rows.append({"week_start": ws.isoformat(), "week_end": we.isoformat(),
                                  "close": None, "adjusted": None,
                                  "quote_date": "", "n": 0})
        prev_adj = None
        n_returns = 0
        empty_weeks = []
        for w in week_rows:
            if w["adjusted"] is None:
                log_ret, frac_ret = None, None
                if w["n"] == 0:
                    empty_weeks.append(w["week_start"])
                prev_adj = None
            elif prev_adj is None:
                log_ret, frac_ret = None, None
                prev_adj = w["adjusted"]
            else:
                log_ret = math.log(w["adjusted"] / prev_adj)
                frac_ret = w["adjusted"] / prev_adj - 1.0
                n_returns += 1
                prev_adj = w["adjusted"]
            status = "yahoo_adjclose" if not info["excluded"] else "yahoo_adjclose_excl_zero_volume_placeholders"
            rows.append({
                "symbol": cfg["symbol"], "company": cfg["company"],
                "currency": meta["currency"], "market": meta["fullExchangeName"],
                "week_start": w["week_start"], "week_end": w["week_end"],
                "close": "" if w["close"] is None else repr(float(w["close"])),
                "adjusted_close": "" if w["adjusted"] is None else repr(float(w["adjusted"])),
                "return_log": "" if log_ret is None else repr(log_ret),
                "return_fraction": "" if frac_ret is None else repr(frac_ret),
                "quote_date": w["quote_date"], "n_trading_days": w["n"],
                "adjustment_status": status, "source_file": cfg["raw"],
                "source_sha256": info["digest"]})
        cross = {}
        if "naver_raw" in cfg:
            nav = parse_naver_closes(ROOT / cfg["naver_raw"])
            yh_closes = {d["date"].replace("-", ""): d["close"]
                          for d in info["daily"] if d["close"] is not None}
            nav_only = sorted(set(nav) - set(yh_closes))
            common_eff_keys = {d.replace("-", "") for d in info["by_date"]}
            nav_iso = {k[:4] + "-" + k[4:6] + "-" + k[6:] : v for k, v in nav.items()}
            last_session_mismatches = []
            for w in week_rows:
                if w["quote_date"] == "":
                    continue
                nav_in_week = [d for d in nav_iso if w["week_start"] <= d <= w["week_end"]]
                if not nav_in_week:
                    continue
                nav_last = max(nav_in_week)
                if nav_last != w["quote_date"]:
                    last_session_mismatches.append({"week_end": w["week_end"],
                                                    "naver_last_date": nav_last,
                                                    "yahoo_selected_date": w["quote_date"]})
            mismatch_eff = sorted(k for k in common_eff_keys
                                  if k in nav and round(float(yh_closes[k])) != nav[k])
            cross = {"naver_file": cfg["naver_raw"],
                     "naver_sha256": sha256_of(ROOT / cfg["naver_raw"]),
                     "naver_rows": len(nav),
                     "sessions_only_in_naver": nav_only,
                     "close_mismatch_on_effective_days": mismatch_eff,
                     "zero_volume_note": "Volume-0 flat rows are untrusted carried-forward rows, not confirmed non-trading days (Naver shows real trading there).",
                     "actual_session_data_missing_vs_naver": len(nav) - len(info["effective"]),
                     "missing_breakdown": {"sessions_absent_from_yahoo": nav_only,
                                            "zero_volume_untrusted_rows": len(info["excluded"])},
                     "n_last_session_mismatches": len(last_session_mismatches),
                     "last_session_mismatches": last_session_mismatches}
        per_symbol[cfg["symbol"]] = {
            "company": cfg["company"], "yahoo_symbol": cfg["yahoo_symbol"],
            "currency": meta["currency"], "market": meta["fullExchangeName"],
            "exchange": meta["exchangeName"], "exchangeTimezoneName": info["tzname"],
            "source_file": cfg["raw"], "source_sha256": info["digest"],
            "n_raw_rows": len(info["daily"]),
            "n_effective_trading_days": len(info["effective"]),
            "n_excluded_zero_volume_placeholders": len(info["excluded"]),
            "excluded_dates": info["excluded"],
            "duplicate_timestamps": info["dup_ts"], "duplicate_dates": info["dup_dates"],
            "first_effective_date": eff_dates[0] if eff_dates else None,
            "last_effective_date": eff_dates[-1] if eff_dates else None,
            "max_gap_days_effective": max_gap,
            "dividends": info["dividends"], "splits": info["splits"],
            "weeks_total": 156, "weeks_with_quote": 156 - len(empty_weeks),
            "weeks_empty": len(empty_weeks), "empty_weeks": empty_weeks,
            "returns_computed": n_returns,
            "naver_crosscheck": cross}
        sources["symbols"][cfg["symbol"]] = {
            "company": cfg["company"], "yahoo_symbol": cfg["yahoo_symbol"],
            "chart_url": chart_url(cfg["yahoo_symbol"]),
            "local_file": cfg["raw"], "sha256": info["digest"],
            "exchange": meta["exchangeName"], "market": meta["fullExchangeName"],
            "exchangeTimezoneName": info["tzname"], "currency": meta["currency"],
            "field_meanings": {
                "close": "Yahoo chart quote close for the exchange trading day.",
                "adjusted_close": "Yahoo chart adjclose for the same day, as provided (backward-adjusted for splits/dividends; formula not recomputed here)."},
            "limits": ["adjclose is used as Yahoo's as-provided backward-adjusted series (all applicable splits and dividend distributions); this work does not independently recompute the adjustment multipliers.",
                        "Definition source: Yahoo Help SLN28256 What is the adjusted close? (regional mirror https://in.help.yahoo.com/kb/adjusted-close-sln28256.html): adjusted close reflects all applicable splits and dividend distributions via split/dividend multipliers under CRSP standards; Yahoo Finance history pages likewise label Close as split-adjusted and Adj Close as adjusted for splits and dividend distributions (e.g. https://ca.finance.yahoo.com/quote/AMD.TO/history/).",
                        "See quality_summary.json corporate-action event lists before interpreting jumps."]}
    with open(out_dir / "weekly_stocks.csv", "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    (out_dir / "sources.json").write_text(json.dumps(sources, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = {"grid": sources["grid"], "rows_total": len(rows),
               "per_symbol_rows": {s: 156 for s in per_symbol},
               "symbols": per_symbol}
    (out_dir / "quality_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"rows": len(rows), "weeks_with_quote": {s: v["weeks_with_quote"] for s, v in per_symbol.items()}, "excluded": {s: v["n_excluded_zero_volume_placeholders"] for s, v in per_symbol.items()}}, ensure_ascii=False))
if __name__ == "__main__":
    main()

