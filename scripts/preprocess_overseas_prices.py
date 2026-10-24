"""Build auditable W-FRI quote datasets from saved public PriceHistory JSON.

Python >=3.10, standard library only; no network or modification of raw files.
"""

import argparse
from collections import Counter, defaultdict
import csv
from datetime import date, datetime, timedelta
import hashlib
import json
import math
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[1]
WEEK = timedelta(days=7)


def friday(day):
    """Saturday through Friday, with the actual Friday as the date key."""
    return day + timedelta(days=(4 - day.weekday()) % 7)


def previous_complete_friday(as_of):
    # A date alone does not prove that day's trading/observation has finished.
    return as_of - timedelta(days=(as_of.weekday() - 4) % 7 or 7)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_csv(path, rows, fields=None):
    fields = fields or list(rows[0])
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: (int(v) if isinstance(v, bool) else v)
                             for k, v in row.items()})


def valid_price(value):
    return (isinstance(value, (float, int)) and not isinstance(value, bool)
            and math.isfinite(value) and value > 0)


def normalize(source, record, config):
    raw = source["History"]["Price"]
    rules = {(r["asin"], r["timestamp"]): r for r in config["quarantine"]}
    observations, seen = [], set()
    start, end = map(date.fromisoformat, (config["analysis_start"], config["analysis_end"]))
    as_of = date.fromisoformat(config["snapshot_date"])
    for i, value in enumerate(raw, 1):
        timestamp, price = value.get("x"), value.get("y")
        reason, day = "", None
        try:
            parsed = datetime.fromisoformat(timestamp)
            # A changed timezone schema needs a deliberate alignment decision.
            if parsed.tzinfo is not None:
                raise ValueError("unexpected_timezone")
            day = parsed.date()
        except (TypeError, ValueError):
            reason = "invalid_or_unexpected_timestamp"
        if not valid_price(price):
            reason = reason or "invalid_nonpositive_price"
        if day and day > as_of:
            reason = reason or "future_observation"
        if timestamp in seen:
            # Do not silently choose between duplicate source observations.
            raise ValueError(f"Duplicate timestamp: {record['asin']} {timestamp}")
        seen.add(timestamp)
        rule = rules.get((record["asin"], timestamp))
        if rule:
            if price != rule["price"]:
                raise ValueError(f"Quarantine rule price changed: {rule}")
            reason = reason or rule["reason"]
        core_reason = ""
        if day:
            if not start <= day <= end:
                core_reason = "outside_2020_2022"
            elif friday(day) > end or friday(day) - timedelta(days=6) < start:
                core_reason = "partial_analysis_boundary_week"
        observations.append({
            "product_id": record["asin"], "category": record["category"],
            "product_name": record["name"], "market": "US", "store": record["store"],
            "currency": record["currency"], "source_timestamp": timestamp,
            "source_date": day.isoformat() if day else "", "source_timezone": "unknown",
            "price": price, "status": "quarantined" if reason else "accepted",
            "exclusion_reason": reason, "exclusion_note": rule["note"] if rule else "",
            "core_exclusion_reason": reason or core_reason,
            "neighbor_count": 0, "neighbor_median": "", "ratio_to_neighbor_median": "",
            "statistical_flags": "", "source_url": record["product_url"],
            "source_file": record["source_file"], "source_sha256": record["source_sha256"],
            "raw_row_number": i, "source_pointer": f"/History/Price/{i - 1}",
            "snapshot_date": config["snapshot_date"], "imputed": False,
        })
    for rule in config["quarantine"]:
        if rule["asin"] == record["asin"] and rule["timestamp"] not in seen:
            raise ValueError(f"Quarantine rule missing from snapshot: {rule}")
    # Flags use raw positive observations, not already filtered data. No recursive cleaning.
    dated = [(o, date.fromisoformat(o["source_date"])) for o in observations
             if o["source_date"] and valid_price(o["price"])]
    for observation, day in dated:
        neighbors = [o["price"] for o, d in dated
                     if o is not observation and abs((d - day).days) <= config["neighbor_days"]]
        observation["neighbor_count"] = len(neighbors)
        if len(neighbors) >= config["minimum_neighbors"]:
            middle = median(neighbors)
            ratio = observation["price"] / middle
            observation["neighbor_median"] = middle
            observation["ratio_to_neighbor_median"] = ratio
            if ratio < config["flag_ratio_below"]:
                observation["statistical_flags"] = "low_relative_to_30d_neighbors"
            elif ratio > config["flag_ratio_above"]:
                observation["statistical_flags"] = "high_relative_to_30d_neighbors"
    return observations


