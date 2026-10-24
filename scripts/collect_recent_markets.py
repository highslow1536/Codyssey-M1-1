"""Collect recent public market quotes 2023-01-01..2026-10-22 (single query each).
Reference-only: scripts/probe_alternative_sources.py and
scripts/prepare_weekly_stocks.py are NOT modified; conventions reused:
  - Yahoo v8 chart daily with events=div|split
  - effective trading day = volume>0 with non-null close and adjclose
  - volume-0 / unknown rows conservatively excluded (NOT confirmed holidays)
  - local exchange date via meta.exchangeTimezoneName
  - adjclose used as-provided; multipliers not recomputed here
Scope: 6 equities (AMD/INTC/MU/NVDA/005930.KS/000660.KS) adjustedClose +
1 crypto (ETH-USD) close price only. Each symbol queried EXACTLY once.
No retry loop, no URL enumeration: failures recorded honestly.
Post-merge note: ETH is price-only; no mining-profitability claim.
If live response ends before 2026-10-22, actual last date reported as-is.
Writes (new paths only, existing raw/test values untouched):
  data/verification/2026-10-23/timing/markets_raw/yahoo_<SYM>.json
  data/verification/2026-10-23/timing/recent_markets.json
"""
from __future__ import annotations
import hashlib
import json
import subprocess
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data/verification/2026-10-23/timing/markets_raw"
OUT_PATH = ROOT / "data/verification/2026-10-23/timing/recent_markets.json"
PERIOD1 = 1672531200
PERIOD2 = 1792713600
RANGE_START = "2023-01-01"
RANGE_END = "2026-10-22"
SYMBOLS = [
    {"id": "AMD", "yahoo": "AMD", "kind": "equity"},
    {"id": "INTC", "yahoo": "INTC", "kind": "equity"},
    {"id": "MU", "yahoo": "MU", "kind": "equity"},
    {"id": "NVDA", "yahoo": "NVDA", "kind": "equity"},
    {"id": "005930.KS", "yahoo": "005930.KS", "kind": "equity"},
    {"id": "000660.KS", "yahoo": "000660.KS", "kind": "equity"},
    {"id": "ETH-USD", "yahoo": "ETH-USD", "kind": "crypto"},
]
FALLBACK_NAMES = {
    "AMD": "Advanced Micro Devices, Inc.",
    "INTC": "Intel Corporation",
    "MU": "Micron Technology, Inc.",
    "NVDA": "NVIDIA Corporation",
    "005930.KS": "Samsung Electronics Co., Ltd.",
    "000660.KS": "SK hynix Inc.",
    "ETH-USD": "Ethereum USD",
}
def chart_url(ysym):
    q = urllib.parse.urlencode({"period1": PERIOD1, "period2": PERIOD2, "interval": "1d", "events": "div|split"})
    return "https://query1.finance.yahoo.com/v8/finance/chart/" + ysym + "?" + q
def sha256_of(path):
    import hashlib as hl
    h = hl.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()
def fetch_once(url, path):
    cmd = ["/usr/bin/curl", "--silent", "--show-error", "--location", "--max-time", "40", "-A", "Mozilla/5.0", "-o", str(path), "-w", "%{http_code}", url]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    code_out = (proc.stdout or "").strip()
    if proc.returncode != 0 or code_out != "200":
        return {"ok": False, "http_status": code_out or None, "curl_returncode": proc.returncode, "stderr_tail": (proc.stderr or "")[-500:]}
    return {"ok": True, "http_status": code_out}
