"""Build the licensed public submission from saved Coin Metrics observations.

Offline. Original PC-part/stock observations are not read or republished here.
Run prepare_eth_mining.py first only when rebuilding the ETH derived CSVs.
"""
import csv
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
ETH = ROOT / "data/processed/2026-10-22/crypto"
OUT = ROOT / "data/public"
FIG = ROOT / "docs/assets/public"
SOURCE = {
    "name": "Coin Metrics Community Data",
    "url": "https://github.com/coinmetrics/data",
    "license": "CC BY-NC 4.0",
    "licenseUrl": "https://creativecommons.org/licenses/by-nc/4.0/",
    "changes": "Saved Community API ETH data filtered to 2020–2022; weekly returns, 30-day mean and fixed-100-MH/s proxies calculated locally.",
}


def make():
    OUT.mkdir(parents=True, exist_ok=True)
    FIG.mkdir(parents=True, exist_ok=True)
    daily = pd.read_csv(ETH / "eth_daily.csv", parse_dates=["date"])
    weekly = pd.read_csv(ETH / "eth_weekly.csv", parse_dates=["week_end"])
    assert len(daily) == 1096 and len(weekly) == 156
    assert daily.price_usd.notna().sum() == 1096
    assert daily.rev_usd_per100mh_gross.notna().sum() == 988
    font = Path("/System/Library/Fonts/Supplemental/AppleGothic.ttf")
    if font.exists():
        plt.rcParams["font.family"] = FontProperties(fname=str(font)).get_name()
    plt.rcParams.update({"axes.unicode_minus": False, "svg.hashsalt": "codyssey-public-eth-20261024",
                         "figure.facecolor": "#fbfcfa", "axes.facecolor": "white",
                         "axes.spines.top": False, "axes.spines.right": False,
                         "font.size": 10, "text.color": "#233a32", "axes.labelcolor": "#233a32"})

    def figure(title, subtitle):
        fig, ax = plt.subplots(figsize=(12, 6.5))
        fig.subplots_adjust(left=.09, right=.97, bottom=.19, top=.78)
        fig.suptitle(title, x=.09, y=.96, ha="left", fontsize=18, weight="bold")
        fig.text(.09, .87, subtitle, fontsize=10)
        fig.text(.09, .085, "출처: Coin Metrics Community Data · CC BY-NC 4.0 · 2026-10-21 UTC 저장본 · 재수집 없음", fontsize=9)
        fig.text(.09, .04, "변경: 2020–2022년 선택·집계·자체 시각화. GPU 가격·실제 카드 채굴 순이익·현재 전망이 아님.", fontsize=9)
        ax.grid(axis="y", alpha=.22)
        ax.set_xlim(daily.date.iloc[0], daily.date.iloc[-1])
        ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=(1, 7)))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
        return fig, ax

    def save(fig, stem):
        fig.savefig(FIG / f"{stem}.png", dpi=150)
        fig.savefig(FIG / f"{stem}.svg", metadata={"Date": "2026-10-24"})
        plt.close(fig)

    fig, ax = figure("ETH 가격과 30일 이동평균", "일별 1,096점 · 달력 30일이 모두 있을 때만 평균 · USD · 역사적 사례")
    ax.plot(daily.date, daily.price_usd, color="#99b7ad", linewidth=.9, label="일별 ETH")
    ma = daily.price_usd.rolling(30, min_periods=30).mean()
    ax.plot(daily.date, ma, color="#1c5947", linewidth=2, label="30일 이동평균")
    ax.set_ylabel("ETH 가격 (USD)")
    ax.set_ylim(bottom=0)
    ax.legend(loc="upper left")
    save(fig, "01_eth_trend")

    fig, ax = figure("ETH 주별 변화율", "토–금 156주 · 인접 두 주 가격이 있는 변화율 155개 · 단순 변화율 × 100")
    returns = weekly.price_return_fraction * 100
    ax.vlines(weekly.week_end, 0, returns, colors=np.where(returns >= 0, "#317862", "#c57943"), linewidth=1.8)
    ax.axhline(0, color="#63736c", linewidth=.8)
    ax.set_ylabel("전주 대비 변화율 (%)")
    save(fig, "02_eth_weekly_returns")

    fig, ax = figure("ETH 네트워크 수익 대용 A·B", "고정 100 MH/s 환산 · 988일 유효 · 머지 부분일과 PoW 종료 뒤에는 값을 만들지 않음")
    ax.plot(daily.date, daily.rev_usd_per100mh_gross, color="#ca8a40", linewidth=1, label="A: 발행+수수료")
    ax.plot(daily.date, daily.iss_usd_per100mh, color="#1c5947", linewidth=1, label="B: 발행만")
    ax.axvspan(pd.Timestamp("2022-09-15"), daily.date.iloc[-1], color="#e7ebe5", label="ETH PoW 해당 없음")
    for when in ("2021-08-05", "2022-09-15"):
        ax.axvline(pd.Timestamp(when), color="#87968d", linestyle="--", linewidth=.8)
    ax.set_ylabel("네트워크 수익 대용 (USD / 100 MH/s / 일)")
    ax.set_ylim(bottom=0)
    ax.legend(loc="upper left")
    save(fig, "03_eth_proxies")

    summaries = []
    for year, frame in daily.groupby(daily.date.dt.year):
        wr = weekly.loc[weekly.week_end.dt.year == year, "price_return_fraction"].dropna()
        summaries.append({"year": int(year), "days": len(frame),
                          "mean_price_usd": round(float(frame.price_usd.mean()), 6),
                          "first_price_usd": float(frame.price_usd.iloc[0]),
                          "last_price_usd": float(frame.price_usd.iloc[-1]),
                          "first_to_last_change_pct": round(float((frame.price_usd.iloc[-1] / frame.price_usd.iloc[0] - 1) * 100), 6),
                          "weekly_return_n": len(wr),
                          "weekly_return_std_pct": round(float(wr.std(ddof=1) * 100), 6)})
    with (OUT / "eth_yearly_summary.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(summaries[0]))
        w.writeheader()
        w.writerows(summaries)

    metrics_path = ROOT / "data/analysis/2026-10-23/forecast/forecast_metrics.csv"
    with metrics_path.open(encoding="utf-8-sig") as f:
        metrics = list(csv.DictReader(f))
    ids = ("US_B07STGGQ18", "US_B07MFZY2F2", "KR_21694499")
    examples = []
    for sid in ids:
        row = next(r for r in metrics if r["id"] == sid)
        item = {k: row[k] for k in ("id", "name")}
        item.update({k: int(row[k]) for k in ("n", "nonoverlapN")})
        item.update({k: float(row[k]) for k in ("brier", "baselineBrier", "mae", "naiveMae", "ece")})
        examples.append(item)
    records = []
    for row in daily.to_dict(orient="records"):
        records.append({"date": row["date"].strftime("%Y-%m-%d"), "price_usd": float(row["price_usd"]),
                        "proxy_a": None if pd.isna(row["rev_usd_per100mh_gross"]) else float(row["rev_usd_per100mh_gross"]),
                        "proxy_b": None if pd.isna(row["iss_usd_per100mh"]) else float(row["iss_usd_per100mh"])})
    dashboard = {"edition": "public-submission", "asOf": "2026-10-24", "source": SOURCE,
                 "series": records,
                 "forecast": {"series": len(metrics), "passed": sum(r["passed"].lower() in ("true", "1") for r in metrics),
                              "predictionRows": sum(int(row['n']) for row in metrics), "examples": examples}}
    (OUT / "dashboard.json").write_text(json.dumps(dashboard, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    stats = {"source": SOURCE, "daily_n": 1096, "weekly_n": 156, "weekly_return_n": 155,
             "moving_average_n": int(ma.notna().sum()), "proxy_valid_n": 988,
             "partial_days": 1, "pow_terminated_days": 107, "years": summaries,
             "inputs_sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                               for p in (ETH / "eth_daily.csv", ETH / "eth_weekly.csv", metrics_path)}}
    (OUT / "eth_analysis.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    make()
