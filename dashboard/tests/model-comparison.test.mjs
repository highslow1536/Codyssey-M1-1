import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { comparisonBodyHtml, bestRetrospective, fmtBrier, fmtLogLoss, fmtMaeP, fmtCover, fmtIntervalCell, fmtCount, statusLabel, attachModelComparison, clearComparisonCache } from "../dist/model-comparison-view.js";
var data = JSON.parse(readFileSync(new URL("../../data/public/model_comparison.json", import.meta.url), "utf8"));
function synth() {
  return {
    id: "T1",
    name: "Test Series",
    region: "KR", frequency: "monthly",
    incumbent: { candidate: "logistic", temperature: 1.0 },
    selection: { candidate: "arima", status: "past_validation_only", n: 10, temperature: 4.0, validationLogLoss: 1.0, reason: "과거 선택 사유" },
    common: { selectionN: 10, testN: 8, nonoverlapN: 2, from: "2025-01-01", to: "2025-06-01", candidates: ["logistic", "arima", "ets"] },
    models: [
      { candidate: "arima", name: "ARIMA", status: "evaluated", reasons: [], failures: {}, selection: { n: 10, logLoss: 1.0, brier: null }, evaluation: { n: 8, originsN: 8, nonoverlapN: 2, brier: 0.5, baselineBrier: 0.6, logLoss: 0.9, mae: 0.1, naiveMae: 0.12, ece: 0.05, rmse: 0.2, interval80Coverage: 0.8, interval95Coverage: 0.95, intervalN: 8 }, allTestN: 8 },
      { candidate: "ets", name: "ETS", status: "evaluated", reasons: [], failures: { sparse: 3 }, selection: { n: 10, logLoss: 1.1, brier: null }, evaluation: { n: 8, originsN: 8, nonoverlapN: 2, brier: 0.4, baselineBrier: 0.6, logLoss: 0.85, mae: 0.09, naiveMae: 0.12, ece: 0.04, rmse: null, interval80Coverage: null, interval95Coverage: null, intervalN: 0 }, allTestN: 8 },
      { candidate: "sarima", name: "SARIMA", status: "unavailable", reasons: ["공통 평가 가능한 예측 없음; 0점으로 해석하지 않음"], failures: { insufficient_history: 9 }, selection: { n: null, logLoss: null, brier: null }, evaluation: null, allTestN: 0 }
    ],
    selectedEvaluation: { n: 8, brier: 0.5 },
    selectedAllEvaluation: { n: 20, brier: 0.55 },
    gates: { passed: false, reasons: ["보류 사유"] }
  };
}
function series(id) { return data.series.filter(function(s) { return s.id === id; })[0]; }
function count(h, sub) { return h.split(sub).length - 1; }
test("null entry falls back without throwing", function() {
  var h = comparisonBodyHtml(null, null, {});
  assert.ok(h.indexOf("찾지 못했습니다") >= 0);
});
test("missing scores render as dash, never zero-filled", function() {
  assert.equal(fmtBrier(null), "—");
  assert.equal(fmtLogLoss(undefined), "—");
  assert.equal(fmtMaeP(null), "—");
  assert.equal(fmtCover(null), "—");
  assert.equal(fmtIntervalCell({ intervalN: 0 }), "—");
  assert.equal(fmtIntervalCell(null), "—");
  assert.equal(fmtMaeP(0.05), "5.0%p");
  var h = comparisonBodyHtml(synth(), { summary: { passed: 0 } }, {});
  assert.ok(h.indexOf("0.0000") < 0);
});
test("dropdown highlight never moves the historical selection badge", function() {
  var e = synth();
  var cmp = { summary: { passed: 0 } };
  var h1 = comparisonBodyHtml(e, cmp, {});
  assert.equal(count(h1, "선택됨(과거)"), 1);
  var h2 = comparisonBodyHtml(e, cmp, { selectedModel: "ets" });
  assert.equal(count(h2, "선택됨(과거)"), 1);
  assert.ok(h2.indexOf("mc-row-focus") >= 0);
  var arimaRow = h2.split("<tr").filter(function(r) { return r.indexOf(">arima<") >= 0; });
  assert.equal(arimaRow.length, 1);
  assert.ok(arimaRow[0].indexOf("선택됨(과거)") >= 0);
});
test("header and body columns stay aligned at ten", function() {
  var h = comparisonBodyHtml(synth(), { summary: { passed: 0 } }, {});
  assert.equal(count(h, "<th "), 10);
  assert.equal(count(h, "<td"), 30);
  assert.ok(h.indexOf("전체 n(기존 범위)") >= 0);
});
test("escaping blocks markup injection", function() {
  var e = synth();
  e.name = "<script>alert(1)</scr" + "ipt>";
  e.models[0].name = "ARIMA\" onmouseover=\"x";
  var h = comparisonBodyHtml(e, { summary: { passed: 0 } }, {});
  assert.ok(h.indexOf("<script>") < 0);
  assert.ok(h.indexOf("onmouseover=\"x") < 0);
});
test("best retrospective ignores nulls and is labelled retrospective only", function() {
  var e = synth();
  var b = bestRetrospective(e);
  assert.equal(b.candidate, "ets");
  e.models.forEach(function(m) { m.evaluation = null; });
  assert.equal(bestRetrospective(e), null);
  assert.equal(bestRetrospective(null), null);
});
test("real CPU changed forest to arima with full-vs-common line", function() {
  var s = series("US_B07STGGQ18");
  assert.equal(s.selection.candidate, "arima");
  assert.equal(s.incumbent.candidate, "forest");
  var h = comparisonBodyHtml(s, data, {});
  assert.ok(h.indexOf("선택 변경") >= 0);
  assert.ok(h.indexOf("선택 모형 전체 평가 n=") >= 0);
  assert.equal(count(h, "선택됨(과거)"), 1);
});
test("real SSD changed to sarima T2", function() {
  var s = series("US_B07MFZY2F2");
  assert.equal(s.selection.candidate, "sarima");
  assert.equal(s.selection.temperature, 2.0);
});
test("real domestic 7500F retains logistic despite lower test error", function() {
  var s = series("KR_21694499");
  assert.equal(s.selection.candidate, "logistic");
  assert.equal(s.selection.status, "incumbent_retained_insufficient_selection");
  var sar = s.models.filter(function(m) { return m.candidate === "sarima"; })[0];
  assert.equal(sar.status, "unavailable");
  assert.ok((sar.evaluation === null) || (sar.evaluation && sar.evaluation.brier === null));
  var h = comparisonBodyHtml(s, data, {});
  assert.ok(h.indexOf("선택 유지") >= 0);
  assert.ok(h.indexOf("미산출") >= 0);
  assert.ok(h.indexOf("개선 주장") >= 0);
});
test("real zero series shows unavailable without zero scores", function() {
  var s = series("US_B08J5F3G18");
  assert.ok(s.models.every(function(m) { return m.status === "unavailable"; }));
  var h = comparisonBodyHtml(s, data, {});
  assert.ok(h.indexOf("—") >= 0);
  assert.ok(h.indexOf("0.0000") < 0);
});
test("standalone matured forecasts are explained, not claimed missing", function() {
  var e = synth();
  e.models[2].standaloneTestN = 12;
  var h = comparisonBodyHtml(e, { summary: { passed: 0 } }, {});
  assert.ok(h.indexOf("별도 단독 성숙 예측 n=12") >= 0);
  assert.ok(h.indexOf("미출력으로 보지 않음") >= 0);
});
test("attach is safe with a stub main and no network", async function() {
  clearComparisonCache();
  var fake = { innerHTML: "", querySelector: function() { return null; } };
  attachModelComparison(fake, { forecastSeries: "NOPE" }, {});
  await new Promise(function(res) { setTimeout(res, 50); });
  assert.equal(fake.innerHTML, "");
});
