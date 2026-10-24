import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {evaluate,price,metric,historySeries,historicalReference,anchorEligible,marketFlag,quantile} from '../dist/domestic-model.js';
const D=JSON.parse(readFileSync(new URL('../dist/data/domestic.json',import.meta.url)));
const now=Date.parse('2026-10-23T22:00:00+09:00'),all=[...D.products,...D.marketReferences];
const get=id=>all.find(p=>p.id===id),evaluateAt=(id,o={})=>evaluate(get(id),all,o,now);
test('CPU defaults to observed submission aggregates; estimates stay opt-in and separate',()=>{
 const a=evaluateAt('21694499');assert.equal(a.metric.value,26506);assert.equal(a.metric.kind,'measured-aggregate');assert.equal(a.metric.samples,5987);assert.equal(a.peerN,3);assert.equal(a.index,100);
 const b=evaluateAt('21694499',{cpu:'bridge'});assert.equal(b.metric.kind,'estimate');assert.equal(b.peerN,1);assert.equal(metric(get('18718496'),{cpu:'bridge'}),null);
 assert.equal(evaluateAt('21694499',{cpu:'single'}).metric.value,3824);
});
test('RAM same generation gains one real peer, never treats DDR4 and DDR5 as interchangeable',()=>{
 for(const id of ['11790199','18911780']){const e=evaluateAt(id);assert.equal(e.peerN,1);assert.ok(e.caps.every(x=>get(x.id).chip===get(id).chip));assert.equal(e.metric.kind,'spec');}
 assert.equal(evaluateAt('11790199').cap,184900);
});
test('thin 4060 has measured suite and alternatives but cannot supply a quote anchor or rank',()=>{
 const e=evaluateAt('20740013');assert.equal(e.thin,true);assert.equal(e.index,null);assert.equal(e.recommendation,'가격 재확인');assert.equal(e.metric.value,69);assert.equal(e.peerN,3);assert.equal(e.current,null);assert.equal(anchorEligible(get('20740013'),all,now),false);
 assert.equal(metric(get('20740013'),{gpu:'single'}).value,45);
});
test('MSI 5070 Ti premium is flagged against four real same-chip quotes, not silently deleted',()=>{
 const e=evaluateAt('76550837');assert.equal(e.flag.outlier,true);assert.equal(e.flag.n,4);assert.equal(e.anchorAllowed,false);assert.equal(e.peerN,4);assert.equal(e.chipN,1);assert.equal(e.cap,1995735);assert.equal(e.capLow,e.capHigh);assert.equal(e.index,null);assert.equal(e.recommendation,'비교 제품 우선');
 assert.equal(get('76550837').quote.productPrice,2445890);
});
test('three-mall median is distinct from summary lowest and historical delivery is never backfilled',()=>{
 const p=get('18911780');assert.equal(price(p),349000);assert.equal(price(p,'delivered','median3'),371480);
 const a=evaluateAt('21694499',{basis:'product'}),b=evaluateAt('21694499');assert.notEqual(a.current,b.current);assert.deepEqual(a.reference,b.reference);assert.equal(price(get('21694499')),169220);
});
test('recommendation instability across quote statistics is exposed in either direction',()=>{
 for(const quote of ['lowest','median3']){const e=evaluateAt('76555634',{quote});assert.equal(e.sensitive,true);assert.equal(e.recommendation,'견적에 민감');assert.equal(e.tone,'warn');}
});
test('expanded SSD capacity sample is not substituted into missing measured/spec speed',()=>{
 const a=evaluateAt('17001050'),b=evaluateAt('17001050',{ssd:'read'});assert.equal(a.peerN,3);assert.equal(a.cap,396250);assert.equal(b.peerN,1);assert.equal(a.metric.kind,'spec');assert.notEqual(a.cap,b.cap);
 assert.equal(metric(get('29666111'),{ssd:'read'}),null);assert.equal(evaluateAt('29666111',{ssd:'read'}).index,null);
});
test('platform and minimum-VRAM filters exclude incompatible candidates',()=>{
 const e=evaluateAt('21694499',{platform:'same'});assert.equal(e.peerN,2);assert.ok(e.caps.every(x=>get(x.id).socket==='AM5'));
 assert.equal(evaluateAt('76555634',{platform:'same'}).peerN,0);
 const g=evaluateAt('91909571',{vram:'16'});assert.equal(g.peerN,1);assert.ok(g.caps.every(x=>get(x.id).vramGB>=16));assert.equal(evaluateAt('90956033',{vram:'16'}).index,null);
 const unknown=structuredClone(get('81990338'));delete unknown.vramGB;const pool=all.map(p=>p.id===unknown.id?unknown:p);assert.equal(evaluate(get('91909571'),pool,{vram:'16'},now).peerN,0);
});
test('same-chip boards receive one median vote in all-GPU parity reference',()=>{
 const e=evaluateAt('91909571',{gpuScope:'all'});assert.equal(e.peerN,6);assert.equal(e.chipN,3);
 const groups=new Map();for(const c of e.caps){if(!groups.has(c.chip))groups.set(c.chip,[]);groups.get(c.chip).push(c.cap);}
 assert.equal(e.cap,quantile([...groups.values()].map(x=>quantile(x,.5)),.5));
 assert.notEqual(e.cap,quantile(e.caps.map(x=>x.cap),.5));
});
test('stale and future snapshots cannot support a recommendation or rank',()=>{
 for(const t of [now+8*86400000,now-2*86400000]){const e=evaluate(get('18297002'),all,{},t);assert.equal(e.recommendation,'판단 보류');assert.equal(e.cap,null);assert.equal(e.index,null);assert.equal(e.stale,true);}
});
test('missing or zero quote, unknown delivery, unreconciled fields and too few stores stay excluded',()=>{
 for(const value of [null,0]){const p=structuredClone(get('18297002'));p.quote.deliveredPrice=value;p.marketAudit.top3DeliveredMedian=value;assert.equal(price(p),null);assert.equal(evaluate(p,all,{},now).index,null);}
 for(const change of [{distinctDisplayedStoresWithShipping:2},{firstOfferReconciled:false}]){const p=structuredClone(get('18297002'));Object.assign(p.marketAudit,change);assert.equal(anchorEligible(p,all,now),false);assert.equal(evaluate(p,all,{},now).index,null);}
 const p=structuredClone(get('18297002'));p.quote.displayedSellerCount=9;assert.equal(anchorEligible(p,all,now),false);
});
test('outlier flag requires at least three other real SKU quotes',()=>{
 const p=get('76550837');const reduced=all.filter(x=>!['106710902','90160715'].includes(x.id));assert.equal(marketFlag(p,reduced,now).outlier,false);assert.equal(marketFlag(p,reduced,now).n,2);
});
test('history references retain all observations, including unusual 4060 values',()=>{
 const ref=historicalReference(get('20740013'));assert.equal(ref.n,12);assert.equal(ref.max,2809390);assert.equal(ref.min,2135120);
 assert.equal(historicalReference(get('29666111')).n,0);assert.equal(historySeries(get('29666111'))[0].points.length,0);
});
test('monthly conflicts and missing PC point remain distinct; current quotes not appended',()=>{
 const p=get('21694499'),s=historySeries(p,'monthly');assert.equal(s[0].points[0].value,null);assert.equal(s[1].points[0].value,176590);assert.notEqual(s[0].points[1].value,s[1].points[1].value);
 assert.equal(historySeries(p)[0].points.length,12);assert.equal(historySeries(p)[0].points.at(-1).date,'2026-10-20');assert.equal(s[0].points.at(-1).date,'2026-10-15');
});
