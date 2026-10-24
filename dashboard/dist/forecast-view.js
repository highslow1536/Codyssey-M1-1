import {lineChart} from './charts.js?v=20261023-forecast';
import {escapeHTML as esc, finite, num, pct} from './model.js';
export var CLASS_LABELS = ['하락3%초과', '보합±3%', '상승3%초과'];
function fmtPrice(v, currency) {
  if (!finite(v)) return '확인 필요';
  var c = currency || '원';
  if (c === 'KRW') return num(v, 0) + '원';
  return num(v, 2) + ' ' + c;
}
function fmtChange(v) {
  return finite(v) ? pct(v) : '표본 부족';
}
function fmtScore(v, digits) {
  return finite(v) ? num(v, digits == null ? 4 : digits) : '표본 부족';
}
function fmtMae(v) {
  return finite(v) ? num(v * 100, 1) + '%p' : '표본 부족';
}
function fmtCI(ci) {
  if (!Array.isArray(ci) || ci.length !== 2) return '산출할 시간 표본 부족';
  if (!finite(ci[0]) || !finite(ci[1])) return '산출할 시간 표본 부족';
  return num(ci[0], 4) + ' ~ ' + num(ci[1], 4) + ' (평균 제곱점수 차이, %p 아님)';
}
function opts(rows, selected) {
  return rows.map(function(r) {
    var on = String(r[0]) === String(selected) ? ' selected' : '';
    return '<option value="' + esc(r[0]) + '"' + on + '>' + esc(r[1]) + '</option>';
  }).join('');
}
function selectorRow(id, label, rows, selected) {
  return '<label class="f-control" for="' + id + '"><span>' + label + '</span>' +
    '<select id="' + id + '" data-select="' + id + '">' + opts(rows, selected) + '</select></label>';
}
function metricCard(label, value, sub) {
  return '<div class="f-metric"><span>' + label + '</span><strong>' + value + '</strong><small>' + sub + '</small></div>';
}
function tableHtml(headers, rows) {
  var h = headers.map(function(x) { return '<th scope="col">' + x + '</th>'; }).join('');
  var b = rows.map(function(r) {
    return '<tr>' + r.map(function(c) { return '<td>' + c + '</td>'; }).join('') + '</tr>';
  }).join('');
  return '<div class="table-scroll"><table class="data-table"><thead><tr>' + h + '</tr></thead><tbody>' + b + '</tbody></table></div>';
}
function downloadLink(file, label) {
  return '<a class="button" href="./data/downloads/' + file + '" download>' + label + ' ↓</a>';
}
export function probabilityPresentation(probabilities) {
  var empty = {kind: 'empty', reason: '확률 없음', sum: null, percents: [null, null, null]};
  if (!Array.isArray(probabilities) || probabilities.length !== 3) return empty;
  var vals = probabilities.map(function(v) { return finite(v) ? v : null; });
  if (vals[0] == null || vals[1] == null || vals[2] == null) return empty;
  if (vals[0] < 0 || vals[1] < 0 || vals[2] < 0 || vals[0] > 1 || vals[1] > 1 || vals[2] > 1) {
    return {kind: 'invalid', reason: '확률이 0~1 범위를 벗어났습니다.', sum: vals[0] + vals[1] + vals[2], percents: [null, null, null]};
  }
  var s = vals[0] + vals[1] + vals[2];
  if (!finite(s)) return empty;
  if (Math.abs(s - 1) > 1e-9) {
    return {kind: 'invalid', reason: '세 확률의 합이 1이 아닙니다.', sum: s, percents: [null, null, null]};
  }
  return {kind: 'valid', reason: '', sum: s, percents: vals.map(function(v) { return v * 100; }), values: vals};
}
export function gatePresentation(gates) {
  if (!gates || typeof gates !== 'object') {
    return {passed: false, badge: '실험용', reasons: ['추천 사용 기준 결과 없음. 추천에 사용하지 마십시오.']};
  }
  var raw = Array.isArray(gates.reasons) ? gates.reasons : [];
  var reasons = raw.filter(function(r) { return typeof r === 'string' && r.trim() !== ''; });
  if (gates.passed === true) return {passed: true, badge: '추천 통과', reasons: reasons};
  if (!reasons.length) reasons = ['추천 사용 기준를 통과하지 못했습니다. 실험용으로만 확인하십시오.'];
  return {passed: false, badge: '실험용', reasons: reasons};
}
function freqLabel(f) {
  if (f === 'monthly') return '월간';
  return '주간';
}
function className(i) {
  return CLASS_LABELS[i] || ('구간' + String(i));
}
export function calibrationGraphic(rows){
  const good=rows.filter(r=>finite(r.predicted)&&finite(r.observed)&&r.n>0);
  if(!good.length)return '<p class="f-muted">보정을 그릴 표본이 없습니다.</p>';
  const colors=['#197b68','#8c8f94','#b5653d'],x=v=>52+v*312,y=v=>270-v*220;
  const ticks=[0,.25,.5,.75,1];
  return `<svg viewBox="0 0 410 320" role="img" aria-label="확률 보정: 평균 추정과 실제 발생 빈도. 대각선에 가까울수록 일치합니다."><rect x="52" y="50" width="312" height="220" fill="#f8faf9"/>${ticks.map(t=>`<line x1="52" x2="364" y1="${y(t)}" y2="${y(t)}" stroke="#dce5e0"/><text x="44" y="${y(t)+4}" text-anchor="end" font-size="11" fill="#5c6d67">${Math.round(t*100)}%</text><text x="${x(t)}" y="289" text-anchor="middle" font-size="11" fill="#5c6d67">${Math.round(t*100)}%</text>`).join('')}<line x1="52" y1="270" x2="364" y2="50" stroke="#777" stroke-dasharray="4 4"/>${good.map(r=>`<circle cx="${x(r.predicted)}" cy="${y(r.observed)}" r="${Math.min(8,3+Math.sqrt(r.n)/2)}" fill="${colors[r.class]}" fill-opacity=".8"><title>${className(r.class)} · n=${r.n} · 추정 ${num(r.predicted*100,1)}% · 실제 ${num(r.observed*100,1)}%</title></circle>`).join('')}<text x="208" y="311" text-anchor="middle" font-size="12" fill="#344b42">모형의 평균 추정 확률</text><text x="52" y="25" font-size="12" fill="#344b42">실제 발생 빈도</text></svg><div class="legend">${['하락','보합','상승'].map((c,i)=>`<span><i style="background:${colors[i]}"></i>${c}</span>`).join('')}</div>`;
}
export function backtestChartPoints(rows,field,frequency){
  if(!rows.length)return [];
  const byOrigin=new Map(rows.map(r=>[r.origin,r])),keys=[...byOrigin.keys()].sort(),out=[];
  let d=new Date(keys[0]+'T00:00:00Z');const last=keys.at(-1);
  while(d.toISOString().slice(0,10)<=last){const key=d.toISOString().slice(0,10),r=byOrigin.get(key);
    out.push({date:key,value:finite(r?.[field])?r[field]*100:null});
    if(frequency==='monthly')d.setUTCMonth(d.getUTCMonth()+1);else d.setUTCDate(d.getUTCDate()+7);
  }
  return out;
}
function isOverseas(s) {
  if (s.currency && s.currency !== 'KRW') return true;
  if (s.region && !['KR','국내'].includes(s.region)) return true;
  return false;
}
function beatLine(ok) {
  if (ok === true) return '기준점보다 낮습니다(낮을수록 좋음).';
  if (ok === false) return '기준점을 이기지 못했습니다.';
  return '비교할 기준점 없음.';
}
export function renderForecast(main, data, state) {
  var series = data && Array.isArray(data.series) ? data.series : [];
  var asOf = data && data.asOf ? data.asOf : '기준일 없음';
  var protocolUrl = data && data.protocolUrl ? data.protocolUrl : './data/downloads/forecast_protocol.md';
  state = state || {};
  if (!series.length) {
    main.innerHTML = '<section class="f-hero"><div><div class="f-kicker">3개월 확률 검증 화면</div>' +
      '<h1>표시할 예측 계열이 없습니다</h1><p>모형 산출물이 아직 없습니다. 모형 산출물을 확인해 주세요.</p></div>' +
      '<div class="f-stamp"><b>' + esc(asOf) + '</b><span>프로토콜 확인 필요</span></div></section>' +
      '<section class="panel"><div class="panel-inner"><p>계열이 없습니다. ' +
      '<a href="' + esc(protocolUrl) + '">예측 프로토콜</a>을 먼저 확인하십시오.</p></div></section>';
    return;
  }
  var wanted = state.forecastSeries;
  var s = null;
  var i = 0;
  for (i = 0; i < series.length; i++) { if (String(series[i].id) === String(wanted)) s = series[i]; }
  if (!s) s = series[0];
  state.forecastSeries = s.id;
  var gate = gatePresentation(s.gates);
  var fc = s.forecast && s.forecast.available !== false ? s.forecast : null;
  var prob = fc ? probabilityPresentation(fc.probabilities) : {kind: 'empty', reason: '확률 없음', sum: null, percents: [null, null, null]};
  var ev = s.evaluation || {};
  var cov = s.coverage || {};
  var pts = Array.isArray(s.points) ? s.points : [];
  var bt = Array.isArray(s.backtests) ? s.backtests : [];
  var rel = Array.isArray(ev.reliability) ? ev.reliability : [];
  var cc = Array.isArray(ev.classCounts) && ev.classCounts.length === 3 ? ev.classCounts : [null, null, null];
  var overseas = isOverseas(s);
  var monthly = s.frequency === 'monthly';
  var brierBeat = finite(ev.brier) && finite(ev.baselineBrier) ? ev.brier < ev.baselineBrier : null;
  var maeBeat = finite(ev.mae) && finite(ev.naiveMae) ? ev.mae < ev.naiveMae : null;
  var rows = series.map(function(x) { return [x.id, '['+({'KR':'국내','US':'미국','IN':'인도','DE':'독일'}[x.region]||x.region)+' '+freqLabel(x.frequency)+'] ' + (x.category ? x.category + ' · ' : '') + x.name]; });
  var html = '';
  html += '<section class="f-hero"><div><div class="f-kicker">3개월 실제 학습 확률 · 검증 화면</div>' +
    '<h1>3개월 뒤, 오를까 내릴까?</h1>' +
    '<p>이 화면은 실제 학습한 모형의 확률과 회고 검증 결과를 보여줍니다. ' + esc(String(asOf)) + ' 기준 관측에 한합니다.</p></div>' +
    '<div class="f-stamp"><b>' + esc(String(asOf)) + '</b><span>관측 기준 · 실시간 아님</span></div></section>';
  html += '<section class="f-picker" aria-label="예측 계열 선택">' + selectorRow('forecastSeries', '예측 계열', rows, s.id) +
    '<span class="f-proto"><a href="' + esc(protocolUrl) + '">예측 프로토콜</a></span></section>';
  html += '<section class="panel f-identity"><div class="panel-head"><div><h2>' + esc(s.name || s.id) + '</h2>' +
    '<p class="panel-subtitle">' + esc(s.category || '') + ' · ' + esc({'KR':'한국','US':'미국','IN':'인도','DE':'독일'}[s.region]||s.region||'') + ' · ' + esc(s.currency || '') +
    ' · 조건 ' + esc(s.condition==='renewed'?'리퍼':s.condition==='new'?'신품':s.condition||'미확인') + ' · ' + freqLabel(s.frequency) + ' 관측</p></div>' +
    '<span class="pill ' + (gate.passed ? 'f-pass' : 'f-exp') + '">' + gate.badge + '</span></div>' +
    '<div class="panel-inner"><div class="f-coverage"><strong>유효 관측 '+(cov.observed??0)+' / '+(cov.total??0)+(monthly?'개월':'주')+'</strong><span>'+esc(cov.first||'—')+' → '+esc(cov.last||'—')+' · 원시 '+(cov.rawN??0)+'건 · 제외 '+(cov.excludedN??0)+'건</span></div>' +
    '<p class="f-src">수집 출처: ' + (s.sourceUrl ? '<a href="' + esc(s.sourceUrl) + '" target="_blank" rel="noopener noreferrer">원문 ↗</a>' : '출처 미표기') +
    (s.domesticId ? ' · 국내 제품 코드: ' + esc(s.domesticId) : ' · 해외 리스팅별 모형') + '</p>' +
    (s.selection ? '<details class="f-method"><summary>모형 선택 방식</summary><div><p class="f-muted">선택 상태: ' + esc(s.selection.status || '') + ' · 후보 ' + esc(s.selection.candidate != null ? String(s.selection.candidate) : '—') + ' · 온도 ' + (finite(s.selection.temperature) ? num(s.selection.temperature, 3) : '—') + ' · n=' + (s.selection.n != null ? String(s.selection.n) : '—') + '</p></div></details>' : '') +
    '</div></section>';
  if (overseas) {
    html += '<div class="f-ban" role="alert"><strong>해외 관측값입니다. 국내 구매 추천에 사용하지 마십시오.</strong>' +
      '<span>통화·시장·수집처가 다릅니다. 국내 가격 판단과 같은 선으로 비교하지 마십시오.</span></div>';
  }
  if (monthly) {
    html += '<div class="f-warn"><strong>월간 목표는 마지막 완료월 +3개월입니다.</strong>' +
      '<span>2026-09 → 2026-12 버킷의 실험입니다. 오늘부터 3개월 뒤인 2027-01의 국내 판매가 예측으로 사용하지 않습니다.</span></div>';
  }
  html += '<div class="f-grid">';
  html += '<section class="panel"><div class="panel-head"><div><h2>3개월 뒤 모형 추정</h2>' +
    '<p class="panel-subtitle">' + (fc ? '기준 ' + esc(monthly?(fc.origin||'').slice(0,7):fc.origin||'') + ' → 목표 ' + esc(monthly?(fc.target||'').slice(0,7):fc.target||'') : '제시된 미래 목표 없음') + '</p></div>' +
    '<span class="pill ' + (gate.passed ? 'f-pass' : 'f-exp') + '">' + (gate.passed ? '추천 통과' : '실험용') + '</span></div><div class="panel-inner">';
  if (!fc) {
    html += '<p class="f-muted">예측 없음. 모형이 확률을 제시하지 않았습니다. 학습 표본·클래스 부족으로 산출을 보류했습니다.</p>';
  } else {
    html += '<div class="f-idgrid">' +
      metricCard('기준 가격', fmtPrice(fc.price, s.currency), monthly?'원문 버킷 '+esc((fc.origin||'').slice(0,7)):'실제 관측 '+esc(fc.quoteDate||fc.origin||'')) +
      metricCard('모형', esc(fc.model || '미표기'), '온도 ' + (finite(fc.temperature) ? num(fc.temperature, 3) : '—')) +
      metricCard('학습 행 수', fc.trainN != null ? String(fc.trainN) : '—', (monthly?'SKU×월 · ':'주별 원점 · ')+'정답 확보 '+esc(fc.trainThrough || '')) +
      '</div>';
    if (prob.kind === 'valid') {
      html += '<div class="f-probs">' + prob.values.map(function(v, k) {
        return '<div><span>' + className(k) + '</span><strong>' + num(v * 100, 1) + '%</strong></div>';
      }).join('') + '</div><p class="f-muted">세 확률의 합은 1입니다(합 ' + num(prob.sum, 3) + '). 확률의 보정 결과는 아래에서 확인하세요.</p>';
    } else if (prob.kind === 'invalid') {
      html += '<p class="f-ban f-ban-inline" role="alert">확률 합이 1이 아닙니다(합 ' + esc(fmtScore(prob.sum, 3)) + '). 이 확률을 사용하지 마십시오.</p>';
    } else {
      html += '<p class="f-muted">확률을 산출할 학습 조건을 충족하지 못했습니다. 학습 표본·클래스 부족으로 산출을 보류했습니다.</p>';
    }
    if (!gate.passed) {
      html += '<div class="f-gate-fail" role="note"><strong>실험용 확률입니다. 구매 판단에 사용하지 마십시오.</strong><p class="f-muted">'+(brierBeat===false?'확률 오차가 과거 빈도 기준보다 컸습니다.':brierBeat===true?'평균 점수는 개선됐지만 표본·안정성·보정 기준을 모두 통과하지 못했습니다.':'최종 평가 표본이 부족합니다.')+'</p><details class="f-method"><summary>추천 사용을 보류한 이유 '+gate.reasons.length+'개</summary><ul>' +
        gate.reasons.map(function(r) { return '<li>' + esc(r) + '</li>'; }).join('') + '</ul></details></div>';
    } else if (gate.reasons.length) {
      html += '<ul class="f-gate-pass">' + gate.reasons.map(function(r) { return '<li>' + esc(r) + '</li>'; }).join('') + '</ul>';
    }
  }
  html += '</div></section>';
  html += '<section class="panel"><div class="panel-head"><div><h2>검증 모형과 기준점수</h2>' +
    '<p class="panel-subtitle">' + esc(ev.from || '') + ' → ' + esc(ev.to || '') + ' · 낮을수록 좋음</p></div></div><div class="panel-inner">' +
    '<div class="f-idgrid">' +
    metricCard('검증 횟수', ev.n != null ? String(ev.n) : '—', '서로 다른 원점 ' + (ev.originsN != null ? String(ev.originsN) : '—') + ' · 비중첩 ' + (ev.nonoverlapN != null ? String(ev.nonoverlapN) : '—')) +
    metricCard('Brier', fmtScore(ev.brier), '기준 ' + fmtScore(ev.baselineBrier)) +
    metricCard('LogLoss', fmtScore(ev.logLoss), '기준 ' + fmtScore(ev.baselineLogLoss)) +
    metricCard('정확도', finite(ev.accuracy) ? num(ev.accuracy * 100, 1) + '%' : '표본 부족', '높을수록 좋음') +
    metricCard('ECE', fmtScore(ev.ece), '보정 오차 · 낮을수록 좋음') +
    metricCard('MAE', fmtMae(ev.mae), '단위 %p · 낮을수록 좋음') +
    metricCard('유지 MAE', fmtMae(ev.naiveMae), '가격 그대로 예측한 경우') +
    metricCard('드리프트 MAE', fmtMae(ev.driftMae), '추세 연장 기준') +
    '</div>' +
    '<p class="f-muted">기준 대비 Brier 개선: ' + (finite(ev.brierSkill) ? num(ev.brierSkill * 100, 1) + '%' : '—') + ' · ' + beatLine(brierBeat) + '</p>' +
    '<p class="f-muted">MAE 비교: ' + beatLine(maeBeat) + ' MAE는 %p 단위입니다.</p>' +
    '<p class="f-muted">개선 신뢰구간: ' + fmtCI(ev.improvementCI) + '</p>' +
    '<p class="f-muted">구간 표본: 하락 ' + (cc[0] != null ? String(cc[0]) : '—') + ' · 보합 ' + (cc[1] != null ? String(cc[1]) : '—') + ' · 상승 ' + (cc[2] != null ? String(cc[2]) : '—') + '</p>';
  if (rel.length) {
    html += '<div class="f-calibration">'+calibrationGraphic(rel)+'</div><p class="f-muted">점 하나는 확률대별 묶음입니다. 대각선에서 멀수록 표시한 확률과 실제 빈도가 달랐습니다.</p><details class="f-method"><summary>보정 표와 구간별 표본 수</summary><div>'+tableHtml(['방향 / 예측 확률대', 'n', '평균 추정', '실제 빈도', 'Wilson 하한', '상한'], rel.map(function(r) {
      return [esc(className(r.class))+(finite(r.binLow)?'<br>'+num(r.binLow*100,0)+'–'+num(r.binHigh*100,0)+'%':''), r.n != null ? String(r.n) : '—', fmtScore(r.predicted, 3), fmtScore(r.observed, 3), fmtScore(r.low, 3), fmtScore(r.high, 3)];
    }))+'</div></details>';
  } else {
    html += '<p class="f-muted">보정 bins 없음. 구간별 보정을 평가할 표본이 부족합니다.</p>';
  }
  html += '<p class="f-muted">Brier는 세 방향 확률의 제곱오차 합(0–2)입니다. 기준 확률은 학습 구간의 발생 빈도(+1 보정)입니다. 보정 표는 확률대별 평균 추정과 실제 빈도를 비교합니다. Wilson 구간은 중첩 시계열의 의존성을 반영한 보증 구간이 아닙니다.</p></div></section></div>';
  html += '<section class="panel section-block"><div class="panel-head"><div><h2>원자료 장기 가격</h2>' +
    '<p class="panel-subtitle">' + esc(s.currency || '') + ' · 관측값 그대로 · 이월 없음</p></div></div>' +
    '<div id="forecast-history" class="chart-zone"></div>' +
    '<div class="panel-foot">관측 ' + (cov.observed != null ? String(cov.observed) : '—') + ' / 달력 ' + (cov.total != null ? String(cov.total) : '—') + ' · 회색 공백은 미관측으로 연결하지 않습니다.</div></section>';
  var anchors=Array.isArray(s.archivedObservations)?s.archivedObservations:[];
  if(anchors.length){
    html+='<section class="panel section-block"><div class="panel-head"><div><h2>추가 확보한 국내 과거 가격</h2><p class="panel-subtitle">아카이브 '+anchors.length+'건 · 같은 제품 페이지의 당시 일반 최저가</p></div><span class="pill f-exp">모형 입력 제외</span></div><div id="forecast-anchors" class="chart-zone"></div><div class="panel-inner"><p class="f-muted">위 월간 차트와 가격 집계·배송 기준이 달라 이어 붙이지 않았습니다. 점 사이의 가격은 미관측이며, 학습 표본을 늘리기 위한 보간도 하지 않았습니다.</p>'+tableHtml(['기록 날짜','일반 최저가','배송 포함 표기','현금 최저가','원문'],anchors.map(a=>[esc(a.anchor_date),fmtPrice(a.ordinary_lowest_krw,'KRW'),fmtPrice(a.delivered_krw,'KRW'),fmtPrice(a.cash_lowest_krw,'KRW'),'<a href="'+esc(a.source_url)+'" target="_blank" rel="noopener noreferrer">아카이브 ↗</a>']))+'</div></section>';
  }
  if(s.quarantinedArchives?.length){html+='<div class="f-warn"><strong>과거 원문 1건의 가격 기준 충돌을 확인했습니다.</strong><span>2020-11-25 DDR4 페이지의 hidden 가격 61,900원과 메타 일반가 64,220원이 달라 일반가 그래프·학습에서 격리했습니다. 원문과 제외 사유는 다운로드에 보존했습니다.</span></div>';}
  html += '<section class="panel section-block"><div class="panel-head"><div><h2>회고 검증: 실제와 예측 변화</h2>' +
    '<p class="panel-subtitle">예측 원점 기준 · 3개월 뒤 실제 변화율과 모형 점 예측 · 빈 구간은 미관측</p></div></div>' +
    '<div id="forecast-backtest" class="chart-zone"></div>';
  if (bt.length) {
    html += '<details class="f-method"><summary>검증 사례 '+bt.length+'개 자세히 보기</summary><div>'+tableHtml(['기준일', '목표일', '실제 변화', '예측 변화', '실제 구간', '예측 확률'], bt.map(function(b) {
      var pp = Array.isArray(b.probabilities) && b.probabilities.length === 3 ? b.probabilities.map(function(v) { return finite(v) ? num(v * 100, 1) + '%' : '—'; }).join(' / ') : '확률 없음';
      return [esc(b.origin || ''), esc(b.target || ''), fmtChange(b.actualChange), fmtChange(b.predictedChange), esc(b.actualClass != null ? className(b.actualClass) : '—'), esc(pp)];
    }))+'</div></details>';
  } else {
    html += '<p class="f-muted">회고 검증 표본이 없습니다.</p>';
  }
  html += '</section>';
  var lims = Array.isArray(s.limitations) ? s.limitations : [];
  var topLims = data && Array.isArray(data.limitations) ? data.limitations : [];
  if (lims.length || topLims.length) {
    html += '<details class="f-method"><summary>한계와 주의점</summary><div><p>' +
      lims.map(function(x) { return esc(x); }).join('<br>') +
      (lims.length && topLims.length ? '<br>' : '') +
      topLims.map(function(x) { return esc(x); }).join('<br>') + '</p></div></details>';
  }
  html += '<details class="f-method"><summary>수집 출처와 내려받기</summary><div>' +
    '<p>수집 출처: ' + (s.sourceUrl ? '<a href="' + esc(s.sourceUrl) + '" target="_blank" rel="noopener noreferrer">원문 ↗</a>' : '출처 미표기') +
    ' · 프로토콜: <a href="' + esc(protocolUrl) + '">forecast_protocol.md</a></p>' +
    '<div class="download-list">' + downloadLink('forecast_predictions.csv', '예측 CSV') + downloadLink('forecast_weekly.csv', '가격 입력 CSV · 주/월') + downloadLink('forecast_metrics.csv', '검증지표 CSV') + downloadLink('forecast_report.md','검증 결과 보고서') + downloadLink('forecast_selection_predictions.csv','모형 선택 구간 CSV') + downloadLink('excluded_observations.csv','제외 내역 CSV') + downloadLink('forecast_domestic_archives.csv','국내 과거 스냅샷 CSV') + '<a class="button" href="./data/downloads/forecast.json" download>전체 JSON ↓</a></div>' +
    '<p class="f-muted">예측 CSV에는 원점·목표·학습 마감일·세 확률·실제 결과가 담겨 있습니다.</p></div></details>';
  main.innerHTML = html;
  var hEl = main.querySelector ? main.querySelector('#forecast-history') : null;
  if (hEl) {
    try {
      lineChart(hEl, [{name: s.name || s.id, color: '#197b68', points: pts.map(function(p) { return {date: p.date, value: finite(p.price) ? p.price : null}; })}], {title: (s.name || s.id) + ' 원자료 가격', unit: s.currency || '', showPoints: true, monthly: monthly, monthlyLabel: '원문 월간 버킷'});
    } catch (e) { hEl.innerHTML = '<div class="empty-chart">차트를 표시하지 못했습니다.</div>'; }
  }
  var aEl=main.querySelector?main.querySelector('#forecast-anchors'):null;
  if(aEl){
    var ap=[];
    anchors.forEach((a,i)=>{ap.push({date:a.anchor_date,value:a.ordinary_lowest_krw});if(i<anchors.length-1){var next=anchors[i+1];var mid=new Date((Date.parse(a.anchor_date)+Date.parse(next.anchor_date))/2).toISOString().slice(0,10);ap.push({date:mid,value:null});}});
    lineChart(aEl,[{name:'당시 일반 최저가',color:'#9a6b00',points:ap}],{title:'국내 과거 아카이브 가격 · 미관측 구간을 잇지 않음',unit:'원 · 배송 기준 별도',showPoints:true});
  }
  var bEl = main.querySelector ? main.querySelector('#forecast-backtest') : null;
  if (bEl) {
    try {
      lineChart(bEl, [{name: '실제 변화', color: '#197b68', points: backtestChartPoints(bt,'actualChange',s.frequency)}, {name: '예측 변화', color: '#8270b8', points: backtestChartPoints(bt,'predictedChange',s.frequency), dashed: true}], {title: '회고 검증 실제와 예측 변화', unit: '%', showPoints: true,monthly:monthly,monthlyLabel:'예측 원점 버킷'});
    } catch (e) { bEl.innerHTML = '<div class="empty-chart">차트를 표시하지 못했습니다.</div>'; }
  }
}
