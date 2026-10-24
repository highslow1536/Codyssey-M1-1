"""Domestic price-history dashboard export helper (independent).

Reads only the frozen snapshot data/feasibility/2026-10-21
(mobile raw files and desktop raw files)
plus existing product metadata in
data/processed/2026-10-21/domestic/products.csv.

Raw responses are never modified. The single dashboard-safe derivative is
data/processed/2026-10-23/domestic/history.json.

Scope: the 8 domestic products. Weekly 3-month window on both surfaces
(12 unique rows per product, 96 total) with original labels and prices
preserved; monthly 24-month window kept as two separate arrays (mobile
and desktop) with original values preserved, plus a comparison view that
marks matched / value_mismatch / mobile_only / desktop_only without
merging values.

Deliberate non-goals (enforced by tests):
- Date labels are never renamed to a W-FRI observed-week scheme.
- Monthly values are never asserted to be verified monthly minima nor
  representative market prices.
- No current-price row is appended (the mobile page JS appends one at
  render time; it is not a historical observation).
- No outlier is removed (e.g. RTX 4060 2025-11 observations stay).
- Boundary-month mismatches stay unresolved with both values kept.

Standard library only. Run:
    python3 scripts/prepare_domestic_history.py
"""

import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_DIR = ROOT / "data/feasibility/2026-10-21"
PRODUCTS_CSV = ROOT / "data/processed/2026-10-21/domestic/products.csv"
OUTPUT_DIR = ROOT / "data/processed/2026-10-23/domestic"
OUTPUT_FILE = OUTPUT_DIR / "history.json"

SCHEMA = "domestic_history/1"
SNAPSHOT_DATE_KST = "2026-10-21"
SNAPSHOT_YEAR = 2026
SNAPSHOT_MONTH = 10
PARTIAL_MONTH_LABEL = "26-10"
WEEKLY_PERIOD = 3
MONTHLY_PERIOD = 24
MOBILE_PERIODS = (1, 3, 6, 12, 24)

# Cited from the existing audit (docs/domestic_price_audit.md), all-window scope.
AUDIT_KNOWN = {
    "cross_surface_value_mismatches": 13,
    "cross_surface_mobile_only_rows": 6,
    "cross_surface_desktop_only_rows": 0,
    "mobile_internal_mismatches": 0,
    "desktop_internal_mismatches": 9,
}


