# §12 — Replacement JavaScript for the remaining `Formatting for Grafana*` nodes

Paste each block verbatim into the matching node's **JavaScript Code** field, then **Save Workflow**. Every block follows the same rule: the `stream` object holds only low-cardinality identity labels (`job`, `service_name`, `actor`, `target`, `region`, `host`, plus categorical status enums); all numerics and high-cardinality fields go into the log-line body as JSON.

After all five nodes are saved, re-migrate the dashboards `grpt7hn`, `dflmain`, `hilmain`, `evalmain`, `refinemain`, `alllayers` from `| unwrap <field>` to `| json | unwrap <field>` (use the same Python/REST script that was run against `cplmain`).

---

## 1. CPL — `Formatting for Grafana1`

```javascript
// Access the current input item
const item = $input.item;
const data = item.json || {};

// Compute latency in milliseconds
const latencyMs =
  data.ingestTimestamp && data.timestamp
    ? data.ingestTimestamp - data.timestamp
    : 0;

const eventMs = data.ingestTimestamp ? new Date(data.ingestTimestamp).getTime() : Date.now();
const safeMs = Math.min(eventMs, Date.now());           // cap at now
const ts_ns = String(safeMs * 1e6);

// Identity-only labels (low cardinality)
const streamLabels = {
  job:          data.job    || "context_processing_layer",
  service_name: "context_processing_layer",
  actor:        data.actor  || "unknown",
  target:       data.target || "unknown",
  region:       data.region ?? "unknown",
  host:         data.host   ?? "unknown"
};

// All numerics + the original message go into the log body as JSON
const body = JSON.stringify({
  message:          data.message || "No message",
  ingestCount:      Number(data.ingestCount      ?? 0),
  transformSuccess: Number(data.transformSuccess ?? 0),
  totalCount:       Number(data.totalCount       ?? 0),
  errorCount:       Number(data.errorCount       ?? 0),
  latencyMs:        Number(latencyMs)
});

return {
  streams: [
    { stream: streamLabels, values: [[ts_ns, body]] }
  ]
};
```

---

## 2. DFL — `Formatting for Grafana (Data Fed.)`

```javascript
const item = $input.item;
const data = item.json || {};

// ISO timestamp → nanoseconds
const ts_ns = String((new Date(data.timestamp || Date.now())).getTime() * 1e6);

const streamLabels = {
  job:          "data_federation_layer",
  service_name: "data_federation_layer",
  actor:        data.actor  || "unknown",
  target:       data.target || "unknown",
  region:       data.region || "unknown",
  host:         data.host   || "unknown"
};

const body = JSON.stringify({
  message:          data.message || "No message",
  ingestCount:      Number(data.ingestCount      ?? 0),
  transformSuccess: Number(data.transformSuccess ?? 0),
  totalCount:       Number(data.totalCount       ?? 0),
  errorCount:       Number(data.errorCount       ?? 0),
  latencyMs:        Number(data.latencyMs        ?? 0)
});

return {
  streams: [
    { stream: streamLabels, values: [[ts_ns, body]] }
  ]
};
```

---

## 3. RIL — `Formatting for Grafana2`

> Also drops the high-cardinality dynamic ids (`simulation_run_id`, `scenario_id`, `risk_type_1`, `contributing_factor_1`) from labels into the JSON body to prevent Loki stream-cardinality blow-up. Categorical enums (`relative_severity`, `relative_likelihood`) stay as labels because their value set is small (low/medium/high).

```javascript
const item = $input.item;
const data = item.json || {};

// ---------- Timestamp ----------
const ingestTime = Number(data.ingestTimestamp) || Date.now();
const eventTime  = Number(data.timestamp)       || ingestTime;
const latencyMs  = Math.max(ingestTime - eventTime, 0);
const ts_ns     = String(ingestTime * 1e6);

// ---------- Identity-only labels ----------
const streamLabels = {
  job:                  data.job || "risk_intelligence_layer",
  service_name:         "risk_intelligence_layer",
  relative_severity:    data.relative_severity   ?? "none",
  relative_likelihood:  data.relative_likelihood ?? "none"
};

// ---------- Numerics + dynamic IDs into JSON body ----------
const body = JSON.stringify({
  message:
    (data.notes_for_human_review || data.explanation_trace || []).join(" | ") ||
    `status=${data.status ?? "unknown"}`,

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
```

---

## 4. Refinement — `Formatting for Grafana3`

