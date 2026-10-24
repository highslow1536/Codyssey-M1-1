"""Overseas long-history price-chart collector (public PriceHistory pages only).

Scope: NEW overseas products matching domestic forecast SKUs. Does NOT re-collect
the 6 existing snapshots under data/feasibility/2026-10-21/alternatives/raw/.
Read-only: public product page GET -> in-memory page/token -> chart POST.
No login, no paid access, no anti-bot workaround. Page/token headers stay in
session memory only and are never written to files or stdout. Saved HTML is
sanitized (header values redacted).

Foreign prices are NOT a substitute for domestic forecasts. They only show how
long foreign public charts can run and how dense weekly coverage is.
"""
import argparse
import hashlib
import html
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

PROJECT_ROOT = Path(__file__).resolve().parents[1]

PRICE_BASIS = ("new-unit listing prices as shown on the public chart; "
               "shipping fees, taxes and seller conditions are uncertain and NOT normalized")

TARGETS = [
    {"label": "overseas_990pro_1tb", "category": "SSD",
     "domestic_pcode": "18297002", "domestic_name": "Samsung 990 PRO 1TB (no heatsink)",
     "overseas_name": "Samsung 990 Pro SSD 1TB PCIe 4.0 NVMe M.2",
     "url": "https://pricehistory.app/p/samsung-990-pro-ssd-1tb-pcie-4-LraBLhQ2",
     "currency": "USD", "condition": "new",
     "same_sku_note": "same manufacturer model series + 1TB; domestic board/kit packaging may differ"},
    {"label": "overseas_sn850x_1tb", "category": "SSD",
     "domestic_pcode": "17788487", "domestic_name": "WD BLACK SN850X 1TB",
     "overseas_name": "WD_Black SN850X 1TB NVMe SSD (WDS100T2X0E)",
     "url": "https://pricehistory.app/p/wd-black-sn850x-1tb-nvme-ssd-m-yaDS6vce",
     "currency": "USD", "condition": "new",
     "same_sku_note": "same manufacturer model WDS100T2X0E class; exact sub-model suffix unverified"},
    {"label": "overseas_p41_1tb", "category": "SSD",
     "domestic_pcode": "17001050", "domestic_name": "SK hynix Platinum P41 1TB",
     "overseas_name": "SK Hynix Platinum P41 1TB PCIe NVMe Gen4 M.2 2280",
     "url": "https://pricehistory.app/p/sk-hynix-platinum-p41-2tb-pcie-nvme-vgJlNIyp",
     "currency": "USD", "condition": "new",
     "same_sku_note": "page title reports 1TB; URL slug says 2TB so slug ignored, Store Product Code authoritative"},
    {"label": "overseas_t500_1tb", "category": "SSD",
     "domestic_pcode": "29666111", "domestic_name": "Crucial T500 1TB",
     "overseas_name": "Crucial T500 1TB PCIe Gen4 NVMe Gaming SSD with heatsink",
     "url": "https://pricehistory.app/p/crucial-t500-1tb-pcie-gen4-nvme-gaming-1hEPfsmb",
     "currency": "USD", "condition": "new",
     "same_sku_note": "same T500 1TB series; heatsink variant may differ from domestic option"},
    {"label": "overseas_9600x", "category": "CPU",
     "domestic_pcode": "62794079", "domestic_name": "AMD Ryzen 5 9600X",
     "overseas_name": "AMD Ryzen 5 9600X 3.9 GHz",
     "url": "https://pricehistory.app/p/amd-ryzen-5-9600x-3-9-ghz-Jby9ysce",
     "currency": "INR", "condition": "new",
     "same_sku_note": "same chip model; different market/store (Flipkart, INR), not domestic price proxy"},
    {"label": "overseas_rtx4060_8gb", "category": "GPU",
     "domestic_pcode": "20740013", "domestic_name": "MSI RTX 4060 VENTUS 2X BLACK OC 8GB",
     "overseas_name": "Gigabyte RTX 4060 Eagle OC 8G GV-N4060EAGLE OC-8GD",
     "url": "https://pricehistory.app/p/gigabyte-geforce-rtx-4060-eagle-oc-8g-ZFiDGow8",
     "currency": "USD", "condition": "new",
     "same_sku_note": "same chip RTX 4060 8GB class; board/vendor/cooler differ, NOT same SKU"},
    {"label": "overseas_ddr5_16gb", "category": "RAM",
     "domestic_pcode": "20369126", "domestic_name": "Crucial DDR5-5600 CL46 16GB",
     "overseas_name": "Crucial 16GB DDR5-5600 CL46 CT16G56C46U5 desktop",
     "url": "https://pricehistory.app/p/crucial-ram-16gb-ddr5-5600-mhz-cl46-zrPuclce",
     "currency": "INR", "condition": "new",
     "same_sku_note": "same manufacturer model CT16G56C46U5, 16GB DDR5-5600 CL46 UDIMM; different market (IN)"},
    {"label": "overseas_ddr4_16gb", "category": "RAM",
     "domestic_pcode": "11790199", "domestic_name": "Samsung DDR4-3200 16GB single module",
     "overseas_name": "Crucial Pro 16GB DDR4-3200 CP16G4DFRA32A single module",
     "url": "https://pricehistory.app/p/crucial-pro-16gb-ram-1x16gb-ddr4-3200mhz-36iDhxSj",
     "currency": "INR", "condition": "new",
     "same_sku_note": "same spec class (1x16GB DDR4-3200 UDIMM); brand differs from domestic Samsung/TeamGroup, NOT same SKU"},
]

