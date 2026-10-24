"""Regenerate the recent figure using PUBLIC aggregates only (no price rows)."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
from matplotlib import font_manager
import matplotlib.pyplot as plt
import numpy as np

ROOT=Path(__file__).resolve().parents[1]


def plot_public(data):
    font=Path('/System/Library/Fonts/Supplemental/AppleGothic.ttf')
    if font.exists():plt.rcParams['font.family']=font_manager.FontProperties(fname=font).get_name()
    plt.rcParams['axes.unicode_minus']=False
    plt.rcParams['svg.hashsalt']='codyssey-recent-20261025'
    parts=data['parts'];markets=data['markets'];y=np.arange(len(parts))
    fig,(a,b)=plt.subplots(1,2,figsize=(17,10),gridspec_kw={'width_ratios':[1,1.65]})
    before=[s['coverage']['beforeFirstObservation'] for s in parts]
    observed=[s['coverage']['observed'] for s in parts]
    missing=[s['coverage']['missingAfterFirst'] for s in parts]
    a.barh(y,before,color='#e5e8eb',label='첫 관측 전')
    a.barh(y,observed,left=before,color='#166e58',label='유효 관측 수')
    a.barh(y,missing,left=np.array(before)+observed,color='#c3c9ce',label='첫 관측 이후 빈 주')
    # These stacked counts summarize coverage, not chronology of observations.
    for i,n in enumerate(observed):a.text(data['calendarWeeks']+3,i,str(n),va='center',fontsize=10)
    a.set_yticks(y,[s['shortName'] for s in parts],fontsize=10);a.invert_yaxis()
    a.set_xlim(0,data['calendarWeeks']*1.16);a.set_xlabel('공통 달력 안의 주 수 (연속 구간 표시가 아님)')
    a.set_title(f"최근 {data['calendarWeeks']}주의 실제 관측 수",fontsize=15,pad=18)
    a.legend(loc='upper center',bbox_to_anchor=(.5,-.08),ncol=1,fontsize=10,frameon=False)
    lookup={(r['partId'],r['marketId']):r for r in data['correlations'] if r['lagWeeks']==0}
    matrix=np.array([[lookup[s['id'],m['id']]['pearson'] if lookup[s['id'],m['id']]['pearson'] is not None else np.nan for m in markets] for s in parts])
    cmap=plt.get_cmap('RdBu_r').copy();cmap.set_bad('#eceeef')
    im=b.imshow(matrix,vmin=-1,vmax=1,cmap=cmap,aspect='auto')
    for i,s in enumerate(parts):
        for j,m in enumerate(markets):
            r=lookup[s['id'],m['id']];v=r['pearson']
            b.text(j,i,f"{v:+.2f}\nn={r['n']}" if v is not None else f"—\nn={r['n']}",
                   ha='center',va='center',fontsize=9,color='white' if v is not None and abs(v)>.65 else '#152f28')
    b.set_xticks(np.arange(len(markets)),[m['name'] for m in markets],rotation=25,ha='right')
    b.set_yticks(y,[]);b.set_title('같은 주의 로그 변화율 상관 r · 실제 짝 수 n',fontsize=15,pad=18)
    fig.colorbar(im,ax=b,fraction=.035,pad=.025,label='Pearson r (-1 to +1)')
    fig.suptitle(f"2023년 이후 최근 분석 · {data['firstWeek']} – {data['lastWeek']}",fontsize=22,weight='bold',y=.98)
    fig.text(.03,.025,'출처: data/public/recent_analysis.json · 원가격·정규화 가격곡선은 포함하지 않은 자체 집계.\n'
             '해외 14개 리스팅, USD/INR·신품/리퍼 조건을 분리. 결측 보간·이월 없음. 인접 두 주만 변화율 계산.\n'
             '여러 시차·기업을 탐색한 기술통계이며 유의성·인과·예측력의 증거가 아님. 국내 현재가로 일반화하지 않음.\n'
             '—는 미산출. IN RTX 3070은 변화율 분산이 0이므로 n=77이어도 r을 계산할 수 없음.',fontsize=11)
    fig.tight_layout(rect=(.01,.13,.99,.94))
    out=ROOT/'docs/assets/public';out.mkdir(parents=True,exist_ok=True)
    fig.savefig(out/'06_recent_analysis.png',dpi=150,facecolor='white')
    svg=out/'06_recent_analysis.svg';fig.savefig(svg,metadata={'Date':data['asOf'],'Creator':'plot_recent_report.py'})
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines())+'\n');plt.close(fig)


if __name__=='__main__':
    plot_public(json.loads((ROOT/'data/public/recent_analysis.json').read_text()))
