"""Validate saved chart responses and compare surfaces without network requests."""

import argparse
from datetime import datetime
import json

from probe_price_history import PERIODS, PRODUCTS


def indexed(rows, months, desktop=False):
    values = {}
    for row in rows:
        label = row.get("Fulldate", row["date"]) if desktop else row["date"]
        label = label.replace(".", "-")
        if months == 3:
            label = label[-5:]
        if months == 3:
            # A leap year validates yearless month/day labels without inventing a data year.
            datetime.strptime(f"2000-{label}", "%Y-%m-%d")
        else:
            datetime.strptime(label, "%y-%m-%d" if months == 1 else "%y-%m")
        assert label not in values, f"Duplicate date: {label}"
        price = row["minPrice"]
        assert isinstance(price, (int, float)) and price > 0, row
        values[label] = price
    return values


def audit(base):
    mobile_summary = json.loads((base / "summary.json").read_text())
    desktop_summary = json.loads((base / "desktop/summary.json").read_text())
    mobile_products = {p["product_code"]: p for p in mobile_summary["products"]}
    desktop_products = {p["product_code"]: p for p in desktop_summary["products"]}
    comparison = []
    monthly_total = weekly_total = desktop_monthly_total = 0
    for category, code, name in PRODUCTS:
        mobile = mobile_products[code]
        desktop = desktop_products[code]
        assert desktop["http_status"] == "200" and desktop["curl_exit_code"] == 0
        desktop_raw = json.loads((base / "desktop/raw" / f"{code}.json").read_text())
        mobile_periods = {p["period_months"]: p for p in mobile["periods"]}
        desktop_periods = {p["period_months"]: p for p in desktop["periods"]}
        item = {"code": code, "category": category, "name": name,
                "mobile_24": mobile_periods[24], "desktop_24": desktop_periods[24],
                "comparison": []}
        mobile_values = {}
        for months in PERIODS:
            record = mobile_periods[months]
            assert record["http_status"] == "200" and record["curl_exit_code"] == 0
            mobile_raw = json.loads((base / record["raw_file"]).read_text())
            m = indexed(mobile_raw["graphDataList"], months)
            d = indexed(desktop_raw[str(months)]["result"], months, desktop=True)
            mobile_values[months] = m
            assert len(m) == record["actual_rows"] == record["unique_date_labels"]
            assert len(d) == desktop_periods[months]["actual_rows"] == desktop_raw[str(months)]["count"]
            overlap = sorted(m.keys() & d.keys())
            differences = [{"date": label, "mobile": m[label], "desktop": d[label]}
                           for label in overlap if m[label] != d[label]]
            if months in (1, 3):
                assert len(overlap) == len(m) == len(d) and not differences
            item["comparison"].append({
                "period_months": months, "mobile_rows": len(m), "desktop_rows": len(d),
                "overlap_labels": len(overlap), "different_prices": len(differences),
                "difference_examples": differences,
            })
        # Short mobile ranges repeat observations already in the longer range.
        assert all(mobile_values[3][label[-5:]] == price
                   for label, price in mobile_values[1].items())
        for months in (6, 12):
            assert all(mobile_values[24][label] == price
                       for label, price in mobile_values[months].items())
        monthly_total += len(mobile_values[24])
        weekly_total += len(mobile_values[3])
        desktop_monthly_total += desktop_periods[24]["actual_rows"]
        comparison.append(item)
    (base / "cross_surface_comparison.json").write_text(
        json.dumps(comparison, ensure_ascii=False, indent=2) + "\n")
    result = {
        "checked_date_kst": mobile_summary["checked_date_kst"],
        "products": len(PRODUCTS), "mobile_raw_responses": 40, "desktop_raw_responses": 8,
        "mobile_product_month_rows": monthly_total,
        "desktop_product_month_rows": desktop_monthly_total,
        "mobile_product_week_rows": weekly_total,
        "checks": ["All saved requests report HTTP 200 and curl exit code 0.",
                   "All dates parse, labels are unique within each response, and prices are positive.",
                   "Summary counts match raw rows; desktop source counts match raw rows.",
                   "Weekly price values match between mobile and desktop for all products.",
                   "Mobile shorter periods duplicate observations in longer periods.",
                   "Monthly values can differ between surfaces; see comparison file."],
        "cautions": ["Monthly aggregation semantics are unconfirmed.",
                     "The current month is incomplete.",
                     "Product-month rows are not observations of a single series.",
                     "The mobile source_totalCount field is not the returned row count."]
    }
    (base / "validation.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return result


if __name__ == "__main__":
    from pathlib import Path
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    print(json.dumps(audit(parser.parse_args().snapshot), ensure_ascii=False, indent=2))
