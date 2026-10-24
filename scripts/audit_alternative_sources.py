"""Audit saved price/quote files. No network requests or interpolation."""

import argparse
import ast
from collections import Counter
import csv
from datetime import date, datetime, timedelta, timezone
import hashlib
import html
import json
from pathlib import Path
import re
from statistics import median


BOOM_START, BOOM_END = date(2020, 1, 1), date(2022, 12, 31)


def html_tables(path):
    tables = []
    for table in re.findall(r"<table\b[^>]*>.*?</table>", path.read_text(), re.S | re.I):
        rows = []
        for row in re.findall(r"<tr\b[^>]*>(.*?)</tr>", table, re.S | re.I):
            cells = re.findall(r"<t[dh]\b[^>]*>(.*?)</t[dh]>", row, re.S | re.I)
            rows.append([" ".join(html.unescape(re.sub(r"<[^>]+>", "", c)).split()) for c in cells])
        tables.append(rows)
    return tables


def german_date(value, default_year):
    months = {"Januar": 1, "Februar": 2, "März": 3, "April": 4, "Mai": 5,
              "Juni": 6, "Juli": 7, "August": 8, "September": 9, "Oktober": 10,
              "November": 11, "Dezember": 12}
    match = re.fullmatch(r"(\d+)\. ([A-Za-zä]+)(?: (\d{4}))?", value)
    assert match, value
    return date(int(match[3] or default_year), months[match[2]], int(match[1]))


def extract_3dcenter(base):
    raw = base / "raw"
    history_url = "https://www.3dcenter.org/news/hardware-und-nachrichten-links-des-1112-dezember-2021"
    index_url = "https://www.3dcenter.org/news/news-des-1011-september-2022"
    history_table = next(t for t in html_tables(raw / "3dcenter_2021_12_12.html")
                         if t[0] == ["", "6700XT", "6800", "6800XT", "6900XT", "3060", "3070", "3080", "3090"])
    ranges = []
    history_dates = []
    for row in history_table[2:]:
        if len(row) != 9:
            continue
        d = german_date(row[0], 2021)
        history_dates.append(d)
        for gpu, cell in zip(history_table[0][1:], row[1:]):
            if cell == "-":
                low, high = None, None
            else:
                match = re.fullmatch(r"(\d+)(?:-(\d+))?€", cell)
                assert match, cell
                low, high = int(match[1]), int(match[2] or match[1])
                assert 0 < low <= high
            ranges.append({"date": d.isoformat(), "gpu": gpu,
                           "minimum_eur": low, "maximum_eur": high, "source_url": history_url})
    index_table = next(t for t in html_tables(raw / "3dcenter_2022_09_11.html")
                       if t[0][0] == "US-MSRP vs Straßenpreis")
    indices = []
    index_dates = []
    for row in index_table[1:]:
        if len(row) != 7:
            continue
        d = german_date(row[0], 2022)
        index_dates.append(d)
        for label, position in (("AMD RX 6000", 1), ("NVIDIA RTX 30", 3), ("Core portfolio", 5)):
            assert re.fullmatch(r"\d+%", row[position])
            indices.append({"date": d.isoformat(), "series": label,
                            "percent_of_us_msrp": int(row[position][:-1]), "source_url": index_url})
    assert len(history_dates) == len(set(history_dates)) == 20
    assert len(index_dates) == len(set(index_dates)) == 14
    output = {"product_quote_ranges_eur": ranges, "price_indices_percent_of_msrp": indices}
    (base / "3dcenter_extracted.json").write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
    return {"product_ranges": {**date_stats(history_dates), "gpu_series": 8, "rows": len(ranges),
                               "dated_snapshots": len(history_dates),
                               "valid_price_ranges": sum(r["minimum_eur"] is not None for r in ranges),
                               "selected_series_quotes": {gpu: sum(r["gpu"] == gpu and r["minimum_eur"] is not None for r in ranges)
                                                          for gpu in ("3070", "3080", "3090")},
                               "source_url": history_url},
            "indices": {**date_stats(index_dates), "series": 3, "rows": len(indices),
                        "dated_snapshots": len(index_dates), "source_url": index_url},
            "cautions": ["Irregular snapshots, not daily or complete weekly data.",
                         "2021 data are best/worst available dealer quotes, not sale averages or exact AIB SKUs.",
                         "2022 indices are percentages of converted US MSRP including 19% VAT, not prices in euros.",
                         "Portfolio composition and methodology change over time; do not join ranges and indices as one price series."]}