SANITIZE_PATTERNS = [
    (re.compile(r'FetchHeaders\.append\("page",\s*"[^"]*"\s*\)'), 'FetchHeaders.append("page","REDACTED")'),
    (re.compile(r"FetchHeaders\.append\('page',\s*'[^']*'\s*\)"), "FetchHeaders.append('page','REDACTED')"),
    (re.compile(r'FetchHeaders\.append\("token",\s*"[^"]*"\s*\)'), 'FetchHeaders.append("token","REDACTED")'),
    (re.compile(r"FetchHeaders\.append\('token',\s*'[^']*'\s*\)"), "FetchHeaders.append('token','REDACTED')"),
    (re.compile(r'"token"\s*:\s*"[^"]+"'), '"token":"REDACTED"'),
    (re.compile(r'"page"\s*:\s*"[^"]{8,}"'), '"page":"REDACTED"'),
]


def curl_fetch(url, path, headers=(), post=False):
    if path.exists() and path.stat().st_size:
        return {"cached": True, "file": path.name}
    cmd = ["/usr/bin/curl", "--silent", "--show-error", "--location",
           "--max-time", "30", "-A", "Mozilla/5.0",
           "-o", str(path), "-w", "%{http_code}"]
    if post:
        cmd += ["-X", "POST"]
    for h in headers:
        cmd += ["-H", h]
    proc = subprocess.run(cmd + [url], capture_output=True, text=True, check=False)
    if proc.returncode or proc.stdout.strip() != "200":
        raise RuntimeError(f"fetch failed HTTP {proc.stdout!r} curl {proc.returncode}: {url} {proc.stderr[:300]}")
    return {"cached": False, "http_status": proc.stdout.strip(), "file": path.name}


def sanitize_html(source):
    redacted = source
    for pat, repl in SANITIZE_PATTERNS:
        redacted = pat.sub(repl, redacted)
    return redacted


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_price_points(data):
    hist = data.get("History") or {}
    prices = hist.get("Price") or []
    pts = []
    for p in prices:
        if isinstance(p, dict):
            ts = (p.get("x") if "x" in p else p.get("t", p.get("Timestamp", p.get("date"))))
            val = (p.get("y") if "y" in p else p.get("Price", p.get("price", p.get("v"))))
            pts.append({"t": ts, "v": val})
        elif isinstance(p, list) and len(p) >= 2:
            pts.append({"t": p[0], "v": p[1]})
    return pts


