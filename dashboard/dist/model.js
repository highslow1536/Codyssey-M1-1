export const GPU_NAMES = {3070:'RTX 3070',3080:'RTX 3080 10GB',3090:'RTX 3090'};
export const COMPANY_NAMES = {AMD:'AMD',INTC:'Intel',NVDA:'NVIDIA','005930':'삼성전자','000660':'SK하이닉스',MU:'Micron'};
export const COLORS = ['#166e58','#8270b8','#d27b49','#4a7da2','#7b9b43','#bb6578'];
export const finite = value => typeof value === 'number' && Number.isFinite(value);
export function inYear(rows, year, key='date') { return year==='all'?rows:rows.filter(r=>String(r[key]).startsWith(year)); }
export function normalize(points) {
  const first=points.find(p=>finite(p.value)&&p.value>0);
  return points.map(p=>({...p,value:first&&finite(p.value)?p.value/first.value*100:null}));
}
export function normalizeTogether(series) {
  if (series.length<2) return series.map(s=>({...s,points:normalize(s.points)}));
  const maps=series.map(s=>new Map(s.points.map(p=>[p.date,p.value])));
  const common=series[0].points.find(p=>maps.every(m=>finite(m.get(p.date))&&m.get(p.date)>0));
  if(!common) return series.map(s=>({...s,points:s.points.map(p=>({...p,value:null})),baseDate:null}));
  return series.map((s,i)=>({...s,baseDate:common.date,points:s.points.map(p=>({...p,value:p.date<common.date||!finite(p.value)?null:p.value/maps[i].get(common.date)*100}))}));
}
export function stats(points) {
  const valid=points.filter(p=>finite(p.value));
  return {slots:points.length,n:valid.length,missing:points.length-valid.length,first:valid[0]??null,last:valid.at(-1)??null,
    change:valid.length>1?valid.at(-1).value/valid[0].value-1:null};
}
export function segments(points) {
  const parts=[];let current=[];
  for(const p of points) { if(finite(p.value)){current.push(p);}else if(current.length){parts.push(current);current=[];} }
  if(current.length) parts.push(current);
  return parts;
}
export function pearsonPairs(points) {
  const valid=points.filter(p=>finite(p.x)&&finite(p.y)),n=valid.length;
  if(n<3) return {r:null,n};
  const mx=valid.reduce((a,p)=>a+p.x,0)/n,my=valid.reduce((a,p)=>a+p.y,0)/n;
  let xx=0,yy=0,xy=0;for(const p of valid){xx+=(p.x-mx)**2;yy+=(p.y-my)**2;xy+=(p.x-mx)*(p.y-my);}
  return {r:xx>0&&yy>0?xy/Math.sqrt(xx*yy):null,n};
}
export function stockPairs(product,stock,mode='returns',lag=0) {
  const map=new Map(stock.weeks.map(w=>[w.date,w]));
  return product.weeks.map(w=>{const d=new Date(w.date+'T00:00:00Z');d.setUTCDate(d.getUTCDate()-7*lag);const s=map.get(d.toISOString().slice(0,10));
    return {date:w.date,x:mode==='levels'?s?.price:s?.return,y:mode==='levels'?w.price:w.return};}).filter(p=>finite(p.x)&&finite(p.y));
}
export function miningCorrelation(data,id,frequency,metric,mode) {
  return data.gpu.correlations.find(r=>String(r.series_id)===String(id)&&r.subset==='all'&&
    r.dataset===(frequency==='retail'?'retail_snapshots':'ebay_monthly')&&
    r.method===(frequency==='retail'?(mode==='levels'?'levels':'observation_interval_logchange'):(mode==='levels'?'monthly_levels':'adjacent_month_logchange'))&&r.crypto_metric===metric);
}
export const num = (v,digits=2) => finite(v)?new Intl.NumberFormat('ko-KR',{maximumFractionDigits:digits,minimumFractionDigits:digits}).format(v):'—';
export const pct = (v,digits=1) => finite(v)?`${v>0?'+':''}${num(v*100,digits)}%`:'—';
export const signed = v => finite(v)?`${v>0?'+':''}${num(v,3)}`:'—';
export const escapeHTML = value => String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
