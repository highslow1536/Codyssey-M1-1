"""Calendar-preserving price/stock correlations; offline, reproducible inputs.

Positive lag L means corr(component_return[t], stock_return[t-L]): stock leads.
Dependencies: numpy, pandas; figure generation uses matplotlib in a separate script.
"""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PRICE_DIR = ROOT / "data/processed/2026-10-21/overseas"
STOCK_DIR = ROOT / "data/processed/2026-10-22/stocks"
DEFAULT_OUTPUT = ROOT / "data/analysis/2026-10-22"
CONFIG_PATH = ROOT / "config/correlation_analysis.json"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pearson(x, y):
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    finite = np.isfinite(x) & np.isfinite(y)
    n = int(finite.sum())
    if n < 3:
        return np.nan, n
    a, b = x[finite] - np.mean(x[finite]), y[finite] - np.mean(y[finite])
    denominator = np.linalg.norm(a) * np.linalg.norm(b)
    return (float(np.clip(a @ b / denominator, -1, 1)) if denominator > 0 else np.nan), n


def spearman(x, y):
    finite = np.isfinite(x) & np.isfinite(y)
    return pearson(pd.Series(np.asarray(x)[finite]).rank(method="average"),
                   pd.Series(np.asarray(y)[finite]).rank(method="average"))[0]


def lag_pair(component, stock, lag):
    """Slice full calendar arrays BEFORE dropping paired missing values."""
    if len(component) != len(stock):
        raise ValueError("Calendar arrays must have equal lengths")
    if lag > 0:
        return component[lag:], stock[:-lag]
    if lag < 0:
        return component[:lag], stock[-lag:]
    return component, stock


def bootstrap_ci(x, y, block, repetitions, seed):
    """Paired circular blocks of calendar weeks, retaining the missingness mask."""
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    n = len(x)
    if pearson(x, y)[1] < 3:
        return np.nan, np.nan, 0
    rng = np.random.default_rng(seed)
    starts = rng.integers(0, n, size=(repetitions, int(np.ceil(n / block))))
    indices = ((starts[..., None] + np.arange(block)) % n).reshape(repetitions, -1)[:, :n]
    a, b = x[indices], y[indices]
    finite = np.isfinite(a) & np.isfinite(b)
    counts = finite.sum(axis=1)
    a, b = np.where(finite, a, 0), np.where(finite, b, 0)
    with np.errstate(divide="ignore", invalid="ignore"):
        covariance = (a * b).sum(axis=1) - a.sum(axis=1) * b.sum(axis=1) / counts
        variance_a = (a * a).sum(axis=1) - a.sum(axis=1) ** 2 / counts
        variance_b = (b * b).sum(axis=1) - b.sum(axis=1) ** 2 / counts
        values = covariance / np.sqrt(np.maximum(variance_a * variance_b, 0))
    values = values[(counts >= 3) & np.isfinite(values)]
    if not len(values):
        return np.nan, np.nan, 0
    low, high = np.quantile(np.clip(values, -1, 1), [0.025, 0.975])
    return float(low), float(high), len(values)


def circular_shift_pvalue(component, stock, lag):
    """Exploratory temporal-shift null; includes identity in finite randomization p."""
    observed, _ = pearson(*lag_pair(component, stock, lag))
    if not np.isfinite(observed):
        return np.nan, 0
    null = [pearson(*lag_pair(component, np.roll(stock, shift), lag))[0]
            for shift in range(1, len(stock))]
    null = np.asarray([r for r in null if np.isfinite(r)])
    if not len(null):
        return np.nan, 0
    exceedances = int((np.abs(null) >= abs(observed) - 1e-12).sum())
    return (1 + exceedances) / (1 + len(null)), len(null)


def fdr_adjust(pvalues, arbitrary_dependence=False):
    p = np.asarray(pvalues, dtype=float)
    answer = np.full(len(p), np.nan)
    valid = np.flatnonzero(np.isfinite(p))
    ordered = valid[np.argsort(p[valid], kind="stable")]
    m = len(ordered)
    if not m:
        return answer
    factor = np.sum(1 / np.arange(1, m + 1)) if arbitrary_dependence else 1
    adjusted = p[ordered] * m * factor / np.arange(1, m + 1)
    answer[ordered] = np.minimum(1, np.minimum.accumulate(adjusted[::-1])[::-1])
    return answer


def consecutive_returns(values):
    a = np.asarray(values, dtype=float)
    output = np.full(len(a), np.nan)
    good = np.isfinite(a[1:]) & np.isfinite(a[:-1]) & (a[1:] > 0) & (a[:-1] > 0)
    output[1:][good] = np.log(a[1:][good] / a[:-1][good])
    return output


