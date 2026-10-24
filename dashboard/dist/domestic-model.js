// No imputation, pooled DDR generations, or probability scores. Policy thresholds are explicit.
export const positive=x=>typeof x==='number'&&Number.isFinite(x)&&x>0;
export function quantile(values,q){const a=values.filter(positive).sort((a,b)=>a-b);if(!a.length)return null;const i=(a.length-1)*q,j=Math.floor(i);return a[j]+(a[Math.ceil(i)]-a[j])*(i-j);}
export function historicalReference(p){const a=(p.history?.weekly_3m??[]).map(r=>r.desktop_price).filter(positive);return {n:a.length,low:quantile(a,.25),high:quantile(a,.5),min:quantile(a,0),max:quantile(a,1)};}
// Source summary lowest ordinary product + its delivery; not necessarily lowest total across malls.
export function price(p,basis='delivered',statistic='lowest'){
 const key=basis==='product'?'productPrice':'deliveredPrice';
 const v=statistic==='median3'?p.marketAudit?.[basis==='product'?'top3ProductMedian':'top3DeliveredMedian']:p.quote[key];
 return positive(v)?v:null;
}
export function ageDays(p,now=Date.now()){const t=Date.parse(p.quote.collectedAt);return Number.isFinite(t)?(now-t)/86400000:Infinity;}
export function thinMarket(p){return !Number.isFinite(p.quote.displayedSellerCount)||p.quote.displayedSellerCount<3;}
const fresh=(p,now)=>ageDays(p,now)<=7&&ageDays(p,now)>=-1;
export function metric(p,options={}){
 if(p.category==='CPU')return options.cpu==='bridge'?p.performance.cpuBridge??null:options.cpu==='single'?p.performance.cpuSingle:options.cpu==='none'?null:p.performance.cpuMulti;
 if(p.category==='GPU')return options.gpu==='single'?p.performance.gaming??null:p.performance.gamingSuite;
 if(p.category==='SSD')return options.ssd==='read'?p.performance.read??null:p.performance.capacity;
 return p.performance.capacity;
}
export function comparable(a,b){return !!(a&&b&&a.group===b.group&&a.unit===b.unit&&positive(a.value)&&positive(b.value));}
function marketBase(p,now){return fresh(p,now)&&p.quote.displayedSellerCount>=10&&p.marketAudit?.firstOfferReconciled===true&&p.marketAudit.distinctDisplayedStoresWithShipping>=3&&positive(price(p,'delivered','median3'));}
export function marketFlag(p,all,now=Date.now()){
 const peers=all.filter(q=>q.id!==p.id&&q.marketGroup===p.marketGroup&&marketBase(q,now));
 const middle=quantile(peers.map(q=>price(q,'delivered','median3')),.5),current=price(p,'delivered','median3');
 return {outlier:peers.length>=3&&positive(current)&&current>middle*1.20,n:peers.length,median:middle,premium:positive(current)&&positive(middle)?current/middle-1:null};
}
export function anchorEligible(p,all,now=Date.now()){return marketBase(p,now)&&!marketFlag(p,all,now).outlier;}
function matches(p,q,options){
 if(p.category!==q.category||!comparable(metric(p,options),metric(q,options)))return false;
 if(p.category==='CPU'&&options.platform==='same'&&p.socket!==q.socket)return false;
 if(p.category==='GPU'){
  if(options.gpuScope!=='all'&&p.comparisonTier!==q.comparisonTier)return false;
  if(options.vram==='16'&&!(Number.isFinite(p.vramGB)&&p.vramGB>=16&&Number.isFinite(q.vramGB)&&q.vramGB>=16))return false;
 }
 return true;
}
function calculate(p,all,options,now){
 const statistic=options.quote??'median3',current=price(p,options.basis,statistic),m=metric(p,options),flag=marketFlag(p,all,now);
 const peers=m?all.filter(q=>q.id!==p.id&&anchorEligible(q,all,now)&&positive(price(q,options.basis,statistic))&&matches(p,q,options)):[];
 const caps=peers.map(q=>({id:q.id,name:q.shortName,chip:q.chip,price:price(q,options.basis,statistic),metric:metric(q,options).value,cap:price(q,options.basis,statistic)*m.value/metric(q,options).value})).sort((a,b)=>a.cap-b.cap);
 // Multiple OC boards share one measured chip observation. Give each chip one median vote.
 const groups=new Map();for(const x of caps){if(!groups.has(x.chip))groups.set(x.chip,[]);groups.get(x.chip).push(x.cap);}
 const chipCaps=[...groups.values()].map(a=>quantile(a,.5));
 const cap=quantile(chipCaps,.5),low=quantile(chipCaps,.25),high=quantile(chipCaps,.75);
 const usable=fresh(p,now)&&!thinMarket(p)&&positive(current)&&p.marketAudit?.firstOfferReconciled&&p.marketAudit.distinctDisplayedStoresWithShipping>=3&&!flag.outlier;
 const efficiency=positive(current)&&m&&positive(m.value)?m.value/current:null;
 const best=usable&&peers.length?Math.max(efficiency,...peers.map(q=>metric(q,options).value/price(q,options.basis,statistic))):null;
 let recommendation='판단 보류',reason='동일 지표의 유효한 비교 견적이 부족합니다.',tone='neutral';
 if(!fresh(p,now))reason='조회 후 7일 초과 또는 수집 시각 이상. 현재 가격을 재조회해야 합니다.';
 else if(thinMarket(p)){recommendation='가격 재확인';reason='표시 판매처 3곳 미만. 희소 SKU 호가를 시세·가성비 순위로 쓰지 않습니다. 아래 현역 대안을 확인하세요.';tone='warn';}
 else if(flag.outlier){recommendation='비교 제품 우선';reason='다른 유효 동급 SKU 3개 이상 대비 3몰 중앙값이 20% 넘게 높습니다. 성능·AS 프리미엄이 정당한지는 별도 확인이 필요합니다.';tone='warn';}
 else if(!usable)reason='3개 일반몰의 배송비가 확인되는 견적 또는 선택한 가격이 부족합니다.';
 else if(cap!==null){
  if(current>cap*1.05){recommendation='비교 제품 우선';reason='비교 칩별 동률 가격 중앙값의 105%를 넘습니다. 다른 제품의 호환·보증과 총 교체 비용을 함께 확인하세요.';tone='warn';}
  else {recommendation=m.kind==='estimate'?'추정상 검토':'조건부 검토';reason='선택한 지표 대비 가격이 비교 중앙값의 105% 이내입니다. 확보한 비교군에서의 조건부 판단이며 구매 성공 확률은 아닙니다.';tone='good';}
 }
 return {current,metric:m,reference:historicalReference(p),age:ageDays(p,now),stale:!fresh(p,now),thin:thinMarket(p),flag,peerN:peers.length,chipN:groups.size,caps,cap,capLow:low,capHigh:high,index:best?100*efficiency/best:null,efficiency,recommendation,reason,tone,anchorAllowed:anchorEligible(p,all,now),historicalPremium:positive(historicalReference(p).high)?p.quote.productPrice/historicalReference(p).high-1:null};
}
export function evaluate(p,all,options={},now=Date.now()){
 const e=calculate(p,all,options,now),other=calculate(p,all,{...options,quote:options.quote==='lowest'?'median3':'lowest'},now);
 const sensitive=e.recommendation!==other.recommendation&&e.cap!==null&&other.cap!==null&&!e.thin&&!e.stale&&!e.flag.outlier;
 e.sensitive=sensitive;e.alternate={current:other.current,cap:other.cap,recommendation:other.recommendation};
 e.quoteGap=positive(e.current)&&positive(other.current)?Math.abs(e.current-other.current)/Math.max(e.current,other.current):null;
 e.evidence=e.stale||e.thin||!e.metric?'보류':e.flag.outlier?'가격 주의':e.metric.kind==='spec'?'제한 · 사양 비교':e.metric.kind==='estimate'?'제한 · 간접추정':e.metric.kind==='measured-aggregate'?'제한 · PC 제출 집계':e.metric.kind==='measured-single-game'||e.metric.kind==='same-chip-proxy'?'제한 · 단일 게임':e.chipN>1?'보강 · 다종 게임':'보강 · 동일칩 견적';
 if(!e.stale&&!e.thin&&e.metric&&!e.peerN)e.evidence='제한 · 비교군 부족';
 if(sensitive){e.recommendation='견적에 민감';e.tone='warn';e.reason='요약 최저 상품 견적과 3몰 중앙값에서 구매 분류가 달라집니다. 실제 결제 가격을 확인할 때까지 적극 추천을 보류합니다.';}
 return e;
}
export function historySeries(p,frequency='weekly',surface='both'){
 const monthly=frequency==='monthly',rows=(monthly?p.history?.monthly_comparison_24m:p.history?.weekly_3m)??[];
 return ['pc','mobile'].filter(k=>surface==='both'||surface===k).map(k=>({name:k==='pc'?'PC':'모바일',color:k==='pc'?'#267b61':'#9a81bf',points:rows.map(r=>({date:monthly?r.month_iso+'-15':r.iso_date,value:k==='pc'?r.desktop_price:r.mobile_price}))}));
}