def obs_days(pts):
    import datetime as dt
    days = []
    for p in pts:
        t = p.get("t")
        try:
            if isinstance(t, (int, float)) and t > 1e9:
                ts = t / 1000.0 if t > 1e12 else float(t)
                days.append(dt.datetime.fromtimestamp(ts, tz=dt.timezone.utc).date().isoformat())
            elif isinstance(t, str) and len(t) >= 10:
                days.append(t[:10])
        except Exception:
            continue
    return sorted(set(days))


def weekly_stats(pts):
    # Sat-Fri complete-week grid on source-sorted unique days.
    # A week belongs to the grid only if Sat..Fri lies fully inside [first_day, last_day].
    # weeks_with_points = complete weeks with >=1 observation (the audit "observed" count).
    import datetime as dt
    uniq_days = obs_days(pts)
    if not uniq_days:
        return {"unique_days": 0, "weeks_with_points": 0, "complete_weeks": 0,
                "span_days": 0, "first_day": None, "last_day": None, "missing_weeks": None}
    first = dt.date.fromisoformat(uniq_days[0])
    last = dt.date.fromisoformat(uniq_days[-1])
    span_days = (last - first).days + 1
    def saturday_of(d):
        return d - dt.timedelta(days=(d.weekday() - 5) % 7)
    # First Saturday on/after first_day whose Friday still fits is just ceil to Saturday;
    # a complete week Sat s needs s >= first Saturday on/after first AND s+6 <= last.
    s = first + dt.timedelta(days=(5 - first.weekday()) % 7)
    complete = []
    while s + dt.timedelta(days=6) <= last:
        complete.append(s.isoformat())
        s += dt.timedelta(days=7)
    with_pts = sorted(set(saturday_of(dt.date.fromisoformat(d)).isoformat() for d in uniq_days))
    observed = [w for w in complete if w in set(with_pts)]
    first_sat_week = saturday_of(first).isoformat()
    last_sat_week = saturday_of(last).isoformat()
    return {"unique_days": len(uniq_days), "weeks_with_points": len(observed),
            "complete_weeks": len(complete), "week_def": "Sat-Fri",
            "weeks_any_with_points": len(with_pts),
            "partial_leading_week": first_sat_week,
            "partial_trailing_week": last_sat_week,
            "span_days": span_days, "first_day": uniq_days[0], "last_day": uniq_days[-1],
            "missing_weeks": len(complete) - len(observed)}


