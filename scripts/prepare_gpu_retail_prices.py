"""Extract genuine 3DCenter GPU observations; never expand quotes by filling gaps."""
import hashlib
import json
from pathlib import Path
import re

import numpy as np
import pandas as pd

from audit_alternative_sources import german_date, html_tables
from analyze_price_stock_correlations import consecutive_returns, export_csv

ROOT = Path(__file__).resolve().parents[1]
OLD = ROOT / "data/feasibility/2026-10-21/alternatives/raw"
NEW = ROOT / "data/verification/2026-10-22/gpu"
OUT = ROOT / "data/processed/2026-10-22/gpu_retail"
URL_2021 = "https://www.3dcenter.org/news/hardware-und-nachrichten-links-des-1112-dezember-2021"
URL_2022 = "https://www.3dcenter.org/news/news-des-1011-september-2022"
GPUS = {"3070": "RTX 3070", "3080": "RTX 3080 10GB", "3090": "RTX 3090"}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def euro_range(cell):
    match = re.fullmatch(r"(\d+)(?:-(\d+))?€", cell)
    if not match:
        return None
    low, high = int(match[1]), int(match[2] or match[1])
    if not 0 < low <= high:
        raise ValueError(cell)
    return low, high


def extract_current(path):
    """Keep exact model identities; exclude Ti, 12GB and LHR-specific substitutions."""
    tables = html_tables(path)
    # Jan-May 2022: columns are GPU families, rows are retailers.
    old = [t for t in tables if t and "3070" in t[0] and "3090" in t[0]]
    if old:
        assert len(old) == 1
        table = old[0]
        output = {}
        for gpu in GPUS:
            names = (gpu, "3080-10GB") if gpu == "3080" else (gpu,)
            position = next(i for i, c in enumerate(table[0]) if c in names)
            cells = [euro_range(row[position]) for row in table[1:] if len(row) == len(table[0])
                     and row[0] not in ("Listenpreis", "Mehrpreis", "Veränderung", "Verfügbarkeit")]
            # Ignore list-price and percentage cells (no euro-range match for USD).
            # January's Listenpreis is in EUR, hence explicitly excluded above.
            valid = [v for v in cells if v is not None]
            if not valid:
                raise ValueError(f"No in-stock price: {path.name} {gpu}")
            output[gpu] = (min(v[0] for v in valid), max(v[1] for v in valid), "minimum_available_retailer_quote")
        return output
    # May-Sep 2022: GPU rows, explicit 'bester Preis' column.
    table = next(t for t in tables if t and "bester Preis" in t[0] and "Geizhals" in t[0]
                 and any(r and r[0] == "GeForce RTX 3070" for r in t))
    output = {}
    for gpu in GPUS:
        names = ("GeForce RTX 3080", "GeForce RTX 3080 10GB") if gpu == "3080" else (f"GeForce RTX {gpu}",)
        row = next(r for r in table if r and r[0] in names)
        match = re.match(r"ab (\d+)€", row[table[0].index("bester Preis")])
        if not match:
            raise ValueError(f"Unrecognized best price: {row}")
        output[gpu] = (int(match[1]), np.nan, "explicit_best_available_retailer_quote")
    return output


