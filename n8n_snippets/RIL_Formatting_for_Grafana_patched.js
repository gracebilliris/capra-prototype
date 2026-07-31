// ============================================================================
// RIL — Formatting for Grafana (patched)
// ----------------------------------------------------------------------------
// Adds the fields needed by the Risk Register dashboard while keeping every
// existing field the current dashboards depend on. NO new labels beyond
// `severity` (4-value enum) and `domain` (3-value enum) — both safe.
// ============================================================================

const item = $input.item;
const data = item.json || {};

// ---------- Timestamp ----------
const ingestTime = Number(data.ingestTimestamp) || Date.now();
const eventTime  = Number(data.timestamp)       || ingestTime;
const latencyMs  = Math.max(ingestTime - eventTime, 0);
const ts_ns     = String(ingestTime * 1e6);

// ---------- Severity normalisation (score → enum) ----------
// severity_score can be either 0-1 float OR small integer (0..3+).
// Auto-detect: if > 1, treat as integer scale (0=LOW..3+=CRITICAL); else float thresholds.
// Empirically the RIL LLM emits severity_score as a small integer (0..3+),
// not the 0-1 float the original spec assumed. Map on integer scale.
const sevScoreRaw = Number(data.severity_score ?? 0);
const severity =
  sevScoreRaw >= 3 ? "CRITICAL" :
  sevScoreRaw >= 2 ? "HIGH"     :
  sevScoreRaw >= 1 ? "MEDIUM"   :
                     "LOW";
// NOTE: intentionally NOT honouring data.severity (the LLM emits "CRITICAL"
// for almost everything even when its own severity_score contradicts it).
// Score-based bucket is the source of truth.

// ---------- Domain derivation ----------
// Prefer explicit data.domain; fall back to task_id / scenario_id prefix.
const idHint = (data.domain || data.task_id || data.scenario_id || "").toString().toLowerCase();
let domain = "unknown";
if      (idHint.indexOf("student")   >= 0 || idHint.indexOf("admission") >= 0) domain = "student";
else if (idHint.indexOf("health")    >= 0 || idHint.indexOf("triage")    >= 0) domain = "healthcare";
else if (idHint.indexOf("retail")    >= 0 || idHint.indexOf("fashion")   >= 0) domain = "retail";

// ---------- Risk identifiers ----------
const risk_id   = data.risk_id
               || (data.scenario_id ? `${data.scenario_id}-${ingestTime}` : `ril-${ingestTime}`);
const risk_type = data.risk_types?.[0] ?? data.risk_type ?? null;

// Explanation: prefer the LLM narrative if present, else stitch together the
// notes/trace fields RIL already emits.
const explanation =
  data.explanation
  || data.context_summary
  || (data.notes_for_human_review || []).join(" | ")
  || (data.explanation_trace       || []).join(" | ")
  || null;

// ---------- Identity-only labels (low cardinality) ----------
const streamLabels = {
  job:                  data.job || "risk_intelligence_layer",
  service_name:         "risk_intelligence_layer",
  relative_severity:    data.relative_severity   ?? "none",
  relative_likelihood:  data.relative_likelihood ?? "none",
  severity:             severity,   // NEW — 4 values
  domain:               domain      // NEW — 3 values + "unknown"
};

// ---------- JSON body (high cardinality fields live HERE) ----------
const body = JSON.stringify({
  message:
    (data.notes_for_human_review || data.explanation_trace || []).join(" | ") ||
    `status=${data.status ?? "unknown"}`,

  // ----- Risk register fields (NEW) -----
  risk_id:              risk_id,
  risk:                 risk_type,
  severity:             severity,
  explanation:          explanation,
  actor:                data.actor  ?? null,
  target:               data.target ?? null,
  domain:               domain,
  confidence:           Number(data.confidence_score ?? data.likelihood_score ?? 0),

  // ----- Existing fields (unchanged) -----
  status:               data.status ?? "unknown",
  simulation_run_id:    data.simulation_run_id ?? null,
  scenario_id:          data.scenario_id       ?? null,

  totalCount:           Number(data.totalCount       ?? 0),
  ingestCount:          Number(data.ingestCount      ?? 0),
  transformSuccess:     Number(data.transformSuccess ?? 0),
  errorCount:           Number(data.errorCount       ?? 0),

  latencyMs:            Number(latencyMs),
  pipeline_latency_ms:  Number(data.pipeline_latency_ms ?? 0),

  severity_score:       Number(data.severity_score   ?? 0),
  likelihood_score:     Number(data.likelihood_score ?? 0),

  risk_type_1:           data.risk_types?.[0]           ?? null,
  contributing_factor_1: data.contributing_factors?.[0] ?? null
});

return {
  streams: [
    { stream: streamLabels, values: [[ts_ns, body]] }
  ]
};
