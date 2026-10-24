"""Prepare daily + Sat-Fri weekly ETH PoW mining-revenue proxy (2020-01-01..2022-12-31).
Read-only over data/verification/2026-10-22/crypto/cm_eth_daily_raw.json; never
modifies raw inputs. Public Coin Metrics community API data only.
Two assumption-based proxies (RevUSD unavailable in community tier):
  A) fee-fully-included: rev_ntv_proxy = IssTotNtv + FeeTotNtv. From London on
     (2021-08-05) FeeTotNtv includes burned base fees, so this OVERSTATES the
     fee part actually paid to miners (flagged per row). No FeeBurn/FeePrio
     metric exists in the community tier to correct it.
  B) fee-excluded: iss-only = IssTotNtv valued at PriceUSD. Excludes all fees
     by construction, omits MEV entirely, and IssTotNtv includes Beacon-chain
     staking issuance after its launch per Coin Metrics methodology -- so B is
     NOT a strict lower bound of true miner revenue either.
Neither proxy is a guaranteed bound. Per-100MH/s: rev_usd_proxy / (hashrate_THS * 1e6) * 100. Electricity scenarios
are fixed assumptions (200 W, 0.10/0.20 USD/kWh -> 0.48/0.96 USD/day), NOT
measured RTX figures. Merge: 2022-09-15 is a partial transition day (revenue
excluded); later dates are PoW-terminated (revenue not-applicable, distinct
from missing). No interpolation anywhere.
Weekly grid matches stocks: Saturday-to-Friday, 2020-01-04..2022-12-30 (156)."""
from __future__ import annotations
import csv
import hashlib
import json
import math
from datetime import date, timedelta
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/verification/2026-10-22/crypto/cm_eth_daily_raw.json"
OUT_DIR = ROOT / "data/processed/2026-10-22/crypto"
DAY_START = date(2020, 1, 1)
DAY_END = date(2022, 12, 31)
GRID_START = date(2020, 1, 4)
GRID_END = date(2022, 12, 30)
MERGE_DATE = date(2022, 9, 15)
LONDON_DATE = date(2021, 8, 5)
BEACON_DATE = date(2020, 12, 1)
ELEC_W = 200.0
ELEC_COST_010 = ELEC_W * 24 / 1000 * 0.10
ELEC_COST_020 = ELEC_W * 24 / 1000 * 0.20
DAILY_COLUMNS = ["date", "price_usd", "hashrate_ths", "fee_tot_ntv",
    "iss_tot_ntv", "iss_tot_usd", "rev_ntv_proxy", "rev_usd_proxy",
    "rev_usd_per100mh_gross", "rev_usd_per100mh_7d",
    "elec_usd_perday_010", "elec_usd_perday_020",
    "net_usd_per100mh_010", "net_usd_per100mh_020",
    "iss_usd_per100mh", "iss_usd_per100mh_7d",
    "london_burn_overincluded", "beacon_issuance_included", "is_partial_transition",
    "pow_terminated", "unobserved", "source_file", "source_sha256"]
WEEKLY_COLUMNS = ["week_start", "week_end", "price_usd_last", "price_date",
    "rev_usd_per100mh_last", "rev_date_last", "rev_usd_per100mh_week_mean",
    "iss_usd_per100mh_last", "iss_usd_per100mh_week_mean",
    "price_return_log", "price_return_fraction", "n_days", "n_price_days",
    "n_rev_days", "unobserved_days", "partial_days", "pow_terminated_days",
    "pow_status", "lastdate", "source_file", "source_sha256"]
def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()

def fmt(x, nd=6):
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return ""
    s = repr(round(float(x), nd))
    return s

def load_inputs():
    digest = sha256_of(RAW)
    payload = json.loads(RAW.read_text(encoding="utf-8"))
    by = {}
    for met, rows in payload["data"].items():
        for r in rows:
            by.setdefault(r["time"], {})[met] = r[met]
    return digest, by, payload.get("manifest", {})

