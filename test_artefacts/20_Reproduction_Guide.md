# Reproduction Guide & Glossary

**Document ID:** RG-01
**Purpose:** Shared environment, terminology, authentication setup, and reusable queries referenced by all layer test reports (`13_…` to `19_…`). Read this once before attempting to reproduce any single layer test.

---

## 1. Architecture overview

CAPRA (Contextual Agentic Privacy Risk Assessment) is a 5-layer reference architecture implemented as a single n8n workflow with sub-workflows. Telemetry flows left to right; metrics flow down to Grafana Cloud.

```
                          ┌──────────────────────────────────────┐
                          │  Grafana Cloud (Loki + Dashboards)   │
                          └─▲────▲────▲────▲────▲────────────────┘
                            │    │    │    │    │
                  Push Grafana Metrics (HTTP, httpBasicAuth)
                            │    │    │    │    │
ESL ─► DFL ─► CPL ─► RIL ─► E&RL ─► HIL
                │     │     │     │     │
                └──── Mongo Atlas (multiple DBs/collections) ────┘
                            ▲
                            │
                       GraphDB Desktop (FedX/SPARQL repo `fedxvirtualsparql`)
```

| Layer | Long name | Purpose | Job label (Loki) | Dashboard UID |
|---|---|---|---|---|
| ESL | External Systems Layer | Per-domain ingestion (3 cron triggers: Student / Healthcare / Retail) | — (covered by DFL output) | — |
| DFL | Data Federation Layer | Normalises raw events to a shared 24-field schema | `data_federation_layer` | `dflmain` |
| CPL | Context Processing Layer | Enriches with severity / confidence / context; writes ontology triples | `context_processing_layer` | `cplmain` |
| RIL | Risk Intelligence Layer | Scenario → Simulation → Inference chain over enriched events | `risk_intelligence_layer` | `grpt7hn` |
| E&RL | Evaluation & Refinement Layer | Contextual scoring, evaluation, feedback, refinement | `evaluation_and_refinement_layer` | `evalmain` |
| HIL | Human Interaction Layer | Form-based reviewer Approve/Reject loop | `human_interaction_layer` | `hilmain` |
| — | All-Layers Overview | Aggregate dashboard | — | `alllayers` |

---

## 2. Environment & prerequisites

Tested on macOS 14 with the following local services. Versions are the ones used in this campaign; reasonable adjacent versions should also work.

| Service | Version | Where it runs | How to start |
|---|---|---|---|
| Docker Desktop | 4.59.1 | macOS host | `open -a Docker` |
| n8n | 1.x in container `n8n` | Docker container, port `5678` | `docker start n8n` |
| GraphDB Desktop | 10.x | macOS host, port `7200` | `open -a "GraphDB Desktop"` |
| MongoDB Atlas | M10 (cloud) | Atlas cluster | n8n credential `MongoDB Atlas` |
| Grafana Cloud | free tier | Cloud, `https://gracebilliris.grafana.net` | login |
| Grafana Loki | Cloud datasource UID `grafanacloud-logs`, push host `https://logs-prod-026.grafana.net` | Cloud | — |

### 2.1 Boot order (after a cold start)

```bash
# 1. Docker (host)
open -a Docker
for i in $(seq 1 18); do docker info >/dev/null 2>&1 && break; sleep 5; done

# 2. n8n container
docker start n8n
for i in $(seq 1 30); do curl -sf http://localhost:5678/healthz >/dev/null && break; sleep 3; done

# 3. GraphDB Desktop (required for RIL)
open -a "GraphDB Desktop"
for i in $(seq 1 30); do curl -sf http://localhost:7200/rest/repositories/fedxvirtualsparql >/dev/null && break; sleep 2; done

# 4. Activate the CAPRA Prototype workflow if it deactivated on the last save
curl -X POST -H "X-N8N-API-KEY: $N8N_API_KEY" \
     http://localhost:5678/api/v1/workflows/XUSBdhyaqrZVIXqp/activate
```

### 2.2 Known cold-start gotchas

