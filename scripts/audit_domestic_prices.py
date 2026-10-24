"""Domestic (Danawa) price-history audit: mobile vs PC surfaces.

Read-only over the frozen snapshot data/feasibility/2026-10-21
(raw responses are never modified). Writes reproducible derivatives to
data/processed/2026-10-21/domestic/.

Covers the 8 domestic products from probe_price_history.PRODUCTS:
all five chart periods on both surfaces, weekly/monthly linkage,
within-surface nesting of the 6/12-month windows inside the 24-month
window, boundary-month diagnosis, and price-meaning evidence split
into verified facts vs explicitly unverified semantics.

Run:
    <bundled python3> scripts/audit_domestic_prices.py
"""

import csv
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
from probe_price_history import PERIODS, PRODUCTS

SNAPSHOT_DIR = Path("data/feasibility/2026-10-21")
OUTPUT_DIR = Path("data/processed/2026-10-21/domestic")
EVIDENCE_DIR = Path("data/verification/2026-10-21/danawa")
EVIDENCE_FILES = [
    "prod_21694499.html",
    "m_21694499.html",
    "summary.min.js",
    "common.min.js",
]
MOBILE_ROUTE = "https://m2.danawa.com/product/getPriceTendencyGraph.json"
DESKTOP_ROUTE = "https://prod.danawa.com/info/ajax/getProductPriceList.ajax.php"

VERIFIED_SEMANTICS = [
    {
        "fact": "PC product page titles the chart lowest-price trend and says "
        "to check it by period from 1 month to 24 months.",
        "evidence": "data/verification/2026-10-21/danawa/prod_21694499.html",
    },
    {
        "fact": "The mobile request route with productCode and period "
        "(1/3/6/12/24) and the per-period cache are the page JS first-party "
        "UI route, not a guessed endpoint.",
        "evidence": "data/verification/2026-10-21/danawa/summary.min.js",
    },
    {
        "fact": "The mobile page JS appends a current-price row to the "
        "returned graphDataList, so that row is not a historical observation.",
        "evidence": "data/verification/2026-10-21/danawa/summary.min.js",
    },
    {
        "fact": "The mobile page JS enables period tabs using totalCount "
        "thresholds (4/12/24/48).",
        "evidence": "data/verification/2026-10-21/danawa/summary.min.js",
    },
    {
        "fact": "The PC request route with productCode returns per-period "
        "count/result rows (Fulldate/date/minPrice) plus maxPrice/minPrice "
        "summaries.",
        "evidence": "data/verification/2026-10-21/danawa/common.min.js",
    },
    {
        "fact": "The PC page shows lowest price and cash lowest price "
        "separately, offers a shipping-included toggle, and notes that "
        "sellers with inaccurate shipping data are shown without shipping.",
        "evidence": "data/verification/2026-10-21/danawa/prod_21694499.html",
    },
    {
        "fact": "The product name carries packing conditions (e.g. multipack "
        "genuine) and bulk/parallel options exist as separate listings.",
        "evidence": "data/verification/2026-10-21/danawa/prod_21694499.html",
    },
]

UNVERIFIED_SEMANTICS = [
    {
        "item": "Whether minPrice follows the card price or the cash price.",
        "reason": "Both prices appear on the page; no chart rule text found.",
    },
    {
        "item": "Whether shipping fees are included in minPrice.",
        "reason": "Listing toggle and notice exist, chart applicability unknown.",
    },
    {
        "item": "Whether coupon, membership, or card-benefit prices apply.",
        "reason": "No chart rule text found.",
    },
    {
        "item": "Sold-out, delisted, or missing-price seller exclusion rules.",
        "reason": "No chart rule text found.",
    },
    {
        "item": "Monthly aggregation definition beyond the verified window.",
        "reason": "Verified only for 2026-08 to 2026-10 where weekly rows exist.",
    },
    {
        "item": "Weekly aggregation definition (weekday anchor or week low).",
        "reason": "No aggregation rule text found; sampling weekday unconfirmed.",
    },
    {
        "item": "Cause of boundary-month mismatches.",
        "reason": "Pattern matches window-cut position but cause is unconfirmed; "
        "left unresolved, values are not merged.",
    },
    {
        "item": "Retroactive application of current UI conditions to past minPrice.",
        "reason": "Not permitted: past rows must not inherit current conditions.",
    },
]