def sha256_of(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_products():
    with PRODUCTS_CSV.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    products = []
    for row in rows:
        products.append(
            {
                "product_code": row["product_code"],
                "category": row["category"],
                "name": row["name"],
                "product_url": row["product_url"],
            }
        )
    assert len(products) == 8, len(products)
    return products


def mobile_rows(code, months):
    path = SNAPSHOT_DIR / "raw" / ("%s_%dm.json" % (code, months))
    payload = json.loads(path.read_text(encoding="utf-8"))
    out = []
    seen = set()
    for row in payload["graphDataList"]:
        label = row["date"].replace(".", "-")
        if months == 3:
            label = label[-5:]
        assert label not in seen, (code, months, label)
        seen.add(label)
        price = row["minPrice"]
        assert isinstance(price, (int, float)) and price > 0, (code, months, row)
        out.append((label, price))
    return out


def desktop_rows(code, months):
    path = SNAPSHOT_DIR / "desktop" / "raw" / (code + ".json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    out = []
    seen = set()
    for row in payload[str(months)]["result"]:
        fulldate = row.get("Fulldate")
        label = (fulldate if fulldate is not None else row["date"]).replace(".", "-")
        if months == 3:
            label = label[-5:]
        assert label not in seen, (code, months, label)
        seen.add(label)
        price = row["minPrice"]
        assert isinstance(price, (int, float)) and price > 0, (code, months, row)
        out.append((label, fulldate, price))
    return out


def weekly_iso(mobile_label, desktop_fulldate):
    confirmed = "20" + desktop_fulldate
    month = int(mobile_label.split("-")[0])
    year = SNAPSHOT_YEAR if month <= SNAPSHOT_MONTH else SNAPSHOT_YEAR - 1
    inferred = "%04d-%s" % (year, mobile_label)
    assert inferred == confirmed, (mobile_label, desktop_fulldate)
    return inferred


def collect_hashes(codes):
    sources = []
    for code in codes:
        for months in MOBILE_PERIODS:
            rel = "raw/%s_%dm.json" % (code, months)
            path = SNAPSHOT_DIR / rel
            rows = len(json.loads(path.read_text(encoding="utf-8"))["graphDataList"])
            sources.append(
                {
                    "file": "data/feasibility/2026-10-21/" + rel,
                    "sha256": sha256_of(path),
                    "rows": rows,
                }
            )
        rel = "desktop/raw/%s.json" % code
        path = SNAPSHOT_DIR / rel
        payload = json.loads(path.read_text(encoding="utf-8"))
        sources.append(
            {
                "file": "data/feasibility/2026-10-21/" + rel,
                "sha256": sha256_of(path),
                "rows": {str(m): len(payload[str(m)]["result"]) for m in MOBILE_PERIODS},
            }
        )
    assert len(sources) == 48, len(sources)
    return sources


def build_history():
    products_meta = load_products()
    codes = [m["product_code"] for m in products_meta]
    sources = collect_hashes(codes)

    products = []
    weekly_total = 0
    monthly_mobile_total = 0
    monthly_desktop_total = 0
    cmp_matched = 0
    cmp_mismatch = 0
    cmp_mobile_only = 0
    cmp_desktop_only = 0

    for meta in products_meta:
        code = meta["product_code"]
        mob3 = mobile_rows(code, WEEKLY_PERIOD)
        desk3 = desktop_rows(code, WEEKLY_PERIOD)
        assert len(mob3) == 12, (code, len(mob3))
        assert len(desk3) == 12, (code, len(desk3))
        desk3_by_label = {label: (full, price) for label, full, price in desk3}
        assert set(dict(mob3)) == set(desk3_by_label), code

        weekly = []
        for seq, (label, mprice) in enumerate(mob3):
            full, dprice = desk3_by_label[label]
            iso = weekly_iso(label, full)
            weekly.append(
                {
                    "seq": seq,
                    "label_mobile": label,
                    "label_desktop": label,
                    "desktop_fulldate": full,
                    "mobile_price": mprice,
                    "desktop_price": dprice,
                    "match": mprice == dprice,
                    "iso_date": iso,
                    "iso_year_inferred": True,
                    "iso_basis": "desktop Fulldate confirmed by 20-prefix; mobile MM-DD year from snapshot context",
                }
            )

        mob24 = mobile_rows(code, MONTHLY_PERIOD)
        desk24 = desktop_rows(code, MONTHLY_PERIOD)
        monthly_mobile = [{"label": label, "price": price} for label, price in mob24]
        monthly_desktop = [{"label": label, "price": price} for label, _full, price in desk24]

        mob24_by_label = dict(mob24)
        desk24_by_label = {label: price for label, _full, price in desk24}
        comparison = []
        ordered = [label for label, _ in mob24]
        ordered += [label for label, _, _ in desk24 if label not in mob24_by_label]
        for label in ordered:
            in_m = label in mob24_by_label
            in_d = label in desk24_by_label
            if in_m and in_d:
                mprice = mob24_by_label[label]
                dprice = desk24_by_label[label]
                status = "matched" if mprice == dprice else "value_mismatch"
            elif in_m:
                mprice, dprice, status = mob24_by_label[label], None, "mobile_only"
            else:
                mprice, dprice, status = None, desk24_by_label[label], "desktop_only"
            comparison.append(
                {
                    "month_label": label,
                    "month_iso": "20" + label,
                    "mobile_price": mprice,
                    "desktop_price": dprice,
                    "status": status,
                    "partial_month": label == PARTIAL_MONTH_LABEL,
                }
            )

        weekly_total += len(weekly)
        monthly_mobile_total += len(monthly_mobile)
        monthly_desktop_total += len(monthly_desktop)
        for row in comparison:
            if row["status"] == "matched":
                cmp_matched += 1
            elif row["status"] == "value_mismatch":
                cmp_mismatch += 1
            elif row["status"] == "mobile_only":
                cmp_mobile_only += 1
            else:
                cmp_desktop_only += 1

        products.append(
            {
                "product_code": code,
                "category": meta["category"],
                "name": meta["name"],
                "product_url": meta["product_url"],
                "currency": "KRW",
                "historical_field": "minPrice",
                "price_basis": "source_label_lowest_price_trend",
                "shipping_basis": "unknown",
                "cash_card_basis": "unknown",
                "coupon_basis": "unknown",
                "aggregation_basis": "unconfirmed",
                "weekly_aggregation": "unknown",
                "weekly_3m": weekly,
                "monthly_mobile_24m": monthly_mobile,
                "monthly_desktop_24m": monthly_desktop,
                "monthly_comparison_24m": comparison,
            }
        )

    history = {
        "schema": SCHEMA,
        "snapshot": str(SNAPSHOT_DIR),
        "snapshot_date_kst": SNAPSHOT_DATE_KST,
        "generated_date_kst": datetime.now(ZoneInfo("Asia/Seoul")).date().isoformat(),
        "currency": "KRW",
        "price_semantics": {
            "historical_field": "minPrice",
            "price_basis": "source_label_lowest_price_trend",
            "shipping_basis": "unknown",
            "cash_card_basis": "unknown",
            "coupon_basis": "unknown",
            "aggregation_basis": "unconfirmed",
            "weekly_aggregation": "unknown",
        },
        "counts": {
            "products": len(products),
            "weekly_unique_rows_per_product": 12,
            "weekly_unique_rows_total": weekly_total,
            "monthly_mobile_24m_rows_total": monthly_mobile_total,
            "monthly_desktop_24m_rows_total": monthly_desktop_total,
            "comparison_24m_matched": cmp_matched,
            "comparison_24m_value_mismatch": cmp_mismatch,
            "comparison_24m_mobile_only": cmp_mobile_only,
            "comparison_24m_desktop_only": cmp_desktop_only,
        },
        "audit_consistency": {
            "cited": AUDIT_KNOWN,
            "note": "Cited audit totals count window occurrences across 1/3/6/12/24m windows; this export compares the 24m window only, so comparison counts are a subset. Every value is verbatim; no mismatch was merged or removed.",
        },
        "cautions": [
            "Single-day snapshot (2026-10-21); 26-10 is an incomplete partial month.",
            "Original date labels are authoritative; timeline ISO strings are display aids only.",
            "Weekly 3m MM-DD labels carry no year; the year is inferred from snapshot context and flagged.",
            "Monthly rows are returned source-label values, not verified monthly minima.",
            "Values must not be presented as representative market prices.",
            "No current-price row was appended and no outlier was removed.",
            "Boundary-month mismatches are unresolved; both values are preserved.",
        ],
        "sources": sources,
        "products": products,
    }
    return history


def main():
    codes = [m["product_code"] for m in load_products()]
    before = {s["file"]: s["sha256"] for s in collect_hashes(codes)}
    history = build_history()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with OUTPUT_FILE.open("w", encoding="utf-8") as handle:
        json.dump(history, handle, ensure_ascii=False, indent=2)
        handle.write(chr(10))
    after = {s["file"]: s["sha256"] for s in collect_hashes(codes)}
    assert before == after, "raw snapshot changed during export"
    print(json.dumps(history["counts"], ensure_ascii=False, indent=2))
    print("wrote " + str(OUTPUT_FILE))


if __name__ == "__main__":
    main()
