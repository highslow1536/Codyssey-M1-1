"""Draw plain-language REPORT guides from public aggregate metadata only.

The four-week missing-value example is fictional and unitless. It is never
used as an observation, model input or evaluation result.
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
from matplotlib import font_manager
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

ROOT = Path(__file__).resolve().parents[1]
INK, MUTED, GREEN, BLUE, AMBER = '#19332f', '#526764', '#14715b', '#345d8b', '#95662a'


def box(ax, x, y, w, h, color='#ffffff', edge='#dce5e1'):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle='round,pad=0.014,rounding_size=.015',
                               facecolor=color, edgecolor=edge, linewidth=1))


def label(ax, x, y, text, size=16, color=INK, weight='normal', **kw):
    return ax.text(x, y, text, fontsize=size, color=color, weight=weight, va='top', **kw)


def canvas(title, subtitle):
    fig, ax = plt.subplots(figsize=(14, 9))
    fig.patch.set_facecolor('#f5f8f5')
    ax.set(xlim=(0, 1), ylim=(0, 1)); ax.axis('off')
    label(ax, .04, .96, title, 27, weight='bold')
    label(ax, .04, .892, subtitle, 13, MUTED)
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    return fig, ax


def save(fig, name, as_of):
    out = ROOT/'docs/assets/public'; out.mkdir(parents=True, exist_ok=True)
    fig.savefig(out/f'{name}.png', dpi=150, facecolor=fig.get_facecolor())
    svg = out/f'{name}.svg'
    fig.savefig(svg, facecolor=fig.get_facecolor(), metadata={'Date': as_of, 'Creator': 'plot_report_reader_guide.py'})
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines())+'\n')
    plt.close(fig)


def main():
    font = Path('/System/Library/Fonts/Supplemental/AppleGothic.ttf')
    if font.exists(): plt.rcParams['font.family'] = font_manager.FontProperties(fname=font).get_name()
    plt.rcParams['axes.unicode_minus'] = False
    plt.rcParams['svg.hashsalt'] = 'codyssey-report-reader-guide'
    recent = json.loads((ROOT/'data/public/recent_analysis.json').read_text())
    models = json.loads((ROOT/'data/public/model_comparison.json').read_text())
    parts = recent['parts']
    ddr5 = next(s for s in parts if s['shortName']=='Crucial DDR5 16GB (IN)')['coverage']['recent13WeekChange']
    ddr4 = next(s for s in parts if s['shortName']=='Crucial Pro DDR4 16GB (IN)')['coverage']['recent13WeekChange']
    s = models['summary']
    fig, ax = canvas('결론부터: 가격 비교는 가능, 구매 시점 추천은 보류',
                      f"최근 분석 {recent['firstWeek']}–{recent['lastWeek']} · 해외 {len(parts)}개 제품 · 예측 대상 {s['series']}개")
    cards = [
        (.61, '01  같은 RAM도 가격 방향이 달랐습니다',
         f"DDR5(인도) {ddr5:+.1%}   /   DDR4(인도) {ddr4:+.1%}",
         '최근 13주 실제 변화입니다. 이 두 해외 제품을 국내 RAM 전체로 일반화하지 않습니다.', GREEN),
        (.385, '02  주가만 보고 살 시점을 정할 근거는 부족합니다',
         '주가 상승 → 부품 가격 상승, 이 규칙은 확인되지 않았습니다',
         '관계가 제품·기간마다 다르고, 큰 상관계수도 실제 비교 횟수가 적을 수 있습니다.', BLUE),
        (.16, '03  3개월 뒤 가격 예측은 아직 추천에 쓸 수준이 아닙니다',
         f"구매 추천 기준 통과  {s['passed']} / {s['series']}",
         '모델이 일부 점수에서 나아져도, 표본 수·오차·확률 신뢰성 조건을 함께 통과해야 합니다.', AMBER),
    ]
    for y, title, takeaway, detail, color in cards:
        box(ax, .04, y, .92, .18)
        label(ax, .06, y+.157, title, 18, color, 'bold')
        label(ax, .06, y+.105, takeaway, 19, weight='bold')
        label(ax, .06, y+.049, detail, 12, MUTED)
    label(ax, .045, .105, '구매 판단: 필요한 성능·배송 포함 가격은 비교하되, 이 모델로 “지금 구매 / 3개월 대기”를 단정하지 않습니다.', 13, weight='bold')
    label(ax, .045, .055, '출처: 프로젝트 공개 집계 recent_analysis.json · model_comparison.json.\n14개는 개별 해외 판매 목록이며, 국내 실거래·시장 전체 지수·미래 가격 보장이 아닙니다.', 10, MUTED)
    save(fig, '07_report_summary', recent['asOf'])

    fig, ax = canvas('빈 가격은 채워 만들지 않았습니다',
                      '아래는 규칙을 설명하는 가상 예시입니다. 실제 제품 가격·학습·검증 자료가 아닙니다.')
    for i, (price, note, color) in enumerate([
        ('100', '1주 · 실제 관측', GREEN), ('빈칸', '2주 · 관측 없음', MUTED),
        ('120', '3주 · 실제 관측', GREEN), ('121', '4주 · 실제 관측', GREEN)]):
        x = .04+i*.245
        box(ax, x, .63, .19, .17, '#ffffff' if i!=1 else '#e9edeb')
        label(ax, x+.095, .777, note, 13, color, ha='center')
        label(ax, x+.095, .719, price, 29, color, 'bold', ha='center')
    for x, text, color in [(.2575, '계산 안 함', MUTED), (.5025, '계산 안 함', MUTED), (.7475, '+0.83%', GREEN)]:
        label(ax, x, .595, text, 15, color, 'bold', ha='center')
    label(ax, .04, .538, '1주 → 3주의 +20%는 2주 사이 변화이므로, “한 주 변화율”로 쓰지 않았습니다.', 16, weight='bold')
    box(ax, .04, .287, .92, .19)
    label(ax, .06, .453, '분석에서는 이렇게 처리했습니다', 19, GREEN, 'bold')
    label(ax, .06, .402, '① 빈 주는 유지    ② 0·평균·직전 가격으로 채우지 않음\n③ 연속 두 주가 있을 때만 변화율 계산    ④ 실제로 비교한 횟수 n을 따로 표시', 16)
    box(ax, .04, .108, .92, .125, '#edf2f8', '#d3dfe9')
    label(ax, .06, .212, '구분: 예측 모델의 입력 요약값은 일부 보완했습니다', 17, BLUE, 'bold')
    label(ax, .06, .164, '과거 변동성 같은 입력값은 학습 자료의 중앙값과 빈값 표시로 보완했습니다.\n실제 가격과 3개월 뒤 정답은 채우지 않았습니다. 적용할 수 없는 ETH 채굴 대용도 0으로 만들지 않았습니다.', 12)
    label(ax, .045, .062, f"실제 최근 자료: 공통 달력 {recent['calendarWeeks']}주 중 제품별 관측 {min(p['coverage']['observed'] for p in parts)}–{max(p['coverage']['observed'] for p in parts)}주.\n첫 관측 전 기간·첫 관측 뒤 빈 주·계산 대상이 아닌 값은 구분합니다. 출처: 전처리 코드와 공개 관측 수 집계.", 10, MUTED)
    save(fig, '08_missing_values_guide', recent['asOf'])


if __name__=='__main__': main()
