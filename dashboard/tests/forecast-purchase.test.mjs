import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {timingDecision} from '../dist/timing-model.js';
import {forecastPurchaseDecision,forecastSummary} from '../dist/forecast-model.js';
import {calibrationGraphic,backtestChartPoints} from '../dist/forecast-view.js';
const read=n=>JSON.parse(fs.readFileSync(new URL('../dist/data/'+n+'.json',import.meta.url)));
const D=read('domestic'),T=read('timing'),F=read('forecast');
const all=[...D.products,...D.marketReferences],p=all.find(p=>p.id==='21694499');
const base=timingDecision(p,T.products.find(h=>h.id===p.id),all,{horizon:12,now:Date.parse('2026-10-23T23:00:00+09:00')});
const s=F.series.find(s=>s.domesticId===p.id);
test('failed probabilistic validation replaces the long-plan momentum purchase action',()=>{
 const observed={...base,code:'consider',tone:'buy',title:'trend purchase'};
 const out=forecastPurchaseDecision(observed,s);
 assert.equal(out.code,'unvalidated');assert.equal(out.probability,null);
 assert.match(out.reason,/7회/);assert.match(out.reason,/나빴/);
 assert.ok(forecastSummary(s).includes('구매 추천에 미사용'));
});
test('foreign, monthly and invalid probabilities can never become domestic 3-month buy signals',()=>{
 const observed={...base,code:'neutral'},candidate={...s,gates:{passed:true},forecast:{...s.forecast,probabilities:[.05,.1,.85]}};
 assert.equal(forecastPurchaseDecision(observed,candidate).code,'unvalidated');
 candidate.frequency='weekly';candidate.region='US';assert.equal(forecastPurchaseDecision(observed,candidate).code,'unvalidated');
 candidate.region='KR';candidate.forecast.probabilities=[.1,.1,.1];assert.equal(forecastPurchaseDecision(observed,candidate).code,'unvalidated');
 candidate.forecast.probabilities=[.05,.1,.85];assert.equal(forecastPurchaseDecision(observed,candidate).code,'consider');
 candidate.forecast.probabilities=[.85,.1,.05];assert.equal(forecastPurchaseDecision(observed,candidate).code,'wait');
});
test('quote integrity still blocks recommendations and short plans remain observational rules',()=>{
 const bad={...base,code:'verify',title:'가격 재확인',peer:{...base.peer,stale:true}};
 assert.equal(forecastPurchaseDecision(bad,s).title,'가격 재확인');
 assert.equal(forecastPurchaseDecision(base,s,{horizon:4}),base);
 assert.equal(forecastPurchaseDecision(base,null).code,'unvalidated');
});
test('calibration graphic plots actual frequencies with sample counts and escapes no invalid data into SVG',()=>{
 const svg=calibrationGraphic([{class:0,n:8,predicted:.7,observed:.25},{class:1,n:0,predicted:NaN,observed:NaN}]);
 assert.match(svg,/n=8/);assert.match(svg,/70.0%/);assert.match(svg,/25.0%/);
 assert.equal(svg.includes('NaN'),false);assert.equal((svg.match(/<circle/g)||[]).length,1);
});
test('backtest plots preserve missing origins and never overwrite two forecasts sharing one target date',()=>{
 const rows=[{origin:'2024-03-29',target:'2024-07-05',actualChange:.1},
 {origin:'2024-04-05',target:'2024-07-05',actualChange:.2},
 {origin:'2024-04-19',target:'2024-07-19',actualChange:.3}];
 assert.deepEqual(backtestChartPoints(rows,'actualChange','weekly'),[
 {date:'2024-03-29',value:10},{date:'2024-04-05',value:20},
 {date:'2024-04-12',value:null},{date:'2024-04-19',value:30}]);
});
