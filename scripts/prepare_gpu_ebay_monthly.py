"""Build auditable Toms Hardware eBay monthly GPU prices (offline, stdlib only).

Reads saved HTML under data/verification/2026-10-22/gpu_ebay and extracts
monthly avg eBay price + QTY Sold for RTX 3070 / RTX 3080-10GB / RTX 3090.
No network. No modification of raw inputs. No estimated 1-month shift.
"""
import argparse
import csv
import hashlib
import json
import math
import re
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGETS = ["RTX 3070", "RTX 3080_10GB", "RTX 3090"]
CANON_LABEL = {"RTX 3070": "GeForce RTX 3070", "RTX 3080_10GB": "GeForce RTX 3080", "RTX 3090": "GeForce RTX 3090"}
# page -> (sale_month YYYY-MM, sale_label, period_type)
PAGE_MAP = {
    11: ("2022-12", "December 2022", "monthly"),
    12: ("2022-11", "November 2022", "monthly"),
    13: ("2022-10", "October 2022", "monthly"),
    14: ("2022-09", "September 2022", "monthly_merge_mixed"),
    15: ("2022-08", "August 2022", "monthly"),
    16: ("2022-07", "July 2022", "monthly"),
    17: ("2022-06", "June 2022", "monthly"),
    18: ("2022-05", "May 2022", "monthly"),
    19: ("2022-04", "April 2022", "monthly"),
    20: ("2022-03", "March 2022", "monthly"),
    21: ("2022-02", "February 2022", "monthly"),
    22: ("2022-01", "January 2022", "monthly"),
    23: ("2022-12", "December 2021", "monthly"),
}
PAGE_MAP2 = {
    23: ("2021-12", "December 2021", "monthly"),
    24: ("2021-11", "November 2021", "monthly"),
    25: ("2021-10", "October 2021", "monthly"),
}
PAGE_MAP.update(PAGE_MAP2)
# p26 handled separately: table0=partial Oct01-15, table1/2=Sep2021 monthly
P26_PARTIAL = ("2021-10-partial", "October 1-15, 2021", "partial_half_month")
P26_MONTHLY = ("2021-09", "September 2021", "monthly")
MONTHS_36 = [f"{y:04d}-{m:02d}" for y in (2020, 2021, 2022) for m in range(1, 13)]
IMAGE_ONLY_MONTHS = {"2020-12", "2021-01", "2021-02", "2021-03"}
class TableParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables = []
        self._cur_table = None
        self._cur_row = None
        self._cur_cell = None
        self._in_thtd = False
    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self._cur_table = {"headers": [], "rows": [], "header_done": False}
        elif tag == "tr" and self._cur_table is not None:
            self._cur_row = {"header_cells": [], "cells": [], "is_header": False}
        elif tag in ("th", "td") and self._cur_row is not None:
            self._in_thtd = True
            self._cur_cell = {"tag": tag, "text": ""}
            if tag == "th":
                self._cur_row["is_header"] = True
    def handle_data(self, data):
        if self._in_thtd and self._cur_cell is not None:
            self._cur_cell["text"] += data
    def handle_endtag(self, tag):
        if tag in ("th", "td") and self._in_thtd:
            txt = " ".join(self._cur_cell["text"].split())
            if self._cur_cell["tag"] == "th":
                self._cur_row["header_cells"].append(txt)
            else:
                self._cur_row["cells"].append(txt)
            self._cur_cell = None
            self._in_thtd = False
        elif tag == "tr" and self._cur_table is not None and self._cur_row is not None:
            if self._cur_row["is_header"] and not self._cur_table["header_done"]:
                self._cur_table["headers"] = self._cur_row["header_cells"]
                self._cur_table["header_done"] = True
            elif self._cur_row["cells"]:
                self._cur_table["rows"].append(self._cur_row["cells"])
            self._cur_row = None
        elif tag == "table" and self._cur_table is not None:
            if self._cur_table["headers"] or self._cur_table["rows"]:
                self.tables.append(self._cur_table)
            self._cur_table = None

def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(65536), b""):
            h.update(b)
    return h.hexdigest()

def extract_title(html):
    m = re.search(r"<title>(.*?)</title>", html, re.S)
    if not m:
        return ""
    return re.sub(r"\\s+", " ", re.sub(r"<[^>]+>", "", m.group(1))).strip()
def parse_price(s):
    t = (s or "").strip()
    if not t or t in ("-", "--", "---", "N/A", "NA"):
        return None
    t = t.replace("$", "").replace(",", "").strip()
    if not t or not re.match(r"^[0-9]+(\\.[0-9]+)?$", t):
        return None
    try:
        return float(t) if "." in t else int(t)
    except ValueError:
        return None