def collect_one(target, raw_dir, now_utc, now_kst):
    url = target["url"]
    label = target["label"]
    page_path = raw_dir / f"{label}_page.html"
    pr = curl_fetch(url, page_path)
    source = page_path.read_text(errors="replace")
    m_page = re.search(r'FetchHeaders\.append\("page",\s*"([^"]+)"\s*\)', source)
    m_token = re.search(r'FetchHeaders\.append\("token",\s*"([^"]+)"\s*\)', source)
    if not m_page or not m_token:
        m_page = re.search(r"FetchHeaders\.append\('page',\s*'([^']+)'\s*\)", source)
        m_token = re.search(r"FetchHeaders\.append\('token',\s*'([^']+)'\s*\)", source)
    if not m_page or not m_token:
        raise RuntimeError(f"chart headers not found in {url}")
    code = m_page.group(1)
    nonce = m_token.group(1)
    endpoint = "https://pricehistory.app/api/price/" + code
    data_path = raw_dir / f"{label}_prices.json"
    dr = curl_fetch(endpoint, data_path, post=True, headers=(
        "Content-Type: application/json", "page: " + code, "token: " + nonce,
        "Referer: " + url))
    data = json.loads(data_path.read_text())
    assert isinstance(data.get("History", {}).get("Price"), list), f"unexpected chart shape for {label}"
    sanitized = sanitize_html(source)
    # Token must never persist; page code legitimately appears in canonical/og URLs,
    # so only the FetchHeaders page/token lines are redacted and asserted.
    assert nonce not in sanitized, "token leak in sanitized HTML"
    assert 'FetchHeaders.append("page","REDACTED")' in sanitized or "FetchHeaders.append('page','REDACTED')" in sanitized
    assert 'FetchHeaders.append("token","REDACTED")' in sanitized or "FetchHeaders.append('token','REDACTED')" in sanitized
    san_path = raw_dir / f"{label}_page.sanitized.html"
    san_path.write_text(sanitized)
    # Never retain the unsanitized page (it embeds the session token).
    try:
        page_path.unlink()
    except FileNotFoundError:
        pass
    pr = {"cached": pr.get("cached", False), "file": san_path.name, "sanitized": True}
    title_m = re.search(r"<h1[^>]*>(.*?)</h1>", source, re.S)
    title = html.unescape(re.sub(r"<[^>]+>", "", title_m.group(1))).strip() if title_m else None
    meta = {}
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", source, re.S):
        cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S)
        clean = [html.unescape(re.sub(r"<[^>]+>", "", c)).strip() for c in cells]
        if len(clean) >= 2 and clean[0] in ("Store Product Code", "Store Name"):
            meta[clean[0]] = clean[1]
    pts = parse_price_points(data)
    stats = weekly_stats(pts)
    return {
        "label": label, "category": target["category"],
        "domestic_pcode": target["domestic_pcode"], "domestic_name": target["domestic_name"],
        "overseas_name": target["overseas_name"], "page_title": title,
        "product_url": url, "chart_endpoint": "https://pricehistory.app/api/price/<code-redacted>",
        "store": meta.get("Store Name"), "store_code": meta.get("Store Product Code"),
        "currency": target["currency"], "condition": target["condition"],
        "collected_at_utc": now_utc, "collected_at_kst": now_kst,
        "files": {"prices": data_path.name, "page_sanitized": san_path.name,
                  "prices_sha256": sha256_of(data_path), "page_sanitized_sha256": sha256_of(san_path)},
        "source_updated_on": (data.get("Price") or {}).get("UpdatedOn"),
        "price_points": len(pts), "weekly": stats,
        "same_sku_note": target["same_sku_note"],
        "page_request": pr, "data_request": dr,
    }


def safe_id(store_code, store):
    safe_store = re.sub(r"[^A-Za-z0-9]+", "-", (store or "unknown").lower()).strip("-")
    safe_code = re.sub(r"[^A-Za-z0-9]+", "-", (store_code or "unknown")).strip("-")
    return f"{safe_code}__{safe_store}"


def region_of(store):
    s = (store or "").lower()
    if "flipkart" in s or "amazon.in" in s:
        return "IN"
    if "geizhals" in s or s.endswith(".de"):
        return "DE"
    return "US"


def restats(outdir):
    # Recompute price_points + weekly from cached raw prices only.
    # Never modifies raw files or observation prices.
    raw = outdir / "raw"
    manifest = json.loads((outdir / "manifest.json").read_text())
    for rec in manifest["records"]:
        data = json.loads((raw / rec["files"]["prices"]).read_text())
        pts = parse_price_points(data)
        rec["price_points"] = len(pts)
        rec["weekly"] = weekly_stats(pts)
        print(json.dumps({k: rec[k] for k in ("label", "price_points", "weekly")}, ensure_ascii=False))
    tmp = outdir / "manifest.json.tmp"
    tmp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    os.replace(tmp, outdir / "manifest.json")
    print("rewrote " + str(outdir / "manifest.json"))
    build_series(outdir)