def returns(rows):
    previous = None
    for row in rows:
        row["previous_week_price_usd"] = ""
        row["quote_interval_days"] = ""
        row["price_change_fraction"] = ""
        row["log_return"] = ""
        row["log_return_unflagged"] = ""
        row["return_eligible"] = False
        row["unflagged_return_eligible"] = False
        reason = "first_week_in_dataset" if previous is None else ""
        if previous is not None:
            if date.fromisoformat(row["week_end"]) - date.fromisoformat(previous["week_end"]) != WEEK:
                raise ValueError("Weekly grid is not contiguous")
            if row["price_usd"] == "":
                reason = "current_week_missing"
            elif previous["price_usd"] == "":
                reason = "previous_week_missing"
            else:
                before, now = previous["price_usd"], row["price_usd"]
                row["previous_week_price_usd"] = before
                row["quote_interval_days"] = (date.fromisoformat(row["quote_date"])
                                              - date.fromisoformat(previous["quote_date"])).days
                row["price_change_fraction"] = now / before - 1
                row["log_return"] = math.log(now / before)
                row["return_eligible"] = True
                if not row["selected_quote_flags"] and not previous["selected_quote_flags"]:
                    row["log_return_unflagged"] = row["log_return"]
                    row["unflagged_return_eligible"] = True
        row["return_missing_reason"] = reason
        previous = row
    return rows


def weekly(observations, record, config):
    grouped = defaultdict(list)
    for observation in observations:
        if observation["source_date"]:
            grouped[friday(date.fromisoformat(observation["source_date"]))].append(observation)
    if not grouped:
        raise ValueError("No dated observations")
    cutoff = previous_complete_friday(date.fromisoformat(config["snapshot_date"]))
    first = min(grouped)
    first_observed_day = min(o["source_date"] for o in observations if o["source_date"])
    rows, current = [], first
    while current <= cutoff:
        original = sorted(grouped[current], key=lambda o: o["source_timestamp"])
        accepted = [o for o in original if o["status"] == "accepted"]
        valid_original = [o for o in original if valid_price(o["price"])]
        selected = accepted[-1] if accepted else None
        raw_last = valid_original[-1] if valid_original else None
        week_start = current - timedelta(days=6)
        rows.append({
            "product_id": record["asin"], "category": record["category"],
            "product_name": record["name"], "market": "US", "store": record["store"],
            "currency": record["currency"], "week_start": week_start.isoformat(),
            "week_end": current.isoformat(), "frequency": "W-FRI",
            "price_usd": selected["price"] if selected else "",
            "quote_timestamp": selected["source_timestamp"] if selected else "",
            "quote_date": selected["source_date"] if selected else "",
            "quote_age_days": (current - date.fromisoformat(selected["source_date"])).days if selected else "",
            "source_timezone": "unknown", "n_quotes_raw": len(original),
            "n_quotes_used": len(accepted), "n_quote_days": len({o["source_date"] for o in accepted}),
            "n_quarantined": len(original) - len(accepted),
            "n_statistically_flagged_quotes": sum(bool(o["statistical_flags"]) for o in accepted),
            "selected_quote_flags": selected["statistical_flags"] if selected else "",
            "raw_last_price_usd": raw_last["price"] if raw_last else "",
            "raw_last_quote_timestamp": raw_last["source_timestamp"] if raw_last else "",
            "cleaning_changed_week_price": bool(raw_last and (not selected or raw_last["price"] != selected["price"])),
            "missing_reason": "no_accepted_observation_in_week" if not selected else "",
            "is_partial_first_source_week": week_start.isoformat() < first_observed_day and current == first,
            "source_url": record["product_url"], "source_file": record["source_file"],
            "source_sha256": record["source_sha256"],
            "selected_raw_row_number": selected["raw_row_number"] if selected else "",
            "snapshot_date": config["snapshot_date"], "imputed": False,
        })
        current += WEEK
    return returns(rows)


def summarize(rows):
    observed = [r for r in rows if r["price_usd"] != ""]
    return {
        "grid_weeks": len(rows), "observed_weeks": len(observed),
        "missing_weeks": len(rows) - len(observed),
        "quote_rows_used": sum(r["n_quotes_used"] for r in rows),
        "adjacent_week_returns": sum(r["return_eligible"] for r in rows),
        "unflagged_adjacent_week_returns": sum(r["unflagged_return_eligible"] for r in rows),
        "weeks_changed_by_quarantine": sum(r["cleaning_changed_week_price"] for r in rows),
        "weeks_with_one_quote_day": sum(r["n_quote_days"] == 1 for r in rows),
        "weeks_with_at_least_3_quote_days": sum(r["n_quote_days"] >= 3 for r in rows),
        "quote_age_days_counts": dict(sorted(Counter(str(r["quote_age_days"]) for r in observed).items())),
        "first_week_end": rows[0]["week_end"], "last_week_end": rows[-1]["week_end"],
    }