```javascript
const item = $input.item;
const data = item.json || {};

const ingestTime = Number(data.ingestTimestamp) || Date.now();
const eventTime  = Number(data.timestamp)       || ingestTime;
const latencyMs  = Math.max(ingestTime - eventTime, 0);
const ts_ns     = String(ingestTime * 1e6);

// Identity-only labels (status/decision are small enums → safe as labels)
const streamLabels = {
  job:          data.job || "refinement_layer",
  service_name: "ontology_revision_layer",
  status:       data.status   ?? "unknown",
  decision:     data.decision ?? "none"
};

const body = JSON.stringify({
  revision_id:                   data.revision_id ?? null,
  requires_human_confirmation:   Boolean(data.requires_human_confirmation ?? false),

  // Numerics — must live in body so dashboards can `| json | unwrap`
  transformSuccess:              Number(data.transformSuccess ?? 0),
  errorCount:                    Number(data.errorCount       ?? 0),

  decision_score:                Number(data.decision_score   ?? 0),
  confidence_score:              Number(data.confidence_score ?? 0),

  total_changes:                 Number(data.total_changes                ?? 0),
  mapping_changes:               Number(data.mapping_changes              ?? 0),
  ontology_changes:              Number(data.ontology_changes             ?? 0),
  simulation_parameter_changes:  Number(data.simulation_parameter_changes ?? 0),

  latencyMs:                     Number(latencyMs),
  pipeline_latency_ms:           Number(data.pipeline_latency_ms ?? 0),

  justification:                 data.justification     ?? null,
  proposed_changes:              data.proposed_changes  ?? null
});

return {
  streams: [
    { stream: streamLabels, values: [[ts_ns, body]] }
  ]
};
```

---

## 5. Task Execution — `Formatting for Grafana4`

```javascript
const item = $input.item;
const data = item.json || {};

const ingestTime = Number(data.ingestTimestamp) || Date.now();
const eventTime  = Number(data.timestamp)       || ingestTime;
const latencyMs  = Math.max(ingestTime - eventTime, 0);
const ts_ns     = String(ingestTime * 1e6);

// Identity-only labels (small enums kept as labels)
const streamLabels = {
  job:              data.job || "task_execution_layer",
  service_name:     "task_execution_layer",
  status:           data.status           ?? "unknown",
  task_type:        data.task_type        ?? "none",
  change_type:      data.change_type      ?? "none",
  execution_status: data.execution_status ?? "none"
};

const body = JSON.stringify({
  task_id:                      data.task_id     ?? null,
  revision_id:                  data.revision_id ?? null,
  target:                       data.target      ?? null,
  description:                  data.description ?? null,
  requires_human_confirmation:  Boolean(data.requires_human_confirmation ?? false),

  // Numerics
  transformSuccess:     Number(data.transformSuccess ?? 0),
  errorCount:           Number(data.errorCount       ?? 0),
  latencyMs:            Number(latencyMs),
  pipeline_latency_ms:  Number(data.pipeline_latency_ms ?? 0)
});

return {
  streams: [
    { stream: streamLabels, values: [[ts_ns, body]] }
  ]
};
```

---

## After saving all five nodes

Run the dashboard migration (already proven against `cplmain`):

```bash
TOKEN=$(cat /tmp/grafana_token)
python3 - << 'PY'
import json, re, requests
TOKEN = open('/tmp/grafana_token').read().strip()
BASE = "https://gracebilliris.grafana.net"
H = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
DASHES = ["grpt7hn","dflmain","hilmain","evalmain","refinemain","alllayers"]

def fix(expr):
    if not isinstance(expr, str): return expr, False
    if "| json |" in expr or "| json|" in expr: return expr, False
    new = re.sub(r'\|\s*unwrap\b', '| json | unwrap', expr, count=1)
    return new, new != expr

def visit(panels):
    n = 0
    for p in panels or []:
        if isinstance(p.get('panels'), list): n += visit(p['panels'])
        for t in p.get('targets') or []:
            new, ch = fix(t.get('expr',''))
            if ch: t['expr'] = new; n += 1
    return n

for uid in DASHES:
    r = requests.get(f"{BASE}/api/dashboards/uid/{uid}", headers=H, timeout=30).json()
    n = visit(r['dashboard'].get('panels'))
    if not n:
        print(f"[{uid}] nothing to change"); continue
    pr = requests.post(f"{BASE}/api/dashboards/db", headers=H,
        data=json.dumps({"dashboard": r['dashboard'],
                         "folderUid": r.get('meta',{}).get('folderUid',''),
                         "overwrite": True,
                         "message": f"CAPRA: migrate {n} queries to | json | unwrap"}),
        timeout=30)
    print(f"[{uid}] {pr.status_code} — migrated {n} queries")
PY
```

Wait ~3–5 minutes for Loki ingestion, then re-screenshot each dashboard.
