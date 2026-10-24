import {finite, num, escapeHTML as esc} from './model.js';

export var MODEL_META = [
  {id: 'logistic', name: 'L2 다항 로지스틱 회귀'},
  {id: 'forest', name: '깊이 제한 랜덤포레스트'},
  {id: 'arima', name: 'ARIMA(1,1,0) + drift'},
  {id: 'sarima', name: 'SARIMA(1,1,0)(1,0,0,s)'},
  {id: 'ets', name: 'ETS(A,Ad,N) · log price'},
  {id: 'baseline', name: '과거 방향 빈도 / 가격 유지'}
];
export var COMPARISON_URL = './data/model_comparison.json';
var cache = null;

export function clearComparisonCache() { cache = null; }

export function modelName(id) {
  for (var i = 0; i < MODEL_META.length; i++) { if (MODEL_META[i].id === id) return MODEL_META[i].name; }
  return String(id == null ? '—' : id);
}

export function fmtBrier(v) { return finite(v) ? num(v, 4) : '—'; }
export function fmtLogLoss(v) { return finite(v) ? num(v, 4) : '—'; }
export function fmtMaeP(v) { return finite(v) ? num(v * 100, 1) + '%p' : '—'; }
export function fmtCover(v) { return finite(v) ? num(v * 100, 1) + '%' : '—'; }
export function fmtIntervalCell(ev) {
  ev = ev || {};
  var n = ev.intervalN;
  if (n == null || n <= 0) return '—';
  return fmtCover(ev.interval80Coverage) + ' / ' + fmtCover(ev.interval95Coverage) + ' (n=' + esc(String(n)) + ')';
}
export function fmtCount(v) { return v == null ? '—' : esc(String(v)); }

export function statusLabel(st) {
  if (st === 'evaluated') return '평가됨';
  if (st === 'insufficient_data') return '표본 부족';
  if (st === 'unevaluated') return '미평가';
  return '미산출';
}

export function bestRetrospective(entry) {
  if (!entry || !Array.isArray(entry.models)) return null;
  var best = null;
  entry.models.forEach(function(m) {
    if (!m) return;
    var b = m.evaluation ? m.evaluation.brier : null;
    if (!finite(b)) return;
    if (!best || b < best.brier) best = {candidate: m.candidate, name: m.name || modelName(m.candidate), brier: b};
  });
  return best;
}

