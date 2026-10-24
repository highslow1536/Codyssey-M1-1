"""Descriptive GPU/ETH mining analysis on actual observations, without imputation.

Sparse retail quotes are analysed at their genuine dates and interval lengths.
Monthly sold-listing means remain monthly and separate from EUR retail quotes.
"""
import argparse
import calendar
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from analyze_price_stock_correlations import consecutive_returns, export_csv, pearson, spearman

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data/processed/2026-10-22"
OUT = ROOT / "data/analysis/2026-10-22/gpu_mining"
METRICS = {"eth_price": "price_usd", "fees_included_proxy": "rev_usd_per100mh_gross",
           "fees_excluded_proxy": "iss_usd_per100mh"}


def strict_mean(values, expected):
    return float(values.mean()) if len(values) == expected and values.notna().all() else np.nan


def align_snapshots(observations, daily, offset=0):
    """Use seven source-date records ending BEFORE the GPU quote date by default."""
    daily = daily.set_index("date").sort_index()
    aligned = []
    for observation in observations.to_dict("records"):
        date = pd.Timestamp(observation["observation_date"])
        end = date - pd.Timedelta(days=1) + pd.Timedelta(days=offset)
        expected = pd.date_range(end - pd.Timedelta(days=6), end, freq="D").strftime("%Y-%m-%d")
        window = daily.reindex(expected)
        row = dict(observation)
        row.update({"crypto_window_start": expected[0], "crypto_window_end": expected[-1],
                    "crypto_calendar_offset_days": offset})
        for metric, field in METRICS.items():
            row[f"{metric}_7d"] = strict_mean(window[field], 7)
            row[f"{metric}_n_days"] = int(window[field].notna().sum())
        aligned.append(row)
    frame = pd.DataFrame(aligned)
    for _, group in frame.groupby("series_id", sort=False):
        valid = group[group.value.notna()].sort_values("observation_date")
        dates = pd.to_datetime(valid.observation_date)
        frame.loc[valid.index, "previous_observation_date"] = valid.observation_date.shift(1)
        frame.loc[valid.index, "interval_days"] = dates.diff().dt.days
        frame.loc[valid.index, "gpu_interval_logchange"] = np.log(valid.value / valid.value.shift(1))
        for metric in METRICS:
            a = valid[f"{metric}_7d"]
            # These are between genuine consecutive valid GPU observations, NOT weekly returns.
            frame.loc[valid.index, f"{metric}_interval_logchange"] = np.log(a / a.shift(1))
    return frame


def monthly_crypto(daily):
    rows = []
    month = daily.date.str[:7]
    for label, group in daily.groupby(month, sort=True):
        year, m = map(int, label.split("-"))
        expected = calendar.monthrange(year, m)[1]
        row = {"month": label, "n_calendar_days": expected,
            "pow_status": ("mixed_transition" if label == "2022-09" else
                           "terminated" if label > "2022-09" else "active")}
        for metric, field in METRICS.items():
            row[f"{metric}_mean"] = strict_mean(group[field], expected)
            row[f"{metric}_n_days"] = int(group[field].notna().sum())
        rows.append(row)
    frame = pd.DataFrame(rows)
    for metric in METRICS:
        frame[f"{metric}_return_log"] = consecutive_returns(frame[f"{metric}_mean"])
    return frame


def add_correlations(rows, group, dataset, identity, subset="all"):
    if dataset == "retail_snapshots":
        methods = [("levels", "value", "7d"), ("observation_interval_logchange", "gpu_interval_logchange", "interval_logchange"),
                   ("observation_interval_logchange_per_day", "gpu_interval_logchange", "interval_logchange")]
    else:
        methods = [("monthly_levels", "price_usd", "mean"), ("adjacent_month_logchange", "gpu_return_log", "return_log")]
    for method, left, suffix in methods:
        for metric in METRICS:
            x, y = group[left].to_numpy(dtype=float), group[f"{metric}_{suffix}"].to_numpy(dtype=float)
            if method.endswith("per_day"):
                days = group.interval_days.to_numpy(dtype=float)
                x, y = x / days, y / days
            coefficient, n = pearson(x, y)
            rows.append({"dataset": dataset, "series_id": identity, "subset": subset, "method": method,
                "crypto_metric": metric, "pearson": coefficient, "spearman": spearman(x, y), "n": n,
                "interpretation": "insufficient_n" if n < 3 else "descriptive_only_no_causal_or_forecast_test"})


