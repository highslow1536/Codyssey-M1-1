"""Render exportable model-comparison figures using public aggregates only."""
import csv
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
from matplotlib import font_manager
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'docs/assets/public'
COLORS = ['#2f6d91', '#8270b8', '#166e58', '#e18b3b', '#b74d61', '#9aa4ad']


def main():
    path = ROOT/'data/public/model_comparison.json'
    data = json.loads(path.read_text())
    font_path = Path('/System/Library/Fonts/Supplemental/AppleGothic.ttf')
    if font_path.exists():
        plt.rcParams['font.family'] = font_manager.FontProperties(fname=font_path).get_name()
    plt.rcParams['axes.unicode_minus'] = False
    plt.rcParams['svg.hashsalt'] = 'codyssey-model-comparison-20261024'
    OUT.mkdir(parents=True, exist_ok=True)
    ids = ['US_B07STGGQ18', 'US_B07MFZY2F2', 'KR_21694499']
    names = ['미국 Ryzen 3600', '미국 970 EVO Plus', '국내 7500F']
    models = ['logistic', 'forest', 'arima', 'sarima', 'ets', 'baseline']
    labels = ['Logistic', 'Forest', 'ARIMA', 'SARIMA', 'ETS', '기준']
    fig, axes = plt.subplots(2, 3, figsize=(14, 8.5))
    fig.suptitle('같은 원점·3개월 목표에서 비교한 모델 오차', fontsize=20, weight='bold', y=.98)
    for col, (sid, title) in enumerate(zip(ids, names)):
        series = next(s for s in data['series'] if s['id'] == sid)
        lookup = {m['candidate']: m for m in series['models']}
        for row, (metric, unit, scale) in enumerate([('brier', 'Brier (0–2)', 1), ('mae', '변화율 MAE (%p)', 100)]):
            ax = axes[row, col]
            vals = [lookup[m]['evaluation'][metric] for m in models]
            vals = [v * scale if v is not None else np.nan for v in vals]
            ax.bar(np.arange(6), vals, color=COLORS, width=.7)
            top = max((v for v in vals if np.isfinite(v)), default=1)
            for i, v in enumerate(vals):
                ax.text(i, (v+.035*top) if np.isfinite(v) else .02*top,
                        f'{v:.3f}' if np.isfinite(v) and metric == 'brier' else f'{v:.1f}' if np.isfinite(v) else '미산출',
                        ha='center', va='bottom', fontsize=9)
            ax.set_ylim(0, top*1.24)
            ax.set_xticks(np.arange(6), labels, rotation=30, ha='right')
            ax.set_ylabel(unit)
            ax.grid(axis='y', alpha=.2)
            ax.set_axisbelow(True)
            if row == 0:
                c = series['common']
                ax.set_title(f'{title}\n공통 n={c["testN"]}, 비중첩 {c["nonoverlapN"]}구간', fontsize=13)
    fig.text(.03, .015, '출처: data/public/model_comparison.json · 2025–2026년 회고 평가 · 낮을수록 좋음. 국내 SARIMA는 연간 2주기 미달.\n'
             '선택은 2023–2024년 결과만 사용. 점 예측 산정법이 달라 확률 점수와 MAE를 구분. 기준: 과거 방향 빈도 / 가격 유지.', fontsize=11)
    fig.tight_layout(rect=(.01,.085,.99,.93))
    save(fig, '04_model_comparison')
    series = data['series']
    # Full selected-model n is distinct from common n; both are observed targets.
    full = [s['selectedAllEvaluation']['n'] for s in series]
    common = [s['common']['testN'] for s in series]
    fig, ax = plt.subplots(figsize=(13, 16))
    y = np.arange(len(series))
    ax.barh(y-.18, full, height=.34, label='선택 모델 전체 평가 n', color='#b8c4cb')
    ax.barh(y+.18, common, height=.34, label='후보 공통 평가 n', color='#166e58')
    for i, s in enumerate(series):
        ax.text(max(full[i], common[i])+.7, i, f'{common[i]}/{full[i]} · {s["selection"]["candidate"]}', va='center', fontsize=9)
    ax.set_yticks(y, [f'{s["region"]} · {s["name"][:46]}' for s in series], fontsize=9)
    ax.invert_yaxis()
    ax.set_xlim(0, max(full+[1])*1.4)
    ax.set_xlabel('관측 정답이 있는 원점 수 (독립 표본 수가 아님)')
    ax.set_title('35개 계열의 공통 비교 표본과 선택 모델', fontsize=19, weight='bold', pad=20)
    ax.grid(axis='x', alpha=.2)
    ax.set_axisbelow(True)
    ax.legend(loc='lower right')
    fig.text(.02, .012, '출처: data/public/model_comparison.json · 오른쪽 숫자=공통 n/선택 모델 전체 n.\n'
             '예측 실패·이력 부족으로 공통 날짜가 줄어듭니다. 0은 관측 부재이며 오차 0이 아닙니다. 제품 수를 독립 시간 구간으로 합산하지 않습니다.', fontsize=11)
    fig.tight_layout(rect=(.01,.055,.99,.98))
    save(fig, '05_model_coverage')
    rows = []
    for s in series:
        for m in s['models']:
            e = m['evaluation']
            rows.append({'id':s['id'], 'name':s['name'], 'candidate':m['candidate'],
                         'selected':m['candidate']==s['selection']['candidate'],
                         'status':m['status'], 'allTestN':m.get('allTestN'),
                         **{k:e[k] for k in ['n','nonoverlapN','brier','logLoss','ece','mae','rmse','intervalN','interval80Coverage','interval95Coverage']}})
    with (ROOT/'data/public/model_comparison_metrics.csv').open('w', newline='', encoding='utf-8-sig') as handle:
        w = csv.DictWriter(handle, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    (OUT/'model_comparison_figures.json').write_text(json.dumps({'source':str(path.relative_to(ROOT)),
        'sha256':hashlib.sha256(path.read_bytes()).hexdigest(), 'figures':['04_model_comparison','05_model_coverage'],
        'asOf':data['asOf'], 'generatedAt':data['generatedAt']}, indent=2)+'\n')
    print('2 PNG/SVG figures + public aggregate CSV generated')


def save(fig, stem):
    fig.savefig(OUT/(stem+'.png'), dpi=150, facecolor='white')
    fig.savefig(OUT/(stem+'.svg'), metadata={'Date':'2026-10-24','Creator':'plot_model_comparison.py'}, facecolor='white')
    plt.close(fig)


if __name__ == '__main__':
    main()