- **Grafana Cloud Loki** suspends after idle on the free tier. The first query after a quiet period returns `{"code":"Loading","message":"Your instance is loading, and will be ready shortly."}`. Poll `/api/datasources/uid/grafanacloud-logs/health` every 10 s until `{"status":"OK"}`; typical warm-up is 1–10 minutes.
- **GraphDB Desktop** can enter an "alive but unresponsive" state with the process running and the port bound LISTEN but all HTTP requests timing out. Symptom: `Get Context` node in RIL fails with `ECONNREFUSED`. Recovery: `kill <PID>` then `open -a "GraphDB Desktop"`.
- **Saving a workflow via the n8n REST API silently deactivates it.** Always `POST /api/v1/workflows/<id>/activate` after a PUT and verify with a fresh GET.

---

## 3. Authentication artefacts

| Artefact | Where it lives | Purpose | How to obtain |
|---|---|---|---|
| n8n API key | `/tmp/n8n_apikey` (re-create per session — `/tmp` is wiped on reboot) | Workflow CRUD, execution inspection | n8n UI → Settings → API → Create API Key |
| Grafana service-account token | `/tmp/grafana_token` | Loki queries, dashboard CRUD, render API | Grafana UI → Administration → Service accounts → Add token (Editor role) |
| Mongo Atlas connection | Stored as n8n credential `MongoDB Atlas` | Mongo inserts/finds from n8n nodes | Atlas UI → Database → Connect → Application |
| Grafana Loki push credential | Stored as n8n credential `Grafana Credentials` (httpBasicAuth, id `P7IXLPyS97p7I1od`) | `Push Grafana Metrics*` nodes | Grafana Cloud → Loki → Send logs → Generate API token |
| Azure OpenAI deployments | Stored as n8n credentials per agent | LLM calls in ESL/CPL/RIL/E&RL/HIL | Azure portal |

> **Important:** Tokens in `/tmp/*` are session-scoped and will not survive reboot. Re-create before each test campaign.

---

## 4. Glossary of recurring terms

| Term | Meaning in CAPRA |
|---|---|
| **Capture Metrics emitter** | A Code node named `(1) Capture Metrics`, `…1`, `…2`, `…3`, or `…4` whose job is to emit one Loki log line per cycle on the success path of its layer. Sits *after* the layer's terminal Mongo write or decision. See §6 below for the **always-success pattern**. |
| **Formatting for Grafana** | A Code node downstream of a Capture Metrics emitter that wraps the metric body into the Loki HTTP push schema `{streams:[{stream:{...labels...}, values:[[ts_ns, json_body]]}]}`. |
| **Push Grafana Metrics** | An HTTP Request node that POSTs to `https://logs-prod-026.grafana.net/loki/api/v1/push` with `httpBasicAuth` (credential `Grafana Credentials`). Returns 204 on success. |
| **transformSuccess / errorCount** | Numerics in the metric body (not Loki labels). `transformSuccess=1` indicates a completed cycle; `errorCount=1` indicates a real failure surfaced via the error-path emitter. Dashboards `unwrap` these as Prometheus-style numerics. |
| **status (Loki label)** | A low-cardinality label: `success` / `failed` / `skipped` / `approved` / `rejected`. Safe to filter on. |
| **always-success pattern** | A Capture Metrics emitter that hard-codes `transformSuccess=1; errorCount=0; status='success'` because reaching the emitter means upstream Mongo + GraphDB writes already succeeded. Real failures are reported by a parallel error-path emitter, not by the success-path emitter self-reporting failure. Introduced in `07_Test_Run_Findings.md` §19. |
| **DSRM** | Design Science Research Methodology (Sonnenberg & vom Brocke, 2012). The CA1 report uses Stage 5 (Evaluation) with three criteria: Applicability, Generality, Novelty. |
| **FedX / `fedxvirtualsparql`** | A virtual GraphDB repository that federates multiple SPARQL endpoints into one. RIL's `Get Context` node reads from this repo. |
| **Merge2 / Merge6 / Merge7** | n8n Merge nodes that join branches inside HIL (Merge2), E&RL (Merge6), and HIL again (Merge7). Each Merge has 2–3 input branches and the items flowing through carry different shapes per branch — a frequent source of the "wrong-shape input" bug fixed in §19. |
| **form-waiting** | n8n form trigger pattern: the first form POST returns `{"formWaitingUrl":"http://localhost:5678/form-waiting/<execId>"}`; the reviewer (or test script) POSTs the second form (decision) to that URL. Requires **multipart/form-data**. |