def build_series(cfg, collected_at):
    ysym = cfg["yahoo"]
    url = chart_url(ysym)
    fname = "yahoo_" + ysym.replace("/", "_") + ".json"
    raw_path = RAW_DIR / fname
    fetch = fetch_once(url, raw_path)
    base = {"id": cfg["id"], "name": FALLBACK_NAMES.get(cfg["id"], cfg["id"]), "currency": None, "priceBasis": None, "sourceUrl": url, "collectedAt": collected_at, "sha256": None, "rawFile": str(raw_path.relative_to(ROOT)), "points": [], "limitations": [], "fetch": fetch, "firstDate": None, "lastDate": None, "nValid": 0, "nRawRows": 0, "nExcluded": 0, "excludedDates": [], "dividends": [], "splits": [], "meta": {}}
    if not fetch.get("ok"):
        base["limitations"].append("Single-query fetch failed; recorded honestly, no retry.")
        return base
    digest = sha256_of(raw_path)
    base["sha256"] = digest
    try:
        payload = json.loads(raw_path.read_text(encoding="utf-8"))
    except Exception as exc:
        base["fetch"] = dict(fetch, ok=False, parse_error=str(exc)[:300])
        base["limitations"].append("Raw JSON unparsable; no points.")
        return base
    try:
        result = payload["chart"]["result"][0]
    except Exception:
        base["limitations"].append("Unexpected chart payload shape; error=" + json.dumps(payload.get("chart", {}).get("error"))[:300])
        return base
    meta = result.get("meta", {})
    tzname = meta.get("exchangeTimezoneName") or "UTC"
    try:
        tz = ZoneInfo(tzname)
    except Exception:
        tz = timezone.utc
    base["currency"] = meta.get("currency")
    base["name"] = meta.get("longName") or meta.get("shortName") or base["name"]
    base["meta"] = {"exchange": meta.get("exchangeName"), "market": meta.get("fullExchangeName"), "exchangeTimezoneName": tzname, "instrumentType": meta.get("instrumentType")}
    stamps = result.get("timestamp") or []
    quote = (result.get("indicators", {}).get("quote") or [{}])[0]
    closes = quote.get("close") or []
    volumes = quote.get("volume") or []
    adj_list = result.get("indicators", {}).get("adjclose") or [{}]
    adjs = adj_list[0].get("adjclose") if adj_list else None
    events = result.get("events") or {}
    divs = events.get("dividends") or {}
    spls = events.get("splits") or {}
    for v in divs.values():
        try:
            base["dividends"].append({"date": datetime.fromtimestamp(v["date"], tz=tz).date().isoformat(), "amount": v.get("amount")})
        except Exception:
            continue
    for v in spls.values():
        try:
            base["splits"].append({"date": datetime.fromtimestamp(v["date"], tz=tz).date().isoformat(), "splitRatio": v.get("splitRatio"), "numerator": v.get("numerator"), "denominator": v.get("denominator")})
        except Exception:
            continue
    base["dividends"].sort(key=lambda x: x["date"])
    base["splits"].sort(key=lambda x: x["date"])
    has_adj = isinstance(adjs, list) and len(adjs) == len(stamps)
    if cfg["kind"] == "equity" and has_adj:
        base["priceBasis"] = "adjustedClose"
    else:
        base["priceBasis"] = "close"
    points = []
    excluded = []
    n_raw = len(stamps)
    for i, ts in enumerate(stamps):
        try:
            day = datetime.fromtimestamp(ts, tz=tz).date().isoformat()
        except Exception:
            continue
        if day < RANGE_START or day > RANGE_END:
            continue
        close = closes[i] if i < len(closes) else None
        vol = volumes[i] if i < len(volumes) else None
        adj = adjs[i] if (has_adj and i < len(adjs)) else None
        if cfg["kind"] == "equity":
            price = adj
            valid = (price is not None and close is not None and vol is not None and vol > 0)
        else:
            price = close
            valid = (price is not None and vol is not None and vol > 0)
        if valid:
            points.append({"date": day, "price": float(price)})
        else:
            excluded.append(day)
    points.sort(key=lambda p: p["date"])
    base["points"] = points
    base["excludedDates"] = excluded
    base["nRawRows"] = n_raw
    base["nValid"] = len(points)
    base["nExcluded"] = len(excluded)
    if points:
        base["firstDate"] = points[0]["date"]
        base["lastDate"] = points[-1]["date"]
    if cfg["kind"] == "equity":
        if has_adj:
            base["limitations"].append("adjustedClose is Yahoo as-provided backward-adjusted series (events=div|split requested); multipliers not recomputed here.")
        else:
            base["limitations"].append("No usable adjclose array in response; priceBasis=close (NOT called adjusted).")
        base["limitations"].append("Volume-0/unknown rows conservatively excluded; not confirmed holidays.")
    else:
        base["limitations"].append("ETH price-only (close); no mining-profitability claim. PoW ended 2022-09-15, so post-merge revenue is not applicable.")
        base["limitations"].append("No adjclose for crypto; priceBasis=close by construction.")
    return base
def main():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    collected_at = datetime.now(timezone.utc).isoformat()
    sources = {"endpoint": "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}", "params": {"period1": PERIOD1, "period2": PERIOD2, "period1_iso": RANGE_START, "period2_exclusive_iso": "2026-10-23", "interval": "1d", "events": "div|split"}, "queries": "one per symbol, no retry, no enumeration"}
    full_series = []
    for cfg in SYMBOLS:
        full_series.append(build_series(cfg, collected_at))
    series_out = []
    for s in full_series:
        pub = {k: s[k] for k in ("id", "name", "currency", "priceBasis", "sourceUrl", "collectedAt", "sha256", "rawFile", "points")}
        series_out.append(pub)
    limitations = [
        "Range capped at completion date 2026-10-22; actual last date reported as-is, never fabricated to reach 2026.",
        "Dates are local exchange trading days via meta.exchangeTimezoneName.",
        "Volume-0/unknown rows conservatively excluded (untrusted placeholders, not confirmed non-trading days).",
        "Stock priceBasis=adjustedClose only when Yahoo adjclose present; otherwise priceBasis=close and NOT called adjusted.",
        "Yahoo adjustment multipliers (splits/dividends) not independently recomputed; see stdout for per-series dividends/splits counts.",
        "ETH is price-only; post-2022-merge mining profitability is not applicable and not claimed.",
        "Single query per symbol; failures recorded honestly without retry or URL enumeration.",
        "Public quotes only; no secrets or personal data.",
        "Latest corporate policies/forecasts out of scope; monthly-change correlation left to main task.",
        "Existing raw/test values untouched; only new files under data/verification/2026-10-23/timing/ written.",
    ]
    doc = {"asOf": RANGE_END, "sources": sources, "series": series_out, "limitations": limitations}
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = {}
    for s in full_series:
        summary[s["id"]] = {"first": s["firstDate"], "last": s["lastDate"], "n": s["nValid"], "nRaw": s["nRawRows"], "nExcluded": s["nExcluded"], "priceBasis": s["priceBasis"], "currency": s["currency"], "market": s["meta"].get("market"), "tz": s["meta"].get("exchangeTimezoneName"), "nDiv": len(s["dividends"]), "nSplit": len(s["splits"]), "ok": s["fetch"].get("ok"), "sha256": (s["sha256"] or "")[:12], "raw": s["rawFile"]}
    print(json.dumps({"out": str(OUT_PATH.relative_to(ROOT)), "collectedAt": collected_at, "series": summary}, ensure_ascii=False, indent=2))
if __name__ == "__main__":
    main()