def build_daily(by):
    daily = []
    d = DAY_START
    while d <= DAY_END:
        k = d.isoformat()
        v = by.get(k, {})
        price = float(v["PriceUSD"]) if v.get("PriceUSD") is not None else None
        hr = float(v["HashRate"]) if v.get("HashRate") is not None else None
        fee = float(v["FeeTotNtv"]) if v.get("FeeTotNtv") is not None else None
        iss = float(v["IssTotNtv"]) if v.get("IssTotNtv") is not None else None
        issu = float(v["IssTotUSD"]) if v.get("IssTotUSD") is not None else None
        partial = (d == MERGE_DATE)
        terminated = (d > MERGE_DATE)
        have_all = all(x is not None for x in (price, hr, fee, iss))
        unobserved = (not terminated and not partial and not have_all)
        rev_ntv = rev_usd = g100 = iss100 = None
        if not partial and not terminated and have_all and hr > 0:
            rev_ntv = iss + fee
            rev_usd = rev_ntv * price
            g100 = rev_usd / (hr * 1e6) * 100.0
            iss100 = iss * price / (hr * 1e6) * 100.0
        daily.append({"date": k, "price": price, "hr": hr, "fee": fee,
            "iss": iss, "issu": issu, "rev_ntv": rev_ntv, "rev_usd": rev_usd,
            "g100": g100, "iss100": iss100, "partial": partial, "terminated": terminated,
            "unobserved": unobserved})
        d += timedelta(days=1)
    for i, row in enumerate(daily):
        win = daily[max(0, i - 6):i + 1]
        if len(win) == 7 and all(w["g100"] is not None for w in win):
            row["g100_7d"] = sum(w["g100"] for w in win) / 7.0
            row["iss100_7d"] = sum(w["iss100"] for w in win) / 7.0
        else:
            row["g100_7d"] = None
            row["iss100_7d"] = None
    return daily

def week_grid():
    weeks = []
    s = GRID_START
    while s <= GRID_END:
        weeks.append((s, s + timedelta(days=6)))
        s += timedelta(days=7)
    return weeks
