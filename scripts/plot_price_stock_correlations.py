"""Create standalone PNG/SVG figures from the verified analysis tables."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".mplconfig"))
import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
from matplotlib import font_manager
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.patches import Rectangle
import numpy as np
import pandas as pd

from analyze_price_stock_correlations import CONFIG_PATH, DEFAULT_OUTPUT, read_inputs
import json

LABELS = {"AMD": "AMD", "INTC": "Intel", "NVDA": "NVIDIA", "005930": "삼성전자",
          "000660": "SK하이닉스", "MU": "Micron"}
PRODUCTS = {"B07STGGQ18": "CPU · Ryzen 5 3600", "B07MFZY2F2": "SSD · 970 EVO Plus 1TB"}
COLORS = {"AMD": "#3865b8", "INTC": "#b6572c", "NVDA": "#40907e", "005930": "#3865b8",
          "000660": "#b6572c", "MU": "#40907e"}


def setup_style():
    path = Path("/System/Library/Fonts/Supplemental/AppleGothic.ttf")
    if path.exists():
        font_manager.fontManager.addfont(str(path))
        font = font_manager.FontProperties(fname=path).get_name()
    else:
        font = "DejaVu Sans"
    plt.rcParams.update({"font.family": font, "axes.unicode_minus": False,
        "font.size": 11, "axes.titlesize": 14, "axes.labelsize": 11,
        "figure.facecolor": "#fafbfe", "axes.facecolor": "white", "axes.edgecolor": "#d3dae5",
        "axes.labelcolor": "#29384a", "text.color": "#18283d", "xtick.color": "#516176",
        "ytick.color": "#516176", "grid.color": "#e6ebf2", "grid.linewidth": .7,
        "axes.spines.top": False, "axes.spines.right": False, "savefig.dpi": 160,
        "svg.fonttype": "none"})


def save(fig, directory, name, footer):
    fig.text(.018, .018, footer, fontsize=9, color="#516176", va="bottom")
    for extension in ("png", "svg"):
        fig.savefig(directory / f"{name}.{extension}", facecolor=fig.get_facecolor())
    plt.close(fig)


def make_all(output_dir=DEFAULT_OUTPUT):
    setup_style()
    config = json.loads(CONFIG_PATH.read_text())
    prices, stocks, weeks = read_inputs(config)
    dates = pd.to_datetime(weeks)
    stats = pd.read_csv(output_dir / "correlations.csv", dtype={"product_id": str, "symbol": str})
    lags = pd.read_csv(output_dir / "lag_correlations.csv", dtype={"product_id": str, "symbol": str})
    metadata = json.loads((output_dir / "analysis_metadata.json").read_text())
    directory = output_dir / "figures"
    directory.mkdir(exist_ok=True)

    fig, axes = plt.subplots(2, 1, figsize=(15, 9))
    fig.subplots_adjust(left=.075, right=.975, top=.86, bottom=.11, hspace=.40)
    fig.suptitle("부품 가격과 관련 기업 주가의 장기 추이", x=.07, y=.965, ha="left", fontsize=21, weight="bold")
    fig.text(.07, .915, "같은 기준일을 100으로 환산 · 각 선의 움직임을 비교하는 그래프이며 수익률 예측은 아님", fontsize=12)
    for ax, product, base in zip(axes, config["product_order"], metadata["trend_bases"]):
        p = prices.loc[product].loc[weeks]
        anchor = base["common_base_week"]
        if anchor is None:
            ax.text(.5, .5, "공통 기준일 가격 확보 불가", transform=ax.transAxes, ha="center")
            continue
        values = p["price_usd"].copy()
        values.loc[values.index < anchor] = np.nan
        ax.plot(dates, values / p.loc[anchor, "price_usd"] * 100, color="#172b4b", lw=2.6,
                marker=".", ms=3, label=f"부품 가격 (USD, n={p['price_usd'].notna().sum()})", zorder=3)
        for symbol in config["primary_pairs"][product]:
            s = stocks.loc[symbol].loc[weeks, "adjusted_close"].copy()
            s.loc[s.index < anchor] = np.nan
            ax.plot(dates, s / s.loc[anchor] * 100, color=COLORS[symbol], lw=1.6, alpha=.85,
                    label=f"{LABELS[symbol]} 수정주가")
        ax.set_title(f"{PRODUCTS[product]}   |   기준 {anchor} = 100", loc="left")
        ax.set_ylabel("기준일 대비 지수")
        ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1, 7]))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
        ax.grid(axis="y")
        ax.legend(loc="upper left", fontsize=10, ncol=2, frameon=False)
    save(fig, directory, "01_indexed_trends", "출처: PriceHistory·Yahoo Finance | 토~금 마지막 관측 | 부품 결측 구간은 선을 끊음 | 한국 주가는 KRW, 환율 미조정")

    fig, axes = plt.subplots(2, 1, figsize=(13, 6.8))
    fig.subplots_adjust(left=.20, right=.88, top=.82, bottom=.14, hspace=.65)
    fig.suptitle("가격 수준과 주별 변화율은 다른 결과를 보인다", x=.065, y=.96, ha="left", fontsize=20, weight="bold")
    for ax, metric, nfield, title in zip(axes, ["level_pearson", "return_pearson"], ["n_level", "n_return"],
        ["가격 수준의 Pearson r · 장기 추세의 영향 포함", "주별 로그 변화율의 Pearson r · 동시 상관"]):
        matrix = stats.pivot(index="product_id", columns="symbol", values=metric).reindex(index=config["product_order"], columns=config["stock_order"])
        counts = stats.pivot(index="product_id", columns="symbol", values=nfield).reindex_like(matrix)
        im = ax.imshow(matrix, cmap="RdBu_r", vmin=-1, vmax=1, aspect="auto")
        ax.set_xticks(range(6), [LABELS[s] for s in config["stock_order"]])
        ax.set_yticks(range(2), ["CPU · Ryzen 3600", "SSD · 970 EVO Plus"])
        ax.set_title(title, loc="left", pad=13)
        for i in range(2):
            for j in range(6):
                value = matrix.iloc[i, j]
                text = f"{value:+.3f}\nn={int(counts.iloc[i, j])}" if np.isfinite(value) else "자료 부족"
                ax.text(j, i, text, ha="center", va="center", fontsize=11,
                        color="white" if abs(value) > .6 else "#18283d")
    cax = fig.add_axes([.915, .2, .018, .57])
    fig.colorbar(im, cax=cax, label="Pearson r", ticks=[-1, -.5, 0, .5, 1])
    save(fig, directory, "02_correlations", "셀의 n은 두 값이 동시에 있는 주 수 | 가격·주가 수준의 높은 상관은 인과관계나 예측력을 뜻하지 않음")

    fig, axes = plt.subplots(2, 3, figsize=(16, 9))
    fig.subplots_adjust(left=.065, right=.975, top=.85, bottom=.12, hspace=.48, wspace=.28)
    fig.suptitle("실제 주별 변화율의 관계", x=.065, y=.965, ha="left", fontsize=21, weight="bold")
    fig.text(.065, .915, "점 하나가 같은 주의 가격·주가 변화율 한 쌍 · CI는 4주 블록 부트스트랩의 개별 95% 구간", fontsize=12)
    for i, product in enumerate(config["product_order"]):
        p = prices.loc[product].loc[weeks, "log_return"].to_numpy()
        for j, symbol in enumerate(config["primary_pairs"][product]):
            ax = axes[i, j]
            s = stocks.loc[symbol].loc[weeks, "return_log"].to_numpy()
            good = np.isfinite(p) & np.isfinite(s)
            row = stats[(stats["product_id"] == product) & (stats["symbol"] == symbol)].iloc[0]
            ax.scatter(p[good] * 100, s[good] * 100, s=25, color=COLORS[symbol], alpha=.65, edgecolors="white", linewidths=.3)
            if good.sum() > 2 and np.std(p[good]) > 0:
                slope, intercept = np.polyfit(p[good] * 100, s[good] * 100, 1)
                xs = np.array([p[good].min(), p[good].max()]) * 100
                ax.plot(xs, intercept + slope * xs, color="#172b4b", lw=1.3)
            ax.axhline(0, color="#aab7c9", lw=.7)
            ax.axvline(0, color="#aab7c9", lw=.7)
            ax.set_title(f"{PRODUCTS[product].split(' · ')[0]} × {LABELS[symbol]}", loc="left")
            ax.text(.03, .97, f"r={row.return_pearson:+.3f} · n={int(row.n_return)}\n95% CI [{row.return_ci_low_block4:+.3f}, {row.return_ci_high_block4:+.3f}]",
                    transform=ax.transAxes, va="top", fontsize=10,
                    bbox={"facecolor": "white", "edgecolor": "none", "alpha": .88, "pad": 3})
            ax.set_xlabel("부품 가격 로그 변화율 × 100")
            ax.set_ylabel("수정주가 로그 변화율 × 100")
            ax.grid(alpha=.5)
    save(fig, directory, "03_return_scatter", "직선은 표본 내 선형 관계 표시 | CI는 시차·기업 전체를 동시에 보장하는 구간이 아님 | 2020-01-10~2022-12-30")

    fig, axes = plt.subplots(2, 1, figsize=(18, 11.5))
    fig.subplots_adjust(left=.12, right=.93, top=.87, bottom=.12, hspace=.38)
    fig.suptitle("시차별 변화율 상관 · -8주부터 +8주까지", x=.055, y=.965, ha="left", fontsize=22, weight="bold")
    fig.text(.055, .92, "r(부품 변화율[t], 주가 변화율[t-L])   |   +L: 주가가 먼저 · -L: 부품 가격이 먼저   |   셀은 r과 실제 n", fontsize=12)
    lag_values = list(range(-8, 9))
    for ax, product in zip(axes, config["product_order"]):
        group = lags[lags["product_id"] == product]
        matrix = group.pivot(index="symbol", columns="lag_weeks", values="pearson").reindex(index=config["stock_order"], columns=lag_values)
        counts = group.pivot(index="symbol", columns="lag_weeks", values="n").reindex_like(matrix)
        im = ax.imshow(matrix, cmap="RdBu_r", vmin=-.5, vmax=.5, aspect="auto")
        ax.set_title(PRODUCTS[product], loc="left", pad=12)
        ax.set_xticks(range(17), [f"{v:+d}" if v else "0" for v in lag_values])
        ax.set_yticks(range(6), [LABELS[s] for s in config["stock_order"]])
        ax.add_patch(Rectangle((7.5, -.5), 1, 6, fill=False, ec="#172b4b", lw=1.4))
        for i in range(6):
            for j in range(17):
                value = matrix.iloc[i, j]
                text = f"{value:+.2f}\nn={int(counts.iloc[i, j])}" if np.isfinite(value) else "n/a"
                ax.text(j, i, text, ha="center", va="center", fontsize=8.4,
                        color="white" if abs(value) > .31 else "#18283d")
        ax.set_xlabel("시차 L (주)")
    cax = fig.add_axes([.945, .16, .012, .64])
    fig.colorbar(im, cax=cax, label="Pearson r", ticks=[-.5, 0, .5], extend="both")
    save(fig, directory, "04_lag_correlations", "그리드를 유지한 후 시차 적용 · 결측을 제거하고 행 번호를 밀지 않음 | 204개 조합의 최대값은 탐색 결과이며 예측 검증 결과가 아님")

    fig, ax = plt.subplots(figsize=(16, 6.8))
    fig.subplots_adjust(left=.18, right=.975, top=.80, bottom=.18)
    fig.suptitle("실제로 관측된 주와 빠진 주", x=.055, y=.96, ha="left", fontsize=21, weight="bold")
    fig.text(.055, .905, "파랑: 사용 가능 · 회색: 결측 또는 첫 주의 변화율 없음 · 공란을 전 주 값으로 채우지 않음", fontsize=12)
    masks, labels = [], []
    for product in config["product_order"]:
        p = prices.loc[product].loc[weeks]
        short = "CPU" if product == config["product_order"][0] else "SSD"
        for field, label in (("price_usd", "가격"), ("log_return", "변화율")):
            mask = p[field].notna().to_numpy()
            masks.append(mask)
            labels.append(f"{short} {label}  {int(mask.sum())}/156")
    for symbol in config["stock_order"]:
        mask = stocks.loc[symbol].loc[weeks, "return_log"].notna().to_numpy()
        masks.append(mask)
        labels.append(f"{LABELS[symbol]} 변화율  {int(mask.sum())}/156")
    ax.imshow(np.array(masks, dtype=int), cmap=ListedColormap(["#e1e5eb", "#3566a8"]), vmin=0, vmax=1, aspect="auto", interpolation="nearest")
    ax.set_yticks(range(len(labels)), labels)
    ticks = [i for i, w in enumerate(weeks) if w[:7] in ("2020-01", "2020-07", "2021-01", "2021-07", "2022-01", "2022-07") and (i == 0 or weeks[i - 1][:7] != w[:7])]
    ax.set_xticks(ticks, [weeks[i][:7] for i in ticks])
    ax.set_xlabel("주 종료일 (금요일)")
    save(fig, directory, "05_missing_coverage", "변화율 기회는 최대 155개 | 부품 결측은 다음 주 변화율에도 영향 | 주가의 파랑은 주 안의 유효값 존재를 뜻함. 마지막 거래일 누락은 별도 감사")
    print(f"Created 5 PNG + 5 SVG figures: {directory}")


if __name__ == "__main__":
    make_all()
