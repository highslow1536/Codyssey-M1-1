#!/usr/bin/env python3
# 과제 문서용 시각자료 6종 생성 스크립트 (신규, 오프라인 전용).
# 허용 입력만 읽는다: domestic_expanded.csv, forecast_metrics/predictions.csv,
# docs/forecast_protocol.md, data/processed/2026-10-23/recent/README.md, REPORT.md.
# AppleGothic 폰트, 흰바탕 + 남색/초록/주황 일관색, 폭 1500px PNG + SVG.
import csv
import hashlib
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from matplotlib.ticker import FuncFormatter
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "assets" / "figures"
FONT_PATH = "/System/Library/Fonts/Supplemental/AppleGothic.ttf"
SVG_META = {"Date": "2026-10-24", "Creator": "plot_documentation_figures.py"}
DPI = 150
NAVY = "#1E3A5F"
GREEN = "#2E9E6B"
ORANGE = "#E8833A"
LIGHT_BLUE = "#DCE6F2"
LIGHT_GREEN = "#D9EFE4"
LIGHT_ORANGE = "#FBE7D3"
INK = "#222222"
SUB = "#555555"
def setup_font():
    fp = fm.FontProperties(fname=FONT_PATH)
    plt.rcParams["font.family"] = fp.get_name()
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["svg.hashsalt"] = "codyssey-documentation-2026-10-24"
def save(fig, stem):
    OUT.mkdir(parents=True, exist_ok=True)
    png = OUT / (stem + ".png")
    svg = OUT / (stem + ".svg")
    fig.savefig(png, dpi=DPI)
    try:
        fig.savefig(svg, format="svg", metadata=dict(SVG_META))
    except TypeError:
        fig.savefig(svg, format="svg")
    plt.close(fig)
    return [str(png.relative_to(ROOT)), str(svg.relative_to(ROOT))]
def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()
def comma(v, _=None):
    return format(int(v), ",")
def fig01_flow():
    top = [
        ("1 수집", "공개 가격", "CSV와 스냅샷"),
        ("2 가격정의 감사", "SKU와 통화", "조건 분리"),
        ("3 결측유지 집계", "이월과 보간", "하지 않음"),
    ]
    bottom = [
        ("6 대시보드와 리포트", "스냅샷과", "재현근거 공개"),
        ("5 시간순 예측검증", "분기 재학습", "미래차단"),
        ("4 추이와 사건 비교", "지수와 시차", "머지 전후"),
    ]
    fig, ax = plt.subplots(figsize=(10, 6.0))
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    fig.suptitle("분석 흐름 (설명용 개념도)", fontsize=18, fontweight="bold", y=0.97)
    ax.text(0.5, 0.865, "수집부터 리포트까지 한 방향으로 진행하며, 이후 정보가 이전 단계로 새지 않게 차단한다.",
            ha="center", va="center", fontsize=12, color=SUB)
    bw, bh = 0.27, 0.20
    xs = [0.045, 0.365, 0.685]
    y_top, y_bot = 0.62, 0.26
    for i, (title, d1, d2) in enumerate(top):
        x = xs[i]
        y0 = y_top
        box = FancyBboxPatch((x, y0), bw, bh, boxstyle="round,pad=0.008",
                             facecolor="white", edgecolor=NAVY, linewidth=2.2)
        ax.add_patch(box)
        ax.text(x + bw / 2, y0 + bh - 0.055, title, ha="center", va="center",
                fontsize=14, fontweight="bold", color=NAVY)
        ax.text(x + bw / 2, y0 + 0.075, d1, ha="center", va="center",
                fontsize=12, color=SUB)
        ax.text(x + bw / 2, y0 + 0.035, d2, ha="center", va="center",
                fontsize=12, color=SUB)
    for i, (title, d1, d2) in enumerate(bottom):
        x = xs[i]
        y0 = y_bot
        box = FancyBboxPatch((x, y0), bw, bh, boxstyle="round,pad=0.008",
                             facecolor="white", edgecolor=NAVY, linewidth=2.2)
        ax.add_patch(box)
        ax.text(x + bw / 2, y0 + bh - 0.055, title, ha="center", va="center",
                fontsize=14, fontweight="bold", color=NAVY)
        ax.text(x + bw / 2, y0 + 0.075, d1, ha="center", va="center",
                fontsize=12, color=SUB)
        ax.text(x + bw / 2, y0 + 0.035, d2, ha="center", va="center",
                fontsize=12, color=SUB)
    yc_top = y_top + bh / 2
    for i in range(2):
        a = FancyArrowPatch((xs[i] + bw + 0.005, yc_top), (xs[i + 1] - 0.005, yc_top),
                            arrowstyle="-|>", mutation_scale=18, color=NAVY, linewidth=2.2)
        ax.add_patch(a)
    xc = xs[2] + bw / 2
    d = FancyArrowPatch((xc, y_top - 0.006), (xc, y_bot + bh + 0.006),
                        arrowstyle="-|>", mutation_scale=18, color=NAVY, linewidth=2.2)
    ax.add_patch(d)
    yc_bot = y_bot + bh / 2
    for i in [2, 1]:
        b = FancyArrowPatch((xs[i] - 0.005, yc_bot), (xs[i - 1] + bw + 0.005, yc_bot),
                            arrowstyle="-|>", mutation_scale=18, color=NAVY, linewidth=2.2)
        ax.add_patch(b)
    ax.text(0.5, 0.12, "원칙 3가지: 결측은 유지한다  |  다른 정의는 이어붙이지 않는다  |  검증 실패도 삭제하지 않는다",
            ha="center", va="center", fontsize=12, color=INK,
            bbox=dict(boxstyle="round,pad=0.4", facecolor=LIGHT_BLUE, edgecolor=NAVY))
    fig.text(0.02, 0.015, "출처: 허용 입력 목록(REPORT.md, forecast_protocol.md 등) 기반 정리. 설명용 개념도이며 수치 주장이 아님.",
             fontsize=10, color=SUB, wrap=True, ha="left", va="bottom")
    fig.tight_layout(rect=[0, 0.06, 1, 0.90])
    return save(fig, "01_analysis_flow")