---

## 5. Reusable Loki queries

All queries assume `datasource UID = grafanacloud-logs` and that the time window is supplied as `$__range` (Grafana variable) or a literal like `[1h]`.

### 5.1 Success / failure / total (per layer)

```logql
# Success rate (%)
( sum(sum_over_time({job="$JOB"} | json | __error__="" | unwrap transformSuccess [$__range]))
/ sum(count_over_time({job="$JOB"} | json | __error__="" | transformSuccess!="" [$__range])) ) * 100

# Failure rate (%)
( sum(sum_over_time({job="$JOB"} | json | __error__="" | unwrap errorCount [$__range]))
/ sum(count_over_time({job="$JOB"} | json | __error__="" | transformSuccess!="" [$__range])) ) * 100
```

For RIL and the All-Layers overview, add `| status!="skipped"` to **both** numerator and denominator to exclude gated-out events.

### 5.2 Verifying a layer is "alive" right now

```bash
TOKEN=$(cat /tmp/grafana_token)
curl -s -H "Authorization: Bearer $TOKEN" -G \
  "https://gracebilliris.grafana.net/api/datasources/proxy/uid/grafanacloud-logs/loki/api/v1/query_range" \
  --data-urlencode 'query={job="context_processing_layer"}' \
  --data-urlencode 'limit=1' --data-urlencode 'direction=BACKWARD' \
  --data-urlencode "start=$(( ($(date +%s) - 3600) * 1000000000 ))" \
  --data-urlencode "end=$(( $(date +%s) * 1000000000 ))" \
  | python3 -m json.tool | head -30
```

If `data.result[0].values[0][0]` is within the last 60 s, the layer is currently emitting.

### 5.3 Render a dashboard to PNG (no browser needed)

```bash
TOKEN=$(cat /tmp/grafana_token)
curl -sf -H "Authorization: Bearer $TOKEN" \
  "https://gracebilliris.grafana.net/render/d/<uid>/<slug>?orgId=1&from=now-1h&to=now&width=1600&height=900&timeout=60&kiosk=tv&tz=Australia%2FSydney" \
  -o "<uid>.png"
```

Slugs used:

```
grpt7hn             /risk-intelligence-layer
cplmain             /context-processing-layer
dflmain             /data-federation-layer
evalmain            /evaluation-layer
hilmain             /human-interaction-layer
alllayers           /all-layers-e28094-overview
capra-risk-register /capra-e28094-risk-dashboard   # added 26–31 Jul 2026
```

For the Risk Dashboard (Figure 5.7 in the CA3 report) use the absolute
window and full kiosk mode so the Grafana AI Week promo overlay is
suppressed:

```bash
TOKEN=$(cat /tmp/grafana_token)
FROM=$(python3 -c "import datetime; print(int(datetime.datetime(2026,7,26,21,10,0).timestamp()*1000))")
TO=$(python3   -c "import datetime; print(int(datetime.datetime(2026,7,26,22,25,0).timestamp()*1000))")
curl -sf -H "Authorization: Bearer $TOKEN" \
  "https://gracebilliris.grafana.net/render/d/capra-risk-register/capra-e28094-risk-dashboard?from=${FROM}&to=${TO}&width=1600&height=1200&tz=Australia%2FSydney&kiosk" \
  -o dashboard_screenshots/RiskDashboard_20260731_101000.png
```

For per-panel PNGs suitable for slides, use `/render/d-solo/<uid>/<slug>`
with `&panelId=<n>` — see `15_Layer_Report_RIL.md` §12.5 for the panel-id
manifest.