def sha256_of(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def mobile_label(date_str, months):
    label = date_str.replace(".", "-")
    if months == 3:
        label = label[-5:]
    return label


def desktop_label(row, months):
    label = row.get("Fulldate", row["date"]).replace(".", "-")
    if months == 3:
        label = label[-5:]
    return label


def check_label(label, months):
    if months == 3:
        datetime.strptime("2000-" + label, "%Y-%m-%d")
    elif months == 1:
        datetime.strptime(label, "%y-%m-%d")
    else:
        datetime.strptime(label, "%y-%m")


def load_mobile(code):
    series = {}
    for months in PERIODS:
        path = SNAPSHOT_DIR / "raw" / ("%s_%dm.json" % (code, months))
        rows = json.loads(path.read_text(encoding="utf-8"))["graphDataList"]
        values = {}
        order = []
        for row in rows:
            label = mobile_label(row["date"], months)
            check_label(label, months)
            assert label not in values, (code, months, label)
            price = row["minPrice"]
            assert isinstance(price, (int, float)) and price > 0, (code, months, row)
            values[label] = price
            order.append(label)
        series[months] = {"values": values, "order": order}
    return series


def load_desktop(code):
    data = json.loads((SNAPSHOT_DIR / "desktop" / "raw" / (code + ".json")).read_text(encoding="utf-8"))
    series = {}
    for months in PERIODS:
        rows = data[str(months)]["result"]
        values = {}
        order = []
        for row in rows:
            label = desktop_label(row, months)
            check_label(label, months)
            assert label not in values, (code, months, label)
            price = row["minPrice"]
            assert isinstance(price, (int, float)) and price > 0, (code, months, row)
            values[label] = price
            order.append(label)
        series[months] = {"values": values, "order": order}
    return series


def main():
    mobile_summary = json.loads((SNAPSHOT_DIR / "summary.json").read_text(encoding="utf-8"))
    desktop_summary = json.loads((SNAPSHOT_DIR / "desktop" / "summary.json").read_text(encoding="utf-8"))
    mobile_meta = {p["product_code"]: p for p in mobile_summary["products"]}
    desktop_meta = {p["product_code"]: p for p in desktop_summary["products"]}

    hashes = {}
    for _category, code, _name in PRODUCTS:
        for months in PERIODS:
            rel = "raw/%s_%dm.json" % (code, months)
            hashes[rel] = sha256_of(SNAPSHOT_DIR / rel)
        rel = "desktop/raw/%s.json" % code
        hashes[rel] = sha256_of(SNAPSHOT_DIR / rel)

    discrepancies = []
    products_rows = []
    weekly_total = 0
    monthly_mobile_total = 0
    monthly_desktop_total = 0
    value_mismatch_total = 0
    mobile_only_total = 0
    desktop_only_total = 0
    internal = {"mobile": [], "desktop": []}
    linkage_ok = 0
    linkage_checked = 0

    for category, code, name in PRODUCTS:
        mob = mobile_meta[code]
        desk = desktop_meta[code]
        mob_periods = {p["period_months"]: p for p in mob["periods"]}
        desk_periods = {p["period_months"]: p for p in desk["periods"]}
        for months in PERIODS:
            assert mob_periods[months]["http_status"] == "200"
            assert mob_periods[months]["curl_exit_code"] == 0
        assert desk["http_status"] == "200" and desk["curl_exit_code"] == 0

        mobile = load_mobile(code)
        desktop = load_desktop(code)
        for months in PERIODS:
            assert len(mobile[months]["values"]) == mob_periods[months]["actual_rows"]
            assert len(mobile[months]["values"]) == mob_periods[months]["unique_date_labels"]
            assert len(desktop[months]["values"]) == desk_periods[months]["actual_rows"]
            assert len(desktop[months]["values"]) == desk_periods[months]["source_count"]

        for label, price in mobile[1]["values"].items():
            assert mobile[3]["values"][label[-5:]] == price, (code, label)
        for label, price in desktop[1]["values"].items():
            assert desktop[3]["values"][label[-5:]] == price, (code, label)
        for months in (6, 12):
            for label, price in mobile[months]["values"].items():
                assert mobile[24]["values"][label] == price, (code, months, label)

        for months in PERIODS:
            mv = mobile[months]["values"]
            dv = desktop[months]["values"]
            overlap = sorted(set(mv) & set(dv))
            oldest_m = mobile[months]["order"][0]
            oldest_d = desktop[months]["order"][0]
            for label in overlap:
                if mv[label] != dv[label]:
                    boundary = label in (oldest_m, oldest_d)
                    discrepancies.append({
                        "scope": "cross_surface",
                        "product_code": code,
                        "window_a": "mobile_%dm" % months,
                        "window_b": "desktop_%dm" % months,
                        "month_label": label,
                        "price_a": mv[label],
                        "price_b": dv[label],
                        "kind": "value_mismatch",
                        "boundary_month": str(boundary).lower(),
                        "note": "oldest month of at least one window" if boundary else "non-boundary mismatch",
                    })
                    value_mismatch_total += 1
            for label in sorted(set(mv) - set(dv)):
                discrepancies.append({
                    "scope": "cross_surface",
                    "product_code": code,
                    "window_a": "mobile_%dm" % months,
                    "window_b": "desktop_%dm" % months,
                    "month_label": label,
                    "price_a": mv[label],
                    "price_b": "",
                    "kind": "only_in_a",
                    "boundary_month": str(label == oldest_m).lower(),
                    "note": "mobile-only oldest month" if label == oldest_m else "mobile-only row",
                })
                mobile_only_total += 1
            for label in sorted(set(dv) - set(mv)):
                discrepancies.append({
                    "scope": "cross_surface",
                    "product_code": code,
                    "window_a": "mobile_%dm" % months,
                    "window_b": "desktop_%dm" % months,
                    "month_label": label,
                    "price_a": "",
                    "price_b": dv[label],
                    "kind": "only_in_b",
                    "boundary_month": str(label == oldest_d).lower(),
                    "note": "desktop-only row",
                })
                desktop_only_total += 1

        for surface_name, series in (("mobile", mobile), ("desktop", desktop)):
            for short, long in ((6, 12), (6, 24), (12, 24)):
                sv = series[short]["values"]
                lv = series[long]["values"]
                oldest_s = series[short]["order"][0]
                oldest_l = series[long]["order"][0]
                for label in sorted(set(sv) & set(lv)):
                    if sv[label] != lv[label]:
                        boundary = label in (oldest_s, oldest_l)
                        discrepancies.append({
                            "scope": surface_name + "_internal",
                            "product_code": code,
                            "window_a": "%s_%dm" % (surface_name, short),
                            "window_b": "%s_%dm" % (surface_name, long),
                            "month_label": label,
                            "price_a": sv[label],
                            "price_b": lv[label],
                            "kind": "value_mismatch",
                            "boundary_month": str(boundary).lower(),
                            "note": "oldest month of at least one window" if boundary else "non-boundary mismatch",
                        })
                        internal[surface_name].append((code, short, long, label))

        ref_year, ref_month = 26, 10
        last1 = mobile[1]["order"][-1]
        ref_year = int(last1.split("-")[0])
        ref_month = int(last1.split("-")[1])
        weekly_groups = {}
        for label, price in mobile[3]["values"].items():
            mm = int(label.split("-")[0])
            yy = ref_year if mm <= ref_month else ref_year - 1
            weekly_groups.setdefault("%02d-%02d" % (yy, mm), []).append(price)
        ddata = json.loads((SNAPSHOT_DIR / "desktop" / "raw" / (code + ".json")).read_text(encoding="utf-8"))
        desktop_weekly_groups = {}
        for row in ddata["3"]["result"]:
            full = row["Fulldate"]
            key = full[:5]
            desktop_weekly_groups.setdefault(key, []).append(row["minPrice"])
        for key in weekly_groups:
            assert key in desktop_weekly_groups, (code, key)
            assert sorted(weekly_groups[key]) == sorted(desktop_weekly_groups[key]), (code, key)
        for key, prices in weekly_groups.items():
            for months in (6, 12, 24):
                if key in mobile[months]["values"]:
                    linkage_checked += 1
                    assert mobile[months]["values"][key] == min(prices), (code, key)
                    assert desktop[months]["values"][key] == min(prices), (code, key)
                    linkage_ok += 1

        weekly_unique = len(mobile[3]["values"])
        weekly_total += weekly_unique
        monthly_mobile_total += len(mobile[24]["values"])
        monthly_desktop_total += len(desktop[24]["values"])
        value_mismatches = sum(1 for d in discrepancies if d["product_code"] == code and d["scope"] == "cross_surface" and d["kind"] == "value_mismatch")
        mob_only = sum(1 for d in discrepancies if d["product_code"] == code and d["scope"] == "cross_surface" and d["kind"] == "only_in_a")
        desk_only = sum(1 for d in discrepancies if d["product_code"] == code and d["scope"] == "cross_surface" and d["kind"] == "only_in_b")
        products_rows.append({
            "product_code": code,
            "category": category,
            "name": name,
            "product_url": mob["product_url"],
            "source_totalCount": mob_periods[24].get("source_totalCount", ""),
            "mobile_24m_rows": len(mobile[24]["values"]),
            "desktop_24m_rows": len(desktop[24]["values"]),
            "weekly_unique_rows": weekly_unique,
            "value_mismatches": value_mismatches,
            "mobile_only_rows": mob_only,
            "desktop_only_rows": desk_only,
            "oldest_mobile_month": mobile[24]["order"][0],
            "oldest_desktop_month": desktop[24]["order"][0],
            "currency": "KRW",
            "historical_field": "minPrice",
            "price_basis": "source_label_lowest_price_trend",
            "shipping_basis": "unknown",
            "cash_card_basis": "unknown",
            "coupon_basis": "unknown",
            "aggregation_basis": "unconfirmed",
        })

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_DIR / "products.csv", "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(products_rows[0].keys()))
        writer.writeheader()
        writer.writerows(products_rows)
    disc_fields = ["scope", "product_code", "window_a", "window_b", "month_label",
                   "price_a", "price_b", "kind", "boundary_month", "note"]
    with open(OUTPUT_DIR / "discrepancies.csv", "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=disc_fields)
        writer.writeheader()
        for row in sorted(discrepancies, key=lambda d: (d["scope"], d["product_code"], d["window_a"], d["month_label"])):
            writer.writerow(row)
    evidence = []
    for fname in EVIDENCE_FILES:
        path = EVIDENCE_DIR / fname
        evidence.append({
            "file": "data/verification/2026-10-21/danawa/" + fname,
            "bytes": path.stat().st_size,
            "sha256": sha256_of(path),
        })
    summary = {
        "run_date_kst": datetime.now(ZoneInfo("Asia/Seoul")).date().isoformat(),
        "snapshot": str(SNAPSHOT_DIR),
        "snapshot_date_kst": mobile_summary["checked_date_kst"],
        "routes": {
            "mobile": MOBILE_ROUTE,
            "desktop": DESKTOP_ROUTE,
            "note": "Undocumented website UI endpoints; accessibility does not establish redistribution rights.",
        },
        "counts": {
            "products": len(PRODUCTS),
            "periods_per_surface": list(PERIODS),
            "mobile_raw_responses": 40,
            "desktop_raw_responses": 8,
            "weekly_unique_rows_per_product": 12,
            "weekly_unique_rows_total": weekly_total,
            "monthly_mobile_24m_rows_total": monthly_mobile_total,
            "monthly_desktop_24m_rows_total": monthly_desktop_total,
            "cross_surface_value_mismatches": value_mismatch_total,
            "cross_surface_mobile_only_rows": mobile_only_total,
            "cross_surface_desktop_only_rows": desktop_only_total,
            "mobile_internal_mismatches": len(internal["mobile"]),
            "desktop_internal_mismatches": len(internal["desktop"]),
            "weekly_linkage_checks_passed": "%d/%d" % (linkage_ok, linkage_checked),
        },
        "row_reconciliation": {
            "mobile_summary_counts_match_raw": True,
            "desktop_source_counts_match_raw": True,
            "mobile_totalCount_is_not_row_count": True,
            "totalCount_note": "Inferred only, not verified: 104 is consistent with about "
            "52 weeks x 2 years for full-history products; 87 and 86 for newer "
            "listings reflect shorter histories. totalCount is never used as a row count.",
            "totalCount_interpretation": "inferred",
        },
        "boundary_month_diagnosis": {
            "all_cross_surface_mismatches_boundary": all(
                d["boundary_month"] == "true" for d in discrepancies
                if d["scope"] == "cross_surface" and d["kind"] == "value_mismatch"),
            "all_internal_mismatches_boundary": all(
                d["boundary_month"] == "true" for d in discrepancies
                if d["scope"].endswith("_internal") and d["kind"] == "value_mismatch"),
            "verdict": "Mismatches cluster on the oldest month of a queried window; "
            "cause unconfirmed, left unresolved, values not merged.",
        },
        "price_semantics": {
            "verified": VERIFIED_SEMANTICS,
            "unverified": UNVERIFIED_SEMANTICS,
        },
        "evidence": evidence,
        "limitations": [
            "Single-day snapshot (2026-10-21); the current month is incomplete.",
            "Monthly-min-equals-weekly-min verified only for 2026-08 to 2026-10.",
            "Past minPrice rows must not inherit current UI conditions.",
            "Endpoint accessibility does not establish redistribution rights.",
        ],
        "raw_hashes": hashes,
    }
    with open(OUTPUT_DIR / "summary.json", "w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    for rel, digest in hashes.items():
        assert sha256_of(SNAPSHOT_DIR / rel) == digest, rel
    print(json.dumps(summary["counts"], ensure_ascii=False, indent=2))
    print("wrote " + str(OUTPUT_DIR))


if __name__ == "__main__":
    main()
