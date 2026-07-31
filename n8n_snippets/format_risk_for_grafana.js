// ---------------------------------------------------------------------------
// CAPRA — Format Risk for Grafana
// ---------------------------------------------------------------------------
// Purpose:
//   Wrap a single risk record (produced upstream by the Risk Intelligence Layer
//   or Evaluation & Refinement Layer) into the Loki HTTP push schema so it can
//   be POSTed to the Grafana Cloud Loki endpoint by the downstream
//   "Push Grafana Metrics" HTTP Request node.
//
// Placement:
//   Add this Code node (Run Once For Each Item) on the success path immediately
//   after the node that emits the final risk shape.
//   Upstream node's $json is expected to contain (all optional but recommended):
//     risk_id, risk, severity, explanation, actor, target, domain, layer,
//     confidence, task_id
//
// Downstream:
//   HTTP Request node (POST):
//     URL:     https://logs-prod-026.grafana.net/loki/api/v1/push
//     Auth:    Basic (credential "Grafana Credentials", id P7IXLPyS97p7I1od)
//     Body:    JSON (raw), passthrough $json
//     Success: 204 No Content
//
// Label design notes:
//   * LOW-CARDINALITY labels only. Never put risk_id / actor / target / risk
//     text into labels — those would multiply active-stream count and hit the
//     10k stream cap. They live in the JSON *value* and are pulled out of the
//     log line by `| json` at query time.
//   * `job=risk_register` is the anchor label all dashboard queries filter on.
//   * `severity`, `domain`, `layer` are the three low-cardinality dimensions
//     the dashboard variables read.
// ---------------------------------------------------------------------------

const r = $json || {};

const now = Date.now();
const ts_ns = String(now) + '000000'; // Loki wants nanosecond string

// Normalise severity to one of CRITICAL / HIGH / MEDIUM / LOW; default MEDIUM.
const rawSev = (r.severity || '').toString().toUpperCase();
const allowedSev = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'];
const severity = allowedSev.indexOf(rawSev) >= 0 ? rawSev : 'MEDIUM';

// Domain + layer normalisation (lowercase, snake_case; safe as Loki labels).
const domain = (r.domain || 'unknown').toString().toLowerCase().replace(/\s+/g, '_');
const layer  = (r.layer  || 'unknown').toString().toUpperCase(); // e.g. RIL, ERL

// The JSON body — high-cardinality fields live HERE (not in labels).
const body = {
  risk_id:     r.risk_id     || null,
  risk:        r.risk        || null,
  severity:    severity,
  explanation: r.explanation || null,
  actor:       r.actor       || r.actor_entity?.id || null,
  target:      r.target      || r.target_entity?.id || null,
  domain:      domain,
  layer:       layer,
  confidence:  typeof r.confidence === 'number' ? r.confidence : null,
  task_id:     r.task_id     || null,
  ts:          new Date(now).toISOString()
};

// Loki HTTP push payload.
return {
  streams: [
    {
      stream: {
        job:      'risk_register',
        severity: severity,
        domain:   domain,
        layer:    layer
      },
      values: [
        [ts_ns, JSON.stringify(body)]
      ]
    }
  ]
};
