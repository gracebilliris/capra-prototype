# Grafana Dashboard Fixes — n8n Node Code Changes

This document explains exactly **what to change**, **where**, and **why**, to fix the two Grafana issues observed during testing:

1. CPL dashboard shows 0% success / 0% failure
2. RIL and Task Execution dashboards show success% + failure% < 100%

All fixes are surgical — edit one or two code nodes and one or two dashboard panels. No re-architecting needed.

---

## Problem 1 — Numeric metrics being pushed as Loki stream labels

### Affected nodes (ALL of them — same bug, same fix)

| Node | Layer | Why it matters |
|---|---|---|
| `Formatting for Grafana` | CPL | Causes CPL 0%/0% |
| `Formatting for Grafana1` | CPL | Causes CPL 0%/0% |
| `Formatting for Grafana (Data Fed.)` | DFL | Borderline OK now; will break as volume grows |
| `Formatting for Grafana2` | RIL | Borderline OK now; will break as volume grows |
| `Formatting for Grafana3` | Refinement | Borderline OK now; will break as volume grows |
| `Formatting for Grafana4` | Task Execution | Borderline OK now; will break as volume grows |

### Why it's broken

Every one of these nodes builds the Loki `stream` block like this:

```js
stream: {
  job: "context_processing_layer",
  actor: data.actor || "unknown",
  target: data.target || "unknown",
  // === these next 5 are the bug ===
  ingestCount:     String(data.ingestCount ?? "0"),
  transformSuccess: String(data.transformSuccess ?? "0"),
  totalCount:      String(data.totalCount ?? "0"),
  errorCount:      String(data.errorCount ?? "0"),
  latencyMs:       String(latencyMs)
}
```

