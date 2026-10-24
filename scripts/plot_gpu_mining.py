"""Standalone scientific figures; observation gaps and PoW termination stay visible."""
import calendar
import json
import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/codyssey-matplotlib")
import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
import numpy as np
import pandas as pd

from plot_price_stock_correlations import setup_style, save
from analyze_gpu_mining import OUT, PROCESSED, METRICS

COLORS = {"3070": "#3865b8", "3080": "#b6572c", "3090": "#40907e"}
LABELS = {"3070": "RTX 3070", "3080": "RTX 3080 10GB", "3090": "RTX 3090"}
MERGE = pd.Timestamp("2022-09-15")
LONDON = pd.Timestamp("2021-08-05")


def events(ax, london=True, label=False):
    if london:
        ax.axvline(LONDON, color="#987c3c", ls=":", lw=1.1, alpha=.75)
    ax.axvline(MERGE, color="#733d62", ls="--", lw=1.2, alpha=.8)
    if label:
        if london:
            ax.text(LONDON, .95, "런던", transform=ax.get_xaxis_transform(), ha="center", va="top", fontsize=9)
        ax.text(MERGE, .95, "머지", transform=ax.get_xaxis_transform(), ha="center", va="top", fontsize=9)


def dates(ax, start="2020-01-01", end="2023-01-01"):
    ax.set_xlim(pd.Timestamp(start), pd.Timestamp(end))
    ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1, 7]))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax.grid(axis="y", alpha=.8)