def build_series(outdir):
    raw = outdir / "raw"
    manifest = json.loads((outdir / "manifest.json").read_text())
    series = []
    for rec in manifest["records"]:
        data = json.loads((raw / rec["files"]["prices"]).read_text())
        obs = []
        for p in (data.get("History") or {}).get("Price") or []:
            if isinstance(p, dict) and "x" in p and "y" in p:
                try:
                    price = float(p["y"])
                except (TypeError, ValueError):
                    continue
                obs.append({"date": str(p["x"]), "price": price})
        obs.sort(key=lambda o: o["date"])
        series.append({
            "id": safe_id(rec.get("store_code"), rec.get("store")),
            "category": rec.get("category"),
            "name": rec.get("overseas_name"),
            "domestic_pcode": rec.get("domestic_pcode"),
            "domestic_name": rec.get("domestic_name"),
            "region": region_of(rec.get("store")),
            "currency": rec.get("currency"),
            "condition": rec.get("condition"),
            "sourceUrl": rec.get("product_url"),
            # Project-root-relative path (unambiguous no matter the reader's cwd).
            # Also resolvable relative to series.json: "raw/" + basename.
            "rawFile": "data/verification/2026-10-23/forecast/overseas_extended/raw/" + rec["files"]["prices"],
            "sha256": rec["files"]["prices_sha256"],
            "collectedAt": rec.get("collected_at_kst"),
            "same_sku_note": rec.get("same_sku_note"),
            "price_basis": PRICE_BASIS,
            "observations": obs,
        })
    doc = {
        # Top-level basis (applies to every series) + per-series copy for model loaders.
        # Exact field spec: series[].price_basis (snake_case, per series).
        "priceBasis": PRICE_BASIS,
        "rawFileBase": "project-root; also resolvable as raw/<basename> relative to series.json",
        "disclaimer": manifest.get("disclaimer"),
        "series": series,
    }
    tmp = outdir / "series.json.tmp"
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n")
    os.replace(tmp, outdir / "series.json")
    total = sum(len(s["observations"]) for s in series)
    print(f"wrote {outdir / 'series.json'}: {len(series)} series, {total} observations")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("outdir", type=Path)
    ap.add_argument("--series-only", action="store_true",
                    help="rebuild series.json from cached raw + manifest without network")
    ap.add_argument("--restats-only", action="store_true",
                    help="recompute weekly stats from cached raw (no price changes), rewrite manifest + series without network")
    args = ap.parse_args()
    if args.series_only:
        build_series(args.outdir)
        return
    if args.restats_only:
        restats(args.outdir)
        return
    raw = args.outdir / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    now_utc = datetime.now(timezone.utc).isoformat()
    now_kst = datetime.now(ZoneInfo("Asia/Seoul")).isoformat()
    records = []
    for t in TARGETS:
        rec = collect_one(t, raw, now_utc, now_kst)
        records.append(rec)
        print(json.dumps({k: rec[k] for k in ("label", "store", "store_code", "currency", "price_points", "weekly")}, ensure_ascii=False))
    manifest = {
        "disclaimer": "Foreign public chart prices are NOT substitutes for domestic forecasts; they only extend observable history length and weekly density for same-series hardware.",
        "method": "public product page GET, in-memory FetchHeaders page/token, chart POST; headers never saved; saved HTML sanitized; no login/paid/anti-bot.",
        "sources": "each product_url is a real web-search result URL, not guessed enumeration",
        "collected_at_utc": now_utc, "collected_at_kst": now_kst,
        "records": records,
    }
    # Atomic rename so concurrent readers never see a partial manifest.
    tmp_manifest = args.outdir / "manifest.json.tmp"
    tmp_manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    os.replace(tmp_manifest, args.outdir / "manifest.json")
    print("wrote " + str(args.outdir / "manifest.json"))
    build_series(args.outdir)


if __name__ == "__main__":
    main()
