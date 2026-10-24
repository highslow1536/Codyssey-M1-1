"""Checks for the ETH PoW mining-proxy normalization contract."""
import csv
import hashlib
import math
from datetime import date, timedelta
from pathlib import Path
import unittest
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/processed/2026-10-22/crypto"
RAW = ROOT / "data/verification/2026-10-22/crypto/cm_eth_daily_raw.json"
EXPECTED_DAILY = ["date", "price_usd", "hashrate_ths", "fee_tot_ntv",
    "iss_tot_ntv", "iss_tot_usd", "rev_ntv_proxy", "rev_usd_proxy",
    "rev_usd_per100mh_gross", "rev_usd_per100mh_7d",
    "elec_usd_perday_010", "elec_usd_perday_020",
    "net_usd_per100mh_010", "net_usd_per100mh_020",
    "iss_usd_per100mh", "iss_usd_per100mh_7d",
    "london_burn_overincluded", "beacon_issuance_included", "is_partial_transition",
    "pow_terminated", "unobserved", "source_file", "source_sha256"]
EXPECTED_WEEKLY = ["week_start", "week_end", "price_usd_last", "price_date",
    "rev_usd_per100mh_last", "rev_date_last", "rev_usd_per100mh_week_mean",
    "iss_usd_per100mh_last", "iss_usd_per100mh_week_mean",
    "price_return_log", "price_return_fraction", "n_days", "n_price_days",
    "n_rev_days", "unobserved_days", "partial_days", "pow_terminated_days",
    "pow_status", "lastdate", "source_file", "source_sha256"]
EXPECTED_WEEKS = [(date(2020, 1, 4) + timedelta(days=7 * k)).isoformat() for k in range(156)]
def read(name):
    with (OUT / name).open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))