def fig02_coverage():
    cats = ["과거 CPU(156주)", "과거 SSD(156주)", "최근 CPU(198주)", "최근 SSD(198주)"]
    obs = [148, 135, 158, 173]
    miss = [8, 21, 40, 25]
    fig, ax = plt.subplots(figsize=(10, 5.6))
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    x = list(range(len(cats)))
    b1 = ax.bar(x, obs, color=NAVY, edgecolor="white", label="관측주")
    b2 = ax.bar(x, miss, bottom=obs, color="#C3CDD8", edgecolor="white", label="결측주(미관측)")
    for i in x:
        ax.text(i, obs[i] / 2, "관측 " + str(obs[i]), ha="center", va="center",
                fontsize=13, fontweight="bold", color="white")
        ax.text(i, obs[i] + miss[i] + 3, "결측 " + str(miss[i]), ha="center", va="bottom",
                fontsize=12, color=INK)
    ax.set_xticks(x)
    ax.set_xticklabels(cats, fontsize=12)
    ax.set_ylabel("주(week)", fontsize=13)
    ax.set_ylim(0, 228)
    ax.set_title("관측 커버리지: 관측주와 결측주", fontsize=17, fontweight="bold", pad=12)
    ax.legend(fontsize=12, frameon=True, loc="upper left")
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    fig.text(0.02, 0.055, "출처: REPORT.md(과거 2020-2022년 156주: CPU 148주, SSD 135주 관측) 및 recent README(최근 198주: CPU 158주, SSD 173주).",
             fontsize=10, color=SUB, wrap=True, ha="left", va="bottom")
    fig.text(0.02, 0.008, "단위: 주. 변화율 n(최근 CPU 135, SSD 157 등)은 분모가 달라 막대에 합산하지 않음. 한계: 호가 관측 기준이며 빈 구간은 미관측.",
             fontsize=10, color=SUB, wrap=True, ha="left", va="bottom")
    fig.tight_layout(rect=[0, 0.10, 1, 0.93])
    return save(fig, "02_observation_coverage")
def load_domestic_gpus():
    path = ROOT / "dashboard" / "dist" / "data" / "downloads" / "domestic_expanded.csv"
    rows = list(csv.DictReader(open(path, encoding="utf-8-sig")))
    gpus = [r for r in rows if "5070 Ti" in (r.get("name") or "")]
    items = []
    for r in gpus:
        med = (r.get("median3_delivered_krw") or "").strip()
        if not med:
            continue
        items.append({"id": r["id"], "name": r["name"], "median": int(med),
                      "sellers": r.get("displayed_sellers", "")})
    items.sort(key=lambda d: d["median"], reverse=True)
    return items