---

## 6. The always-success pattern (referenced from CPL, HIL, E&RL reports)

### 6.1 The anti-pattern

Each success-path Capture Metrics emitter sat after a Merge node and read a property off `$json` that only existed on *some* of the merge's input branches:

```js
// Anti-pattern — half the inputs lack item.revision → 50% reported failure
const revision = item.revision || {};
const hasRevision = Object.keys(revision).length > 0;
return { transformSuccess: hasRevision ? 1 : 0, ... };
```

Branches without that property reported `transformSuccess=0` even though their cycle had succeeded — the merge structure just routed differently-shaped objects through the same emitter.

### 6.2 The fix

Reaching the success-path emitter means the upstream Mongo write / GraphDB write / form decision *already succeeded* (otherwise the workflow would have routed to the error branch, which has its own emitter). The semantically correct metric is therefore "cycle completed":

```js
// Always-success — semantically correct
const transformSuccess = 1;
const errorCount = 0;
const status = 'success';
// Descriptive fields still recovered from named upstream nodes for traceability:
try { taskId    = $('Feedback-to-Action Translation Agent').item?.json?.task_id || taskId; } catch(e){}
try { revisionId = $('Insert to Feedback Results').item?.json?.revision_id   || revisionId; } catch(e){}
return { transformSuccess, errorCount, status, task_id: taskId, revision_id: revisionId, ... };
```

Real failures still surface through the parallel error-path emitters (which write `errorCount=1`). The dashboards' Failure % panels are driven by those, not by the success-path emitter.

This pattern was applied to:
- CPL `(1) Capture Metrics` (LR-CPL-01 §4.2)
- HIL `(1) Capture Metrics4` (LR-HIL-01 §4.2)
- E&RL `(1) Capture Metrics3` (LR-ERL-01 §4.2)

---

## 7. Quick-reference: layer-specific webhooks and triggers

| Layer | How to fire a test event |
|---|---|
| ESL Student | Cron-driven; or manual via n8n UI → "Execute ESL Admission Data" |
| ESL Healthcare | Cron-driven; or manual via n8n UI → "Execute ESL EHR Data" |
| ESL Retail | Cron-driven; or manual via n8n UI → "Execute ESL Retail Data" |
| DFL / CPL / RIL / E&RL | All cron-driven; or trigger upstream ESL and observe propagation |
| HIL | Multipart POST to `http://localhost:5678/form/2b5380bf-e9a9-4287-8679-0fb8c1636bae` with `Reviewer Name` + `Reviewer Email`; then second multipart POST to `/form-waiting/<execId>` with `Approval Decision=Approve\|Reject` + `Reviewer Comments` |

---

## 8. Where evidence lives

| Evidence type | Path (relative to `files/`) |
|---|---|
| Findings narrative | `test_artefacts/07_Test_Run_Findings.md` |
| Results matrix (CSV) | `test_artefacts/Results_Matrix_Filled.csv` |
| Per-domain evidence | `test_artefacts/evidence/post_*.md` |
| Mongo snapshots | `test_artefacts/snapshots/` |
| Earlier screenshots | `test_artefacts/grafana_screenshots/` |
| Current screenshots (15 Jun) | `dashboard_screenshots/` |
| Screen recordings | `test_artefacts/recordings/` |
| Node code replacements | `test_artefacts/12_Node_Code_Replacements.md` |
| Dashboard fix history | `test_artefacts/10_Grafana_Fixes_Code_Changes.md` |
| Comparative analysis | `test_artefacts/08_Comparative_Analysis_and_Performance.md` |
| DSRM populated | `test_artefacts/02_DRSM_Evaluation_Populated.md` |
| **Layer test reports** | `test_artefacts/13_…` to `test_artefacts/18_…` |
| **DSRM evaluation report** | `test_artefacts/19_DSRM_Evaluation_Report.md` |

All paths exist in both the working copy and the OneDrive backup at `Grace's PhD/Artefact/copilot_session_artefacts_20260615_222148/69643f49-…/files/`.