export function comparisonBodyHtml(entry, comparison, opts) {
  opts = opts || {};
  if (!entry) {
    return '<p class="f-muted">모형 비교 대상 계열을 찾지 못했습니다. 기존 예측 검증 결과는 위에서 확인할 수 있습니다.</p>';
  }
  var models = Array.isArray(entry.models) ? entry.models : [];
  if (!models.length) {
    return '<p class="f-muted">이 계열의 모형 비교 표본이 없습니다.</p>';
  }
  var sel = entry.selection || {};
  var gates = entry.gates || {};
  var actualSel = sel.candidate || (entry.incumbent && entry.incumbent.candidate);
  var selId = opts.selectedModel || actualSel;
  var known = false;
  models.forEach(function(m) { if (m && m.candidate === selId) known = true; });
  if (!known) selId = actualSel;
  var best = bestRetrospective(entry);
  var passed = comparison && comparison.summary ? comparison.summary.passed : null;
  var common = entry.common || {};
  var optsHtml = MODEL_META.map(function(m) {
    return '<option value="' + esc(m.id) + '"' + (m.id === selId ? ' selected' : '') + '>' + esc(m.name) + '</option>';
  }).join('');
  var rows = models.map(function(m) {
    var ev = m.evaluation || {};
    var sl = m.selection || {};
    var isSel = m.candidate === actualSel;
    var isFocus = m.candidate === selId;
    var isBest = !!(best && m.candidate === best.candidate);
    var badges = '<span class="mc-badge' + (isSel ? ' mc-sel' : '') + '">' + (isSel ? '선택됨(과거)' : '미선택') + '</span>';
    if (isBest) badges += ' <span class="mc-badge mc-best">회고 최저</span>';
    var reasons = Array.isArray(m.reasons) ? m.reasons.filter(function(x) { return typeof x === 'string' && x.trim() !== ''; }) : [];
    var failObj = (m.failures && typeof m.failures === 'object') ? m.failures : null;
    var failKeys = failObj ? Object.keys(failObj) : [];
    var reasonHtml = reasons.length ? reasons.map(function(x) { return esc(x); }).join('<br>') : '—';
    if (failObj && failObj.code) {
      var fd = failObj.detail != null && failObj.detail !== '' ? String(failObj.detail) : '';
      reasonHtml += '<br><span class="mc-fail">' + esc('[' + String(failObj.code) + ']' + (fd ? ' ' + fd : '')) + '</span>';
      failKeys = failKeys.filter(function(k) { return k !== 'code' && k !== 'detail'; });
    }
    if (failKeys.length) reasonHtml += '<br><span class="mc-fail">' + failKeys.map(function(k) { var v = failObj[k]; return esc(k + ((v == null || v === '') ? '' : ': ' + String(v))); }).join('<br>') + '</span>';
    var standalone = finite(m.standaloneTestN) ? Number(m.standaloneTestN) : null;
    if (standalone !== null && standalone > 0) reasonHtml += '<br><span class="mc-fail">' + esc('별도 단독 성숙 예측 n=' + String(standalone) + ' (공통원점 비교 범위 밖; 미출력으로 보지 않음)') + '</span>';
    var rowCls = isSel ? ' class="mc-row-sel"' : (isFocus ? ' class="mc-row-focus"' : '');
    return '<tr' + rowCls + '><td>' + esc(m.name || modelName(m.candidate)) + '<br><span class="mc-id">' + esc(m.candidate) + '</span><br>' + badges + '</td>' +
      '<td>' + esc(statusLabel(m.status)) + '</td>' +
      '<td class="num">' + fmtCount(sl.n) + ' / ' + fmtLogLoss(sl.logLoss) + '</td>' +
      '<td class="num">' + fmtBrier(ev.brier) + '</td>' +
      '<td class="num">' + fmtLogLoss(ev.logLoss) + '</td>' +
      '<td class="num">' + fmtMaeP(ev.mae) + (finite(ev.rmse) ? '<br><span class="mc-id">RMSE ' + fmtMaeP(ev.rmse) + '</span>' : '') + '</td>' +
      '<td class="num">' + fmtIntervalCell(ev) + '</td>' +
      '<td class="num">' + fmtCount(ev.n) + ' / ' + fmtCount(ev.nonoverlapN) + '</td>' +
      '<td class="num">' + fmtCount(m.allTestN) + '</td>' +
      '<td>' + reasonHtml + '</td></tr>';
  }).join('');
  var html = '';
  html += '<p class="f-muted">선택됨 표시는 과거 선택 구간 기준이며 테스트 구간 성적이 아닙니다. 회고 테스트 최저는 같은 원점의 사후 조회일 뿐이고 선택 근거가 아닙니다.';
  if (passed === 0) html += ' 어떤 모형도 추천 기준을 통과하지 못했습니다(통과 0건). 개선 주장을 하지 않습니다.';
  html += '</p>';
  html += '<p class="f-muted">공통 원점: ' + fmtCount(common.selectionN) + ' 선택 / ' + fmtCount(common.testN) + ' 테스트 / 비중첩 ' + fmtCount(common.nonoverlapN) + (common.from ? (' · ' + esc(common.from) + ' → ' + esc(common.to || '')) : '') + '. 점수 없음은 —/미산출이며 0으로 채우지 않습니다. MAE는 %p, Brier/확률은 무단위입니다. 비교 universe는 기존 분류기 유효 원점으로 고정되며, 전체 n(기존 범위)은 그 안의 후보별 평가 가능 수입니다.</p>';
  var incumbent = entry.incumbent || {};
  var changed = incumbent.candidate && actualSel && incumbent.candidate !== actualSel;
  if (changed) html += '<p class="f-muted">선택 변경(과거 선택 구간 기준): ' + esc(modelName(incumbent.candidate)) + ' → ' + esc(modelName(actualSel)) + '. ' + esc(sel.reason || '') + ' 테스트 최저 모형으로 교체한 것이 아닙니다.</p>';
  else if (sel.reason) html += '<p class="f-muted">선택 유지: ' + esc(modelName(actualSel)) + '. ' + esc(sel.reason) + '</p>';
  var commonEv = entry.selectedEvaluation || {};
  var fullEv = entry.selectedAllEvaluation || null;
  if (fullEv) html += '<p class="f-muted">선택 모형의 공통원점 평가 n=' + fmtCount(commonEv.n != null ? commonEv.n : common.testN) + ' · Brier ' + fmtBrier(commonEv.brier) + ' / 선택 모형 전체 평가 n=' + fmtCount(fullEv.n) + ' · Brier ' + fmtBrier(fullEv.brier) + '. 두 n을 구분해 확인하십시오.</p>';
  html += '<p class="f-muted">80/95% 가격구간은 원분포 구간이며 검증된 확률이 아닙니다. 강조 드롭다운은 행 강조만 바꾸며 과거 선택 배지는 바뀌지 않습니다.</p>';
  html += '<label class="f-control" for="mc-model-' + esc(entry.id) + '"><span>강조할 모형</span><select id="mc-model-' + esc(entry.id) + '" data-mc-model>' + optsHtml + '</select></label>';
  html += '<div class="table-scroll"><table class="data-table mc-table"><thead><tr><th scope="col">모형</th><th scope="col">상태</th><th scope="col">선택 n · LogLoss</th><th scope="col">테스트 Brier</th><th scope="col">LogLoss</th><th scope="col">MAE(%p)</th><th scope="col">가격구간 80/95%(n)</th><th scope="col">공통 n / 비중첩</th><th scope="col">전체 n(기존 범위)</th><th scope="col">실패·사유</th></tr></thead><tbody>' + rows + '</tbody></table></div>';
  if (!gates.passed) {
    var gr = Array.isArray(gates.reasons) ? gates.reasons.filter(function(x) { return typeof x === 'string' && x.trim() !== ''; }) : [];
    html += '<p class="f-muted">선택 모형의 추천 사용 보류 사유: ' + (gr.length ? gr.map(function(x) { return esc(x); }).join(' · ') : '사유 없음') + '</p>';
  }
  return html;
}

