import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {timingDecision,recentSeriesPoints,scenarioCost,monthlyChartPoints} from '../dist/timing-model.js';
const D=JSON.parse(fs.readFileSync(new URL('../dist/data/domestic.json',import.meta.url)));
const T=JSON.parse(fs.readFileSync(new URL('../dist/data/timing.json',import.meta.url)));
const R=JSON.parse(fs.readFileSync(new URL('../dist/data/recent.json',import.meta.url)));
const all=[...D.products,...D.marketReferences],p=all.find(x=>x.id==='21694499');
const history=T.products.find(x=>x.id===p.id),now=Date.parse('2026-10-23T22:00:00+09:00');
const run=(h=history,options={})=>timingDecision(p,h,all,{now,...options});

test('falling price changes the action with urgency, without inventing probabilities',()=>{
 const flexible=run(),needed=run(history,{urgency:'immediate'});
 assert.equal(flexible.code,'wait');assert.equal(needed.code,'needed');
 assert.equal(flexible.probability,null);assert.equal(needed.probability,null);
 assert.ok(flexible.evidence.trend.fourWeek<-.03);
});
test('sustained rise, reversal and mixed momentum lead to distinct timing actions',()=>{
 const h=structuredClone(history),t=h.analysis['4'].trend;
 Object.assign(t,{fourWeek:.08,oneWeek:.02,upWeeks:3});assert.equal(run(h).code,'consider');
 t.oneWeek=-.02;assert.equal(run(h).code,'wait');
 t.fourWeek=.01;assert.equal(run(h).code,'neutral');
});
test('thin, abnormal, stale quotes and mismatched history block timing promotion',()=>{
 for(const id of ['20740013','76550837']){
  const q=all.find(x=>x.id===id);assert.equal(timingDecision(q,T.products.find(x=>x.id===id),all,{now}).code,'alternative');
 }
 assert.equal(run(history,{now:Date.parse('2026-11-15')}).code,'verify');
 const h=structuredClone(history);h.analysis['4'].lastPrice=100;assert.equal(run(h).code,'verify');
 h.analysis['4'].lastPrice=160650;h.analysis['4'].lastDate='2026-09-01';assert.equal(run(h).code,'verify');
});
test('every domestic quote has fresh history and every horizon withholds unvalidated odds',()=>{
 assert.deepEqual(all.map(x=>x.id).sort(),T.products.map(x=>x.id).sort());
 for(const h of T.products){assert.equal(h.weekly.length,12);assert.equal(h.weekly.at(-1).date,'2026-10-20');
  for(const horizon of ['4','8','12']){const a=h.analysis[horizon];assert.equal(a.validation.probabilityAvailable,false);assert.ok(a.validation.n<30);assert.equal(a.trend.twelveWeek,null);}
 }
});
test('recent display keeps null weeks and same calendar lag coefficients',()=>{
 const p=R.series.find(s=>s.id==='B07STGGQ18');assert.equal(p.coverage.total,198);assert.equal(p.coverage.observed,158);
 const points=recentSeriesPoints(p,'2026');assert.ok(points.some(x=>x.value===null));assert.ok(points.every(x=>x.date.startsWith('2026')));
 const q=R.series.find(s=>s.id==='AMD'),lp=new Map(p.points.map((x,i,a)=>[x.date,i&&Number.isFinite(x.value)&&Number.isFinite(a[i-1].value)?Math.log(x.value/a[i-1].value):null]));
 const pairs=q.points.flatMap((x,i,a)=>{const target=new Date(x.date+'T00:00:00Z');target.setUTCDate(target.getUTCDate()+7);const y=lp.get(target.toISOString().slice(0,10));return i&&Number.isFinite(y)&&Number.isFinite(x.value)&&Number.isFinite(a[i-1].value)?[[Math.log(x.value/a[i-1].value),y]]:[];});
 const r=R.correlations.find(r=>r.partId===p.id&&r.marketId==='AMD'&&r.mode==='returns'&&r.lag_weeks===1);
 assert.equal(r.n,pairs.length);const mx=pairs.reduce((a,p)=>a+p[0],0)/pairs.length,my=pairs.reduce((a,p)=>a+p[1],0)/pairs.length;
 const cov=pairs.reduce((a,[x,y])=>a+(x-mx)*(y-my),0),vx=pairs.reduce((a,[x])=>a+(x-mx)**2,0),vy=pairs.reduce((a,[,y])=>a+(y-my)**2,0);
 assert.ok(Math.abs(r.pearson-cov/Math.sqrt(vx*vy))<1e-12);
});
test('budget scenarios are explicit arithmetic, missing quote remains missing',()=>{
 assert.equal(scenarioCost(200000,.05),210000);assert.equal(scenarioCost(null,.05),null);
});
test('monthly chart leaves missing calendar months empty instead of joining them',()=>{
 assert.deepEqual(monthlyChartPoints([{date:'2025-12',price:10},{date:'2026-02',price:12}]),[{date:'2025-12-15',value:10},{date:'2026-01-15',value:null},{date:'2026-02-15',value:12}]);
});
test('three-month plans combine long and short trends and withhold weak long evidence',()=>{
 const h=structuredClone(history),a=h.analysis['12'];
 Object.assign(a.longTrend,{threeMonth:.2,sixMonth:.3});Object.assign(a.trend,{fourWeek:.08,oneWeek:.02,upWeeks:3});
 assert.equal(run(h,{horizon:12}).code,'consider');
 a.trend.fourWeek=-.08;assert.equal(run(h,{horizon:12}).code,'wait');
 a.longTrend.threeMonth=-.2;assert.match(run(h,{horizon:12}).title,/한 달/);
 a.longTrend.sixMonth=null;assert.equal(run(h,{horizon:12}).code,'verify');
 assert.equal(T.rules.defaultHorizonWeeks,12);
});