def parse_qty(s):
    t = (s or "").strip().replace(",", "")
    if not re.match(r"^[0-9]+$", t):
        return None
    return int(t)

def match_gpu(cell):
    t = " " + cell.lower() + " "
    if "rtx 3090" in t:
        if " ti" in t:
            return None
        return "RTX 3090"
    if "rtx 3080" in t:
        if " ti" in t or "12gb" in t or "12 gb" in t:
            return None
        return "RTX 3080_10GB"
    if "rtx 3070" in t:
        if " ti" in t:
            return None
        return "RTX 3070"
    return None

def extract_page(html_path):
    html = html_path.read_text(encoding="utf-8", errors="replace")
    title = extract_title(html)
    parser = TableParser()
    parser.feed(html)
    return title, parser.tables

def find_price_qty_indexes(headers):
    pl = [h.lower() for h in headers]
    price_idx, qty_idx = None, None
    for i, h in enumerate(pl):
        if "ebay price" in h or "avg ebay" in h:
            if price_idx is None:
                price_idx = i
        if "qty sold" in h:
            if qty_idx is None:
                qty_idx = i
    if price_idx is None and len(headers) >= 2:
        price_idx = 1
    if qty_idx is None and len(headers) >= 3:
        qty_idx = 2
    return price_idx, qty_idx
def collect_observations(verify_dir):
    verify_dir = Path(verify_dir)
    observations = []
    audits = []
    partials = []
    for page in range(11, 27):
        html_path = verify_dir / f"tomshardware_p{page}.html"
        if not html_path.exists():
            audits.append({"source_page": page, "status": "missing_html"})
            continue
        sha = sha256_of(html_path)
        title, tables = extract_page(html_path)
        url = f"https://www.tomshardware.com/news/gpus-historical-ebay-pricing/{page}"
        if page != 26:
            exp_month, exp_label, exp_type = PAGE_MAP[page]
            if exp_label.lower() not in title.lower():
                audits.append({"source_page": page, "source_title": title, "status": "title_mismatch_no_shift"})
                continue
            for ti, tb in enumerate(tables):
                headers = tb["headers"]
                pi, qi = find_price_qty_indexes(headers)
                hits = 0
                is_monthly = any("ebay price" in h.lower() or "avg ebay" in h.lower() for h in headers)
                for row in tb["rows"]:
                    if not row:
                        continue
                    gpu = match_gpu(row[0])
                    if not gpu:
                        continue
                    if max(pi or 0, qi or 0) >= len(row):
                        continue
                    price = parse_price(row[pi]) if pi is not None else None
                    qty = parse_qty(row[qi]) if qi is not None else None
                    if price is None and qty is None:
                        continue
                    hits += 1
                    observations.append({"gpu_model": gpu, "gpu_label_source": row[0][:80], "sale_month": exp_month, "sale_period_label": exp_label, "sale_period_type": exp_type, "source_page": page, "source_url": url, "source_title": title, "source_sha256": sha, "table_index": ti, "table_header_price": headers[pi] if pi is not None and pi < len(headers) else "", "table_header_qty": headers[qi] if qi is not None and qi < len(headers) else "", "ebay_avg_price_usd": price, "qty_sold": qty, "is_monthly_table": is_monthly})
                audits.append({"source_page": page, "table_index": ti, "source_title": title, "price_header": headers[pi] if pi is not None and pi < len(headers) else "", "qty_header": headers[qi] if qi is not None and qi < len(headers) else "", "n_rows": len(tb["rows"]), "n_target_hits": hits, "sale_month_inferred": exp_month, "sale_period_type": exp_type, "is_monthly_table": is_monthly, "source_sha256": sha, "source_url": url})
        else:
            for ti, tb in enumerate(tables):
                headers = tb["headers"]
                pi, qi = find_price_qty_indexes(headers)
                if ti == 0:
                    sm, sl, st = P26_PARTIAL
                else:
                    sm, sl, st = P26_MONTHLY
                hits = 0
                for row in tb["rows"]:
                    if not row:
                        continue
                    gpu = match_gpu(row[0])
                    if not gpu:
                        continue
                    if max(pi or 0, qi or 0) >= len(row):
                        continue
                    price = parse_price(row[pi]) if pi is not None else None
                    qty = parse_qty(row[qi]) if qi is not None else None
                    if price is None and qty is None:
                        continue
                    hits += 1
                    rec = {"gpu_model": gpu, "gpu_label_source": row[0][:80], "sale_month": sm, "sale_period_label": sl, "sale_period_type": st, "source_page": page, "source_url": url, "source_title": title, "source_sha256": sha, "table_index": ti, "table_header_price": headers[pi] if pi is not None and pi < len(headers) else "", "table_header_qty": headers[qi] if qi is not None and qi < len(headers) else "", "ebay_avg_price_usd": price, "qty_sold": qty, "is_monthly_table": (ti != 0)}
                    if ti == 0:
                        partials.append(rec)
                    else:
                        observations.append(rec)
                audits.append({"source_page": page, "table_index": ti, "source_title": title, "price_header": headers[pi] if pi is not None and pi < len(headers) else "", "qty_header": headers[qi] if qi is not None and qi < len(headers) else "", "n_rows": len(tb["rows"]), "n_target_hits": hits, "sale_month_inferred": sm, "sale_period_type": st, "is_monthly_table": (ti != 0), "source_sha256": sha, "source_url": url})
    return observations, audits, partials
