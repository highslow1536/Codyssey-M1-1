import test from 'node:test';
import assert from 'node:assert/strict';
import {probabilityPresentation, gatePresentation, renderForecast, CLASS_LABELS} from '../dist/forecast-view.js';
function series(over) {
  var base = {id: 'GPU-RTX4070', category: 'GPU', name: 'RTX 4070', region: '미국', currency: 'USD', condition: '신품', frequency: 'weekly', sourceUrl: 'https://example.com/gpu', domesticId: '65820424', coverage: {rawN: 120, observed: 100, total: 110, first: '2023-01-03', last: '2025-12-30', excludedN: 10}, points: [{date: '2025-12-23', price: 599, quoteDate: '2025-12-23'}, {date: '2025-12-30', price: 589, quoteDate: '2025-12-30'}], selection: {status: 'selected', candidate: 4, temperature: 1.2, n: 40}, evaluation: {n: 24, originsN: 24, nonoverlapN: 8, from: '2024-01-01', to: '2025-12-01', brier: 0.2, baselineBrier: 0.18, brierSkill: -0.11, logLoss: 0.7, baselineLogLoss: 0.65, accuracy: 0.4, ece: 0.05, mae: 0.04, naiveMae: 0.03, driftMae: 0.05, improvementCI: [-0.02, 0.01], classCounts: [8, 8, 8], reliability: [{class: 0, n: 8, predicted: 0.3, observed: 0.25, low: 0.1, high: 0.5}, {class: 1, n: 8, predicted: 0.4, observed: 0.5, low: 0.2, high: 0.6}, {class: 2, n: 8, predicted: 0.3, observed: 0.25, low: 0.1, high: 0.5}]}, gates: {passed: false, reasons: ['표본 부족으로 추천 불가']}, forecast: {origin: '2025-12-30', target: '2026-03-31', price: 589, probabilities: [0.5, 0.3, 0.2], model: 'ordered-logit', temperature: 1.2, trainN: 100, trainThrough: '2025-12-30', available: true}, backtests: [{origin: '2025-09-01', target: '2025-12-01', actualChange: -0.04, predictedChange: -0.01, probabilities: [0.45, 0.35, 0.2], actualClass: 0}], limitations: ['짧은 검증 구간']};
  if (over) { for (var k in over) { base[k] = over[k]; } }
  return base;
}
function dataWith(s) {
  return {asOf: '2026-10-23', protocolUrl: './data/downloads/forecast_protocol.md', series: [s], limitations: ['전체 한계']};
}
function fakeMain() {
  return {innerHTML: '', querySelector: function() { return null; }};
}
test('class labels use exact Korean buckets', function() {
  assert.deepEqual(CLASS_LABELS, ['하락3%초과', '보합±3%', '상승3%초과']);
});
test('valid probabilities sum to one', function() {
  var r = probabilityPresentation([0.2, 0.5, 0.3]);
  assert.equal(r.kind, 'valid');
  assert.ok(Math.abs(r.sum - 1) < 0.001);
  assert.deepEqual(r.percents.map(function(v) { return Math.round(v); }), [20, 50, 30]);
});
test('empty probabilities never invent confidence', function() {
  assert.equal(probabilityPresentation(null).kind, 'empty');
  assert.equal(probabilityPresentation([]).kind, 'empty');
  assert.equal(probabilityPresentation([0.5, 0.5]).kind, 'empty');
  assert.equal(probabilityPresentation([null, 0.5, 0.5]).kind, 'empty');
  assert.equal(probabilityPresentation([0.5, 0.5, 0.5]).kind, 'invalid');
  assert.equal(probabilityPresentation([0.3, 0.4, 0.299]).kind,'invalid');
});
test('gate presentation keeps pass and fail distinct with reasons', function() {
  var p = gatePresentation({passed: true, reasons: ['표본 충족']});
  assert.equal(p.passed, true);
  assert.equal(p.badge, '추천 통과');
  var f = gatePresentation({passed: false, reasons: ['표본 부족']});
  assert.equal(f.passed, false);
  assert.equal(f.badge, '실험용');
  assert.ok(f.reasons[0].indexOf('표본 부족') >= 0);
  var e = gatePresentation(null);
  assert.equal(e.passed, false);
  assert.ok(e.reasons.length > 0);
});
test('renderer works without DOM and shows experimental forecast with reasons', function() {
  var m = fakeMain();
  renderForecast(m, dataWith(series()), {});
  assert.ok(m.innerHTML.indexOf('data-select="forecastSeries"') >= 0);
  assert.ok(m.innerHTML.indexOf('forecast-history') >= 0);
  assert.ok(m.innerHTML.indexOf('forecast-backtest') >= 0);
  assert.ok(m.innerHTML.indexOf('하락3%초과') >= 0);
  assert.ok(m.innerHTML.indexOf('보합±3%') >= 0);
  assert.ok(m.innerHTML.indexOf('상승3%초과') >= 0);
  assert.ok(m.innerHTML.indexOf('실험용') >= 0);
  assert.ok(m.innerHTML.indexOf('표본 부족으로 추천 불가') >= 0);
  assert.ok(m.innerHTML.indexOf('해외 관측값입니다. 국내 구매 추천에 사용하지 마십시오.') >= 0);
  assert.ok(m.innerHTML.indexOf('기준점을 이기지 못했습니다.') >= 0);
  assert.ok(m.innerHTML.indexOf('forecast_predictions.csv') >= 0);
  assert.ok(m.innerHTML.indexOf('forecast_weekly.csv') >= 0);
  assert.ok(m.innerHTML.indexOf('forecast_metrics.csv') >= 0);
  assert.ok(m.innerHTML.indexOf('forecast.json') >= 0);
});
test('monthly domestic target warns Dec not Jan and never promotes signal', function() {
  var s = series({frequency: 'monthly', region: 'KR', currency: 'KRW'});
  var m = fakeMain();
  renderForecast(m, dataWith(s), {});
  assert.ok(m.innerHTML.indexOf('2026-09') >= 0);
  assert.ok(m.innerHTML.indexOf('2026-12') >= 0);
  assert.ok(m.innerHTML.indexOf('국내 판매가 예측으로 사용하지 않습니다') >= 0);
  assert.equal(m.innerHTML.includes('해외 관측값입니다'),false);
  assert.ok(m.innerHTML.includes('개월'));
});
test('missing forecast shows no probabilities and state defaults to first series', function() {
  var s = series({forecast: null, backtests: []});
  var m = fakeMain();
  var st = {};
  renderForecast(m, dataWith(s), st);
  assert.equal(st.forecastSeries, 'GPU-RTX4070');
  assert.ok(m.innerHTML.indexOf('학습 표본·클래스 부족으로 산출을 보류했습니다') >= 0);
  assert.ok(m.innerHTML.indexOf('회고 검증 표본이 없습니다') >= 0);
});
test('empty series never throws and keeps protocol link', function() {
  var m = fakeMain();
  renderForecast(m, {asOf: '2026-10-23', protocolUrl: './data/downloads/forecast_protocol.md', series: []}, {});
  assert.ok(m.innerHTML.indexOf('forecast_protocol.md') >= 0);
});