def week(d):
    return d.isocalendar()[:2]


def date_stats(dates):
    unique = sorted(set(dates))
    gaps = [(b - a).days for a, b in zip(unique, unique[1:])]
    boom = [d for d in unique if BOOM_START <= d <= BOOM_END]
    weeks = Counter(week(d) for d in boom)
    boom_gaps = [(b - a).days for a, b in zip(boom, boom[1:])]
    week_starts = {date.fromisocalendar(y, w, 1) for y, w in weeks}
    return {"first_date": unique[0].isoformat(), "last_date": unique[-1].isoformat(),
            "rows": len(dates), "unique_dates": len(unique),
            "duplicate_dates": len(dates) - len(unique),
            "median_gap_days": median(gaps) if gaps else None,
            "max_gap_days": max(gaps) if gaps else None,
            "2020_2022_unique_dates": len(boom),
            "2020_2022_dates_by_year": {str(y): sum(d.year == y for d in boom)
                                       for y in (2020, 2021, 2022)},
            "2020_2022_max_gap_days": max(boom_gaps) if boom_gaps else None,
            "2020_2022_weeks_with_any_quote": len(weeks),
            "2020_2022_adjacent_week_pairs_with_quotes": sum(
                d - timedelta(days=7) in week_starts for d in week_starts),
            "2020_2022_weeks_with_at_least_3_quote_days": sum(n >= 3 for n in weeks.values())}