MERGE_NOTE = "2022-09 merge-mixed month (merge before/after mixed); monthly total is normal, exclude only from Jul-Aug vs Oct-Nov event comparison"
def build_grid(observations):
    obs_by_key = {}
    for o in observations:
        if o["sale_period_type"] not in ("monthly", "monthly_merge_mixed"):
            continue
        obs_by_key[(o["gpu_model"], o["sale_month"])] = o
    grid = []
    for gpu in TARGETS:
        for m in MONTHS_36:
            o = obs_by_key.get((gpu, m))
            if o:
                price, qty = o["ebay_avg_price_usd"], o["qty_sold"]
                is_mix = 1 if o["sale_period_type"] == "monthly_merge_mixed" else 0
                grid.append({"gpu_model": gpu, "gpu_label_source": o["gpu_label_source"], "month": m, "sale_period_label": o["sale_period_label"], "sale_period_type": o["sale_period_type"], "source_page": o["source_page"], "source_url": o["source_url"], "source_title": o["source_title"][:160], "source_sha256": o["source_sha256"], "table_index": o["table_index"], "table_header_price": o["table_header_price"], "table_header_qty": o["table_header_qty"], "ebay_avg_price_usd": price if price is not None else "", "qty_sold": qty if qty is not None else "", "price_missing_reason": "" if price is not None else "not_extracted", "qty_missing_reason": "" if qty is not None else "not_extracted", "is_merge_mixed_flag": is_mix, "merge_note": MERGE_NOTE if is_mix else "", "exclude_from_event_compare": is_mix})
            else:
                if m in IMAGE_ONLY_MONTHS:
                    reason = "image_chart_only_Dec2020_Mar2021_no_numeric_table"
                elif m < "2021-09":
                    reason = "out_of_scope_before_Sep2021"
                else:
                    reason = "no_monthly_table_for_sale_month"
                grid.append({"gpu_model": gpu, "gpu_label_source": CANON_LABEL[gpu], "month": m, "sale_period_label": "", "sale_period_type": "no_data", "source_page": "", "source_url": "", "source_title": "", "source_sha256": "", "table_index": "", "table_header_price": "", "table_header_qty": "", "ebay_avg_price_usd": "", "qty_sold": "", "price_missing_reason": reason, "qty_missing_reason": reason, "is_merge_mixed_flag": 0, "merge_note": "", "exclude_from_event_compare": 1 if m == "2022-09" else 0})
    by_gpu = {}
    for r in grid:
        by_gpu.setdefault(r["gpu_model"], []).append(r)
    for gpu, rows in by_gpu.items():
        rows.sort(key=lambda x: x["month"])
        for i, r in enumerate(rows):
            if i == 0:
                r["log_return_price"] = ""
                r["return_missing_reason"] = "first_month_no_previous"
                continue
            prev = rows[i - 1]
            try:
                p0 = float(prev["ebay_avg_price_usd"]) if prev["ebay_avg_price_usd"] != "" else None
            except ValueError:
                p0 = None
            try:
                p1 = float(r["ebay_avg_price_usd"]) if r["ebay_avg_price_usd"] != "" else None
            except ValueError:
                p1 = None
            if p0 and p1 and p0 > 0 and p1 > 0 and prev["sale_period_type"] in ("monthly", "monthly_merge_mixed") and r["sale_period_type"] in ("monthly", "monthly_merge_mixed"):
                r["log_return_price"] = math.log(p1 / p0)
                r["return_missing_reason"] = ""
            else:
                r["log_return_price"] = ""
                if r["ebay_avg_price_usd"] == "" or prev["ebay_avg_price_usd"] == "":
                    r["return_missing_reason"] = "current_or_previous_missing"
                else:
                    r["return_missing_reason"] = "non_monthly_period_involved"
    return grid