def fig03_gpu():
    items = load_domestic_gpus()
    short = {"76550837": "MSI 5070 Ti", "106710902": "PALIT 5070 Ti",
             "90160715": "MSI TRIO", "76510673": "GIGABYTE OC", "99839876": "GALAX 2X"}
    labels = [short.get(d["id"], d["id"]) for d in items]
    vals = [d["median"] for d in items]
    sellers = [d["sellers"] for d in items]
    others = [v for d, v in zip(items, vals) if d["id"] != "76550837"]
    med_others = sum(sorted(others)[1:3]) / 2
    top = vals[0]
    premium = (top - med_others) / med_others * 100
    fig, ax = plt.subplots(figsize=(10, 5.8))
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    colors = [ORANGE if d["id"] == "76550837" else NAVY for d in items]
    x = list(range(len(items)))
    ax.bar(x, vals, color=colors, edgecolor="white", width=0.62)
    ax.axhline(med_others, color=GREEN, linestyle="--", linewidth=2,
               label="나머지 4종 중앙값 " + format(int(med_others), ",") + "원")
    for i, (v, s) in enumerate(zip(vals, sellers)):
        ax.text(i, v + 28000, format(v, ",") + "원", ha="center", va="bottom",
                fontsize=11.5, fontweight="bold", color=INK)
        ax.text(i, v * 0.52, "노출 " + str(s), ha="center", va="center",
                fontsize=11, color="white")
    ax.annotate("최고가 +" + format(premium, ".1f") + "%", xy=(0, top), xytext=(1.6, top + 130000),
                fontsize=12, color=ORANGE, fontweight="bold", ha="center",
                arrowprops=dict(arrowstyle="->", color=ORANGE, linewidth=2))
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=12)
    ax.set_ylabel("원 (배송포함 3몰 중앙값)", fontsize=13)
    ax.yaxis.set_major_formatter(FuncFormatter(comma))
    ax.set_ylim(0, max(vals) * 1.18)
    ax.set_title("국내 RTX 5070 Ti 5종 가격 비교 (2026-10-23 스냅샷)", fontsize=16, fontweight="bold", pad=12)
    ax.legend(fontsize=12, loc="lower right")
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    fig.text(0.02, 0.055, "출처: domestic_expanded.csv. 값은 배송포함 3몰 중앙값(median3_delivered_krw). 표시판매처(노출 수)는 재고량이 아님.",
             fontsize=10, color=SUB, wrap=True, ha="left", va="bottom")
    fig.text(0.02, 0.008, "막대는 0부터. RTX 4060(노출 2곳, 중앙값 없음)은 비교에서 제외. 한계: 당일 스냅샷이며 실제 결제가는 조건에 따라 다름.",
             fontsize=10, color=SUB, wrap=True, ha="left", va="bottom")
    fig.tight_layout(rect=[0, 0.10, 1, 0.93])
    files = save(fig, "03_domestic_gpu_quotes")
    return files, items, med_others, premium
def load_metrics(ids):
    path = ROOT / "data" / "analysis" / "2026-10-23" / "forecast" / "forecast_metrics.csv"
    rows = list(csv.DictReader(open(path, encoding="utf-8-sig")))
    out = {}
    for r in rows:
        if r["id"] in ids:
            out[r["id"]] = r
    return rows, out
