#!/usr/bin/env python3
"""Collect longer domestic history from legal public surfaces only (new file).

Reads (read-only): data/verification/2026-10-23/timing/{cpu_gpu_history,ram_ssd_history}.json
Writes (only): data/verification/2026-10-23/forecast/domestic_extended/**

Allowed surfaces (public GET, no login, no bot-block bypass, no hidden-date enumeration):
- Danawa product page HTML: only the period buttons the UI itself exposes (1/3/6/12/24m).
  No getProductPriceList period probing beyond the UI-exposed set (no 36m/param guessing).
- Enuri price.enuri.com catalog/search pages the UI links to; trend-string presence check only.
- Quasarzone public search page; presence check only.
- Wayback Machine CDX + archived Danawa product snapshots (explicit archive timestamps,
  not Danawa chart-date enumeration). One anchor row per fetched snapshot; no interpolation,
  monthly points are never synthesized from daily data and daily data are never fabricated.
"""
import hashlib
import json
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/verification/2026-10-23/forecast/domestic_extended"
RAW = OUT / "raw"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
KST = ZoneInfo("Asia/Seoul")

SKUS = [
    ("21694499", "CPU", "AMD Ryzen 5 7500F, multipack genuine", "7500F"),
    ("76555634", "CPU", "Intel Core i5-14400F, valuepack genuine", "14400F"),
    ("18718496", "CPU", "Ryzen 5 7600", "7600"),
    ("62794079", "CPU", "Ryzen 5 9600X", "9600X"),
    ("20740013", "GPU", "MSI RTX 4060 VENTUS 2X BLACK OC D6 8GB", "4060"),
    ("76550837", "GPU", "MSI RTX 5070 Ti VENTUS 3X OC D7 16GB", "5070 Ti"),
    ("106710902", "GPU", "5070 Ti board reference (PALIT peer family)", "5070 Ti"),
    ("90160715", "GPU", "MSI RTX 5070 Ti GAMING TRIO OC D7 16GB", "5070 Ti"),
    ("76510673", "GPU", "GIGABYTE RTX 5070 Ti GAMING OC D7 16GB", "5070 Ti"),
    ("99839876", "GPU", "5070 Ti-class board reference", "5070 Ti"),
    ("81990338", "GPU", "MSI RTX 5060 Ti 16GB", "5060 Ti"),
    ("90956033", "GPU", "MSI RTX 5060 8GB", "5060"),
    ("91909571", "GPU", "SAPPHIRE RX 9060 XT 16GB", "9060"),
    ("11790199", "RAM", "Samsung DDR4-3200 16GB, one module", "DDR4-3200"),
    ("18911780", "RAM", "Samsung DDR5-5600 16GB, one module", "DDR5-5600"),
    ("18297002", "SSD", "Samsung 990 PRO 1TB, without heatsink", "990 PRO"),
    ("17001050", "SSD", "SK hynix Platinum P41 1TB", "P41"),
    ("14907467", "RAM", "TeamGroup DDR4-3200 Elite 16GB", "DDR4-3200"),
    ("20369126", "RAM", "Crucial DDR5-5600 16GB", "DDR5-5600"),
    ("17788487", "SSD", "WD BLACK SN850X 1TB", "SN850X"),
    ("29666111", "SSD", "Crucial T500 1TB", "T500"),
]
FOCUS = {"11790199", "18297002", "17001050", "21694499", "18911780"}

def curl_get(url, out_path, referer=None):
    cmd = ["/usr/bin/curl", "-sL", "--max-time", "40", "-A", UA, url,
           "-o", str(out_path), "-w", "%{http_code}"]
    if referer:
        cmd[1:1] = ["-H", "Referer: " + referer]
    p = subprocess.run(cmd, capture_output=True, text=True)
    return (p.stdout.strip() if p.returncode == 0 else "curl_exit_" + str(p.returncode))


def curl_get_retry(url, out_path, referer=None, tries=3):
    last = None
    for _ in range(tries):
        last = curl_get(url, out_path, referer)
        try:
            ok = Path(out_path).stat().st_size > 20000 and str(last).startswith("2")
        except OSError:
            ok = False
        if ok:
            return last
        time.sleep(3.0)
    return last