def write_csv(path, rows, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify-dir", default=str(ROOT / "data/verification/2026-10-22/gpu_ebay"))
    ap.add_argument("--processed-dir", default=str(ROOT / "data/processed/2026-10-22/gpu_ebay"))
    ap.add_argument("--existing-csv", default=str(ROOT / "data/feasibility/2026-10-21/alternatives/raw/ebay_gpu_monthly.csv"))
    a = ap.parse_args()
    vdir, pdir = Path(a.verify_dir), Path(a.processed_dir)
    pdir.mkdir(parents=True, exist_ok=True)
    observations, audits, partials = collect_observations(vdir)
    seen, uniq = set(), []
    for o in observations:
        k = (o["gpu_model"], o["sale_month"])
        if k in seen:
            continue
        seen.add(k)
        uniq.append(o)
    observations = sorted(uniq, key=lambda x: (x["gpu_model"], x["sale_month"]))
    grid = build_grid(observations)
    obs_fields = ["gpu_model", "gpu_label_source", "sale_month", "sale_period_label", "sale_period_type", "source_page", "source_url", "source_title", "source_sha256", "table_index", "table_header_price", "table_header_qty", "ebay_avg_price_usd", "qty_sold", "is_monthly_table"]
    grid_fields = ["gpu_model", "gpu_label_source", "month", "sale_period_label", "sale_period_type", "source_page", "source_url", "source_title", "source_sha256", "table_index", "table_header_price", "table_header_qty", "ebay_avg_price_usd", "qty_sold", "price_missing_reason", "qty_missing_reason", "is_merge_mixed_flag", "merge_note", "exclude_from_event_compare", "log_return_price", "return_missing_reason"]
    write_csv(pdir / "monthly_observations.csv", observations, obs_fields)
    write_csv(pdir / "monthly_grid_2020_2022.csv", grid, grid_fields)
    write_csv(pdir / "audit_tables.csv", audits, ["source_page", "table_index", "source_title", "price_header", "qty_header", "n_rows", "n_target_hits", "sale_month_inferred", "sale_period_type", "is_monthly_table", "source_sha256", "source_url", "status", "note"])
    if partials:
        write_csv(pdir / "partial_oct01_15_2021.csv", partials, obs_fields)
    xrows = []
    try:
        with open(a.existing_csv, encoding="utf-8-sig") as f:
            existing = list(csv.DictReader(f))
    except FileNotFoundError:
        existing = []
    def norm_gpu(s):
        s = (s or "").lower()
        if "3090" in s and " ti" not in s:
            return "RTX 3090"
        if "3080" in s and " ti" not in s and "12gb" not in s and "12 gb" not in s:
            return "RTX 3080_10GB"
        if "3070" in s and " ti" not in s:
            return "RTX 3070"
        return None
    for o in observations:
        for e in existing:
            if norm_gpu(e.get("GPU", "")) != o["gpu_model"]:
                continue
            if parse_price(e.get("eBay Price", "")) == o["ebay_avg_price_usd"]:
                try:
                    eq = int(str(e.get("QTY Sold", "")).replace(",", ""))
                except ValueError:
                    eq = None
                xrows.append({"gpu_model": o["gpu_model"], "sale_month": o["sale_month"], "sale_period_label": o["sale_period_label"], "observed_price": o["ebay_avg_price_usd"], "observed_qty": o["qty_sold"], "existing_month_label": e.get("Month", ""), "existing_price": e.get("eBay Price", ""), "existing_qty": e.get("QTY Sold", ""), "qty_match": (eq == o["qty_sold"]), "label_match": (e.get("Month", "") == o["sale_period_label"]), "source_page": o["source_page"]})
                break
    write_csv(pdir / "crosscheck_existing_csv.csv", xrows, ["gpu_model", "sale_month", "sale_period_label", "observed_price", "observed_qty", "existing_month_label", "existing_price", "existing_qty", "qty_match", "label_match", "source_page"])
    manifest = []
    for page in range(11, 27):
        hp = vdir / f"tomshardware_p{page}.html"
        if hp.exists():
            manifest.append({"source_page": page, "file": hp.name, "source_url": f"https://www.tomshardware.com/news/gpus-historical-ebay-pricing/{page}", "sha256": sha256_of(hp), "bytes": hp.stat().st_size})
    (vdir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    monthly_n = sum(1 for g in grid if g["ebay_avg_price_usd"] != "")
    logret_n = sum(1 for g in grid if g["log_return_price"] != "")
    summary = {"n_observations_monthly": len(observations), "n_grid_rows": len(grid), "n_grid_with_price": monthly_n, "n_log_returns": logret_n, "n_partials_oct01_15": len(partials), "n_audit_tables": len(audits), "n_crosscheck_hits": len(xrows), "expectation": "16 months x 3 GPUs = 48 monthly obs (Sep2022 is monthly_merge_mixed with normal monthly total; Oct01-15 partial excluded from grid)", "sources": manifest}
    (pdir / "quality_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (pdir / "sources.json").write_text(json.dumps({"verification_dir": str(vdir), "manifest": manifest, "existing_csv": str(a.existing_csv)}, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))

if __name__ == "__main__":
    main()