def build(output_dir=OUT):
    output_dir.mkdir(parents=True, exist_ok=True)
    observations, inputs = [], {}

    def add(date, identity, value, upper, kind, source, url, basis):
        inputs[str(source.relative_to(ROOT))] = digest(source)
        observations.append({"series_id": identity, "series_label": GPUS.get(identity, identity),
            "kind": kind, "observation_date": date, "value": value, "upper_value": upper,
            "unit": "EUR" if kind == "retail_quote" else "percent_of_converted_us_msrp_including_19pct_vat",
            "observation_status": "observed" if pd.notna(value) else "no_available_quote_in_source",
            "source_basis": basis, "source_url": url, "source_file": str(source.relative_to(ROOT)),
            "source_sha256": digest(source)})

    source = OLD / "3dcenter_2021_12_12.html"
    table = next(t for t in html_tables(source)
                 if t[0] == ["", "6700XT", "6800", "6800XT", "6900XT", "3060", "3070", "3080", "3090"])
    for row in table[2:]:
        if len(row) != 9:
            continue
        date = german_date(row[0], 2021).isoformat()
        for gpu in GPUS:
            pair = euro_range(row[table[0].index(gpu)])
            if pair is None and row[table[0].index(gpu)] != "-":
                raise ValueError(row)
            low, high = pair if pair else (np.nan, np.nan)
            add(date, gpu, low, high, "retail_quote", source, URL_2021, "historical_available_quote_range_minimum")

    manifest_path = NEW / "retail_requests.json"
    manifest = json.loads(manifest_path.read_text())
    requests = manifest["requests"] + [{"date": "2022-09-11", "status": "ok", "url": URL_2022,
        "file": str((OLD / "3dcenter_2022_09_11.html").relative_to(ROOT)),
        "sha256": digest(OLD / "3dcenter_2022_09_11.html")}]
    for request in requests:
        if request["status"] != "ok":
            raise ValueError(f"GPU source not verified: {request}")
        source = ROOT / request["file"]
        if digest(source) != request["sha256"]:
            raise ValueError(f"Source hash changed: {source}")
        for gpu, (low, high, basis) in extract_current(source).items():
            add(request["date"], gpu, low, high, "retail_quote", source, request["url"], basis)

    source = OLD / "3dcenter_2022_09_11.html"
    table = next(t for t in html_tables(source) if t[0][0] == "US-MSRP vs Straßenpreis")
    for row in table[1:]:
        if len(row) != 7:
            continue
        date = german_date(row[0], 2022).isoformat()
        for identity, pos in (("AMD RX 6000", 1), ("NVIDIA RTX 30", 3), ("Core portfolio", 5)):
            assert re.fullmatch(r"\d+%", row[pos]), row
            add(date, identity, int(row[pos][:-1]), np.nan, "msrp_index", source, URL_2022,
                "portfolio_index_fx_vat_composition_sensitive")

    frame = pd.DataFrame(observations).sort_values(["series_id", "observation_date"])
    if frame.duplicated(["series_id", "observation_date"]).any():
        raise ValueError("Duplicate observations")
    dates = pd.to_datetime(frame.observation_date)
    frame["week_end"] = (dates + pd.to_timedelta((4 - dates.dt.dayofweek) % 7, unit="D")).dt.strftime("%Y-%m-%d")
    export_csv(output_dir / "observations.csv", frame)
    weeks = pd.date_range("2020-01-10", "2022-12-30", freq="W-FRI").strftime("%Y-%m-%d")
    weekly, coverage = [], []
    for identity, group in frame.groupby("series_id", sort=False):
        selected = []
        for _, within_week in group.groupby("week_end", sort=True):
            valid_quotes = within_week[within_week.value.notna()]
            selected.append((valid_quotes if not valid_quotes.empty else within_week).iloc[-1])
        w = pd.DataFrame(selected).set_index("week_end").reindex(weeks)
        values = w.value.to_numpy(dtype=float)
        returns = consecutive_returns(values)
        for i, week_end in enumerate(weeks):
            weekly.append({"series_id": identity, "kind": group.iloc[0].kind, "week_end": week_end,
                "value": values[i], "weekly_return_log": returns[i],
                "observation_date": w.iloc[i].observation_date,
                "observation_status": ("observed" if np.isfinite(values[i]) else
                    "source_no_quote" if pd.notna(w.iloc[i].observation_date) else "not_observed"),
                "unit": group.iloc[0].unit})
        valid = group[group.value.notna()]
        gaps = pd.to_datetime(valid.observation_date).diff().dt.days.dropna()
        coverage.append({"series_id": identity, "kind": group.iloc[0].kind, "total_calendar_weeks": len(weeks),
            "source_snapshot_dates": len(group), "valid_price_snapshots": len(valid),
            "source_no_quote": int(group.value.isna().sum()), "weeks_with_quote": int(np.isfinite(values).sum()),
            "weeks_without_quote": int((~np.isfinite(values)).sum()), "adjacent_week_returns": int(np.isfinite(returns).sum()),
            "first_observation": valid.observation_date.min(), "last_observation": valid.observation_date.max(),
            "median_observation_gap_days": gaps.median(), "max_observation_gap_days": gaps.max()})
    export_csv(output_dir / "weekly_retail.csv", weekly)
    export_csv(output_dir / "coverage.csv", coverage)
    export_csv(output_dir / "excluded_sources.csv", [
        {"source": "risyad_rtx3090_daily.csv", "reason": "Interpolation described by authors; genuine quote mask and price basis unverified", "used": False},
        {"source": "pricehistory_gpu_prices.json", "reason": "No 2020-2022 observations", "used": False},
        {"source": "pricehistory_gpu_india3070_prices.json", "reason": "Only 3 dates in 2020-2022; INR market differs", "used": False},
        {"source": "pricehistory_gpu_renewed3080_prices.json", "reason": "Only 3 dates in 2020-2022; renewed condition differs", "used": False},
        {"source": "toms_page38_90day_charts", "reason": "Dec2020-Mar2021 is plotted as images; underlying daily numerical observations not acquired", "used": False}])
    (output_dir / "sources.json").write_text(json.dumps({"input_sha256": inputs,
        "calendar": "Saturday-Friday; first week_end2020-01-10; 156 weeks",
        "rules": ["No forward fill or interpolation", "Only original quote dates count as observations",
            "If multiple observations share a week, choose the last valid quote; all original observations remain in observations.csv",
            "Retail EUR prices, MSRP indices and US eBay prices stay separate",
            "3080 Ti and 3080 12GB excluded; LHR/FHR mix unobserved",
            "Retailer/model/seller composition may change; quote upper bounds are not confidence intervals",
            "MSRP indices include FX, VAT and portfolio composition effects"]}, ensure_ascii=False, indent=2) + "\n")
    print(pd.DataFrame(coverage).to_string(index=False))


if __name__ == "__main__":
    build()