def read_ebay():
    path = PROCESSED / "gpu_ebay/monthly_grid_2020_2022.csv"
    frame = pd.read_csv(path).rename(columns={"ebay_avg_price_usd": "price_usd", "qty_sold": "quantity_sold"})
    frame["gpu"] = frame.gpu_model.map({"RTX 3070": "3070", "RTX 3080_10GB": "3080", "RTX 3090": "3090"})
    if len(frame) != 108 or frame.gpu.isna().any() or frame.duplicated(["gpu", "month"]).any():
        raise ValueError("Expected three GPUs on the full 36-month grid, with no duplicates")
    return path, frame


def build(output_dir=OUT):
    output_dir.mkdir(parents=True, exist_ok=True)
    observations_path = PROCESSED / "gpu_retail/observations.csv"
    weekly_path = PROCESSED / "gpu_retail/weekly_retail.csv"
    crypto_path = PROCESSED / "crypto/eth_daily.csv"
    observations = pd.read_csv(observations_path, dtype={"series_id": str})
    weekly = pd.read_csv(weekly_path, dtype={"series_id": str})
    daily = pd.read_csv(crypto_path)
    if len(daily) != 1096 or daily.date.duplicated().any():
        raise ValueError("Expected complete daily calendar 2020-2022")
    snapshots = align_snapshots(observations, daily)
    crypto_months = monthly_crypto(daily)
    ebay_path, ebay = read_ebay()
    monthly = ebay.merge(crypto_months, on="month", how="left", validate="many_to_one")
    correlations, sensitivity, stages, changes = [], [], [], []
    for identity, group in snapshots.groupby("series_id", sort=False):
        add_correlations(correlations, group, "retail_snapshots", identity)
        short = group[group.interval_days <= 35]
        add_correlations(correlations, short, "retail_snapshots", identity, "interval_at_most_35_days")
        for year in (2021, 2022):
            subset = group[group.observation_date.str.startswith(str(year))]
            # Drop crossing-year intervals; levels stay in their actual year.
            subset = subset.copy()
            crossed = ~subset.previous_observation_date.fillna("").str.startswith(str(year))
            for field in ["gpu_interval_logchange"] + [f"{m}_interval_logchange" for m in METRICS]:
                subset.loc[crossed, field] = np.nan
            add_correlations(correlations, subset, "retail_snapshots", identity, str(year))
        if group.iloc[0].kind == "retail_quote":
            valid = group[group.value.notna()]
            year21 = valid[valid.observation_date.str.startswith("2021")]
            first, peak, last = year21.iloc[0], year21.loc[year21.value.idxmax()], valid.iloc[-1]
            jan22 = valid[valid.observation_date == "2022-01-02"].iloc[0]
            for label, before, after in (("first_2021_to_observed_peak", first, peak),
                    ("observed_peak_to_last_premerge", peak, last), ("jan2022_to_last_premerge", jan22, last)):
                changes.append({"dataset": "retail_eur", "series_id": identity, "comparison": label,
                    "before_start": before.observation_date, "before_end": before.observation_date,
                    "after_start": after.observation_date, "after_end": after.observation_date,
                    "before_value": before.value, "after_value": after.value,
                    "change_fraction": after.value / before.value - 1, "n_before": 1, "n_after": 1,
                    "unit": "EUR", "causal_effect": False})
    for offset in (-1, 0, 1):
        shifted = snapshots if offset == 0 else align_snapshots(observations, daily, offset)
        for identity, group in shifted.groupby("series_id", sort=False):
            if group.iloc[0].kind != "retail_quote":
                continue
            for metric in METRICS:
                r, n = pearson(group.gpu_interval_logchange, group[f"{metric}_interval_logchange"])
                sensitivity.append({"series_id": identity, "crypto_window_offset_days": offset,
                    "method": "observation_interval_logchange", "crypto_metric": metric, "pearson": r, "n": n})
    for identity, group in monthly.groupby("gpu", sort=False):
        group = group.sort_values("month").copy()
        group["gpu_return_log"] = consecutive_returns(group.price_usd)
        monthly.loc[group.index, "gpu_return_log"] = group.gpu_return_log
        add_correlations(correlations, group, "ebay_monthly", identity)
        for label, begin, end in (("2022_Q1", "2022-01", "2022-03"), ("2022_Q2", "2022-04", "2022-06"),
                ("premerge_Jul_Aug", "2022-07", "2022-08"), ("merge_mixed_month", "2022-09", "2022-09"),
                ("postmerge_Oct_Nov", "2022-10", "2022-11"), ("2022_Q4", "2022-10", "2022-12")):
            selected = group[group.month.between(begin, end) & group.price_usd.notna()]
            stages.append({"series_id": identity, "period": label, "start_month": begin, "end_month": end,
                "mean_monthly_price_usd": selected.price_usd.mean(), "n_months": len(selected),
                "monthly_sale_count_sum": selected.quantity_sold.sum(min_count=1)})
        for label, prestart, preend, poststart, postend in (
            ("premerge_Jul_Aug_vs_postmerge_Oct_Nov", "2022-07", "2022-08", "2022-10", "2022-11"),
            ("Q1_vs_Q4_2022", "2022-01", "2022-03", "2022-10", "2022-12")):
            before = group[group.month.between(prestart, preend)].price_usd.dropna()
            after = group[group.month.between(poststart, postend)].price_usd.dropna()
            changes.append({"dataset": "ebay_monthly_usd", "series_id": identity, "comparison": label,
                "before_start": prestart, "before_end": preend, "after_start": poststart, "after_end": postend,
                "before_value": before.mean(), "after_value": after.mean(),
                "change_fraction": after.mean() / before.mean() - 1, "n_before": len(before), "n_after": len(after),
                "unit": "USD_monthly_mean_unweighted_across_months", "causal_effect": False})
    for filename, frame in (("aligned_snapshots.csv", snapshots), ("aligned_monthly.csv", monthly),
            ("crypto_monthly.csv", crypto_months), ("correlations.csv", correlations),
            ("date_sensitivity.csv", sensitivity), ("period_summary.csv", stages), ("price_changes.csv", changes)):
        export_csv(output_dir / filename, frame)
    # Full weekly calendar for coverage/traceability only; sparse returns are not inflated.
    crypto_weekly_path = PROCESSED / "crypto/eth_weekly.csv"
    crypto_weekly = pd.read_csv(crypto_weekly_path)
    export_csv(output_dir / "aligned_weekly.csv", weekly.merge(crypto_weekly, on="week_end", how="left", validate="many_to_one"))
    inputs = [observations_path, weekly_path, crypto_path, crypto_weekly_path, ebay_path,
              PROCESSED / "gpu_retail/sources.json", PROCESSED / "crypto/quality_summary.json", PROCESSED / "crypto/sources.json",
              PROCESSED / "gpu_ebay/sources.json", PROCESSED / "gpu_ebay/quality_summary.json"]
    metadata = {"analysis_date_kst": "2026-10-22", "calendar_weeks": 156,
        "snapshot_count_with_missing_prices": len(observations), "monthly_grid_rows": len(monthly),
        "method": "Descriptive: no imputation, no p-values or causal treatment-effect claims",
        "default_crypto_alignment": "Mean of 7 source-date records ending one calendar day before each GPU quote",
        "intervals": "Between consecutive valid original GPU observations; actual elapsed days retained; not weekly returns",
        "mining_measure": "Network-based fixed-100MH/s revenue proxies, not measured GPU net profitability",
        "post_london_warning": "Total fees include burned base fee; fees-included proxy overcounts this component after 2021-08-05",
        "issuance_warning": "ETH IssTotNtv includes Beacon staking rewards after Beacon launch; unavailable ETH_CL breakdown prevents separation. Both proxies are network issuance/fee indicators, not pure miner revenues.",
        "merge": "2022-09-15 partial day excluded; later ETH PoW not applicable; Sep2022 monthly mining proxy omitted",
        "input_sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},
        "versions": {"numpy": np.__version__, "pandas": pd.__version__}}
    (output_dir / "analysis_metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n")
    print(pd.DataFrame(changes).to_string(index=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=OUT)
    build(parser.parse_args().output_dir)