def build(source_dir, output_dir, config_path):
    config = json.loads(config_path.read_text())
    manifest_path = source_dir / "requests.json"
    manifest = json.loads(manifest_path.read_text())
    records = [r.copy() for r in manifest["pricehistory_products"] if r["category"] in ("CPU", "SSD")]
    if Counter(r["category"] for r in records) != {"CPU": 1, "SSD": 1}:
        raise ValueError("Expected exactly one CPU and one SSD")
    observations, all_weeks, core_weeks, summaries, sources = [], [], [], {}, []
    input_hashes = {str(manifest_path.relative_to(ROOT)): digest(manifest_path),
                    str(config_path.relative_to(ROOT)): digest(config_path)}
    basis_evidence = ROOT / "data/verification/2026-10-21/pricehistory/pricing_disclaimer.html"
    if not basis_evidence.exists():
        raise ValueError("Saved pricing-definition evidence is missing")
    input_hashes[str(basis_evidence.relative_to(ROOT))] = digest(basis_evidence)
    for record in records:
        path = source_dir / "raw" / record["raw_file"]
        record["source_file"], record["source_sha256"] = str(path.relative_to(ROOT)), digest(path)
        input_hashes[record["source_file"]] = record["source_sha256"]
        page_path = source_dir / "raw" / f"pricehistory_{record['label']}.html"
        input_hashes[str(page_path.relative_to(ROOT))] = digest(page_path)
        source = json.loads(path.read_text())
        clean = normalize(source, record, config)
        weeks = weekly(clean, record, config)
        core = [r.copy() for r in weeks if r["week_start"] >= config["analysis_start"]
                and r["week_end"] <= config["analysis_end"]]
        returns(core)  # Reset the boundary: never use an unlisted week for core returns.
        observations.extend(clean)
        all_weeks.extend(weeks)
        core_weeks.extend(core)
        quarantined = [o for o in clean if o["status"] == "quarantined"]
        summaries[record["asin"]] = {
            "name": record["name"], "raw_price_rows": len(clean),
            "accepted_rows": len(clean) - len(quarantined), "quarantined_rows": len(quarantined),
            "accepted_statistically_flagged_rows": sum(bool(o["statistical_flags"]) and o["status"] == "accepted" for o in clean),
            "first_observed_date": min(o["source_date"] for o in clean if o["source_date"]),
            "last_observed_date": max(o["source_date"] for o in clean if o["source_date"]),
            "accepted_core_exclusion_counts": dict(Counter(o["core_exclusion_reason"] or "included"
                for o in clean if o["status"] == "accepted")),
            "offer_price_placeholders_not_used": sum(o.get("x") is None and o.get("y") is None
                for o in source["History"].get("OfferPrice", [])),
            "offer_price_nonnull_not_used": sum(o.get("x") is not None or o.get("y") is not None
                for o in source["History"].get("OfferPrice", [])),
            "full_history": summarize(weeks), "analysis_2020_2022": summarize(core),
        }
        sources.append({**{k: record[k] for k in ("asin", "category", "name", "store", "currency", "product_url", "source_file", "source_sha256")},
            "source_updated_on": record["source_updated_on"], "historical_field": "History.Price",
            "price_basis": "listed_price_from_seller_selected_by_price_plus_shipping",
            "basis_document_url": "https://pricehistory.app/page/pricing-disclaimer",
            "historical_shipping_amount": "unknown", "historical_tax_basis": "unknown",
            "historical_seller_and_condition": "unknown", "source_timezone": "unknown",
            "latest_main_price": source["Main"].get("Price"),
            "latest_main_shipping": source["Main"].get("Shipping"),
            "latest_main_final_price": source["Main"].get("FinalPrice"),
            "latest_fields_are_not_historical_conditions": True})
    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(output_dir / "observations_audit.csv", observations)
    write_csv(output_dir / "excluded_records.csv", [r for r in observations if r["status"] != "accepted"], list(observations[0]))
    write_csv(output_dir / "weekly_prices.csv", all_weeks)
    write_csv(output_dir / "weekly_2020_2022.csv", core_weeks)
    for name, value in (("sources.json", sources), ("quality_summary.json", {
        "schema_version": 1, "snapshot_date": config["snapshot_date"],
        "last_complete_week_end": previous_complete_friday(date.fromisoformat(config["snapshot_date"])).isoformat(),
        "analysis_start": config["analysis_start"], "analysis_end": config["analysis_end"],
        "core_week_policy": "Only Saturday-Friday weeks wholly inside the analysis window; reset first return.",
        "config_file": str(config_path.relative_to(ROOT)), "input_sha256": input_hashes,
        "products": summaries,
        "checks": {"raw_row_conservation": len(observations) == sum(s["raw_price_rows"] for s in summaries.values()),
                   "raw_files_unchanged": all(digest(ROOT / p) == h for p, h in input_hashes.items()),
                   "all_prices_positive": all(valid_price(r["price_usd"]) for r in all_weeks if r["price_usd"] != ""),
                   "no_imputation": all(not r["imputed"] for r in all_weeks)},
    })):
        (output_dir / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    return summaries


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, default=ROOT / "data/feasibility/2026-10-21/alternatives")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data/processed/2026-10-21/overseas")
    parser.add_argument("--config", type=Path, default=ROOT / "config/price_preprocessing.json")
    args = parser.parse_args()
    print(json.dumps(build(args.source_dir, args.output_dir, args.config), ensure_ascii=False, indent=2))
