import {finite,num,segments,escapeHTML} from './model.js';
const NS='http://www.w3.org/2000/svg';
function tag(name,attrs={},text=''){const el=document.createElementNS(NS,name);for(const [k,v] of Object.entries(attrs))el.setAttribute(k,String(v));if(text)el.textContent=text;return el;}
function extent(values){const clean=values.filter(finite);if(!clean.length)return [0,1];let lo=Math.min(...clean),hi=Math.max(...clean);if(lo===hi){lo-=Math.max(1,Math.abs(lo)*.1);hi+=Math.max(1,Math.abs(hi)*.1);}return [lo,hi];}
function frame(container,title,height=330){container.innerHTML='';const box=document.createElement('div');box.className='chart-wrap';container.append(box);const width=Math.max(300,Math.min(960,box.clientWidth)),H=width<480?Math.min(height,270):height;const svg=tag('svg',{viewBox:`0 0 ${width} ${H}`,role:'img','aria-label':title});box.append(svg);return {box,svg,width,height:H};}
function empty(container,text){container.innerHTML=`<div class="empty-chart">${escapeHTML(text)}</div>`;}
export function lineChart(container,series,{title='가격 추이',unit='',start,end,events=[],height=330,showPoints=false,monthly=false,monthlyLabel='월평균'}={}){
  const all=series.flatMap(s=>s.points);if(!all.some(p=>finite(p.value))){empty(container,'선택한 기간에는 실제 관측한 가격이 없습니다. 다른 기간을 선택하세요.');return;}
  const {box,svg,width,height:H}=frame(container,title,height),m={l:64,r:24,t:35,b:42};
  svg.setAttribute('role','group');
  const time=d=>Date.parse(d+'T00:00:00Z');const t0=time(start??all.map(p=>p.date).sort()[0]),t1=time(end??all.map(p=>p.date).sort().at(-1));
  let [lo,hi]=extent(all.map(p=>p.value));const pad=(hi-lo)*.14;lo-=pad;hi+=pad;if(lo<0&&all.filter(p=>finite(p.value)).every(p=>p.value>=0))lo=0;
  const x=d=>m.l+(time(d)-t0)/Math.max(1,t1-t0)*(width-m.l-m.r),y=v=>H-m.b-(v-lo)/(hi-lo)*(H-m.t-m.b);
  svg.append(tag('text',{x:m.l,y:15,class:'svg-unit'},unit));
  for(let i=0;i<5;i++){const v=lo+(hi-lo)*i/4,py=y(v);svg.append(tag('line',{x1:m.l,x2:width-m.r,y1:py,y2:py,class:'gridline'}));svg.append(tag('text',{x:m.l-12,y:py+4,'text-anchor':'end',class:'tick'},num(v,Math.abs(hi)>20?0:2)));}
  const steps=width<480?2:5;
  for(let i=0;i<=steps;i++){const t=t0+(t1-t0)*i/steps,iso=new Date(t).toISOString(),d=!monthly&&t1-t0<=100*86400000?iso.slice(5,10):iso.slice(0,7);svg.append(tag('text',{x:m.l+(width-m.l-m.r)*i/steps,y:H-12,'text-anchor':i===0?'start':i===steps?'end':'middle',class:'tick'},d));}
  for(const e of events){if(time(e.date)<t0||time(e.date)>t1)continue;const px=x(e.date);svg.append(tag('line',{x1:px,x2:px,y1:m.t,y2:H-m.b,class:'event-line'}));svg.append(tag('text',{x:px-5,y:m.t-9,'text-anchor':'end',class:'event-label'},e.label));}
  for(const s of series){for(const part of segments(s.points)){const path=part.map((p,i)=>`${i?'L':'M'}${x(p.date).toFixed(2)},${y(p.value).toFixed(2)}`).join(' ');svg.append(tag('path',{d:path,fill:'none',stroke:s.color,'stroke-width':s.width??2.5,'stroke-linejoin':'round','stroke-linecap':'round',...(s.dashed?{'stroke-dasharray':'5 5'}:{})}));
      if(showPoints||s.points.filter(p=>finite(p.value)).length<60)for(const p of part)svg.append(tag('circle',{cx:x(p.date),cy:y(p.value),r:3,fill:s.color,stroke:'white','stroke-width':1}));}}
  const cross=tag('line',{x1:0,x2:0,y1:m.t,y2:H-m.b,class:'crosshair',visibility:'hidden'});svg.append(cross);
  const tip=document.createElement('div');tip.className='chart-tooltip';tip.hidden=true;box.append(tip);
  const dates=[...new Set(all.map(p=>p.date))].sort();
  const show=index=>{const d=dates[Math.max(0,Math.min(dates.length-1,index))],px=x(d);cross.setAttribute('x1',px);cross.setAttribute('x2',px);cross.setAttribute('visibility','visible');tip.hidden=false;
    tip.innerHTML=`<strong>${monthly?d.slice(0,7)+' '+escapeHTML(monthlyLabel):d}</strong>`+series.map(s=>{const p=s.points.find(v=>v.date===d);return `<div><i style="background:${s.color}"></i>${escapeHTML(s.name)}<b>${p&&finite(p.value)?num(p.value,2):'미관측'}</b></div>`;}).join('');
    const screenX=px/width*box.clientWidth;tip.style.left=`${Math.max(4,Math.min(screenX,box.clientWidth-tip.offsetWidth-4))}px`;
    overlay.setAttribute('aria-valuenow',index);overlay.setAttribute('aria-valuetext',tip.textContent);};
  const overlay=tag('rect',{x:m.l,y:m.t,width:width-m.l-m.r,height:H-m.t-m.b,fill:'transparent',tabindex:0,role:'slider','aria-label':'날짜별 값 탐색. 좌우 방향키로 이동','aria-valuemin':0,'aria-valuemax':dates.length-1,'aria-valuenow':0});svg.append(overlay);let focusIndex=0;
  overlay.addEventListener('pointermove',e=>{const rect=svg.getBoundingClientRect(),target=t0+((e.clientX-rect.left)/rect.width*width-m.l)/(width-m.l-m.r)*(t1-t0);let index=0,best=Infinity;dates.forEach((d,i)=>{const dist=Math.abs(time(d)-target);if(dist<best){best=dist;index=i;}});focusIndex=index;show(index);});
  overlay.addEventListener('pointerleave',()=>{tip.hidden=true;cross.setAttribute('visibility','hidden');});
  overlay.addEventListener('focus',()=>show(focusIndex));overlay.addEventListener('blur',()=>{tip.hidden=true;cross.setAttribute('visibility','hidden');});
  overlay.addEventListener('keydown',e=>{if(!['ArrowLeft','ArrowRight','Home','End'].includes(e.key))return;e.preventDefault();focusIndex=e.key==='Home'?0:e.key==='End'?dates.length-1:Math.max(0,Math.min(dates.length-1,focusIndex+(e.key==='ArrowRight'?1:-1)));show(focusIndex);});
}
export function scatterChart(container,points,{title='변화율 산점도',color='#166e58',percent=true,xLabel='주가 변화율',yLabel='부품 변화율'}={}){
  const valid=points.filter(p=>finite(p.x)&&finite(p.y));if(valid.length<3){empty(container,'상관을 표시하기 위한 실제 관측 쌍이 부족합니다.');return;}
  const {svg,width,height:H}=frame(container,title,295),m={l:65,r:28,t:20,b:48};let [xl,xh]=extent(valid.map(p=>p.x)),[yl,yh]=extent(valid.map(p=>p.y));const xp=(xh-xl)*.12,yp=(yh-yl)*.12;xl-=xp;xh+=xp;yl-=yp;yh+=yp;
  const x=v=>m.l+(v-xl)/(xh-xl)*(width-m.l-m.r),y=v=>H-m.b-(v-yl)/(yh-yl)*(H-m.t-m.b);
  const steps=width<480?2:4;
  for(let i=0;i<=steps;i++){const vx=xl+(xh-xl)*i/steps,vy=yl+(yh-yl)*i/steps;svg.append(tag('line',{x1:m.l,x2:width-m.r,y1:y(vy),y2:y(vy),class:'gridline'}));svg.append(tag('text',{x:m.l-10,y:y(vy)+4,'text-anchor':'end',class:'tick'},num(vy*(percent?100:1),1)+(percent?'%':'')));svg.append(tag('text',{x:x(vx),y:H-25,'text-anchor':'middle',class:'tick'},num(vx*(percent?100:1),1)+(percent?'%':'')));}
  if(xl<0&&xh>0)svg.append(tag('line',{x1:x(0),x2:x(0),y1:m.t,y2:H-m.b,class:'zero-line'}));if(yl<0&&yh>0)svg.append(tag('line',{x1:m.l,x2:width-m.r,y1:y(0),y2:y(0),class:'zero-line'}));
  for(const p of valid){const dot=tag('circle',{cx:x(p.x),cy:y(p.y),r:4.4,fill:color,opacity:.58});dot.append(tag('title',{},`${p.date} · ${xLabel}: ${num(p.x*(percent?100:1),2)}${percent?'%':''} · ${yLabel}: ${num(p.y*(percent?100:1),2)}${percent?'%':''}`));svg.append(dot);}
  svg.append(tag('text',{x:(width+m.l-m.r)/2,y:H-3,'text-anchor':'middle',class:'svg-unit'},xLabel));svg.append(tag('text',{x:m.l,y:12,class:'svg-unit'},yLabel));
}
export function barChart(container,rows,{title='시차별 상관',selected=0}={}){
  const {svg,width:W,height:H}=frame(container,title,230),m={l:46,r:20,t:20,b:35},width=W-m.l-m.r,bw=width/rows.length;
  const y=v=>m.t+(1-v)/2*(H-m.t-m.b),zero=y(0);
  for(const v of [-1,-.5,0,.5,1]){svg.append(tag('line',{x1:m.l,x2:W-m.r,y1:y(v),y2:y(v),class:v===0?'zero-line':'gridline'}));svg.append(tag('text',{x:m.l-10,y:y(v)+4,'text-anchor':'end',class:'tick'},String(v)));}
  rows.forEach((r,i)=>{if(!finite(r.pearson))return;const bar=tag('rect',{x:m.l+i*bw+bw*.18,y:Math.min(zero,y(r.pearson)),width:bw*.64,height:Math.max(1,Math.abs(zero-y(r.pearson))),rx:3,fill:r.lag_weeks===selected?'#166e58':'#bed3c9'});bar.append(tag('title',{},`시차 ${r.lag_weeks}주 · r=${num(r.pearson,3)} · n=${r.n}`));svg.append(bar);svg.append(tag('text',{x:m.l+(i+.5)*bw,y:H-10,'text-anchor':'middle',class:'tick'},`${r.lag_weeks>0?'+':''}${r.lag_weeks}`));});
}