export function loadComparison(url) {
  var u = url || COMPARISON_URL;
  if (cache) return Promise.resolve(cache);
  if (typeof fetch !== 'function') return Promise.resolve(null);
  return fetch(u, {cache: 'no-store'}).then(function(res) {
    if (!res.ok) throw new Error('HTTP ' + res.status);
    return res.json();
  }).then(function(data) { cache = data; return data; }).catch(function() { return cache; });
}

export function attachModelComparison(main, state, opts) {
  opts = opts || {};
  var wanted = state ? state.forecastSeries : null;
  var url = opts.url || COMPARISON_URL;
  var selectedModel = opts.selectedModel;
  function render(data) {
    if (state && state.forecastSeries !== wanted) return;
    if (!main || !main.querySelector) return;
    var box = main.querySelector('#model-comparison');
    if (!box || box.getAttribute('data-series') !== String(wanted)) return;
    var body = box.querySelector('[data-mc-body]');
    if (!body) return;
    var entry = null;
    if (data && Array.isArray(data.series)) {
      for (var i = 0; i < data.series.length; i++) {
        if (String(data.series[i].id) === String(wanted)) { entry = data.series[i]; break; }
      }
    }
    var sel = selectedModel;
    function paint() {
      if (state && state.forecastSeries !== wanted) return;
      body.innerHTML = comparisonBodyHtml(entry, data, {selectedModel: sel});
      var dd = body.querySelector('[data-mc-model]');
      if (dd && dd.addEventListener) {
        dd.addEventListener('change', function(ev) {
          sel = ev && ev.target ? ev.target.value : sel;
          paint();
        });
      }
    }
    try { paint(); } catch (e) { /* keep existing verification visible */ }
  }
  if (cache) { try { render(cache); } catch (e) {} return; }
  if (typeof fetch !== 'function') { try { render(null); } catch (e) {} return; }
  try {
    fetch(url, {cache: 'no-store'}).then(function(res) {
      if (!res.ok) throw new Error('HTTP ' + res.status);
      return res.json();
    }).then(function(data) { cache = data; render(data); }).catch(function() { try { render(cache); } catch (e) {} });
  } catch (e) { try { render(cache); } catch (e2) {} }
}
