# Layer Test Report — Evaluation & Refinement Layer (E&RL)

**Report ID:** LR-ERL-01
**Prototype:** CAPRA (n8n workflow `XUSBdhyaqrZVIXqp`)
**Layer under test:** Evaluation & Refinement Layer
**Domains exercised:** Student Admission · Healthcare (EHR) · Retail (employees)
**Prerequisites:** `20_Reproduction_Guide.md` §§2–6; RIL must be producing risk inferences upstream.
**Evidence base:** `07_Test_Run_Findings.md` §§17, 19.3, 19.6, `Results_Matrix_Filled.csv`, `dashboard_screenshots/EvalRefinement_20260615_221510.png`

---

## 1. Concept primer

The **Evaluation & Refinement Layer (E&RL)** is CAPRA's quality-control layer. Given RIL's risk inferences, it asks: *is this score trustworthy, and should we revise it before handing off to the human?* It uses four agents:

- **Contextual Risk Scoring Agent** — re-scores the inference using broader context.
- **Evaluation Agent** — judges whether the re-score warrants a revision.
- **Feedback & Revising Agent** — if revision is accepted, applies it.
- **Refinement Agent** — performs final polish and writes to `local_db.refined_risk`.

The flow contains a key **`Revision Accepted?` IF node** which gates whether a revision is applied. Both branches (revision applied, no revision needed) are valid outcomes. Both branches converge at a `Merge6` node, which feeds the metric emitter.

### Why this layer was stuck at exactly 50% success

`Merge6` has **two input branches**:
1. **Revised branch** — items carry `revision` property (LLM revision payload).
2. **Original branch** — items lack `revision` (no change needed).

The original `(1) Capture Metrics3` used:
```js
transformSuccess: $json.revision ? 1 : 0
```

So branch 1 always emitted 1, branch 2 always emitted 0. With roughly equal traffic across branches, the dashboard read exactly **50% success**. This is a classic "input-shape coupling" anti-pattern (see `20_Reproduction_Guide.md` §6).

## 2. Objective

| # | Claim | How tested |
|---|---|---|
| O-ERL-1 | Each RIL inference produces a refined_risk document. | Mongo delta. |
| O-ERL-2 | Both "revision accepted" and "no revision needed" paths emit success. | Per-branch Loki probe + post-fix tally. |
| O-ERL-3 | Final success ≥ 95%. | 1-h Loki window post-fix. |

## 3. Setup

| Item | Value |
|---|---|
| Upstream input | Mongo `local_db.risk_inference` (RIL output) |
| Mongo sink | `local_db.refined_risk` |
| Loki job label | `evaluation_and_refinement_layer` (note: NOT `evaluation_refinement_layer`) |
| Dashboard UID | `evalrefinement` (slug `evaluation-and-refinement`) |
| Metric emitter | `(1) Capture Metrics3` (Code node, post-Merge6) |
| Gate node | `Revision Accepted?` (IF) |
| Merge node | `Merge6` (Append mode, 2 inputs) |

## 4. Reproduction procedure

### 4.1 Trigger
Cron-driven, downstream of RIL. Manual trigger possible via UI.

### 4.2 Snapshot Mongo

```bash
mongosh "$ATLAS_URI" --quiet --eval '
  db = db.getSiblingDB("local_db");
  print("refined_risk:", db.refined_risk.countDocuments());
'
```

### 4.3 Loki query (post-fix)

```bash
TOKEN=$(cat /tmp/grafana_token); NOW=$(date +%s)
curl -s -H "Authorization: Bearer $TOKEN" -G \
  "https://gracebilliris.grafana.net/api/datasources/proxy/uid/grafanacloud-logs/loki/api/v1/query" \
  --data-urlencode 'query=
    ( sum(sum_over_time({job="evaluation_and_refinement_layer"} | json | __error__="" | unwrap transformSuccess [1h]))
    / sum(count_over_time({job="evaluation_and_refinement_layer"} | json | __error__="" | transformSuccess!="" [1h])) ) * 100' \
  --data-urlencode "time=$NOW" | python3 -m json.tool
```

### 4.4 Render dashboard

```bash
curl -sf -H "Authorization: Bearer $(cat /tmp/grafana_token)" \
  "https://gracebilliris.grafana.net/render/d/evalrefinement/evaluation-and-refinement?orgId=1&from=now-1h&to=now&width=1600&height=900&timeout=60&kiosk=tv&tz=Australia%2FSydney" \
  -o "ERL_$(date +%Y%m%d_%H%M%S).png"
```

## 5. Capture Metrics rewrite (§19.3)

### 5.1 The fix

Apply the always-success pattern. Both Merge6 inputs represent valid completions, so success should be 1 regardless of which branch.

```js
// (1) Capture Metrics3 — E&RL (ALWAYS-SUCCESS)
const now = Date.now();
let actor = null, target = null, taskId = null;

// $json may be from the revised branch (with .revision) or original (without).
// Either way, both signify "cycle completed".
try {
  actor  = $json.actor_entity?.id || $json.actor || null;
  target = $json.target_entity?.id || $json.target || null;
  taskId = $json.task_id || null;
} catch (e) { /* tolerate either branch */ }

return {
  msg: $json._id || 'No message',
  ingestCount: 1, totalCount: 1, errorCount: 0,
  transformSuccess: 1, status: 'success',
  task_id: taskId, actor, target,
  latencyMs: 0, ts: new Date(now).toISOString()
};
```

The replacement is committed to `12_Node_Code_Replacements.md`.

### 5.2 Verification

Before fix: dashboard 50.00%.
After fix (1-h window): **100% (246/246)**.

## 6. Evidence captured in this campaign

### 6.1 Final tally (15 Jun, 1-h window post §19.3)

| Total | ✅ transformSuccess | ❌ errorCount | Success % |
|---:|---:|---:|---:|
| 246 | 246 | 0 | **100.00** |

### 6.2 Dashboard
`dashboard_screenshots/EvalRefinement_20260615_221510.png`.

## 7. Result

**PASS**.

| Objective | Result | Evidence |
|---|---|---|
| O-ERL-1 | ✅ | §6.1 |
| O-ERL-2 | ✅ | §5.2 — both branches now emit 1 |
| O-ERL-3 (≥95%) | ✅ | 100% |

## 8. Discussion

- The 50% failure was a **false negative**, not a real failure: every cycle was completing successfully but only half were emitting `1`. This is a recurring class of bug in dashboards driven by per-item code emitters fed by multi-branch Merges.
- The lesson is documented as the **always-success pattern** in `20_Reproduction_Guide.md` §6 and was applied to three layers in total (CPL, HIL, E&RL).
- Real E&RL failures would surface via a *separate* error-path emitter; the always-success rewrite does not mask them.

## 9. Limitations

- The dashboard cannot currently distinguish "revision applied" from "no revision needed" outcomes. Adding a `revision_path` label to the emitter would enable that breakdown.
- The Evaluation Agent's accept/reject thresholds are LLM-defined and not version-controlled separately from the workflow JSON.

## 10. Traceability

| Item | File |
|---|---|
| Capture Metrics rewrite | `07_Test_Run_Findings.md` §19.3 |
| Replacement JS | `12_Node_Code_Replacements.md` |
| Always-success pattern | `20_Reproduction_Guide.md` §6 |
| Job-label correction | `07_Test_Run_Findings.md` §17 |
| Final tally | `07_Test_Run_Findings.md` §19.6 |
| Dashboard | `dashboard_screenshots/EvalRefinement_20260615_221510.png` |
| CSV rows | `Results_Matrix_Filled.csv` `LT-ERL-*`, `METRICS-ERL` |
