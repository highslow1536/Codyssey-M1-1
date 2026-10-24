"""Independent audit of timing sources: raw integrity + normalization cross-check.

Read-only except for its own output file. For every product in
cpu_gpu_history.json and ram_ssd_history.json (21 SKUs total) it checks:
  - rawFile sha256 matches the bytes on disk
  - raw period keys are read directly (expect 1/3/6/12/24)
  - normalized weekly rows exactly match the raw 3m group
    (Fulldate priority, MM-DD-only inferred as 2026, date/price pairwise)
  - normalized monthly rows exactly match the raw 24m group
    (YY-MM mapped to YYYY-MM, price pairwise, partial flag)
  - weekly dates are Tuesdays spaced 7 days apart
  - partial-month marking: 2026-10 partial, all earlier months not partial
  - no duplicate SKU ids, and the audited set equals all 21 domestic SKUs
    (products + marketReferences in dashboard/dist/data/domestic.json)

Writes data/verification/2026-10-23/timing/source_audit.json
and prints exact-match counts plus any errors.
"""

import hashlib
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TIMING = ROOT / "data" / "verification" / "2026-10-23" / "timing"
HISTORIES = [TIMING / "cpu_gpu_history.json", TIMING / "ram_ssd_history.json"]
OUT = TIMING / "source_audit.json"


def full_to_iso(full):
    yy, mm, dd = full.split("-")
    return "20" + yy + "-" + mm + "-" + dd


def ym_to_iso(ym):
    yy, mm = ym.split("-")
    return "20" + yy + "-" + mm


def iso_to_date(iso):
    y, m, d = iso.split("-")
    return date(int(y), int(m), int(d))


