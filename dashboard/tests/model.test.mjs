import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {normalizeTogether,segments,stats,stockPairs,miningCorrelation,inYear,finite,pearsonPairs} from '../dist/model.js';
const d=JSON.parse(readFileSync(new URL('../dist/data/dashboard.json',import.meta.url),'utf8'));
test('normalization uses one common observed date and preserves every gap',()=>{
  const result=normalizeTogether([{name:'price',points:[{date:'2020-01-01',value:10},{date:'2020-01-08',value:null},{date:'2020-01-15',value:20},{date:'2020-01-22',value:30}]},{name:'stock',points:[{date:'2020-01-01',value:null},{date:'2020-01-08',value:5},{date:'2020-01-15',value:10},{date:'2020-01-22',value:20}]}]);
  assert.deepEqual(result.map(s=>s.baseDate),['2020-01-15','2020-01-15']);
  assert.deepEqual(result[0].points.map(p=>p.value),[null,null,100,150]);
  assert.deepEqual(result[1].points.map(p=>p.value),[null,null,100,200]);
});
test('disjoint dates never create a false normalized comparison',()=>{
  const out=normalizeTogether([{points:[{date:'2020-01-01',value:10}]},{points:[{date:'2020-01-02',value:20}]}]);
  assert.ok(out.every(s=>s.baseDate===null&&s.points.every(p=>p.value===null)));
});
test('line segments stop at null observations',()=>assert.deepEqual(segments([{value:1},{value:null},{value:2},{value:3},{value:null}]).map(a=>a.length),[1,2]));
test('CPU/SSD displayed coverage is exactly the saved weekly grid',()=>{
  for(const p of d.products){const st=stats(p.weeks.map(w=>({date:w.date,value:w.price})));assert.equal(st.n,p.coverage.observed);assert.equal(st.missing,156-p.coverage.observed);}
  assert.equal(inYear(d.gpu.monthly.filter(r=>r.gpu==='3070'),'2020','month').filter(r=>finite(r.price_usd)).length,0);
});
test('every stock scatter and lag preserves actual calendar weeks and matches published n and r',()=>{
  for(const p of d.products)for(const s of d.stocks){const row=d.stockCorrelations.find(r=>r.product_id===p.id&&r.symbol===s.symbol);
    for(const mode of ['returns','levels']){const actual=pearsonPairs(stockPairs(p,s,mode));assert.equal(actual.n,mode==='returns'?row.n_return:row.n_level);assert.ok(Math.abs(actual.r-(mode==='returns'?row.return_pearson:row.level_pearson))<1e-9);}
    for(const lag of [-8,-1,0,1,8]){const row=d.stockLags.find(r=>r.product_id===p.id&&r.symbol===s.symbol&&r.lag_weeks===lag),actual=pearsonPairs(stockPairs(p,s,'returns',lag));assert.equal(actual.n,row.n);assert.ok(Math.abs(actual.r-row.pearson)<1e-9);}}
});
test('positive lag means stock leads, not a compressed missing-date shift',()=>{
  const p={weeks:[{date:'2020-01-17',return:.1},{date:'2020-01-31',return:.2}]},s={weeks:[{date:'2020-01-10',return:.4},{date:'2020-01-17',return:.5},{date:'2020-01-31',return:.6}]};
  assert.deepEqual(stockPairs(p,s,'returns',1),[{date:'2020-01-17',x:.4,y:.1}]);
});
test('GPU correlations select genuine intervals/months and correct metric n',()=>{
  for(const id of ['3070','3080','3090'])for(const source of ['retail','monthly'])for(const metric of ['eth_price','fees_included_proxy','fees_excluded_proxy']){
    const r=miningCorrelation(d,id,source,metric,'changes');assert.ok(r);assert.equal(r.n,source==='retail'?(id==='3080'?28:32):metric==='eth_price'?15:11);}
});
test('mining proxy ends at the Merge and never becomes zero after it',()=>{
  assert.equal(d.eth.daily.filter(r=>finite(r.proxyA)).length,988);
  assert.ok(d.eth.daily.filter(r=>r.date>='2022-09-15').every(r=>r.proxyA===null&&r.proxyB===null));
});