def read_inputs(config):
    prices = pd.read_csv(PRICE_DIR / "weekly_2020_2022.csv", dtype={"product_id": str})
    stocks = pd.read_csv(STOCK_DIR / "weekly_stocks.csv", dtype={"symbol": str})
    stocks["symbol"] = stocks["symbol"].str.replace(".KS", "", regex=False)
    weeks = pd.date_range(config["first_week_end"], config["last_week_end"], freq="W-FRI").strftime("%Y-%m-%d").tolist()
    for data, key, identities in ((prices, "product_id", config["product_order"]),
                                  (stocks, "symbol", config["stock_order"])):
        if data.duplicated([key, "week_end"]).any():
            raise ValueError(f"Duplicate weekly key: {key}")
        if set(data[key]) != set(identities):
            raise ValueError(f"Unexpected identities in {key}")
        for identity in identities:
            if sorted(data.loc[data[key] == identity, "week_end"].tolist()) != weeks:
                raise ValueError(f"Missing calendar rows for {identity}")
    return (prices.set_index(["product_id", "week_end"]).sort_index(),
            stocks.set_index(["symbol", "week_end"]).sort_index(), weeks)


def price_scenarios(prices, product, weeks):
    frame = prices.loc[product].loc[weeks]
    scenarios = {"baseline": frame["log_return"].to_numpy(dtype=float),
                 "no_quarantine": consecutive_returns(frame["raw_last_price_usd"])}
    age = frame["quote_age_days"].to_numpy(dtype=float)
    days = frame["n_quote_days"].to_numpy(dtype=float)
    for label, good in (("quotes_within_1d_of_friday", age <= 1), ("at_least_3_quote_days", days >= 3)):
        eligible = good & np.r_[False, good[:-1]]
        scenarios[label] = np.where(eligible, scenarios["baseline"], np.nan)
    audit = pd.read_csv(PRICE_DIR / "observations_audit.csv", dtype={"product_id": str})
    audit = audit[(audit["product_id"] == product) & (audit["status"] == "accepted")].copy()
    for shift in (-1, 1):
        shifted = pd.to_datetime(audit["source_timestamp"]) + pd.Timedelta(days=shift)
        audit["shifted_timestamp"] = shifted
        audit["week_end"] = (shifted.dt.normalize() + pd.to_timedelta((4 - shifted.dt.dayofweek) % 7, unit="D")).dt.strftime("%Y-%m-%d")
        last = audit.sort_values("shifted_timestamp").groupby("week_end").tail(1).set_index("week_end")
        value = pd.to_numeric(last["price"], errors="raise").reindex(weeks).to_numpy(dtype=float)
        scenarios[f"source_date_shift_{shift:+d}d"] = consecutive_returns(value)
    return scenarios


def export_csv(path, records):
    frame = records if isinstance(records, pd.DataFrame) else pd.DataFrame(records)
    frame.to_csv(path, index=False, encoding="utf-8-sig", float_format="%.12g")