def sha256_of(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def parse_wayback_prices(html, code):
    """Same-SKU lowest-price evidence inside one archived Danawa product page."""
    title_m = re.search(r'og:title\" content\="([^\"]*)\"', html)
    title = title_m.group(1) if title_m else None
    full_m = re.search(r'sProductFullName\s*:\s*"([^"]*)"', html)
    full = full_m.group(1) if full_m else None
    ord_p = cash_p = delivered = offers = None
    ord_src = None
    meta_ord = None
    meta_cash = None
    m = re.search(r'id="min_price_' + code + r'" value="([0-9,]+)"', html)
    if m:
        ord_p = int(m.group(1).replace(",", ""))
        ord_src = "hidden"
    m = re.search(r'"lowPrice"\s*:\s*"([0-9,]+)"', html)
    low_json = int(m.group(1).replace(",", "")) if m else None
    m = re.search(r'"offerCount"\s*:\s*"([0-9]+)"', html)
    offers = int(m.group(1)) if m else None
    m = re.search(r'"priceCurrency"\s*:\s*"([A-Z]+)"', html)
    curr = m.group(1) if m else None
    m = re.search(r'id="intIncludeDeliveryFee" value="([0-9,]+)"', html)
    if m:
        delivered = int(m.group(1).replace(",", ""))
    m = re.search(r'id="lowPriceCash".{0,900}?prc_c\">([0-9,]+)', html, re.S)
    if m:
        cash_p = int(m.group(1).replace(",", ""))
    md = re.search(r'og:description[^>]{0,60}?content="([^"]*)"', html)
    if md:
        m0 = re.search(r'최저가\s*([0-9,]+)원', md.group(1))
        if m0:
            meta_ord = int(m0.group(1).replace(",", ""))
        m00 = re.search(r'현금최저가\s*:?\s*([0-9,]+)원', md.group(1))
        if m00:
            meta_cash = int(m00.group(1).replace(",", ""))
    if ord_p is None:
        ord_p = low_json
        ord_src = "json_ld"
    if ord_p is None:
        d = re.search(r'og:description\" content\="([^\"]*)\"', html)
        if d:
            m2 = re.search(r'최저가\s*([0-9,]+)원', d.group(1))
            if m2:
                ord_p = int(m2.group(1).replace(",", ""))
                ord_src = "body_scan"
            m3 = re.search(r'현금최저가\s*:?\s*([0-9,]+)원', d.group(1))
            if m3 and cash_p is None:
                cash_p = int(m3.group(1).replace(",", ""))
    return {"title": title or full, "ordinary": ord_p, "cash": cash_p,
            "delivered": delivered, "offers": offers, "currency": curr,
            "low_json": low_json,
            "meta_ordinary": meta_ord, "meta_cash": meta_cash,
            "ordinary_source": ord_src}


def write_enuri_reference():
    """Current-price reference only: Enuri model != Danawa SKU, condition mix flagged."""
    import re as _re
    try:
        h = (RAW / "enuri_catalog_79148017.html").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return
    h2 = h.replace(chr(92) + chr(34), chr(34))
    def g(pat):
        m = _re.search(pat, h2)
        return m.group(1) if m else None
    cat = g('"catalogName":"([^"]+)"')
    low = g('"lowPrice":([0-9]+)')
    high = g('"highPrice":([0-9]+)')
    malls = g('"mallCount":([0-9]+)')
    meta = g('content="\ucd5c\uc800\uac00 ([0-9,]+)\uc6d0"')
    sale = g('salePrice.{0,80}?price[^0-9]{0,8}([0-9,]+)')
    shops = []
    for m in _re.finditer('"shopName":"([^"]+)"', h2):
        pw = _re.search('"price":([0-9]+)', h2[m.end():m.end()+400])
        if pw:
            shops.append({"shop": m.group(1), "price_krw": int(pw.group(1))})
        if len(shops) >= 5:
            break
    ref = {"as_of_kst": datetime.now(KST).date().isoformat(),
           "enuri_model": "79148017",
           "catalog_name": cat,
           "representative_lowest_krw": int(low) if low else None,
           "meta_lowest_text_krw": meta,
           "high_price_krw": int(high) if high else None,
           "mall_count": int(malls) if malls else None,
           "membership_sale_price_krw": sale,
           "top_offers": shops,
           "same_sku_as_danawa_11790199": False,
           "comparability": "different model system; catalog name contains used-goods label; membership-discounted sale price kept separate; reference only, not model input",
           "source_url": "https://price.enuri.com/catalog/79148017",
           "raw_file": "data/verification/2026-10-23/forecast/domestic_extended/raw/enuri_catalog_79148017.html"}
    (OUT / "enuri_reference.json").write_text(json.dumps(ref, ensure_ascii=False, indent=2) + chr(10), encoding="utf-8")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    RAW.mkdir(parents=True, exist_ok=True)
    collected_kst = datetime.now(KST).isoformat(timespec="seconds")
    # existing Danawa monthly coverage (read-only reference)
    danawa_cov = {}
    for fn in ("timing/cpu_gpu_history.json", "timing/ram_ssd_history.json"):
        doc = json.loads((ROOT / "data/verification/2026-10-23" / fn).read_text(encoding="utf-8"))
        for p in doc["products"]:
            ms = [r["date"] for r in p.get("monthly", [])]
            danawa_cov[p["id"]] = {"monthly_first": ms[0] if ms else None,
                                     "monthly_last": ms[-1] if ms else None,
                                     "monthly_count": len(ms)}
    # 1) Wayback CDX per SKU (public archive listing)
    cdx_summary = {}
    for code, cat, name, fam in SKUS:
        cdx_path = RAW / ("cdx_" + code + ".json")
        if not cdx_path.exists():
            url = ("https://web.archive.org/cdx/search/cdx?url=prod.danawa.com/info/"
                   "%3Fpcode%3D" + code + "&output=json&filter=statuscode:200"
                   "&fl=timestamp,original,statuscode,digest&collapse=digest&limit=500")
            tmp = RAW / ("cdx_" + code + ".tmp")
            st = curl_get(url, tmp)
            try:
                rows = json.loads(tmp.read_text(encoding="utf-8"))
                snaps = [r[0] for r in rows[1:]]
                cdx_path.write_bytes(tmp.read_bytes())
            except Exception as e:
                snaps = []
                cdx_path.write_text(json.dumps({"error": str(e), "http": st}), encoding="utf-8")
            finally:
                tmp.unlink(missing_ok=True)
            time.sleep(1.0)
        else:
            try:
                rows = json.loads(cdx_path.read_text(encoding="utf-8"))
                snaps = [r[0] for r in rows[1:]] if isinstance(rows, list) else []
            except Exception:
                snaps = []
        pre = [s for s in snaps if s[:6] < "202412"]
        cdx_summary[code] = {"snapshots": len(snaps), "pre_202412": len(pre),
                             "first": snaps[0] if snaps else None,
                             "last": snaps[-1] if snaps else None}
        print(json.dumps({"cdx": code, "s": len(snaps), "pre": len(pre)}, ensure_ascii=False), flush=True)
    # 2) archived snapshots: up to 3 pre-chart anchors per SKU (5 for focus)
    anchors = []
    for code, cat, name, fam in SKUS:
        try:
            rows = json.loads((RAW / ("cdx_" + code + ".json")).read_text(encoding="utf-8"))
            snaps = [r[0] for r in rows[1:]] if isinstance(rows, list) else []
        except Exception:
            snaps = []
        pre = sorted([s for s in snaps if s[:6] < "202412"])
        if not pre:
            continue
        n = 5 if code in FOCUS else 3
        picks = sorted(set([pre[0], pre[len(pre)//2], pre[-1]]) if len(pre) >= 3 else pre)[:n]
        if code in FOCUS and len(pre) > 3:
            picks = sorted(set([pre[0], pre[len(pre)//3], pre[2*len(pre)//3], pre[-1], pre[len(pre)//2]]))[:5]
        day = {}
        for ts in sorted(picks):
            day.setdefault(ts[:8], ts)
        picks = sorted(day.values())
        for ts in picks:
            html_path = RAW / ("wayback_" + code + "_" + ts + ".html")
            if not html_path.exists():
                url = ("https://web.archive.org/web/" + ts +
                       "/https://prod.danawa.com/info/?pcode=" + code)
                st = curl_get_retry(url, html_path,
                                         referer="https://web.archive.org/")
                print(json.dumps({"fetched": code, "ts": ts, "http": st}, ensure_ascii=False), flush=True)
                time.sleep(1.5)
            else:
                st = "cached"
            try:
                html = html_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            pr = parse_wayback_prices(html, code)
            title, ord_p, cash_p = pr["title"], pr["ordinary"], pr["cash"]
            m_ord, m_cash, o_src = pr["meta_ordinary"], pr["meta_cash"], pr["ordinary_source"]
            basis_conflict = (m_ord is not None and ord_p is not None and m_ord != ord_p)
            if ord_p is None and cash_p is None:
                continue
            same = bool(title and fam.lower() in title.lower()) or ("pcode=" + code in html[:2000])
            anchors.append({
                "id": code, "category": cat, "sku_name": name,
                "archive_timestamp": ts, "anchor_date": ts[:4] + "-" + ts[4:6] + "-" + ts[6:8],
                "ordinary_lowest_krw": ord_p, "cash_lowest_krw": cash_p,
                "evidence_meta_ordinary_krw": m_ord, "evidence_meta_cash_krw": m_cash,
                "ordinary_source": o_src, "price_basis_conflict": basis_conflict,
                "display_model_excluded": basis_conflict,
                "conflict_detail": (("og:description ordinary %s conflicts with page ordinary %s" % (m_ord, ord_p)) if basis_conflict else None),
                "price_basis": "archive_page_min_price",
                "basis_differs_from_danawa_minprice": True,
                "shipping_basis": "unknown", "same_sku": bool("pcode=" + code),
                "same_sku_title": title, "same_sku_title_match": same,
                "delivered_krw": pr["delivered"], "offer_count": pr["offers"],
                "currency": pr["currency"], "lowprice_json_ld": pr["low_json"],
                "source_url": "https://web.archive.org/web/" + ts + "/https://prod.danawa.com/info/?pcode=" + code,
                "raw_file": "data/verification/2026-10-23/forecast/domestic_extended/raw/" + html_path.name,
                "sha256": sha256_of(html_path), "http": st,
            })
            print(json.dumps({"anchor": code, "ts": ts, "krw": ord_p}, ensure_ascii=False), flush=True)
    # 2b) dedupe same-day same-price anchors (keep earliest snapshot, drop redundant raws)
    seen = {}
    uniq = []
    for a in sorted(anchors, key=lambda x: x["archive_timestamp"]):
        k = (a["id"], a["anchor_date"], a["ordinary_lowest_krw"])
        if k in seen:
            try:
                (RAW / Path(a["raw_file"]).name).unlink()
            except OSError:
                pass
            continue
        seen[k] = True
        uniq.append(a)
    anchors = uniq
    # 3) UI-limits evidence from already-saved primary HTML (no new hidden probing)
    ev = {}
    try:
        dh = (RAW / "danawa_prod_11790199.html").read_text(encoding="utf-8", errors="replace")
        ev["danawa_ui_periods"] = [p for p in ["1개월", "3개월", "6개월", "12개월", "24개월", "36개월"] if p in dh]
    except OSError:
        ev["danawa_ui_periods"] = []
    try:
        eh = (RAW / "enuri_catalog_79148017.html").read_text(encoding="utf-8", errors="replace")
        ev["enuri_trend_strings"] = {k: eh.count(k) for k in ["가격추이", "가격변동", "그래프", "차트"]}
    except OSError:
        ev["enuri_trend_strings"] = {}
    try:
        qh = (RAW / "quasarzone_search_990pro.html").read_text(encoding="utf-8", errors="replace")
        ev["quasarzone_trend_strings"] = {k: qh.count(k) for k in ["가격", "시세", "차트", "그래프"]}
    except OSError:
        ev["quasarzone_trend_strings"] = {}
    by_sku = {}
    for a in anchors:
        by_sku.setdefault(a["id"], []).append(a)
    products = []
    for code, cat, name, fam in SKUS:
        products.append({
            "id": code, "category": cat, "sku_name": name,
            "danawa_chart_monthly": danawa_cov.get(code),
            "wayback_anchors": sorted(by_sku.get(code, []), key=lambda x: x["archive_timestamp"]),
            "new_month_points": len(by_sku.get(code, [])),
        })
    doc = {
        "schema": "domestic_extended_history/1",
        "collected_at_kst": collected_kst,
        "currency": "KRW",
        "rules": ["monthly anchors are single archived observations only",
                   "no daily interpolation", "no monthly-average reinterpretation",
                   "wayback ordinary-lowest basis differs from Danawa chart minPrice; do not splice as one series without basis flag"],
        "ui_limits": ev,
        "cdx": cdx_summary,
        "products": products,
        "counts": {"skus": len(SKUS), "anchors": len(anchors),
                    "skus_with_anchor": len(by_sku)},
    }
    (OUT / "extended_history.json").write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    import csv as _csv
    with (OUT / "extended_history.csv").open("w", encoding="utf-8-sig", newline="") as f:
        wcsv = _csv.writer(f)
        wcsv.writerow(["id", "category", "anchor_date", "archive_timestamp", "ordinary_lowest_krw",
                        "cash_lowest_krw", "price_basis", "same_sku_title_match", "price_basis_conflict", "display_model_excluded", "source_url", "raw_file"])
        for a in sorted(anchors, key=lambda x: (x["id"], x["archive_timestamp"])):
            wcsv.writerow([a["id"], a["category"], a["anchor_date"], a["archive_timestamp"],
                            a["ordinary_lowest_krw"], a["cash_lowest_krw"], a["price_basis"],
                            a["same_sku_title_match"], a["price_basis_conflict"], a["display_model_excluded"], a["source_url"], a["raw_file"]])
    write_enuri_reference()
    print(json.dumps({"done": True, "anchors": len(anchors), "skus": len(by_sku)}, ensure_ascii=False))

if __name__ == "__main__":
    main()
