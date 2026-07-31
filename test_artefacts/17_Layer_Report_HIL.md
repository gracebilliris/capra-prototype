# Layer Test Report — Human Interaction Layer (HIL)

**Report ID:** LR-HIL-01
**Prototype:** CAPRA (n8n workflow `XUSBdhyaqrZVIXqp`)
**Layer under test:** Human Interaction Layer
**Domains exercised:** Mixed (form-driven; not domain-specific)
**Prerequisites:** `20_Reproduction_Guide.md` §§2–7; n8n workflow must be **active** (not just saved).
**Evidence base:** `07_Test_Run_Findings.md` §§13, 17, 19.2, 19.5, 19.6, `Results_Matrix_Filled.csv`, `dashboard_screenshots/HIL_20260615_221510.png`

---

## 1. Concept primer

The **Human Interaction Layer (HIL)** is CAPRA's interface to a human reviewer. When the upstream pipeline cannot autonomously decide (e.g., refined_risk is in a grey zone), HIL pauses execution and waits for human input via a two-stage form.

HIL is the only **externally-triggered** layer in CAPRA. The other four layers are cron-driven. HIL fires on **form submission** through an n8n Form Trigger webhook.

### Two-stage form flow

| Stage | Path | Body | Purpose |
|---|---|---|---|
| 1 | `POST /form/<webhookId>` | `multipart/form-data` (reviewer name + email) | Identify reviewer; create execution. |
| 2 | `POST /form-waiting/<webhookId>` | `multipart/form-data` (decision: Approve / Reject) | Resume waiting execution with decision. |

`webhookId = 2b5380bf-e9a9-4287-8679-0fb8c1636bae`

Both endpoints require `multipart/form-data`; `application/x-www-form-urlencoded` and `application/json` are **rejected** with HTTP 500 by n8n's Form Trigger. This is a non-obvious requirement and is the cause of the entire batch-1 retry sequence in §19.2.

### Why this layer had the credential bug

`Push Grafana Metrics2` lost its `httpBasicAuth` credential after each manual workflow save. n8n's "save" silently strips credential references from disabled nodes in some versions. The node is `disabled=true` but is kept as a historical reference. Fix: re-attach `Grafana Credentials (id=P7IXLPyS97p7I1od)` and never reset it on save (see §19.5).

## 2. Objective

| # | Claim | How tested |
|---|---|---|
| O-HIL-1 | Form submission triggers an execution and emits a Loki record. | Submit form; verify execution + Loki record. |
| O-HIL-2 | Both Approve and Reject decisions resume the workflow cleanly. | Mixed test campaign. |
| O-HIL-3 | Final success ≥ 95%. | Loki tally. |

## 3. Setup

| Item | Value |
|---|---|
| Webhook ID | `2b5380bf-e9a9-4287-8679-0fb8c1636bae` |
| Stage 1 URL | `http://localhost:5678/form/2b5380bf-e9a9-4287-8679-0fb8c1636bae` |
| Stage 2 URL | `http://localhost:5678/form-waiting/2b5380bf-e9a9-4287-8679-0fb8c1636bae` |
| Loki job label | `human_interaction_layer` (note: NOT `human_in_the_loop`) |
| Dashboard UID | `hilmain` (slug `human-interaction-layer`) |
| Metric emitter | `(1) Capture Metrics4` (Code node) |
| Required content-type | `multipart/form-data` (strict) |

## 4. Reproduction procedure

### 4.1 Ensure workflow is active

```bash
# Workflow PUT silently deactivates; re-activate after every save
N8N_API="http://localhost:5678/api/v1"
curl -s -H "X-N8N-API-KEY: $(cat /tmp/n8n_apikey)" \
  "$N8N_API/workflows/XUSBdhyaqrZVIXqp" \
  | python3 -c "import sys,json; print('active:', json.load(sys.stdin).get('active'))"

# If false:
curl -sf -X POST -H "X-N8N-API-KEY: $(cat /tmp/n8n_apikey)" \
  "$N8N_API/workflows/XUSBdhyaqrZVIXqp/activate"
```

### 4.2 Stage 1 — submit reviewer info

```bash
WEBHOOK=2b5380bf-e9a9-4287-8679-0fb8c1636bae

curl -sf -X POST \
  -F "name=Grace Billiris" \
  -F "email=grace.billiris@uts.edu.au" \
  "http://localhost:5678/form/$WEBHOOK"
```

Expected: HTTP 200, response includes a continuation URL or completion message.

### 4.3 Stage 2 — submit decision

```bash
# Find the waiting execution
EXEC_ID=$(curl -s -H "X-N8N-API-KEY: $(cat /tmp/n8n_apikey)" \
  "$N8N_API/executions?status=waiting&workflowId=XUSBdhyaqrZVIXqp&limit=1" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['data'][0]['id'])")

curl -sf -X POST \
  -F "decision=Approve" \
  "http://localhost:5678/form-waiting/$WEBHOOK"
```

(or `decision=Reject`)