def build(output_dir=DEFAULT_OUTPUT, config_path=CONFIG_PATH):
    config = json.loads(config_path.read_text())
    prices, stocks, weeks = read_inputs(config)
    stock_quality = json.loads((STOCK_DIR / "quality_summary.json").read_text())
    output_dir.mkdir(parents=True, exist_ok=True)
    aligned, summaries, lag_results, sensitivities, yearly, coverage, trend_bases = [], [], [], [], [], [], []
    for product in config["product_order"]:
        p = prices.loc[product].loc[weeks]
        returns = p["log_return"].to_numpy(dtype=float)
        scenarios = price_scenarios(prices, product, weeks)
        coverage.append({"series": product, "kind": "price", "total_weeks": len(weeks),
                         "available": int(p["price_usd"].notna().sum()), "missing": int(p["price_usd"].isna().sum())})
        coverage.append({"series": product, "kind": "return", "total_weeks": len(weeks),
                         "available": int(np.isfinite(returns).sum()), "first_boundary_week": 1,
                         "missing_after_first_week": int((~np.isfinite(returns[1:])).sum())})
        primary = config["primary_pairs"][product]
        common = p["price_usd"].notna().to_numpy()
        for symbol in primary:
            common &= stocks.loc[symbol].loc[weeks, "adjusted_close"].notna().to_numpy()
        base_week = weeks[int(np.flatnonzero(common)[0])] if common.any() else None
        trend_bases.append({"product_id": product, "common_base_week": base_week})
        for symbol in config["stock_order"]:
            s = stocks.loc[symbol].loc[weeks]
            stock_returns = s["return_log"].to_numpy(dtype=float)
            level_r, n_level = pearson(p["price_usd"], s["adjusted_close"])
            return_r, n_return = pearson(returns, stock_returns)
            low, high, draws = bootstrap_ci(returns[1:], stock_returns[1:], config["bootstrap_block_weeks"],
                                            config["bootstrap_repetitions"], config["random_seed"])
            low8, high8, _ = bootstrap_ci(returns[1:], stock_returns[1:], config["bootstrap_sensitivity_block_weeks"],
                                        config["bootstrap_repetitions"], config["random_seed"])
            relation = ("manufacturer" if (product, symbol) in (("B07STGGQ18", "AMD"), ("B07MFZY2F2", "005930"))
                        else "related_sector_comparison" if symbol in primary else "cross_sector_reference")
            summaries.append({"product_id": product, "category": p.iloc[0]["category"], "symbol": symbol,
                "company": s.iloc[0]["company"], "stock_currency": s.iloc[0]["currency"], "relationship": relation,
                "level_pearson": level_r, "level_spearman": spearman(p["price_usd"].to_numpy(), s["adjusted_close"].to_numpy()),
                "n_level": n_level, "return_pearson": return_r,
                "return_spearman": spearman(returns, stock_returns), "n_return": n_return,
                "return_ci_low_block4": low, "return_ci_high_block4": high,
                "return_ci_low_block8": low8, "return_ci_high_block8": high8, "bootstrap_valid_draws": draws})
            for index, week_end in enumerate(weeks):
                aligned.append({"product_id": product, "category": p.iloc[0]["category"], "symbol": symbol,
                    "week_start": p.loc[week_end, "week_start"], "week_end": week_end,
                    "component_price_usd": p.loc[week_end, "price_usd"],
                    "component_return_log": returns[index], "component_quote_date": p.loc[week_end, "quote_date"],
                    "component_quote_age_days": p.loc[week_end, "quote_age_days"],
                    "component_n_quote_days": p.loc[week_end, "n_quote_days"],
                    "stock_adjusted_close": s.loc[week_end, "adjusted_close"], "stock_return_log": stock_returns[index],
                    "stock_quote_date": s.loc[week_end, "quote_date"], "stock_currency": s.loc[week_end, "currency"],
                    "level_pair_available": int(np.isfinite(p.loc[week_end, "price_usd"]) and np.isfinite(s.loc[week_end, "adjusted_close"])),
                    "return_pair_available": int(np.isfinite(returns[index]) and np.isfinite(stock_returns[index]))})
            for lag in range(-config["max_lag_weeks"], config["max_lag_weeks"] + 1):
                a, b = lag_pair(returns[1:], stock_returns[1:], lag)
                coefficient, n = pearson(a, b)
                shift_p, null_count = circular_shift_pvalue(returns[1:], stock_returns[1:], lag)
                lag_results.append({"product_id": product, "symbol": symbol, "lag_weeks": lag,
                    "pearson": coefficient, "spearman": spearman(a, b), "n": n,
                    "calendar_slots": len(a), "shift_pvalue": shift_p, "valid_null_shifts": null_count})
            for label, values in scenarios.items():
                r, n = pearson(values, stock_returns)
                sensitivities.append({"product_id": product, "symbol": symbol, "scenario": label, "lag_weeks": 0,
                                      "pearson": r, "n": n})
            if symbol in ("005930", "000660"):
                quality = stock_quality["symbols"][symbol]
                mismatches = quality.get("last_session_mismatches",
                    quality.get("naver_crosscheck", {}).get("last_session_mismatches"))
                if mismatches is None:
                    raise ValueError(f"Last-session cross-check missing for {symbol}")
                excluded_ends = {row["week_end"] for row in mismatches}
                excluded_ends |= {(pd.Timestamp(w) + pd.Timedelta(days=7)).strftime("%Y-%m-%d")
                                  for w in list(excluded_ends)}
                filtered_stock = np.where([w not in excluded_ends for w in weeks], stock_returns, np.nan)
                r, n = pearson(returns, filtered_stock)
                sensitivities.append({"product_id": product, "symbol": symbol,
                    "scenario": "exclude_stock_last_session_mismatch_and_next_week", "lag_weeks": 0,
                    "pearson": r, "n": n})
            for year in (2020, 2021, 2022):
                mask = np.array([w.startswith(str(year)) for w in weeks])
                # Full-grid returns are retained: a week-over-week return may cross year-end.
                r, n = pearson(returns[mask], stock_returns[mask])
                yearly.append({"product_id": product, "symbol": symbol, "year": year, "pearson": r, "n": n})
    for symbol in config["stock_order"]:
        s = stocks.loc[symbol].loc[weeks]
        coverage.append({"series": symbol, "kind": "stock_return", "total_weeks": len(weeks),
                         "available": int(s["return_log"].notna().sum()), "first_boundary_week": 1,
                         "missing_after_first_week": int(s["return_log"].iloc[1:].isna().sum())})
    lag_frame = pd.DataFrame(lag_results)
    lag_frame["q_shift_bh_all_lags"] = fdr_adjust(lag_frame["shift_pvalue"])
    lag_frame["q_shift_by_all_lags"] = fdr_adjust(lag_frame["shift_pvalue"], arbitrary_dependence=True)
    zero_mask = lag_frame["lag_weeks"] == 0
    zero_adjusted = fdr_adjust(lag_frame.loc[zero_mask, "shift_pvalue"])
    for row, (_, lagrow), q_zero in zip(summaries, lag_frame[zero_mask].iterrows(), zero_adjusted):
        row["shift_pvalue"] = lagrow["shift_pvalue"]
        row["q_shift_bh_zero_lag_12_tests"] = q_zero
        row["q_shift_bh_all_lags"] = lagrow["q_shift_bh_all_lags"]
    peaks = []
    for (product, symbol), group in lag_frame.groupby(["product_id", "symbol"], sort=False):
        candidates = group.dropna(subset=["pearson"]).copy()
        if candidates.empty:
            continue
        candidates["magnitude"] = candidates["pearson"].abs()
        candidates["lag_magnitude"] = candidates["lag_weeks"].abs()
        selected = candidates.sort_values(["magnitude", "lag_magnitude", "lag_weeks"], ascending=[False, True, True]).iloc[0]
        peaks.append({k: selected[k] for k in lag_frame.columns})
    for filename, value in (("aligned_weekly.csv", aligned), ("correlations.csv", summaries),
                            ("lag_correlations.csv", lag_frame), ("lag_peaks_exploratory.csv", peaks),
                            ("sensitivity.csv", sensitivities), ("correlations_by_year.csv", yearly),
                            ("coverage.csv", coverage)):
        export_csv(output_dir / filename, value)
    metadata = {"analysis_date_kst": config["analysis_date_kst"], "config": config,
        "n_calendar_weeks": len(weeks), "n_return_slots": len(weeks) - 1,
        "lag_sign_convention": "corr(component_return[t], stock_return[t-L]); L>0: stock leads",
        "trend_bases": trend_bases, "lag_hypothesis_count": int(lag_frame["shift_pvalue"].notna().sum()),
        "tests_bh_below_0_05": int((lag_frame["q_shift_bh_all_lags"] < .05).sum()),
        "tests_by_below_0_05": int((lag_frame["q_shift_by_all_lags"] < .05).sum()),
        "zero_lag_tests_bh_below_0_05": int((zero_adjusted < .05).sum()),
        "versions": {"numpy": np.__version__, "pandas": pd.__version__},
        "input_sha256": {str(p.relative_to(ROOT)): sha256(p) for p in
            [PRICE_DIR / "weekly_2020_2022.csv", PRICE_DIR / "observations_audit.csv",
             STOCK_DIR / "weekly_stocks.csv", STOCK_DIR / "sources.json", STOCK_DIR / "quality_summary.json", config_path]},
        "limits": ["Levels may share trends; do not interpret level correlations as return prediction.",
                   "Bootstrap intervals are pointwise, not simultaneous; block stationarity is an approximation.",
                   "Circular shifts assume approximate temporal stationarity; 154 shifts give coarse p-values.",
                   "Maxima across lags are exploratory, not out-of-sample forecast results.",
                   "Component timestamps have unknown timezone; stocks use exchange-local dates.",
                   "US product USD quotes vs Korean stock KRW returns are not FX-neutral.",
                   "Irregular quote timing, missingness and changing sellers can bias observed correlations."]}
    (output_dir / "analysis_metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n")
    print(pd.DataFrame(summaries)[["category", "symbol", "level_pearson", "n_level", "return_pearson", "n_return"]].to_string(index=False))
    return pd.DataFrame(summaries), lag_frame


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--config", type=Path, default=CONFIG_PATH)
    args = parser.parse_args()
    build(args.output_dir, args.config)
