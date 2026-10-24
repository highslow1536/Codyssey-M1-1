'use strict';
var DATA_URL = '../../data/public/dashboard.json';
var MC_URL = '../../data/public/model_comparison.json';
var mc = { data: null, model: 'all', series: 'all' };
var MERGE_DATE = '2022-09-15';
var SVG_NS = 'http://www.w3.org/2000/svg';
var state = { data: null, year: 'all', metric: 'price_usd', focusIdx: 0, geom: null };

var METRICS = {
  price_usd: { label: 'ETH USD 가격', title: 'ETH USD 가격 추이', axis: 'USD', color: '#166e58' },
  proxy_a: { label: '수익 대용 A', title: '수익 대용 A 추이', axis: 'USD / 100 MH/s / 일', color: '#2c6e8a' },
  proxy_b: { label: '수익 대용 B', title: '수익 대용 B 추이', axis: 'USD / 100 MH/s / 일', color: '#8270b8' }
};

function el(id) { return document.getElementById(id); }
function fmtInt(v) {
  if (v === null || v === undefined) return '-';
  return Number(v).toLocaleString('en-US');
}
function fmtPrice(v) {
  if (v === null || v === undefined) return '-';
  return '$' + Number(v).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
function fmtIdx(v) {
  if (v === null || v === undefined) return '-';
  return Number(v).toFixed(4);
}
function fmtVal(metric, v) {
  if (metric === 'price_usd') return fmtPrice(v);
  return fmtIdx(v);
}
function fmtErr(v, digits) {
  if (v === null || v === undefined) return '-';
  return Number(v).toFixed(digits);
}
function esc(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function selectTab(name) {
  var tabs = document.querySelectorAll('[role="tab"]');
  tabs.forEach(function(t) {
    var on = t.getAttribute('data-tab') === name;
    t.setAttribute('aria-selected', on ? 'true' : 'false');
    if (on) { t.removeAttribute('tabindex'); } else { t.setAttribute('tabindex', '-1'); }
    el('panel-' + t.getAttribute('data-tab')).hidden = !on;
  });
  document.querySelectorAll('[data-tab-link]').forEach(function(a) {
    if (a.getAttribute('data-tab-link') === name) { a.classList.add('active'); }
    else { a.classList.remove('active'); }
  });
  if (location.hash !== '#' + name) { history.replaceState(null, '', '#' + name); }
}

function filteredSeries() {
  var rows = state.data.series || [];
  if (state.year === 'all') return rows;
  return rows.filter(function(r) { return r.date.indexOf(state.year + '-') === 0; });
}

function render() {
  if (!state.data) return;
  var rows = filteredSeries();
  var m = state.metric;
  var meta = METRICS[m];
  var n = rows.length;
  var valid = 0, nulls = 0, min = null, max = null, sum = 0;
  rows.forEach(function(r) {
    var v = r[m];
    if (v === null || v === undefined) { nulls += 1; return; }
    valid += 1; sum += Number(v);
    if (min === null || v < min) min = v;
    if (max === null || v > max) max = v;
  });
  el('kpi-n').textContent = fmtInt(n);
  el('kpi-valid').textContent = fmtInt(valid);
  el('kpi-metric').textContent = meta.label;
  var rangeTxt = n > 0 ? rows[0].date + ' ~ ' + rows[n - 1].date : '범위 없음';
  el('kpi-range').textContent = rangeTxt;
  el('kpi-nullnote').textContent = '빈 값 ' + fmtInt(nulls) + '행. 대용은 머지 부분일·PoW 종료 뒤 해당 없음 (0으로 채우지 않음)';
  el('n-pill').textContent = 'n ' + fmtInt(n) + ' / 유효 ' + fmtInt(valid);
  el('chart-title').textContent = meta.title;
  el('chart-sub').textContent = rangeTxt + ' · Coin Metrics Community Data';
  drawChart(rows, m, meta);
  renderSummary(rows, m, meta, n, valid, nulls, min, max, sum);
  el('legend').innerHTML = '<span><i style="background:' + meta.color + '"></i>' + esc(meta.label) + ' (' + esc(meta.axis) + '축, 단일 지표)</span><span>빈 값 구간: 선 끊김</span><span>2022-09-15: 부분일 (점선)</span>';
}

function renderSummary(rows, m, meta, n, valid, nulls, min, max, sum) {
  var tb = el('summary-table').querySelector('tbody');
  var mean = valid > 0 ? sum / valid : null;
  var html = '';
  html += '<tr><td>선택 범위</td><td>' + esc(rows.length ? rows[0].date + ' ~ ' + rows[rows.length-1].date : '-') + '</td></tr>';
  html += '<tr><td>선택 기간 날짜 수</td><td class="num">' + fmtInt(n) + '</td></tr>';
  html += '<tr><td>선택 지표 유효 n (' + esc(meta.label) + ', null 제외)</td><td class="num">' + fmtInt(valid) + '</td></tr>';
  html += '<tr><td>빈 값(null) 행 수 · 대용은 전환/종료 구간</td><td class="num">' + fmtInt(nulls) + '</td></tr>';
  html += '<tr><td>최소 / 최대</td><td class="num">' + fmtVal(m, min) + ' / ' + fmtVal(m, max) + '</td></tr>';
  html += '<tr><td>평균 (유효값만)</td><td class="num">' + fmtVal(m, mean) + '</td></tr>';
  tb.innerHTML = html;
}

function drawChart(rows, m, meta) {
  var svg = el('chart');
  while (svg.firstChild) svg.removeChild(svg.firstChild);
  var W = 760, H = 320, L = 64, R = 16, T = 14, B = 34;
  var iw = W - L - R, ih = H - T - B;
  function mk(tag, attrs) {
    var n = document.createElementNS(SVG_NS, tag);
    for (var k in attrs) n.setAttribute(k, attrs[k]);
    return n;
  }
  if (!rows.length) {
    var t = mk('text', { x: W/2, y: H/2, 'text-anchor': 'middle', 'class': 'tick' });
    t.textContent = '해당 범위에 데이터가 없습니다.';
    svg.appendChild(t);
    state.geom = null;
    return;
  }
  var vals = [];
  rows.forEach(function(r) { if (r[m] !== null && r[m] !== undefined) vals.push(Number(r[m])); });
  if (!vals.length) {
    var t2 = mk('text', { x: W/2, y: H/2, 'text-anchor': 'middle', 'class': 'tick' });
    t2.textContent = '선택 지표의 유효값이 없습니다 (전 구간 null).';
    svg.appendChild(t2);
    state.geom = null;
    return;
  }
  var lo = Math.min.apply(null, vals), hi = Math.max.apply(null, vals);
  if (lo === hi) { lo = lo * 0.99; hi = hi * 1.01; }
  var pad = (hi - lo) * 0.08;
  lo = Math.max(0, lo - pad); hi += pad;
  function X(i) { return L + (rows.length === 1 ? iw / 2 : (i / (rows.length - 1)) * iw); }
  function Y(v) { return T + ih - ((Number(v) - lo) / (hi - lo)) * ih; }
  var g = 4;
  for (var gi = 0; gi <= g; gi++) {
    var gv = lo + ((hi - lo) * gi) / g;
    var gy = Y(gv);
    svg.appendChild(mk('line', { x1: L, x2: W - R, y1: gy, y2: gy, 'class': 'gridline' }));
    var lab = mk('text', { x: L - 8, y: gy + 4, 'text-anchor': 'end', 'class': 'tick' });
    lab.textContent = (m === 'price_usd') ? ('$' + Math.round(gv).toLocaleString('en-US')) : Number(gv).toFixed(3);
    svg.appendChild(lab);
  }
  var ticks = 6;
  for (var ti = 0; ti < ticks; ti++) {
    var idx = Math.round((ti / (ticks - 1)) * (rows.length - 1));
    var tx = X(idx);
    var tl = mk('text', { x: tx, y: H - 10, 'text-anchor': 'middle', 'class': 'tick' });
    tl.textContent = rows[idx].date.slice(2);
    svg.appendChild(tl);
  }
  var mi = -1;
  rows.forEach(function(r, i) { if (r.date === MERGE_DATE) mi = i; });
  if (mi >= 0) {
    var mx = X(mi);
    svg.appendChild(mk('line', { x1: mx, x2: mx, y1: T, y2: T + ih, 'class': 'merge-line' }));
    var ml = mk('text', { x: mx + 5, y: T + 12, 'class': 'merge-label' });
    ml.textContent = '2022-09-15 부분일';
    svg.appendChild(ml);
  }
  var seg = [];
  rows.forEach(function(r, i) {
    var v = r[m];
    if (v === null || v === undefined) {
      if (seg.length > 1) drawSeg(seg);
      seg = [];
    } else {
      seg.push(i);
    }
  });
  function drawSeg(idxs) {
    var d = '';
    idxs.forEach(function(i, k) {
      var v = rows[i][m];
      d += (k === 0 ? 'M' : 'L') + X(i).toFixed(1) + ' ' + Y(v).toFixed(1);
    });
    svg.appendChild(mk('path', { d: d, 'class': 'series-line', stroke: meta.color }));
  }
  if (seg.length > 1) drawSeg(seg);
  else if (seg.length === 1) {
    var c = mk('circle', { cx: X(seg[0]), cy: Y(rows[seg[0]][m]), r: 3, 'class': 'focus-dot' });
    svg.appendChild(c);
  }
  var dot = mk('circle', { r: 5, 'class': 'focus-dot', visibility: 'hidden', id: 'focus-dot' });
  svg.appendChild(dot);
  var pts = rows.map(function(r, i) { return { x: X(i), y: (r[m] === null || r[m] === undefined) ? null : Y(r[m]), v: r[m], d: r.date }; });
  state.geom = { pts: pts, L: L, R: W - R };
  if (state.focusIdx >= rows.length) state.focusIdx = rows.length - 1;
}

function showTip(i) {
  var tip = el('tooltip');
  var svg = el('chart');
  var dot = svg.querySelector('#focus-dot');
  if (!state.geom || !state.geom.pts.length) return;
  if (i < 0) i = 0;
  if (i >= state.geom.pts.length) i = state.geom.pts.length - 1;
  state.focusIdx = i;
  var p = state.geom.pts[i];
  var m = state.metric;
  var txt = (p.v === null || p.v === undefined) ? 'null (선 끊김)' : fmtVal(m, p.v);
  tip.hidden = false;
  tip.innerHTML = '<strong>' + esc(p.d) + '</strong><div>' + esc(METRICS[m].label) + '<b>' + esc(txt) + '</b></div>';
  var wrapW = el('chart-wrap').clientWidth || 600;
  var frac = (p.x - 64) / (760 - 64 - 16);
  tip.style.left = (frac > 0.62 ? '8px' : 'auto');
  tip.style.right = (frac > 0.62 ? 'auto' : '8px');
  if (dot) {
    if (p.y === null) { dot.setAttribute('visibility', 'hidden'); }
    else { dot.setAttribute('visibility', 'visible'); dot.setAttribute('cx', p.x); dot.setAttribute('cy', p.y); }
  }
}
function hideTip() {
  el('tooltip').hidden = true;
  var dot = el('chart').querySelector('#focus-dot');
  if (dot) dot.setAttribute('visibility', 'hidden');
}

function renderForecast(fc) {
  el('f-series').textContent = fmtInt(fc.series);
  el('f-passed').textContent = fmtInt(fc.passed);
  el('f-rows').textContent = fmtInt(fc.predictionRows);
  var cards = el('forecast-cards');
  var table = el('forecast-table').querySelector('tbody');
  var ex = fc.examples || [];
  if (!ex.length) {
    cards.innerHTML = '<p class="muted">대표 예시가 없습니다.</p>';
    table.innerHTML = '<tr><td colspan="6">예시 없음</td></tr>';
    return;
  }
  var ch = '';
  ex.forEach(function(e, k) {
    ch += '<article class="card"><h3>' + esc(e.name || ('예시 ' + (k+1))) + '</h3>';
    ch += '<div class="card-id">' + esc(e.id || ('ex-' + (k+1))) + '</div><dl>';
    ch += '<dt>Brier</dt><dd>' + esc(fmtErr(e.brier, 4)) + ' <span class="base">(기준 ' + esc(fmtErr(e.baselineBrier, 4)) + ')</span></dd>';
    ch += '<dt>변화율 MAE</dt><dd>' + esc(fmtErr(e.mae * 100, 1)) + '%p <span class="base">(유지 ' + esc(fmtErr(e.naiveMae * 100, 1)) + '%p)</span></dd>';
    ch += '<dt>ECE</dt><dd>' + esc(fmtErr(e.ece * 100, 1)) + '%p</dd>';
    ch += '<dt>평가 행 / 비중첩 구간</dt><dd>' + esc(fmtInt(e.n)) + ' / ' + esc(fmtInt(e.nonoverlapN)) + '</dd>';
    ch += '<dt class="warn">낮을수록 좋음 · 미래 구매 추천에 미사용</dt>';
    ch += '</dl></article>';
  });
  cards.innerHTML = ch;
  var th = '';
  ex.forEach(function(e) {
    th += '<tr><td>' + esc(e.name || e.id || '-') + '</td><td class="num">' + esc(fmtInt(e.n)) + '</td><td class="num">' + esc(fmtInt(e.nonoverlapN)) + '</td><td class="num">' + esc(fmtErr(e.brier, 4)) + ' (' + esc(fmtErr(e.baselineBrier, 4)) + ')</td><td class="num">' + esc(fmtErr(e.mae * 100, 1)) + ' (' + esc(fmtErr(e.naiveMae * 100, 1)) + ') %p</td><td class="num">' + esc(fmtErr(e.ece * 100, 1)) + '%p</td></tr>';
  });
  table.innerHTML = th;
}

function mcName(id) {
  var fb = { logistic: '다항 로지스틱', forest: '랜덤 포레스트', arima: 'ARIMA', sarima: 'SARIMA', ets: 'ETS', baseline: '기준(과거 빈도·유지)' };
  return fb[id] || String(id);
}
function mcNum(v, digits) {
  if (v === null || v === undefined || !isFinite(Number(v))) return '—';
  return Number(v).toFixed(digits);
}
function mcMaeP(v) {
  if (v === null || v === undefined || !isFinite(Number(v))) return '—';
  return (Number(v) * 100).toFixed(1) + '%p';
}
function mcCover(v) {
  if (v === null || v === undefined || !isFinite(Number(v))) return '—';
  return (Number(v) * 100).toFixed(1) + '%';
}
function mcInterval(ev) {
  ev = ev || {};
  var n = ev.intervalN;
  if (n === null || n === undefined || !isFinite(Number(n)) || Number(n) <= 0) return '—';
  return mcCover(ev.interval80Coverage) + ' / ' + mcCover(ev.interval95Coverage) + ' (n=' + fmtInt(n) + ')';
}
function mcStatus(st) {
  if (st === 'evaluated') return '평가됨';
  if (st === 'unavailable') return '미산출';
  return '미산출';
}
function mcBest(entry) {
  if (!entry || !entry.models) return null;
  var best = null;
  entry.models.forEach(function(m) {
    var b = m && m.evaluation ? m.evaluation.brier : null;
    if (b === null || b === undefined || !isFinite(Number(b))) return;
    if (!best || Number(b) < best.brier) best = { candidate: m.candidate, brier: Number(b) };
  });
  return best;
}
function mcFailHtml(m) {
  var f = m.failures;
  if (!f || typeof f !== 'object') return '';
  var ks = Object.keys(f);
  if (!ks.length) return '';
  if (f.code) {
    var fd = (f.detail === null || f.detail === undefined || f.detail === '') ? '' : ' ' + String(f.detail);
    return '<br><span class="mc-fail">[' + esc(String(f.code)) + ']' + esc(fd) + '</span>';
  }
  return '<br><span class="mc-fail">' + ks.map(function(k) {
    var v = f[k];
    return esc(k + ((v === null || v === undefined || v === '') ? '' : ': ' + String(v)));
  }).join('<br>') + '</span>';
}
function mcRowHtml(s, m, showSeries, best) {
  var ev = m.evaluation || {};
  var sl = m.selection || {};
  var actualSel = (s.selection || {}).candidate;
  var isSel = m.candidate === actualSel;
  var isBest = !!(best && m.candidate === best.candidate);
  var cell = esc(m.name || mcName(m.candidate)) + '<br><span class="mc-id">' + esc(m.candidate) + '</span> ';
  cell += isSel ? '<span class="mc-badge mc-sel">선택됨(과거)</span>' : '<span class="mc-badge">미선택</span>';
  if (isBest) cell += ' <span class="mc-badge mc-best">회고 최저</span>';
  if (showSeries && best && !isBest && mc.model === 'all') {
    cell += '<br><span class="mc-id">회고 최저: ' + esc(mcName(best.candidate)) + ' ' + mcNum(best.brier, 4) + '</span>';
  }
  var reasons = (m.reasons || []).filter(function(x) { return typeof x === 'string' && x !== ''; });
  var rhtml = reasons.length ? reasons.map(function(x) { return esc(x); }).join('<br>') : '—';
  var mcStandalone = (m.standaloneTestN === null || m.standaloneTestN === undefined || !isFinite(Number(m.standaloneTestN))) ? null : Number(m.standaloneTestN);
  if (mcStandalone !== null && mcStandalone > 0) rhtml += '<br><span class="mc-fail">' + esc('별도 단독 성숙 예측 n=' + mcStandalone + ' (공통원점 비교 범위 밖; 미출력으로 보지 않음)') + '</span>';
  var seriesCell = esc(s.name || s.id) + '<br><span class="mc-id">' + esc(s.id + ' · ' + (s.region || '') + ' ' + (s.frequency || '')) + '</span>';
  var rmse = (ev.rmse === null || ev.rmse === undefined || !isFinite(Number(ev.rmse))) ? '' : '<br><span class="mc-id">RMSE ' + mcMaeP(ev.rmse) + '</span>';
  return '<tr><td>' + seriesCell + '</td><td>' + cell + '</td><td>' + esc(mcStatus(m.status)) + '</td>' +
    '<td class="num">' + fmtInt(sl.n) + ' / ' + mcNum(sl.logLoss, 4) + '</td>' +
    '<td class="num">' + mcNum(ev.brier, 4) + '</td>' +
    '<td class="num">' + mcNum(ev.logLoss, 4) + '</td>' +
    '<td class="num">' + mcMaeP(ev.mae) + rmse + '</td>' +
    '<td class="num">' + mcInterval(ev) + '</td>' +
    '<td class="num">' + fmtInt(ev.n) + ' / ' + fmtInt(ev.nonoverlapN) + '</td>' +
    '<td class="num">' + fmtInt(m.allTestN) + '</td>' +
    '<td>' + rhtml + mcFailHtml(m) + '</td></tr>';
}
function buildMcSeriesOptions() {
  var sel = el('mc-series');
  if (!sel || !mc.data) return;
  var html = '<option value="all">전체 계열</option>';
  (mc.data.series || []).forEach(function(s) {
    html += '<option value="' + esc(s.id) + '">' + esc((s.name || s.id) + ' · ' + s.id) + '</option>';
  });
  sel.innerHTML = html;
  sel.value = mc.series;
}
function renderMc() {
  if (!mc.data) return;
  var d = mc.data;
  var sum = d.summary || {};
  el('mc-series-n').textContent = fmtInt(sum.series);
  el('mc-changed').textContent = fmtInt(sum.selectionChanged);
  el('mc-passed').textContent = fmtInt(sum.passed);
  el('mc-common-detail').textContent = '공통 테스트 행 ' + fmtInt(sum.commonTestRows) + ' · 통과 ' + fmtInt(sum.passed);
  var ids = (d.series || []).map(function(s) { return s.id; });
  if (mc.series !== 'all') ids = ids.filter(function(id) { return id === mc.series; });
  var tb = el('mc-table').querySelector('tbody');
  var html = '';
  ids.forEach(function(id) {
    var s = null;
    (d.series || []).forEach(function(x) { if (x.id === id) s = x; });
    if (!s) return;
    var models = s.models || [];
    var best = mcBest(s);
    var list = models;
    if (mc.model === 'all' && mc.series === 'all') {
      var actual = (s.selection || {}).candidate;
      var selM = null;
      models.forEach(function(m) { if (m.candidate === actual) selM = m; });
      list = selM ? [selM] : models.slice(0, 1);
    } else if (mc.model !== 'all') {
      list = models.filter(function(m) { return m.candidate === mc.model; });
    }
    list.forEach(function(m) { html += mcRowHtml(s, m, mc.series === 'all', best); });
  });
  tb.innerHTML = html || '<tr><td colspan="11">표시할 행이 없습니다.</td></tr>';
  var note = '선택됨 표시는 과거 선택 구간 기준이며 테스트 구간 성적이 아닙니다. 회고 테스트 최저는 같은 원점의 사후 조회이며 선택 근거가 아닙니다.';
  if (sum.passed === 0) note += ' 어떤 모형도 추천 기준을 통과하지 못했습니다(통과 0건). 개선 주장을 하지 않습니다.';
  note += ' 비교 universe는 기존 분류기 유효 원점으로 고정되며, 전체 n(기존 범위)은 그 안의 후보별 평가 가능 수입니다.';
  el('mc-note').textContent = note;
  var lim = el('mc-limitations');
  lim.innerHTML = (d.limitations || []).map(function(x) { return '<li>' + esc(String(x)) + '</li>'; }).join('') || '<li>한계 정보 없음</li>';
}
function initMc() {
  var mm = el('mc-model'), ms = el('mc-series');
  if (!mm || !ms) return;
  mm.addEventListener('change', function(ev) { mc.model = ev.target.value; renderMc(); });
  ms.addEventListener('change', function(ev) { mc.series = ev.target.value; renderMc(); });
  fetch(MC_URL, { cache: 'no-store' }).then(function(res) {
    if (!res.ok) throw new Error('HTTP ' + res.status);
    return res.json();
  }).then(function(data) {
    mc.data = data;
    buildMcSeriesOptions();
    renderMc();
  }).catch(function() {
    el('mc-note').textContent = '모형 비교 자료를 불러오지 못했습니다. 기존 예측 검증 요약은 위에서 확인할 수 있습니다.';
  });
}
function showError(msg) {
  var box = document.createElement('div');
  box.className = 'error-box';
  box.setAttribute('role', 'alert');
  box.textContent = msg;
  el('load-error').appendChild(box);
}

document.addEventListener('DOMContentLoaded', function() {
  document.querySelectorAll('[role="tab"]').forEach(function(t) {
    t.addEventListener('click', function() { selectTab(t.getAttribute('data-tab')); });
    t.addEventListener('keydown', function(ev) {
      if (ev.key !== 'ArrowRight' && ev.key !== 'ArrowLeft') return;
      ev.preventDefault();
      var tabs = Array.prototype.slice.call(document.querySelectorAll('[role="tab"]'));
      var i = tabs.indexOf(t);
      var n = (ev.key === 'ArrowRight') ? (i + 1) % tabs.length : (i - 1 + tabs.length) % tabs.length;
      tabs[n].focus();
      selectTab(tabs[n].getAttribute('data-tab'));
    });
  });
  document.querySelectorAll('[data-tab-link]').forEach(function(a) {
    a.addEventListener('click', function() { selectTab(a.getAttribute('data-tab-link')); });
  });
  var h = (location.hash || '').replace('#', '');
  if (h === 'forecast' || h === 'trend' || h === 'comparison') selectTab(h);

  el('year-seg').querySelectorAll('button').forEach(function(b) {
    b.addEventListener('click', function() {
      el('year-seg').querySelectorAll('button').forEach(function(o) { o.classList.remove('active'); o.setAttribute('aria-pressed', 'false'); });
      b.classList.add('active');
      b.setAttribute('aria-pressed', 'true');
      state.year = b.getAttribute('data-year');
      state.focusIdx = 0;
      render();
    });
  });
  el('metric-select').addEventListener('change', function(ev) {
    state.metric = ev.target.value;
    state.focusIdx = 0;
    render();
  });

  var svg = el('chart');
  svg.addEventListener('mousemove', function(ev) {
    if (!state.geom) return;
    var rect = svg.getBoundingClientRect();
    var px = (ev.clientX - rect.left) / rect.width * 760;
    var best = 0, bd = 1e9;
    state.geom.pts.forEach(function(p, i) {
      var d = Math.abs(p.x - px);
      if (d < bd) { bd = d; best = i; }
    });
    showTip(best);
  });
  svg.addEventListener('mouseleave', hideTip);
  svg.addEventListener('keydown', function(ev) {
    if (!state.geom) return;
    if (ev.key === 'ArrowRight') { ev.preventDefault(); showTip(state.focusIdx + 1); }
    if (ev.key === 'ArrowLeft') { ev.preventDefault(); showTip(state.focusIdx - 1); }
    if (ev.key === 'Escape') { hideTip(); }
  });

  initMc();
  fetch(DATA_URL, { cache: 'no-store' }).then(function(res) {
    if (!res.ok) throw new Error('HTTP ' + res.status);
    return res.json();
  }).then(function(data) {
    state.data = data;
    if (data.edition) el('edition-pill').textContent = 'edition: ' + data.edition;
    if (data.asOf) el('asof-side').textContent = String(data.asOf).replace(/-/g, '.');
    el('load-status').textContent = '데이터: ' + DATA_URL + ' 로드 완료, ' + fmtInt((data.series || []).length) + '행, 기준일 ' + (data.asOf || '-');
    render();
    if (data.forecast) renderForecast(data.forecast);
  }).catch(function(err) {
    el('load-status').textContent = '공개 자료를 불러오지 못했습니다 (' + err.message + ').';
    showError('저장소 전체를 받은 뒤 루트에서 HTTP 서버를 실행해 /dashboard/public/ 을 열어 주세요. data/public/dashboard.json 파일도 함께 필요합니다.');
  });
});