def fig04_validation():
    ids = ["US_B07STGGQ18", "US_B07MFZY2F2", "KR_21694499"]
    allrows, m = load_metrics(ids)
    total = len(allrows)
    passed = sum(1 for r in allrows if (r.get("passed") or "") == "True")
    pred_path = ROOT / "data" / "analysis" / "2026-10-23" / "forecast" / "forecast_predictions.csv"
    with open(pred_path, encoding="utf-8-sig") as f:
        pred_n = sum(1 for _ in f) - 1
    labels = ["US CPU 3600", "US SSD 970EVO+", "KR CPU 7500F"]
    brier = [float(m[i]["brier"]) for i in ids]
    base = [float(m[i]["baselineBrier"]) for i in ids]
    mae = [float(m[i]["mae"]) * 100 for i in ids]
    naive = [float(m[i]["naiveMae"]) * 100 for i in ids]
    ns = [m[i]["n"] for i in ids]
    nns = [m[i]["nonoverlapN"] for i in ids]
    fig, axes = plt.subplots(1, 2, figsize=(10, 5.9))
    fig.patch.set_facecolor("white")
    x = list(range(len(ids)))
    w = 0.36
    ax = axes[0]
    ax.set_facecolor("white")
    ax.bar([p - w / 2 for p in x], brier, width=w, color=NAVY, label="모형 Brier")
    ax.bar([p + w / 2 for p in x], base, width=w, color="#C3CDD8", label="빈도기준 Brier")
    for i in x:
        ax.text(i - w / 2, brier[i] + 0.02, format(brier[i], ".4f"), ha="center", fontsize=10, color=NAVY)
        ax.text(i + w / 2, base[i] + 0.02, format(base[i], ".4f"), ha="center", fontsize=10, color=SUB)
    ax.set_xticks(x)
    ax.set_xticklabels([labels[k] + chr(10) + "n=" + ns[k] + " 구간" + nns[k] for k in x], fontsize=10.5)
    ax.set_title("Brier (낮을수록 좋음)", fontsize=14, fontweight="bold")
    ax.legend(fontsize=11)
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    ax = axes[1]
    ax.set_facecolor("white")
    ax.bar([p - w / 2 for p in x], mae, width=w, color=GREEN, label="모형 MAE")
    ax.bar([p + w / 2 for p in x], naive, width=w, color="#C9C9C9", label="유지 MAE")
    for i in x:
        ax.text(i - w / 2, mae[i] + 0.5, format(mae[i], ".1f"), ha="center", fontsize=11, color="#14532d")
        ax.text(i + w / 2, naive[i] + 0.5, format(naive[i], ".1f"), ha="center", fontsize=11, color=SUB)
    ax.set_xticks(x)
    ax.set_xticklabels([labels[k] + chr(10) + "n=" + ns[k] + " 구간" + nns[k] for k in x], fontsize=10.5)
    ax.set_title("MAE (%p, 낮을수록 좋음)", fontsize=14, fontweight="bold")
    ax.legend(fontsize=11)
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    fig.suptitle("예측 검증: 3계열 모형과 기준 비교 (전체 35계열 0통과)", fontsize=15, fontweight="bold", y=0.98)
    fig.text(0.5, 0.90, "예측 " + str(pred_n) + "행은 중첩 원점이라 독립 표본이 아님. SSD도 ECE와 표본 기준으로 실패.",
             ha="center", fontsize=11.5, color=ORANGE, fontweight="bold")
    fig.text(0.02, 0.078, "출처: forecast_metrics.csv. MAE는 실제·예측 단순 변화율 차이의 절댓값 평균(%p). 유지 기준은 미래 가격=원점 가격 가정.",
             fontsize=10, color=SUB, wrap=True, ha="left", va="bottom")
    fig.text(0.02, 0.042, "대상 ID: US_B07STGGQ18, US_B07MFZY2F2, KR_21694499 (metrics CSV에서 실제 확인).",
             fontsize=10, color=SUB, wrap=True, ha="left", va="bottom")
    fig.text(0.02, 0.006, "한계: 비중첩 구간 8개와 계열별 표본 기준 미달로 구매추천에 사용할 검증된 모형 없음.",
             fontsize=10, color=SUB, wrap=True, ha="left", va="bottom")
    fig.tight_layout(rect=[0, 0.12, 1, 0.84])
    files = save(fig, "04_forecast_validation")
    return files, m, total, passed, pred_n