def audit(base):
    raw = base / "raw"
    requests = json.loads((base / "requests.json").read_text())
    result = {"checked_date_kst": "2026-10-21", "pricehistory_products": [], "stocks": []}
    price_weeks = {}
    records = requests["pricehistory_products"]
    extra_requests = base / "extra_gpu_requests.json"
    if extra_requests.exists():
        records += json.loads(extra_requests.read_text())
    for record in records:
        source = json.loads((raw / record["raw_file"]).read_text())
        rows = source["History"]["Price"]
        assert rows and all(isinstance(r["y"], (int, float)) and r["y"] > 0 for r in rows)
        dates = [datetime.fromisoformat(r["x"]).date() for r in rows]
        assert dates == sorted(dates)
        assert len(dates) == len(set(dates))
        low = min(rows, key=lambda r: r["y"])
        high = max(rows, key=lambda r: r["y"])
        result["pricehistory_products"].append({
            **{k: record[k] for k in ("category", "name", "asin", "store", "currency", "product_url", "raw_file")},
            **date_stats(dates), "minimum_quote": low, "maximum_quote": high,
            "source_updated_on": record["source_updated_on"],
            "cautions": ["Irregular quote dates, not a complete daily record or confirmed transactions.",
                         "Seller, condition, timezone and shipping/tax basis are not established by this history array.",
                         "Extreme values and price-series continuity require cross-checking."]})
        price_weeks[record["category"]] = {week(d) for d in dates if BOOM_START <= d <= BOOM_END}
    for record in requests["stocks"]:
        path = Path(record["file"])
        if record["symbol"].isdigit():
            source = ast.literal_eval(path.read_text().strip())
            rows = [r for r in source[1:] if isinstance(r, list) and r and str(r[0]).isdigit()]
            dates = [datetime.strptime(r[0], "%Y%m%d").date() for r in rows]
            assert all(isinstance(r[4], (float, int)) and r[4] > 0 for r in rows)
            adjustment = "Close present; corporate-action adjustment basis not verified."
            valid_close, valid_adjclose = len(rows), None
        else:
            source = json.loads(path.read_text())
            assert source["chart"]["error"] is None
            series = source["chart"]["result"][0]
            dates = [datetime.fromtimestamp(t, timezone.utc).date() for t in series["timestamp"]]
            closes = series["indicators"]["quote"][0]["close"]
            adjusted = series["indicators"]["adjclose"][0]["adjclose"]
            assert len(dates) == len(closes) == len(adjusted)
            valid_close = sum(x is not None and x > 0 for x in closes)
            valid_adjclose = sum(x is not None and x > 0 for x in adjusted)
            adjustment = "close and adjclose fields both present; use adjusted series for return analysis."
        assert dates == sorted(dates) and len(dates) == len(set(dates))
        assert all(BOOM_START <= d <= BOOM_END for d in dates)
        result["stocks"].append({"symbol": record["symbol"], "url": record["url"],
                                 **date_stats(dates), "valid_close": valid_close,
                                 "valid_adjclose": valid_adjclose, "adjustment": adjustment,
                                 "weekly_overlap_with_pricehistory": {
                                     category: len({week(d) for d in dates} & weeks)
                                     for category, weeks in price_weeks.items()}})
    research_path = raw / "risyad_rtx3090_daily.csv"
    research = list(csv.DictReader(research_path.read_text(encoding="utf-8-sig").splitlines()))
    research_dates = [datetime.strptime(r["Date"], "%d/%m/%Y %H:%M").date() for r in research]
    assert all(float(r["Price"]) > 0 for r in research)
    assert research_dates == sorted(research_dates)
    assert len(set(research_dates)) == len(research_dates)
    result["research_rtx3090"] = {
        **date_stats(research_dates), "columns": list(research[0]),
        "source_url": "https://github.com/RisyadFaisalH/Forecasting-GPU-price/blob/main/dataset_fix.csv",
        "paper_url": "https://openlibrary.telkomuniversity.ac.id/pustaka/files/196238/jurnal_eproc/forecasting-of-gpu-prices-using-transformer-method.pdf",
        "currency": "USD (paper Table 1)",
        "cautions": ["Research dataset; paper discusses interpolation in preprocessing.",
                     "Do not equate all calendar rows with independently observed source quotes.",
                     "Future/Last/Difference are derived features, not independent data.",
                     "Use Date and Price only; original ASIN and price basis need confirmation."]}
    ebay_path = raw / "ebay_gpu_monthly.csv"
    ebay = list(csv.DictReader(ebay_path.read_text(encoding="utf-8-sig").splitlines()))
    missing_price_tokens = {"", "—", "-"}
    ebay_missing = [r for r in ebay if r["eBay Price"].strip() in missing_price_tokens]
    ebay_prices = [float(r["eBay Price"].replace("$", "").replace(",", ""))
                   for r in ebay if r["eBay Price"].strip() not in missing_price_tokens]
    invalid_quantity = [r for r in ebay if not re.fullmatch(r"[0-9,]+", r["QTY Sold"])]
    ebay_quantities = [int(r["QTY Sold"].replace(",", ""))
                       for r in ebay if re.fullmatch(r"[0-9,]+", r["QTY Sold"])]
    assert all(p > 0 for p in ebay_prices)
    assert all(q >= 0 for q in ebay_quantities)
    months = sorted({datetime.strptime(r["Month"], "%B %Y").date() for r in ebay})
    month_days = {d.isoformat() for d in months}
    missing_months = []
    current = months[0]
    while current <= months[-1]:
        if current.isoformat() not in month_days:
            missing_months.append(current.isoformat()[:7])
        current = (current.replace(day=28) + timedelta(days=4)).replace(day=1)
    keys = [(r["GPU"], r["Month"]) for r in ebay]
    result["ebay_monthly"] = {
        "rows": len(ebay), "gpu_names": len({r["GPU"] for r in ebay}),
        "first_month": months[0].isoformat()[:7], "last_month": months[-1].isoformat()[:7],
        "distinct_months": len(months), "missing_months_in_span": missing_months,
        "duplicate_gpu_month_keys": len(keys) - len(set(keys)),
        "columns": list(ebay[0]), "frequency": "monthly",
        "positive_price_rows": len(ebay_prices), "nonnegative_quantity_rows": len(ebay_quantities),
        "missing_price_rows": len(ebay_missing),
        "invalid_quantity_rows": invalid_quantity,
        "selected_series_rows": {sku: sum(r["GPU"] == sku for r in ebay)
                                 for sku in ("GeForce RTX 3090", "GeForce RTX 3080", "GeForce RTX 3070")},
        "source_url": "https://github.com/buttke/ebay-2021-2023-gpu-prices/blob/main/gpu_time_series.csv",
        "cautions": ["Month is a dataset label, not a verified underlying sales month.",
                     "Verified example: November 2023 RTX 3090 $704 / 765 sales matches Tom's October 2023 table.",
                     "Reconcile all monthly labels against original table headings before time-series alignment.",
                     "Monthly sold-listing aggregates; condition and seller composition are not constant."],
        "crosscheck_url": "https://www.tomshardware.com/news/gpus-historical-ebay-pricing"}
    if (raw / "3dcenter_2021_12_12.html").exists() and (raw / "3dcenter_2022_09_11.html").exists():
        result["3dcenter"] = extract_3dcenter(base)
    result["raw_file_sha256"] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                for p in sorted(raw.iterdir()) if p.is_file()}
    (base / "validation.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    print(json.dumps(audit(parser.parse_args().snapshot), ensure_ascii=False, indent=2))