def make_all(output_dir=OUT):
    setup_style()
    directory = output_dir / "figures"
    directory.mkdir(exist_ok=True)
    snapshot = pd.read_csv(output_dir / "aligned_snapshots.csv", dtype={"series_id": str})
    monthly = pd.read_csv(output_dir / "aligned_monthly.csv", dtype={"gpu": str})
    weekly = pd.read_csv(PROCESSED / "gpu_retail/weekly_retail.csv", dtype={"series_id": str})
    daily = pd.read_csv(PROCESSED / "crypto/eth_daily.csv")
    dw = pd.read_csv(PROCESSED / "crypto/eth_weekly.csv")
    changes = pd.read_csv(output_dir / "price_changes.csv", dtype={"series_id": str})

    fig, axes = plt.subplots(4, 1, figsize=(16, 13))
    fig.subplots_adjust(left=.085, right=.97, top=.89, bottom=.09, hspace=.55)
    fig.suptitle("GPU 가격과 이더리움 · 확보한 기간부터 확인", x=.07, y=.97, ha="left", fontsize=22, weight="bold")
    fig.text(.07, .933, "소매 EUR · eBay USD를 분리 | 점은 실제 집계·관측 | 선은 관측 사이의 안내선 | 수익 지표는 고정 100MH/s 가정", fontsize=11)
    for identity in LABELS:
        group = snapshot[(snapshot.series_id == identity) & snapshot.value.notna()]
        axes[0].plot(pd.to_datetime(group.observation_date), group.value, ".--", lw=1, ms=6,
            color=COLORS[identity], label=f"{LABELS[identity]} · n={len(group)}")
        group = monthly[(monthly.gpu == identity) & monthly.price_usd.notna()]
        axes[3].plot(pd.to_datetime(group.month + "-15"), group.price_usd, ".-", lw=1.5, ms=5,
            color=COLORS[identity], label=f"{LABELS[identity]} · n={len(group)}개월")
    axes[0].set_ylabel("가용 최저 호가 (EUR)")
    axes[0].set_title("독일 소매 호가 · 2020년과 머지 이후 수치 관측 없음", loc="left")
    axes[0].axvspan(pd.Timestamp("2020-01-01"), pd.Timestamp("2021-01-17"), color="#e9ecf2", alpha=.7)
    axes[0].axvspan(pd.Timestamp("2022-09-12"), pd.Timestamp("2023-01-01"), color="#e9ecf2", alpha=.7)
    axes[0].legend(frameon=False, ncol=3, fontsize=10, loc="upper right")
    axes[1].plot(pd.to_datetime(daily.date), daily.price_usd, color="#172b4b", lw=1.1)
    axes[1].set_ylabel("ETH 가격 (USD)")
    axes[1].set_title(f"이더리움 가격 · 유효 {daily.price_usd.notna().sum():,}일", loc="left")
    # Use seven-day arithmetic means only when all seven days are present.
    rawfee = daily.rev_usd_per100mh_gross.rolling(7, min_periods=7).mean()
    rawiss = daily.iss_usd_per100mh.rolling(7, min_periods=7).mean()
    axes[2].plot(pd.to_datetime(daily.date), rawfee, color="#b6572c", lw=1.3, label="발행량 + 총수수료 대용")
    axes[2].plot(pd.to_datetime(daily.date), rawiss, color="#3865b8", lw=1.3, label="발행량만 사용한 대용")
    axes[2].set_ylabel("USD / 일 / 100MH/s")
    axes[2].set_title("네트워크 수익 대용 · 7일 평균 · PoS 발행 혼입 / 런던 이후 소각 수수료 포함", loc="left")
    axes[2].axvspan(MERGE, pd.Timestamp("2023-01-01"), color="#f0dfd0", alpha=.65)
    axes[2].text(pd.Timestamp("2022-11-06"), .70, "ETH PoW 종료\n수익 지표 해당 없음", ha="center", fontsize=10,
        transform=axes[2].get_xaxis_transform())
    axes[2].legend(frameon=False, fontsize=10, loc="upper left")
    axes[3].set_ylabel("월별 평균 판매가격 (USD)")
    axes[3].set_title("미국 eBay 판매가격 · 월별 집계 · 주별로 늘리지 않음", loc="left")
    axes[3].legend(frameon=False, ncol=3, fontsize=10)
    for ax in axes:
        dates(ax)
        events(ax)
    axes[3].set_xlabel("관측·집계 날짜")
    save(fig, directory, "01_gpu_eth_timeline", "출처: 3DCenter · Tom's Hardware/eBay · Coin Metrics | 네트워크 지표는 카드별 실측 순이익이 아님 | 결측·종료 후 값을 보간하지 않음")

    fig, axes = plt.subplots(3, 1, figsize=(15, 11.5))
    fig.subplots_adjust(left=.08, right=.97, top=.86, bottom=.10, hspace=.46)
    fig.suptitle("같은 실제 관측 시점에 맞춘 상대 변화", x=.065, y=.97, ha="left", fontsize=21, weight="bold")
    fig.text(.065, .927, "GPU 가격: 조사 당일 | ETH·수익 대용: 전날까지 7일 평균 | 각 제품의 첫 유효 관측 = 100", fontsize=11)
    fig.text(.065, .895, "점 사이의 간격은 주로 3주. 이 선의 변화는 주별 변화율이 아님", fontsize=11, color="#733d62")
    for ax, identity in zip(axes, LABELS):
        group = snapshot[(snapshot.series_id == identity) & snapshot.value.notna()].sort_values("observation_date")
        ds = pd.to_datetime(group.observation_date)
        for field, color, label in (("value", "#172b4b", "GPU 소매 호가"),
                ("eth_price_7d", "#40907e", "ETH 가격"), ("fees_included_proxy_7d", "#b6572c", "발행량 + 총수수료 대용"),
                ("fees_excluded_proxy_7d", "#3865b8", "발행량 대용")):
            ax.plot(ds, group[field] / group.iloc[0][field] * 100, ".-", color=color, lw=1.25, ms=5, label=label)
        ax.set_title(f"{LABELS[identity]} · 실제 n={len(group)} · 기준 {group.iloc[0].observation_date}", loc="left")
        ax.set_ylabel("기준일 = 100")
        dates(ax, "2021-01-01", "2022-10-01")
        events(ax, label=True)
        ax.legend(frameon=False, ncol=2, fontsize=9)
    save(fig, directory, "02_matched_observations", "관측 간격·통화·소매점 구성이 다름 | 수준 상관은 장기 추세를 포함하며 인과관계를 뜻하지 않음 | 총수수료 대용은 소각 수수료 과대포함")

    fig, axes = plt.subplots(1, 3, figsize=(16, 5.8))
    fig.subplots_adjust(left=.065, right=.975, top=.77, bottom=.19, wspace=.28)
    fig.suptitle("머지 전후의 GPU 가격 · 월별 판매가격으로 비교", x=.055, y=.96, ha="left", fontsize=20, weight="bold")
    fig.text(.055, .89, "전: 2022년 7~8월 평균 / 후: 10~11월 평균 | 9월은 전환을 포함한 혼합 월 | 각 구간 표본은 2개월", fontsize=11)
    for ax, identity in zip(axes, LABELS):
        group = monthly[(monthly.gpu == identity) & monthly.price_usd.notna()].sort_values("month")
        change = changes[(changes.series_id == identity) & (changes.comparison == "premerge_Jul_Aug_vs_postmerge_Oct_Nov")].iloc[0]
        ax.plot(pd.to_datetime(group.month + "-15"), group.price_usd, "o-", lw=1.5, ms=4.5, color=COLORS[identity])
        for begin, end, color in (("2022-07-01", "2022-09-01", "#d7e9f6"),
                ("2022-09-01", "2022-10-01", "#f4e2bf"), ("2022-10-01", "2022-12-01", "#dcecdf")):
            ax.axvspan(pd.Timestamp(begin), pd.Timestamp(end), color=color, alpha=.65)
        ax.set_title(f"{LABELS[identity]}\n전 {change.before_value:,.0f} → 후 {change.after_value:,.0f} USD ({change.change_fraction:+.1%})", loc="left", fontsize=12)
        ax.set_ylabel("eBay 월별 평균가격 (USD)")
        ax.set_xlim(pd.Timestamp("2021-08-15"), pd.Timestamp("2023-01-01"))
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
        ax.tick_params(axis="x", labelrotation=25)
        ax.grid(axis="y")
        events(ax, london=False)
    save(fig, directory, "03_merge_monthly_prices", "가격은 머지 이전부터 하락 | 전후 차이는 기술 통계이며 머지만의 효과가 아님 | 신품·중고·LHR·판매자 구성 변화 통제 불가")

    fig, axes = plt.subplots(2, 1, figsize=(16, 8.4), gridspec_kw={"height_ratios": [5, 3]})
    fig.subplots_adjust(left=.21, right=.975, top=.81, bottom=.13, hspace=.65)
    fig.suptitle("관측 수와 빈 기간 · 촘촘한 암호화폐 자료가 GPU 결측을 채우지는 않는다", x=.045, y=.96, ha="left", fontsize=18, weight="bold")
    fig.text(.045, .902, "파랑: 실관측·전체 기간 유효 / 회색: 미확보 / 황색: 머지 포함 주 / 살구색: ETH PoW 종료", fontsize=11)
    masks, labels = [], []
    for identity in LABELS:
        w = weekly[weekly.series_id == identity].sort_values("week_end")
        n = int(w.value.notna().sum())
        masks.append(w.value.notna().to_numpy(dtype=int))
        labels.append(f"{LABELS[identity]}   {n}/156주")
    masks.append((dw.n_price_days == 7).to_numpy(dtype=int))
    labels.append(f"ETH 가격   {int((dw.n_price_days == 7).sum())}/156주")
    mining = np.where(dw.n_rev_days == 7, 1, np.where(dw.partial_days > 0, 2, np.where(dw.pow_terminated_days == 7, 3, 0)))
    masks.append(mining)
    labels.append(f"수익 대용   {int((dw.n_rev_days == 7).sum())}/156주")
    cmap = ListedColormap(["#e1e5eb", "#3566a8", "#e8c16a", "#e7bf9c"])
    axes[0].imshow(np.array(masks), aspect="auto", interpolation="nearest", cmap=cmap, vmin=0, vmax=3)
    axes[0].set_yticks(range(5), labels)
    weeklabels = dw.week_end.tolist()
    ticks = [0, 26, 52, 78, 104, 130, 155]
    axes[0].set_xticks(ticks, [weeklabels[i][:7] for i in ticks])
    axes[0].set_title("토~금 주별 그리드 · 빈칸은 가격을 확보하지 못한 주", loc="left", fontsize=12)
    axes[0].set_xlabel("주 종료일")
    mmasks, mlabels = [], []
    allmonths = pd.period_range("2020-01", "2022-12", freq="M").astype(str)
    for identity in LABELS:
        m = monthly[monthly.gpu == identity].set_index("month").reindex(allmonths)
        mmasks.append(m.price_usd.notna().to_numpy(dtype=int))
        mlabels.append(f"{LABELS[identity]}   {int(m.price_usd.notna().sum())}/36개월")
    axes[1].imshow(np.array(mmasks), aspect="auto", interpolation="nearest", cmap=cmap, vmin=0, vmax=3)
    axes[1].set_yticks(range(3), mlabels)
    ticks = [0, 6, 12, 18, 24, 30, 35]
    axes[1].set_xticks(ticks, [allmonths[i] for i in ticks])
    axes[1].set_title("eBay 월별 그리드 · 1개월을 여러 주의 실관측으로 복제하지 않음", loc="left", fontsize=12)
    axes[1].set_xlabel("실제 판매 월")
    save(fig, directory, "04_observation_coverage", "소매 주별 변화율 유효 표본: RTX3070 1개 · RTX3080 0개 · RTX3090 1개 | 관측 간 변화율·월별 변화율과 구분")
    print(f"Created 4 PNG + 4 SVG figures: {directory}")


if __name__ == "__main__":
    make_all()