def fig05_timeline():
    fig, ax = plt.subplots(figsize=(10, 5.4))
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    ax.set_xlim(2022.9, 2026.95)
    ax.set_ylim(0, 3.2)
    ax.axvspan(2023.0, 2025.0, color=LIGHT_BLUE, alpha=0.9)
    ax.axvspan(2025.0, 2026.83, color=LIGHT_GREEN, alpha=0.9)
    ax.text(2024.0, 2.85, "2023-2024년 모형선택", ha="center", fontsize=13, fontweight="bold", color=NAVY)
    ax.text(2024.0, 2.55, "목표일이 2024-12-31 이내인 과거 예측으로", ha="center", fontsize=11, color=SUB)
    ax.text(2024.0, 2.32, "후보와 온도를 고정", ha="center", fontsize=11, color=SUB)
    ax.text(2025.9, 2.85, "2025-2026년 최종평가", ha="center", fontsize=13, fontweight="bold", color="#14532d")
    ax.text(2025.9, 2.55, "정답이 성숙한 사례만 사용", ha="center", fontsize=11, color=SUB)
    ax.text(2025.9, 2.32, "후보와 온도를 다시 고르지 않음", ha="center", fontsize=11, color=SUB)
    ax.axvline(2025.0, color=NAVY, linewidth=2.5)
    ax.text(2025.0, 3.05, "경계 2025-01-01", ha="center", fontsize=11, fontweight="bold", color=NAVY,
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white", edgecolor=NAVY))
    ax.annotate("", xy=(2025.26, 1.55), xytext=(2025.01, 1.55),
                arrowprops=dict(arrowstyle="<->", color=ORANGE, linewidth=2.5))
    ax.text(2025.135, 1.72, "3개월 원점에서 목표까지 미래차단", ha="center", fontsize=11.5, color=ORANGE, fontweight="bold")
    ax.scatter([2025.01], [1.15], s=90, color=NAVY, zorder=5)
    ax.scatter([2025.26], [1.15], s=90, color=ORANGE, zorder=5)
    ax.text(2024.982, 1.15, "원점 2025-01-03", ha="right", va="center", fontsize=11, fontweight="bold", color=NAVY)
    ax.text(2025.288, 1.15, "목표 2025-04-04", ha="left", va="center", fontsize=11, fontweight="bold", color=ORANGE)
    ax.text(2025.0, 0.55, "학습마감 fitCutoff 2025-01-01, 학습범위 끝 trainThrough 2024-12-27",
            ha="center", fontsize=11, color=SUB,
            bbox=dict(boxstyle="round,pad=0.35", facecolor="#F1F4F8", edgecolor="#9AA5B1"))
    ax.text(2024.0, 0.15, "US CPU 실제 행으로 확인 가능 (forecast_predictions.csv)", ha="center", fontsize=10.5, color=SUB)
    ax.set_xticks([2023, 2024, 2025, 2026])
    ax.set_xticklabels(["2023", "2024", "2025", "2026"], fontsize=12)
    ax.set_yticks([])
    ax.set_title("시간순 검증 타임라인 (설명용 개념도)", fontsize=17, fontweight="bold", pad=12)
    for spine in ["top", "left", "right"]:
        ax.spines[spine].set_visible(False)
    fig.text(0.02, 0.015, "출처: forecast_protocol.md와 forecast_predictions.csv. 각 분기는 시작 전에 목표값까지 관측된 사례만 학습. 예시는 개념 설명용 표시.",
             fontsize=10, color=SUB, wrap=True, ha="left", va="bottom")
    fig.tight_layout(rect=[0, 0.06, 1, 0.93])
    return save(fig, "05_forecast_timeline")
SHORT_LABEL = {
    "21694499": "R5 7500F", "76555634": "i5-14400F", "18718496": "R5 7600", "62794079": "R5 9600X",
    "11790199": "삼성 DDR4", "18911780": "삼성 DDR5", "14907467": "Team DDR4", "20369126": "Crucial DDR5",
    "18297002": "삼성 990PRO", "17001050": "SK P41", "17788487": "WD SN850X", "29666111": "Crucial T500",
    "76550837": "MSI 5070Ti", "106710902": "PALIT 5070Ti", "90160715": "MSI TRIO", "76510673": "GIGA OC",
    "99839876": "GALAX 2X", "81990338": "MSI 5060Ti", "90956033": "MSI 5060", "91909571": "RX 9060XT",
    "20740013": "MSI 4060",
}
def fig06_categories():
    path = ROOT / "dashboard" / "dist" / "data" / "downloads" / "domestic_expanded.csv"
    rows = list(csv.DictReader(open(path, encoding="utf-8-sig")))
    cats = [("CPU", "CPU (4종)"), ("RAM", "RAM (4종)"), ("SSD", "SSD (4종)"), ("GPU", "GPU (9종)")]
    fig, axes = plt.subplots(2, 2, figsize=(10, 7.2))
    fig.patch.set_facecolor("white")
    fig.suptitle("국내 품목별 가격: 배송포함 3몰 중앙값 (만원)", fontsize=15, fontweight="bold", y=0.98)
    fig.text(0.5, 0.935, "2026-10-23 스냅샷. 분류별 축 범위가 다르며 각 축은 0부터 시작. 막대 끝 숫자는 만원.",
             ha="center", fontsize=11.5, color=SUB)
    info = {}
    for ax, pair in zip(axes.flat, cats):
        code, title = pair
        ax.set_facecolor("white")
        items = [r for r in rows if r.get("category") == code]
        labels = []
        vals = []
        missing = []
        for r in items:
            med = (r.get("median3_delivered_krw") or "").strip()
            lab = SHORT_LABEL.get(r["id"], r["id"])
            if med:
                labels.append(lab)
                vals.append(int(med) / 10000)
            else:
                missing.append(lab + " 노출 " + (r.get("displayed_sellers") or "?") + "몰")
        y = list(range(len(labels)))
        labels = labels[::-1]
        vals = vals[::-1]
        y = list(range(len(labels)))
        ax.barh(y, vals, color=NAVY, edgecolor="white", height=0.6)
        pad = max(vals) * 0.025
        for i, v in enumerate(vals):
            ax.text(v + pad, i, format(v, ".1f"), va="center", ha="left", fontsize=10.5, color=INK)
        ax.set_yticks(y)
        ax.set_yticklabels(labels, fontsize=10.5)
        ax.set_xlabel("만원", fontsize=11)
        ax.set_title(title, fontsize=13, fontweight="bold")
        ax.set_xlim(0, max(vals) * 1.30)
        ax.grid(axis="x", linestyle="--", alpha=0.4)
        if missing:
            ax.set_ylim(-2.0, len(labels) - 1 + 0.9)
            for mi, m in enumerate(missing):
                ax.text(max(vals) * 0.02, -1.1 - mi * 0.9, m + " 미산정", va="center", ha="left",
                        fontsize=10.5, color=SUB)
        info[code] = {"bars": len(labels), "missing": missing}
    fig.text(0.02, 0.048, "출처: domestic_expanded.csv. 값은 배송포함 3몰 중앙값(median3_delivered_krw)을 만원 단위로 표시. 막대 순서는 CSV 수록 순서.",
             fontsize=10, color=SUB, wrap=True, ha="left", va="bottom")
    fig.text(0.02, 0.026, "표시판매처(노출 수)는 재고량이 아님. MSI 4060은 노출 2몰로 중앙값 미산정이며 0원 막대로 그리지 않음.",
             fontsize=10, color=SUB, wrap=True, ha="left", va="bottom")
    fig.text(0.02, 0.004, "한계: 당일 스냅샷이며 실제 결제가는 조건에 따라 다름. 순위나 추천이 아닌 현황 표시.",
             fontsize=10, color=SUB, wrap=True, ha="left", va="bottom")
    fig.tight_layout(rect=[0, 0.065, 1, 0.90])
    return save(fig, "06_domestic_category_prices"), info
def main():
    setup_font()
    inputs = ["dashboard/dist/data/downloads/domestic_expanded.csv",
              "data/analysis/2026-10-23/forecast/forecast_metrics.csv",
              "data/analysis/2026-10-23/forecast/forecast_predictions.csv",
              "docs/forecast_protocol.md",
              "data/processed/2026-10-23/recent/README.md",
              "REPORT.md"]
    hashes = {p: sha256_of(ROOT / p) for p in inputs}
    f1 = fig01_flow()
    f2 = fig02_coverage()
    f3, gpus, med_others, premium = fig03_gpu()
    f4, metrics, total, passed, pred_n = fig04_validation()
    f5 = fig05_timeline()
    f6, catinfo = fig06_categories()
    shown = {
        "coverage_past_cpu": "148/156", "coverage_past_ssd": "135/156",
        "coverage_recent_cpu": "158/198", "coverage_recent_ssd": "173/198",
        "gpu_medians": {d["id"]: d["median"] for d in gpus},
        "gpu_median_others4": med_others, "gpu_premium_pct": round(premium, 1),
        "forecast_total_series": total, "forecast_passed": passed, "forecast_pred_rows": pred_n,
        "forecast_three": {k: {"n": v["n"], "nonoverlapN": v["nonoverlapN"], "brier": v["brier"],
                               "baselineBrier": v["baselineBrier"], "mae": v["mae"],
                               "naiveMae": v["naiveMae"], "ece": v["ece"]} for k, v in metrics.items()},
        "timeline_example": {"id": "US_B07STGGQ18", "origin": "2025-01-03", "target": "2025-04-04",
                             "fitCutoff": "2025-01-01", "trainThrough": "2024-12-27"},
        "category_panels": catinfo,
    }
    manifest = {"inputs_sha256": hashes, "shown_numbers": shown,
                "outputs": f1 + f2 + f3 + f4 + f5 + f6}
    with open(OUT / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print("saved: " + str(f1 + f2 + f3 + f4 + f5 + f6))
    print("premium: " + format(premium, ".2f"))
    print("total/passed/pred: " + str(total) + "/" + str(passed) + "/" + str(pred_n))
if __name__ == "__main__":
    main()

