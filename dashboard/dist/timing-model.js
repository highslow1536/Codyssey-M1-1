import {evaluate,price,positive} from './domestic-model.js';

// Action rules describe observed momentum. They do not estimate future odds.
export function timingDecision(product,history,all,{horizon=4,urgency='flexible',now=Date.now()}={}){
 const evidence=history?.analysis?.[String(horizon)],peer=evaluate(product,all,{basis:'delivered',quote:'median3',cpu:'multi',gpu:'suite',gpuScope:'tier',ssd:'capacity'},now);
 const result={title:'가격을 다시 확인하세요',tone:'caution',code:'verify',peer,evidence,
  reason:'현재 견적 또는 최근 이력이 부족합니다.',next:'최신 판매가와 최근 관측을 확인한 뒤 판단하세요.',probability:null};
 if(peer.stale){result.reason='저장 견적이 7일을 넘었거나 수집 시각이 잘못됐습니다.';return result;}
 if(peer.thin||peer.flag.outlier){result.title='이 SKU보다 동급 대안을 먼저 보세요';result.code='alternative';result.reason=peer.thin?'표시 판매처가 3곳 미만이라 희소 호가일 수 있습니다.':'동일 칩의 다른 유효 제품들보다 3몰 중앙값이 20% 넘게 높습니다.';result.next='같은 칩 또는 호환되는 동급 제품을 비교한 뒤 실제 결제 가격을 확인하세요.';return result;}
 if(!positive(peer.current)||!evidence||!positive(evidence.lastPrice))return result;
 if((now-Date.parse(evidence.lastDate+'T00:00:00+09:00'))/86400000>14){result.reason='마지막 가격 이력이 14일을 넘었습니다. 과거 방향을 현재 신호로 쓰지 않습니다.';return result;}
 const t=evidence.trend,r=t.fourWeek,w=t.oneWeek,long=evidence.longTrend??{};
 const gap=peer.current/evidence.lastPrice-1;result.basisGap=gap;
 if(Math.abs(gap)>.15){result.title='현재 견적과 이력 차이를 확인하세요';result.reason='현재 3몰 배송 포함 중앙값과 원문 이력 말값이 15% 넘게 다릅니다. 서로 다른 가격 기준일 가능성이 있습니다.';result.next='차트 가격으로 구매할 수 있다고 가정하지 말고 실제 결제 견적을 확인하세요.';return result;}
 if(!Number.isFinite(r)||!Number.isFinite(w))return result;
 result.tone='neutral';result.code='neutral';
 if(r<-.03&&w<=.01){
  result.code=urgency==='immediate'?'needed':'wait';result.tone=urgency==='immediate'?'neutral':'wait';
  result.title=urgency==='immediate'?'급하면 필요한 만큼 구매하세요':'급하지 않다면 1~2주 더 지켜보세요';
  result.reason='최근 4주 가격이 3% 넘게 하락했고 마지막 주에도 뚜렷한 반등이 없습니다. 추가 하락을 관찰할 여지가 있습니다.';
  result.next='다음 관측에서도 하락하는지 확인하세요. 반등하거나 업그레이드가 급해지면 구매를 다시 검토하세요.';
 }else if(r>.03&&w>=0&&t.upWeeks>=2){
  result.code='consider';result.tone='buy';result.title=urgency==='immediate'?'필요한 제품은 지금 구매를 검토하세요':'곧 필요하면 지금 구매를 검토하세요';
  result.reason='최근 4주 가격이 3% 넘게 올랐고 그중 2주 이상 상승했습니다. 계속 오를 경우의 지출 부담을 줄이는 행동 규칙입니다.';
  result.next='업그레이드가 가까우면 현재 견적을 검토하세요. 일정에 여유가 있으면 다음 관측에서 상승이 이어지는지 확인하세요.';
 }else if(r>.03&&w<0){
  result.code=urgency==='immediate'?'needed':'wait';result.tone='caution';result.title='급등 뒤 방향이 바뀌는지 확인하세요';
  result.reason='4주 전보다 비싸지만 마지막 주는 하락했습니다. 직전 급등을 그대로 미래에 연장하기 어렵습니다.';
  result.next=urgency==='immediate'?'급하면 실제 결제 견적을 확인해 필요한 만큼 구매하세요.':'1주 뒤 하락이 이어지는지 확인한 뒤 구매를 결정하세요.';
 }else{
  result.title=urgency==='immediate'?'가격 예측보다 필요한 시점을 우선하세요':'목표 가격을 정하고 기다려도 됩니다';
  result.reason='최근 흐름에서 한 방향의 뚜렷한 신호를 확보하지 못했습니다. 가격을 맞히기보다 필요 시점과 예산으로 결정할 구간입니다.';
  result.next=urgency==='immediate'?'호환성과 실제 결제 가격을 확인한 뒤 구매하세요.':'현재 견적과 아래 성능 대비 기준가를 비교하고, 1주 뒤 다시 확인하세요.';
 }
 if(horizon>=12&&urgency==='flexible'){
  if(!Number.isFinite(long.threeMonth)||!Number.isFinite(long.sixMonth)){
   result.code='verify';result.tone='caution';result.title='장기 판단은 보류하고 월간 이력을 더 모으세요';
   result.reason='3개월 이상 계획에 필요한 완료 월의 3·6개월 비교가 부족합니다. 최근 4주 움직임만으로 구매를 앞당기지 않습니다.';
   result.next='지금 가격을 확정하기보다 예산과 호환성을 정하고, 1개월 뒤 다시 확인하세요.';
  }else if(long.threeMonth<-.05&&r<-.03){
   result.code='wait';result.tone='wait';result.title='구매를 미루고 한 달 뒤 다시 보세요';
   result.reason='완료 월 기준 3개월 추세와 최근 4주가 함께 하락했습니다. 일정에 여유가 있어 지금 구매를 확정할 근거가 약합니다.';
   result.next='약 4주 뒤 가격을 재확인하세요. 월간 하락이 멈추고 주간 반등이 이어지거나 필요 시점이 가까워지면 구매를 재검토하세요.';
  }else if(long.threeMonth>.05&&long.sixMonth>.05&&r>.03&&w>=0&&t.upWeeks>=2){
   result.code='consider';result.tone='buy';result.title='장·단기 상승 중, 구매를 앞당길지 검토하세요';
   result.reason='완료 월 기준 3·6개월 가격이 각각 5% 넘게 올랐고 최근 4주에도 상승이 이어졌습니다. 추가 상승에 따른 예산 초과 위험을 고려할 구간입니다.';
   result.next='곧 쓸 제품이고 추가 상승 비용을 감당하기 어렵다면 구매를 검토하세요. 3개월 이상 남았다면 예산 상한을 정하고 한 달 뒤 추세를 재확인하는 선택도 있습니다.';
  }else{
   result.code='wait';result.tone='neutral';result.title='지금 확정하기보다 한 달 더 관찰하세요';
   result.reason='3·6개월 흐름과 최근 4주가 같은 방향의 강한 신호를 주지 않습니다. 3개월 이상 여유가 있으므로 단기 변동만으로 서두르지 않는 행동 규칙입니다.';
   result.next='예산·호환성을 먼저 정하고 약 4주 뒤 재점검하세요. 장·단기 상승이 함께 이어지거나 실제 필요 시점이 가까워지면 구매를 앞당길지 검토하세요.';
  }
 }
 if(peer.cap&&peer.current>peer.cap*1.05){
  result.next+=' 이 제품은 성능 대비 비교 기준가도 넘어 동급 대안을 함께 확인하세요.';
  if(result.code==='consider'){result.code='alternative';result.tone='caution';result.title='상승 중이지만 동급 대안을 먼저 비교하세요';result.reason+=' 다만 현재 성능 대비 가격이 높아 이 SKU를 서둘러 사는 판단은 보류합니다.';}
 }
 if(horizon===8)result.next+=' 8주 전체 방향은 검증하지 못했습니다. 지금 판단은 최근 4주에 한합니다.';
 return result;
}

export function recentSeriesPoints(series,year='all'){
 return series.points.filter(p=>year==='all'||p.date.startsWith(String(year)));
}
export function scenarioCost(current,change){return positive(current)&&Number.isFinite(change)?Math.round(current*(1+change)):null;}
export function selectTimingProduct(products,id,category){return products.find(p=>p.id===id&&p.category===category)??products.find(p=>p.category===category)??products[0];}
export function monthlyChartPoints(rows){
 if(!rows.length)return [];
 const byMonth=new Map(rows.map(p=>[p.date,p.price])),out=[];
 let [year,month]=rows[0].date.split('-').map(Number);
 const last=rows.at(-1).date;
 while(true){const key=`${year}-${String(month).padStart(2,'0')}`;if(key>last)break;
  out.push({date:key+'-15',value:byMonth.get(key)??null});month++;if(month===13){year++;month=1;}}
 return out;
}