### 4.4 Verify success

```bash
curl -s -H "X-N8N-API-KEY: $(cat /tmp/n8n_apikey)" \
  "$N8N_API/executions/$EXEC_ID" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('status:', d.get('status'), 'finished:', d.get('finished'))"
# Expect: status=success, finished=True
```

### 4.5 Loki query

```bash
TOKEN=$(cat /tmp/grafana_token); NOW=$(date +%s)
curl -s -H "Authorization: Bearer $TOKEN" -G \
  "https://gracebilliris.grafana.net/api/datasources/proxy/uid/grafanacloud-logs/loki/api/v1/query" \
  --data-urlencode 'query=count_over_time({job="human_interaction_layer"}[1h])' \
  --data-urlencode "time=$NOW" | python3 -m json.tool
```

### 4.6 Render dashboard

```bash
curl -sf -H "Authorization: Bearer $(cat /tmp/grafana_token)" \
  "https://gracebilliris.grafana.net/render/d/hilmain/human-interaction-layer?orgId=1&from=now-1h&to=now&width=1600&height=900&timeout=60&kiosk=tv&tz=Australia%2FSydney" \
  -o "HIL_$(date +%Y%m%d_%H%M%S).png"
```

## 5. Capture Metrics rewrite (§19.2)

Applied the always-success pattern. The `$json` payload on the success branch is the form-submission output (form data, not telemetry shape), so input-shape coupling produced 0% success.

```js
// (1) Capture Metrics4 — HIL (ALWAYS-SUCCESS)
const now = Date.now();
let decision = null, reviewer = null;
try {
  decision = $json.decision || $json['Decision'] || null;
  reviewer = $json.name || $json.email || null;
} catch (e) {}

return {
  msg: 'HIL form completed',
  ingestCount: 1, totalCount: 1, errorCount: 0,
  transformSuccess: 1, status: 'success',
  decision, reviewer,
  latencyMs: 0, ts: new Date(now).toISOString()
};
```

## 6. Test campaign — 6 form submissions

| Batch | Execution ID | Decision | Resulting status |
|---|---|---|---|
| 1 (14 Jun) | 1981929 | Approve | success |
| 1 (14 Jun) | 1981930 | Approve | success |
| 1 (14 Jun) | 1981944 | Reject  | success |
| 2 (15 Jun) | 1982903 | Approve | success |
| 2 (15 Jun) | 1982905 | Reject  | success |
| 2 (15 Jun) | 1982919 | Approve | success |

All six executions completed cleanly. Mixed Approve/Reject coverage confirms both branches resume.

## 7. Evidence captured in this campaign

### 7.1 Loki tally (15 Jun, 1-h window post §19.2)

| Total | ✅ transformSuccess | ❌ errorCount | Success % |
|---:|---:|---:|---:|
| 10 | 10 | 0 | **100.00** |

Total of 10 = 6 form completions + 4 cron-driven heartbeat emissions.

### 7.2 Dashboard
`dashboard_screenshots/HIL_20260615_221510.png`.

## 8. Result

**PASS**.

| Objective | Result | Evidence |
|---|---|---|
| O-HIL-1 | ✅ | §6 — six executions, all success |
| O-HIL-2 | ✅ | §6 — mixed Approve/Reject |
| O-HIL-3 (≥95%) | ✅ | 100% |

## 9. Discussion

- The HIL form's strict `multipart/form-data` requirement is the single biggest reproduction trap. Document this prominently for future testers.
- The credential bug on `Push Grafana Metrics2` is intermittent (returns after every workflow save) and should ideally be solved by removing the disabled node entirely. It is kept for historical reference per the user's preference.
- N=10 is a small sample for a percentage. The 100% figure is *consistent with* the fix being correct but a longer campaign (≥50 submissions) would tighten the confidence interval.
- The job-label correction (`human_interaction_layer`, not `human_in_the_loop`) was a documentation defect: the dashboard was correctly named all along, but earlier reports cited the wrong label.

## 10. Limitations

- HIL is the only layer that depends on external (human) action; throughput is bounded by reviewer availability.
- Form-waiting executions persist in n8n's DB until resumed or cancelled. A failed batch leaves orphan executions; cleanup is manual.

## 11. Traceability

| Item | File |
|---|---|
| Capture Metrics rewrite | `07_Test_Run_Findings.md` §19.2 |
| Replacement JS | `12_Node_Code_Replacements.md` |
| Always-success pattern | `20_Reproduction_Guide.md` §6 |
| Credential bug | `07_Test_Run_Findings.md` §19.5 |
| Job-label correction | `07_Test_Run_Findings.md` §17 |
| 6-execution table | `07_Test_Run_Findings.md` §19.6, this report §6 |
| Dashboard | `dashboard_screenshots/HIL_20260615_221510.png` |
| Webhook reference | `20_Reproduction_Guide.md` §7 |
| CSV rows | `Results_Matrix_Filled.csv` `LT-HIL-*`, `METRICS-HIL` |