def main():
    digest, by, manifest = load_inputs()
    src_rel = str(RAW.relative_to(ROOT))
    daily = build_daily(by)
    assert len(daily) == (DAY_END - DAY_START).days + 1 == 1096, len(daily)
    assert daily[0]["date"] == "2020-01-01" and daily[-1]["date"] == "2022-12-31"
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with (OUT_DIR / "eth_daily.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(DAILY_COLUMNS)
        for r in daily:
            d = date.fromisoformat(r["date"])
            w.writerow([r["date"], fmt(r["price"]), fmt(r["hr"]), fmt(r["fee"]),
                fmt(r["iss"]), fmt(r["issu"]), fmt(r["rev_ntv"]), fmt(r["rev_usd"]),
                fmt(r["g100"]), fmt(r.get("g100_7d")), fmt(ELEC_COST_010, 4),
                fmt(ELEC_COST_020, 4),
                fmt(r["g100"] - ELEC_COST_010) if r["g100"] is not None else "",
                fmt(r["g100"] - ELEC_COST_020) if r["g100"] is not None else "",
                fmt(r["iss100"]), fmt(r.get("iss100_7d")),
                1 if (d >= LONDON_DATE and r["g100"] is not None) else 0,
                1 if (d >= BEACON_DATE and r["g100"] is not None) else 0, 1 if r["partial"] else 0,
                1 if r["terminated"] else 0, 1 if r["unobserved"] else 0,
                src_rel, digest])
    weeks = week_grid()
    assert len(weeks) == 156, len(weeks)
    assert weeks[0][0].isoformat() == "2020-01-04"
    assert weeks[-1][1].isoformat() == "2022-12-30"
    by_date = {r["date"]: r for r in daily}
    wrows = []
    for ws, we in weeks:
        dd = [by_date[(ws + timedelta(days=i)).isoformat()] for i in range(7)]
        plast = next((r for r in reversed(dd) if r["price"] is not None), None)
        rlast = next((r for r in reversed(dd) if r["g100"] is not None), None)
        revs = [r["g100"] for r in dd if r["g100"] is not None]
        isss = [r["iss100"] for r in dd if r["iss100"] is not None]
        n_unobs = sum(1 for r in dd if r["unobserved"])
        n_part = sum(1 for r in dd if r["partial"])
        n_term = sum(1 for r in dd if r["terminated"])
        status = "terminated" if n_term == 7 else ("mixed" if (n_term or n_part) else "active")
        wrows.append({"ws": ws.isoformat(), "we": we.isoformat(),
            "plast": plast, "rlast": rlast,
            "wmean": (sum(revs) / len(revs)) if revs else None,
            "ilast": next((r for r in reversed(dd) if r["iss100"] is not None), None),
            "iwmean": (sum(isss) / len(isss)) if isss else None,
            "n_price": sum(1 for r in dd if r["price"] is not None),
            "n_rev": len(revs), "n_unobs": n_unobs, "n_part": n_part,
            "n_term": n_term, "status": status,
            "lastdate": max(r["date"] for r in dd if r["price"] is not None) if plast else ""})
    for i, wr in enumerate(wrows):
        if i == 0:
            wr["rlog"] = wr["rfrac"] = None
            continue
        prev = wrows[i - 1]
        if wr["plast"] and prev["plast"] and prev["plast"]["price"] and wr["plast"]["price"]:
            a, b = prev["plast"]["price"], wr["plast"]["price"]
            wr["rlog"], wr["rfrac"] = math.log(b / a), b / a - 1.0
        else:
            wr["rlog"] = wr["rfrac"] = None
    with (OUT_DIR / "eth_weekly.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(WEEKLY_COLUMNS)
        for wr in wrows:
            w.writerow([wr["ws"], wr["we"],
                fmt(wr["plast"]["price"]) if wr["plast"] else "",
                wr["plast"]["date"] if wr["plast"] else "",
                fmt(wr["rlast"]["g100"]) if wr["rlast"] else "",
                wr["rlast"]["date"] if wr["rlast"] else "",
                fmt(wr["wmean"]) if wr["wmean"] is not None else "",
                fmt(wr["ilast"]["iss100"]) if wr["ilast"] else "",
                fmt(wr["iwmean"]) if wr["iwmean"] is not None else "",
                fmt(wr["rlog"], 9) if wr["rlog"] is not None else "",
                fmt(wr["rfrac"], 9) if wr["rfrac"] is not None else "",
                7, wr["n_price"], wr["n_rev"], wr["n_unobs"], wr["n_part"],
                wr["n_term"], wr["status"], wr["lastdate"], src_rel, digest])
    n_gross = sum(1 for r in daily if r["g100"] is not None)
    summary = {"grid": {"daily": ["2020-01-01", "2022-12-31"],
        "weekly": ["2020-01-04", "2022-12-30"], "n_weeks": 156,
        "convention": "Saturday-to-Friday"},
        "merge_date": MERGE_DATE.isoformat(), "london_date": LONDON_DATE.isoformat(),
        "rows_daily": len(daily), "rows_weekly": len(wrows),
        "n_rev_gross_days": n_gross,
        "n_partial_days": sum(1 for r in daily if r["partial"]),
        "n_terminated_days": sum(1 for r in daily if r["terminated"]),
        "n_unobserved_days": sum(1 for r in daily if r["unobserved"]),
        "electricity": {"watts": ELEC_W, "kwh_per_day": ELEC_W * 24 / 1000,
            "cost_010_usd_perday": ELEC_COST_010, "cost_020_usd_perday": ELEC_COST_020,
            "note": "fixed assumption, NOT measured RTX figures"},
        "proxy": {"formula_ntv": "IssTotNtv + FeeTotNtv",
            "formula_usd_per100mh": "rev_ntv_proxy * PriceUSD / (HashRate_THS * 1e6) * 100",
            "fee_fully_included_overstates_from": LONDON_DATE.isoformat(),
            "reason": "FeeTotNtv includes EIP-1559 base fees burned; no FeeBurn/FeePrio metric in community tier",
            "iss_only_formula": "IssTotNtv * PriceUSD / (HashRate_THS * 1e6) * 100",
            "iss_only_note": "Fee-excluded sensitivity series, NOT a lower bound; IssTotNtv includes Beacon staking rewards after launch",
            "beacon_issuance_included_from": BEACON_DATE.isoformat(),
            "beacon_breakdown_request": "ETH_CL IssContNtv request returned HTTP 403; no separate series acquired"},
        "source_file": src_rel, "source_sha256": digest,
        "fetch_manifest": manifest}
    (OUT_DIR / "quality_summary.json").write_text(
        json.dumps(summary, indent=1, ensure_ascii=False), encoding="utf-8")
    (OUT_DIR / "sources.json").write_text(json.dumps({
        "coinmetrics_community_api": {
            "root": "https://community-api.coinmetrics.io/v4",
            "endpoint": "/timeseries/asset-metrics", "assets": "eth",
            "frequency": "1d", "metrics": ["PriceUSD", "HashRate",
                "FeeTotNtv", "IssTotNtv", "IssTotUSD"],
            "raw_file": src_rel, "raw_sha256": digest,
            "unavailable_in_community_tier": ["RevUSD", "RevNtv",
                "FeeBurnNtv", "FeePrioTotNtv", "miner/uncle breakdowns"]},
        "definitions": {
            "price": "https://gitbook-docs.coinmetrics.io/network-data/network-data-overview/market/price",
            "issuance": "https://gitbook-docs.coinmetrics.io/network-data/network-data-overview/supply/supply-issuance",
            "hash_rate": "https://gitbook-docs.coinmetrics.io/network-data/network-data-overview/mining/hash-rate",
            "fees": "https://gitbook-docs.coinmetrics.io/network-data/network-data-overview/fees-and-revenue/fees"}},
        indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"daily={len(daily)} weekly={len(wrows)} gross_days={n_gross}")
    print(f"sha={digest}")

if __name__ == "__main__":
    main()