class EthMiningTest(unittest.TestCase):
    def test_grid_shapes(self):
        d = read("eth_daily.csv")
        w = read("eth_weekly.csv")
        self.assertEqual(len(d), 1096)
        self.assertEqual(list(d[0].keys()), EXPECTED_DAILY)
        self.assertEqual(d[0]["date"], "2020-01-01")
        self.assertEqual(d[-1]["date"], "2022-12-31")
        self.assertEqual(len(w), 156)
        self.assertEqual(list(w[0].keys()), EXPECTED_WEEKLY)
        self.assertEqual([x["week_start"] for x in w], EXPECTED_WEEKS)
        self.assertEqual(w[0]["week_end"], "2020-01-10")
        self.assertEqual(w[-1]["week_end"], "2022-12-30")
    def test_merge_boundary(self):
        d = {r["date"]: r for r in read("eth_daily.csv")}
        # transition day: price kept, revenue excluded, flagged partial
        t = d["2022-09-15"]
        self.assertEqual(t["is_partial_transition"], "1")
        self.assertEqual(t["pow_terminated"], "0")
        self.assertNotEqual(t["price_usd"], "")
        self.assertEqual(t["rev_usd_per100mh_gross"], "")
        self.assertEqual(t["iss_usd_per100mh"], "")
        # pre-merge last day present
        self.assertNotEqual(d["2022-09-14"]["rev_usd_per100mh_gross"], "")
        # post-merge: revenue not-applicable (empty) but price present;
        # never zero-filled
        for k in ("2022-09-16", "2022-10-01", "2022-12-31"):
            self.assertEqual(d[k]["pow_terminated"], "1")
            self.assertEqual(d[k]["rev_usd_per100mh_gross"], "")
            self.assertNotEqual(d[k]["price_usd"], "")
        gross = [r for r in d.values() if r["rev_usd_per100mh_gross"] != ""]
        self.assertEqual(len(gross), 988)  # 2020-01-01..2022-09-14
        self.assertTrue(all(r["unobserved"] == "0" for r in d.values()))
    def test_formula_recomputation(self):
        d = {r["date"]: r for r in read("eth_daily.csv")}
        for k in ("2020-01-01", "2021-01-17", "2021-08-05", "2022-09-14"):
            r = d[k]
            price, hr = float(r["price_usd"]), float(r["hashrate_ths"])
            rev_ntv = float(r["iss_tot_ntv"]) + float(r["fee_tot_ntv"])
            self.assertAlmostEqual(float(r["rev_ntv_proxy"]), rev_ntv, places=4)
            exp = rev_ntv * price / (hr * 1e6) * 100.0
            self.assertAlmostEqual(float(r["rev_usd_per100mh_gross"]), exp, places=5)
            exp_iss = float(r["iss_tot_ntv"]) * price / (hr * 1e6) * 100.0
            self.assertAlmostEqual(float(r["iss_usd_per100mh"]), exp_iss, places=5)
            # fee-excluded proxy never exceeds fee-fully-included proxy
            self.assertLessEqual(float(r["iss_usd_per100mh"]),
                                 float(r["rev_usd_per100mh_gross"]))
            self.assertAlmostEqual(float(r["net_usd_per100mh_010"]),
                float(r["rev_usd_per100mh_gross"]) - 0.48, places=5)
            self.assertAlmostEqual(float(r["net_usd_per100mh_020"]),
                float(r["rev_usd_per100mh_gross"]) - 0.96, places=5)
        # burn-overinclusion flag only where a revenue value exists post-London
        self.assertEqual(d["2021-01-17"]["london_burn_overincluded"], "0")
        self.assertEqual(d["2021-08-05"]["london_burn_overincluded"], "1")
        self.assertEqual(d["2022-09-15"]["london_burn_overincluded"], "0")
        self.assertEqual(d["2020-01-01"]["beacon_issuance_included"], "0")
        self.assertEqual(d["2021-01-17"]["beacon_issuance_included"], "1")
    def test_trailing_7d(self):
        d = read("eth_daily.csv")
        by = {r["date"]: r for r in d}
        for r in d[:6]:
            self.assertEqual(r["rev_usd_per100mh_7d"], "")
            self.assertEqual(r["iss_usd_per100mh_7d"], "")
        win = [float(by[(date(2021, 1, 11) + timedelta(days=i)).isoformat()]["rev_usd_per100mh_gross"]) for i in range(7)]
        self.assertAlmostEqual(float(by["2021-01-17"]["rev_usd_per100mh_7d"]), sum(win) / 7, places=6)
        # 7d window touching the transition day stays empty (no partial data)
        for k in ("2022-09-15", "2022-09-16", "2022-09-20"):
            self.assertEqual(by[k]["rev_usd_per100mh_7d"], "")
    def test_weekly_merge_and_returns(self):
        w = read("eth_weekly.csv")
        self.assertEqual(w[0]["price_return_log"], "")
        self.assertEqual(w[0]["price_return_fraction"], "")
        prev = None
        for row in w:
            if prev is not None and row["price_usd_last"] and prev["price_usd_last"]:
                a, b = float(prev["price_usd_last"]), float(row["price_usd_last"])
                self.assertAlmostEqual(float(row["price_return_log"]), math.log(b / a), places=6)
                self.assertAlmostEqual(float(row["price_return_fraction"]), b / a - 1.0, places=6)
            prev = row
        mixed = [r for r in w if r["week_start"] == "2022-09-10"][0]
        self.assertEqual(mixed["pow_status"], "mixed")
        self.assertEqual(mixed["n_rev_days"], "5")
        self.assertEqual(mixed["rev_date_last"], "2022-09-14")
        self.assertNotEqual(mixed["price_usd_last"], "")
        stats = [r["pow_status"] for r in w]
        self.assertEqual(stats.count("active"), 140)
        self.assertEqual(stats.count("mixed"), 1)
        self.assertEqual(stats.count("terminated"), 15)
        term = [r for r in w if r["pow_status"] == "terminated"]
        self.assertTrue(all(r["rev_usd_per100mh_week_mean"] == "" for r in term))
        self.assertTrue(all(r["price_usd_last"] != "" for r in term))
    def test_hashes_and_sources(self):
        digest = hashlib.sha256(RAW.read_bytes()).hexdigest()
        for name in ("eth_daily.csv", "eth_weekly.csv"):
            for r in read(name):
                self.assertEqual(r["source_sha256"], digest)
if __name__ == "__main__":
    unittest.main()