`latencyMs` takes a **different value on every push** (it's wall-clock minus event-time). Loki treats every unique combination of label values as a separate stream. So every push creates a new stream. Grafana Cloud's default per-tenant cap is ~10,000 active streams — and CPL has hit it, which is why CPL streams are being dropped/rate-limited and the dashboard reads 0/0.

Counters like `totalCount` and `transformSuccess` are also a *high-cardinality anti-pattern*: Grafana's official docs explicitly warn against putting numeric values into Loki labels.

### The fix (apply to each `Formatting for Grafana*` node)

Move the numeric fields **out of the `stream` block** and **into the log line body** as JSON. Keep only stable, low-cardinality labels (`job`, `actor`, `target`, `region`, `host`).

**Before** (e.g. CPL's `Formatting for Grafana`):

```js
return {
  streams: [{
    stream: {
      job: data.job || "context_processing_layer",
      actor: data.actor || "unknown",
      target: data.target || "unknown",
      region: data.region || "unknown",
      host: data.host || "unknown",

      ingestCount:     String(data.ingestCount ?? "0"),
      transformSuccess: String(data.transformSuccess ?? "0"),
      totalCount:      String(data.totalCount ?? "0"),
      errorCount:      String(data.errorCount ?? "0"),
      latencyMs:       String(latencyMs)
    },
    values: [
      [ts_ns, data.message || data.id || "No message"]
    ]
  }]
};
```

**After**:

```js
const logLine = JSON.stringify({
  msg: data.message || data.id || "No message",
  ingestCount:     Number(data.ingestCount     ?? 0),
  transformSuccess: Number(data.transformSuccess ?? 0),
  totalCount:      Number(data.totalCount      ?? 0),
  errorCount:      Number(data.errorCount      ?? 0),
  latencyMs:       Number(latencyMs            ?? 0),
  status:          data.status                 ?? "unknown"
});

return {
  streams: [{
    stream: {
      job:    data.job    || "context_processing_layer",
      actor:  data.actor  || "unknown",
      target: data.target || "unknown",
      region: data.region || "unknown",
      host:   data.host   || "unknown"
    },
    values: [
      [ts_ns, logLine]
    ]
  }]
};
```

**Apply this exact pattern to all six `Formatting for Grafana*` nodes.** Only the `job` default string changes per node.

### Dashboard panel updates (LogQL queries)

The panels that previously read labels now need to extract from JSON. The pattern:

**Old** (broken — reads a label):

```logql
count_over_time({job="context_processing_layer", transformSuccess="1"} [5m])
```

**New** (correct — extracts from JSON in the log line, then filters):

```logql
sum by (job) (
  count_over_time(
    {job="context_processing_layer"}
    | json
    | transformSuccess = "1"
    [5m]
  )
)
```

For a **success-rate stat panel** showing percent:

```logql
100 *
  sum(count_over_time({job="context_processing_layer"} | json | transformSuccess="1" [$__range]))
/
  sum(count_over_time({job="context_processing_layer"} | json [$__range]))
```

For a **latency p95 panel**:

```logql
quantile_over_time(0.95,
  {job="context_processing_layer"}
  | json
  | unwrap latencyMs
  [$__range]
)
```

For a **throughput/sec time-series**:

```logql
sum by (job) (rate({job="context_processing_layer"} | json [1m]))
```

**Update each layer's dashboard** (`cplmain`, `dflmain`, `grpt7hn`, `evalmain`, `refinemain`, `hilmain`, `alllayers`) to use this `| json | <field>` extraction pattern instead of label selectors.

---

## Problem 2 — RIL and Task Execution success% + failure% < 100%

### Affected nodes

| Node | Job label | The `skipped` branch |
|---|---|---|
| `(1) Capture Metrics2` | `risk_intelligence_layer` | `transformSuccess=0, errorCount=0, status="skipped"` when `hasRiskPayload` is false |
| `(1) Capture Metrics4` | `task_execution_layer` | `transformSuccess=0, errorCount=0, status="skipped"` when `hasTask` is false |

### Why it's broken

Both nodes default `transformSuccess=0` AND `errorCount=0` AND `status="skipped"` when the upstream item is empty. The dashboard's `success / (success + failure)` formula excludes these → percentages don't sum to 100%. The missing percentage IS the skipped count.

### Fix — pick ONE of these three options

#### Option A (recommended) — Add a third "skipped" panel

Keep the node code as-is (the three-state classification is actually useful information) and add a third dashboard stat next to success / failure. Use this LogQL once you've moved metrics to JSON per Problem 1:

```logql
100 *
  sum(count_over_time({job="risk_intelligence_layer"} | json | status="skipped" [$__range]))
/
  sum(count_over_time({job="risk_intelligence_layer"} | json [$__range]))
```

Total: success% + failure% + skipped% = 100%.

#### Option B — Change the denominator on existing panels

Use `totalCount` (which is 1 for every event regardless of branch) instead of `success+failure`:

```logql
100 *
  sum(count_over_time({job="risk_intelligence_layer"} | json | transformSuccess="1" [$__range]))
/
  sum(count_over_time({job="risk_intelligence_layer"} | json [$__range]))
```

Success% and failure% now both show as fractions of total events; their sum will be < 100% but the meaning is now "of all events processed, X% succeeded and Y% failed; the rest were skipped (no upstream payload to act on)".

#### Option C — Re-classify skipped as failed in the node code

Only do this if "no payload received" is genuinely a failure for your domain (it isn't — it's normal).

In `(1) Capture Metrics2`, change:

```js
let transformSuccess = 0;
let errorCount = 0;
let status = "skipped";
if (hasRiskPayload) { ... transformSuccess = 1; status = "success"; }
```

to:

```js
let transformSuccess = 0;
let errorCount = 0;
let status = "no_payload";   // semantic clarity for when there's nothing to do
if (hasRiskPayload) {
  if (risk_types.length > 0) {
    transformSuccess = 1;
    status = "success";
  } else {
    errorCount = 1;
    status = "failed";
  }
}
// If !hasRiskPayload, leave counters at 0 — but don't include these in the dashboard counts.
```

… and update the LogQL on the success/failure panels to filter them out:

```logql
{job="risk_intelligence_layer"} | json | status =~ "success|failed"
```

Then `success% + failure% = 100%` by construction (skipped events are excluded from the denominator entirely).

---

## Recommended rollout order

1. **First**, do Problem 1 on the **two CPL nodes** (`Formatting for Grafana`, `Formatting for Grafana1`) plus a corresponding dashboard panel rewrite for `cplmain`. This alone unblocks the CPL dashboard.
2. **Then**, do Problem 1 on the remaining four `Formatting for Grafana*` nodes and their dashboards. This future-proofs the others before they hit the same cardinality wall.
3. **Last**, do Problem 2 Option A (add skipped panels) on `grpt7hn` (RIL) and the task execution dashboard. This is cosmetic — the underlying metrics are already correct.

After Step 1, run a 12-minute observation window and re-screenshot `cplmain` to confirm the percentages are populating. After all steps, repeat the snapshot+screenshot drill from the test plan and the dashboards should be fully accurate.

---

## How to apply node-code edits in n8n

1. Open `http://localhost:5678/workflow/XUSBdhyaqrZVIXqp`
2. Double-click the node (e.g. `Formatting for Grafana`)
3. In the right panel, replace the code in the **JavaScript Code** editor
4. Click **Execute Node** once to verify no syntax errors
5. Click **Save** (top right) — workflow saves; the schedule trigger will pick up the new code on its next firing (within 5–10 s)

No restart of the n8n container is needed.

---

## Verification checklist (after applying fixes)

- [ ] CPL panel "Success %" shows a non-zero number within 5 minutes
- [ ] Sum of success% + failure% on DFL, CPL, Refinement panels equals 100% (±1% rounding)
- [ ] RIL and Task Execution panels either show all three stats (success/failure/skipped summing to 100%) or use `totalCount` denominators with the legend now explaining the gap
- [ ] Loki query `count_over_time({job="context_processing_layer"} | json [5m])` returns a non-zero count
- [ ] No "stream limit exceeded" or "max active streams" warnings in Grafana Cloud → Connections → Loki → Status
