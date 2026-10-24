import {finite,escapeHTML as esc,num} from './model.js';
import {probabilityPresentation} from './forecast-view.js?v=20261023-forecast';

export function forecastPurchaseDecision(observed,series,{horizon=12,urgency='flexible'}={}){
 if(horizon<12)return observed;
 const result={...observed,code:'unvalidated',tone:'neutral',probability:null,
  title:'3개월 뒤 방향으로 구매를 권할 근거가 부족합니다',
  reason:'실제로 학습한 확률 모형을 과거 시점에서 검증했지만, 이 제품은 구매 추천 기준을 통과하지 못했습니다.',
  next:urgency==='immediate'?'지금 필요하다면 예측보다 호환성·실제 결제 가격·예산을 기준으로 결정하세요.':'급하지 않다면 예산 상한을 정하고 다음 가격 관측을 확인하세요. 추가 하락이나 상승이 더 유력하다고 판단한 대기 권고는 아닙니다.'};
 // Quote integrity is separate from predictive evidence and takes priority.
 if(observed.peer.stale||observed.peer.thin||observed.peer.flag.outlier||observed.code==='verify'){
  return {...result,title:observed.title,reason:observed.reason,next:observed.next,code:observed.code,tone:observed.tone};
 }
 if(!series?.forecast){result.reason='같은 가격 기준의 충분한 학습 자료가 없어 현재 확률을 산출하지 못했습니다.';return result;}
 const e=series.evaluation;
 result.reason=`국내 월간 모형의 과거 시험은 ${e.n}회입니다. `+(finite(e.brierSkill)?e.brierSkill>0?`과거 빈도 기준보다 Brier 점수가 ${(e.brierSkill*100).toFixed(1)}% 개선됐지만 표본·안정성 기준을 통과하지 못했습니다.`:`과거 빈도 기준보다 Brier 점수가 ${(-e.brierSkill*100).toFixed(1)}% 나빴습니다.`:'검증 표본이 부족합니다.');
 if(series.frequency==='monthly')result.reason+=' 완료한 9월 버킷에서 12월 버킷을 예측한 값으로, 오늘부터 3개월 뒤와도 다릅니다.';
 if(!series.gates?.passed||series.region!=='KR'||series.frequency!=='weekly')return result;
 const p=probabilityPresentation(series.forecast.probabilities);
 if(p.kind!=='valid')return result;
 if(p.values[2]>=.6&&p.values[2]-p.values[0]>=.2){
  result.title='상승 위험이 커, 필요한 구매를 앞당길지 검토하세요';result.code='consider';result.tone='buy';
  result.reason='별도 미래 구간의 확률 검증을 통과했고, 상승 추정이 사전에 정한 행동 기준을 넘었습니다.';
  result.next='현재 견적·호환성과 기다리는 비용을 비교해 구매 시점을 결정하세요.';
 }else if(p.values[0]>=.6&&p.values[0]-p.values[2]>=.2){
  result.title='일정에 여유가 있다면 구매를 기다릴지 검토하세요';result.code='wait';result.tone='wait';
  result.reason='별도 미래 구간의 확률 검증을 통과했고, 하락 추정이 사전에 정한 행동 기준을 넘었습니다.';
  result.next='필요 시점과 예산을 정하고 가격을 재확인하세요.';
 }else {result.title='검증한 모형도 한 방향의 우위를 보이지 않습니다';result.reason='상승·하락 확률 차이가 구매 시점을 바꿀 행동 기준보다 작습니다.';}
 return result;
}

export function forecastSummary(series){
 const e=series?.evaluation,p=probabilityPresentation(series?.forecast?.probabilities),f=series?.forecast;
 return `<div class="t-kicker">실제 학습 모형 · 3개월</div><h2>상승·하락 가능성을 검증했습니다</h2><div class="t-probability"><strong>${series?.gates?.passed?'구매 판단 사용 기준 통과':'실험 결과 · 구매 추천에 미사용'}</strong>${f?`<p><b>${esc(f.origin.slice(0,7))} → ${esc(f.target.slice(0,7))} 월간 버킷</b><br>오늘부터 3개월 뒤의 확률이 아닙니다.</p>`:'<p>충분한 학습 표본이 없어 확률을 산출하지 못했습니다.</p>'}</div>${p.kind==='valid'?`<div class="f-probs f-probs-compact">${['하락 >3%','보합 ±3%','상승 >3%'].map((n,i)=>`<div><span>${n}</span><strong>${num(p.values[i]*100,1)}%</strong></div>`).join('')}</div>`:''}<div class="t-eval"><div><span>미래 구간 검증</span><b>${e?.n??0}회 <small>비중첩 시간 ${e?.nonoverlapN??0}구간</small></b></div><div><span>Brier · 낮을수록 좋음</span><b>${finite(e?.brier)?num(e.brier,3):'—'}</b></div><div><span>과거 빈도 기준 Brier</span><b>${finite(e?.baselineBrier)?num(e.baselineBrier,3):'—'}</b></div></div><p class="t-eval-result">확률을 숫자로 출력하는 것과 미래에 잘 맞는 것은 다릅니다. 점수·보정·시간 표본 기준을 통과한 경우에만 추천에 사용합니다.</p><button class="button" data-action="openForecast" data-value="${esc(series?.id??'')}">이 제품의 모형·검증·장기 자료 보기 →</button>`;
}