def main():
    errors = []
    domestic = json.loads((ROOT / "dashboard" / "dist" / "data" / "domestic.json").read_text(encoding="utf-8"))
    expected_ids = [p["id"] for p in domestic["products"]] + [m["id"] for m in domestic["marketReferences"]]
    if len(set(expected_ids)) != len(expected_ids):
        errors.append("domestic.json itself contains duplicate ids")
    seen = {}
    per_sku = []
    tot_w_exact = tot_w = tot_m_exact = tot_m = 0
    for hp in HISTORIES:
        history = json.loads(hp.read_text(encoding="utf-8"))
        for p in history["products"]:
            pid = p["id"]
            rec = {"id": pid, "historyFile": hp.name, "skuErrors": []}
            if pid in seen:
                rec["skuErrors"].append("duplicate id also seen in " + seen[pid])
            seen[pid] = hp.name
            raw_path = ROOT / p["rawFile"]
            try:
                blob = raw_path.read_bytes()
            except OSError as exc:
                rec["skuErrors"].append("rawFile unreadable: " + str(exc))
                per_sku.append(rec)
                continue
            digest = hashlib.sha256(blob).hexdigest()
            rec["shaMatch"] = (digest == p["sha256"])
            if not rec["shaMatch"]:
                rec["skuErrors"].append("sha256 mismatch")
            try:
                raw = json.loads(blob)
            except ValueError as exc:
                rec["skuErrors"].append("raw is not valid JSON: " + str(exc))
                per_sku.append(rec)
                continue
            period_keys = sorted(raw.keys(), key=int)
            rec["periodKeys"] = period_keys
            if period_keys != ["1", "3", "6", "12", "24"]:
                rec["skuErrors"].append("unexpected period keys read from raw: " + str(period_keys))
                per_sku.append(rec)
                continue
            for key in ("1", "3", "6", "12", "24"):
                group = raw[key]
                if group["count"] != len(group["result"]):
                    rec["skuErrors"].append("period " + key + " count field does not match raw row count")
            raw3 = raw["3"]["result"]
            raw24 = raw["24"]["result"]
            weekly = p["weekly"]
            monthly = p["monthly"]
            w_exact = 0
            if len(weekly) != len(raw3):
                rec["skuErrors"].append("weekly length " + str(len(weekly)) + " != raw 3m rows " + str(len(raw3)))
            for i, (r, w) in enumerate(zip(raw3, weekly)):
                exp_date = full_to_iso(r["Fulldate"]) if r.get("Fulldate") else "2026-" + r["date"]
                if not isinstance(r.get("minPrice"), (int, float)) or r["minPrice"] in (0, None):
                    rec["skuErrors"].append("raw 3m row " + str(i) + " has non-positive minPrice kept as-is")
                if w["date"] == exp_date and w["price"] == r["minPrice"]:
                    w_exact += 1
                else:
                    rec["skuErrors"].append("weekly row " + str(i) + " differs from raw 3m row")
            m_exact = 0
            if len(monthly) != len(raw24):
                rec["skuErrors"].append("monthly length " + str(len(monthly)) + " != raw 24m rows " + str(len(raw24)))
            for i, (r, m) in enumerate(zip(raw24, monthly)):
                exp_date = ym_to_iso(r["date"])
                exp_partial = (i == len(raw24) - 1)
                if not isinstance(r.get("minPrice"), (int, float)) or r["minPrice"] in (0, None):
                    rec["skuErrors"].append("raw 24m row " + str(i) + " has non-positive minPrice kept as-is")
                if m["date"] == exp_date and m["price"] == r["minPrice"] and m["partial"] is exp_partial:
                    m_exact += 1
                else:
                    rec["skuErrors"].append("monthly row " + str(i) + " differs from raw 24m row")
            rec["weeklyExact"] = w_exact
            rec["weeklyTotal"] = len(raw3)
            rec["monthlyExact"] = m_exact
            rec["monthlyTotal"] = len(raw24)
            tot_w_exact += w_exact
            tot_w += len(raw3)
            tot_m_exact += m_exact
            tot_m += len(raw24)
            try:
                dates = [iso_to_date(w["date"]) for w in weekly]
            except ValueError as exc:
                rec["skuErrors"].append("weekly date unparsable: " + str(exc))
                dates = []
            tue7 = bool(dates) and all(d.weekday() == 1 for d in dates) and all(
                (b - a).days == 7 for a, b in zip(dates, dates[1:]))
            rec["tuesday7day"] = tue7
            if not tue7:
                rec["skuErrors"].append("weekly dates are not all-Tuesday 7-day spaced")
            oct_rows = [m for m in monthly if m["date"] == "2026-10"]
            oct_ok = all(m["partial"] is True for m in oct_rows) and all(
                m["partial"] is False for m in monthly if m["date"] != "2026-10")
            rec["octPartialOk"] = oct_ok
            rec["lastMonthlyDate"] = monthly[-1]["date"] if monthly else None
            if not oct_ok:
                rec["skuErrors"].append("partial-month Oct marking violated")
            if rec["skuErrors"]:
                errors.append({"id": pid, "issues": list(rec["skuErrors"])})
            per_sku.append(rec)
    audited_ids = sorted(seen.keys())
    missing = sorted(set(expected_ids) - set(audited_ids))
    extra = sorted(set(audited_ids) - set(expected_ids))
    dupes = sorted(pid for pid, first in seen.items() if sum(1 for r in per_sku if r["id"] == pid) > 1)
    if missing:
        errors.append({"scope": "sku-set", "issues": ["missing from audit: " + ", ".join(missing)]})
    if extra:
        errors.append({"scope": "sku-set", "issues": ["extra beyond domestic 21: " + ", ".join(extra)]})
    result = {
        "checkedDateKst": "2026-10-23",
        "historyFiles": [h.name for h in HISTORIES],
        "expectedSkuCount": len(expected_ids),
        "auditedSkuCount": len(audited_ids),
        "skuSetEqualsDomestic21": (not missing and not extra and len(audited_ids) == 21),
        "missing": missing,
        "extra": extra,
        "duplicateIds": dupes,
        "totals": {
            "weeklyExact": tot_w_exact,
            "weeklyTotal": tot_w,
            "monthlyExact": tot_m_exact,
            "monthlyTotal": tot_m,
        },
        "perSku": per_sku,
        "errors": errors,
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("audited skus: " + str(len(audited_ids)) + " / expected " + str(len(expected_ids)))
    print("weekly exact: " + str(tot_w_exact) + " / " + str(tot_w))
    print("monthly exact: " + str(tot_m_exact) + " / " + str(tot_m))
    print("sha mismatches: " + str(sum(1 for r in per_sku if r.get("shaMatch") is False)))
    print("period-key violations: " + str(sum(1 for r in per_sku if r.get("periodKeys") != ["1", "3", "6", "12", "24"])))
    print("tuesday7day failures: " + str(sum(1 for r in per_sku if r.get("tuesday7day") is False)))
    print("oct-partial failures: " + str(sum(1 for r in per_sku if r.get("octPartialOk") is False)))
    print("error entries: " + str(len(errors)))
    for entry in errors:
        print(json.dumps(entry, ensure_ascii=False))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
