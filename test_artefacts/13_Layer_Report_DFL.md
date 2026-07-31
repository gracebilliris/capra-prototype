# Layer Test Report — Data Federation Layer (DFL)

**Report ID:** LR-DFL-01
**Prototype:** CAPRA (n8n workflow `XUSBdhyaqrZVIXqp`)
**Layer under test:** Data Federation Layer
**Domains exercised:** Student Admission · Healthcare (EHR) · Retail (employees)
**Prerequisites:** See `20_Reproduction_Guide.md` §§2–4 (environment, authentication, glossary).
**Evidence base:** `07_Test_Run_Findings.md` §§1–19, `Results_Matrix_Filled.csv`, `evidence/post_*.md`, `dashboard_screenshots/DFL_20260615_221510.png`

---

## 1. Concept primer

The **Data Federation Layer (DFL)** is the second layer in CAPRA. Its job is to take raw telemetry produced by the per-domain triggers in the External Systems Layer (ESL) and normalise it into a single, shared 24-field event schema. After DFL, every downstream layer (CPL, RIL, E&RL, HIL) sees the same event structure regardless of which domain produced it. This separation of concerns is what makes the **generality** claim of CAPRA testable: if shared layers truly do not depend on the source domain, then *adding a fourth domain should require only a new ESL trigger, not changes to DFL or anything downstream*.

The DFL contains one core LLM agent, the **Normalisation Agent**, which:
1. Reads heterogeneous raw events from `local_db.local_raw`.
2. Maps each event's source-specific fields to the canonical 24-field schema (event_id, timestamp, actor_entity, target_entity, task_id, severity_hint, confidence_hint, …).
3. Persists the normalised events to `local_db.telemetry_raw`.
4. Emits a `transformSuccess=1` log line to Loki for each successful cycle.

Loki is queried via PromQL-like LogQL (`{job="data_federation_layer"} | json | unwrap transformSuccess`); the dashboard `dflmain` aggregates this into a Success % / Failure % / throughput panel set.

## 2. Objective

Verify three claims about the DFL:

| # | Claim | How tested |
|---|---|---|
| O-DFL-1 | DFL ingests events from all three domain triggers without per-domain code paths. | Per-domain Mongo growth and per-domain sample documents. |
| O-DFL-2 | The normalised schema is consistent across domains. | Sample document inspection in `evidence/post_*.md`. |
| O-DFL-3 | The layer is reliable at sustained load. | Loki Success % across a 1-hour window. |

## 3. Setup

| Item | Value | Notes |
|---|---|---|
| n8n workflow | `XUSBdhyaqrZVIXqp` (CAPRA Prototype) | Active state required (`active=true`). |
| Sub-workflow | `Data Federation Layer` (`IWlUNLdEUi27BOry`) | Activated by parent on each cron trigger. |
| Upstream input | Output of ESL Student / Healthcare / Retail | Three ESL triggers run independently on cron. |
| Mongo source | `local_db.local_raw` | Raw events from ESL. |
| Mongo sink | `local_db.telemetry_raw` | Normalised events. |
| Loki job label | `data_federation_layer` | Set in `Formatting for Grafana (Data Fed.)`. |
| Dashboard UID | `dflmain` (slug `data-federation-layer`) | https://gracebilliris.grafana.net/d/dflmain/data-federation-layer |
| Service dependencies | Docker, n8n container, Mongo Atlas, Grafana Cloud Loki | GraphDB *not* required for DFL alone. |

## 4. Reproduction procedure

### 4.1 Prepare environment

```bash
# Re-create tokens (see Reproduction Guide §3)
echo "$N8N_API_KEY" > /tmp/n8n_apikey
echo "$GRAFANA_TOKEN" > /tmp/grafana_token

# Boot services (Reproduction Guide §2.1)
open -a Docker
for i in $(seq 1 18); do docker info >/dev/null 2>&1 && break; sleep 5; done
docker start n8n
for i in $(seq 1 30); do curl -sf http://localhost:5678/healthz >/dev/null && break; sleep 3; done

# Activate the CAPRA Prototype
API=$(cat /tmp/n8n_apikey)
curl -s -X POST -H "X-N8N-API-KEY: $API" \
  http://localhost:5678/api/v1/workflows/XUSBdhyaqrZVIXqp/activate \
  | python3 -m json.tool
```

Expected: `"active": true`.

### 4.2 Snapshot Mongo (baseline)

```bash
python3 ~/.copilot/session-state/69643f49-376f-475e-bce7-aafd927eb125/files/test_artefacts/03_snapshot_mongo.py
# Writes pre-test counts to test_artefacts/snapshots/<timestamp>_pre.json
```

### 4.3 Allow at least 15 minutes of cron firing

The three ESL triggers run on independent cron schedules (visible in the n8n UI). No manual action is needed; just wait.

### 4.4 Snapshot Mongo (post)

```bash
python3 ~/.copilot/session-state/69643f49-376f-475e-bce7-aafd927eb125/files/test_artefacts/03_snapshot_mongo.py
# Writes test_artefacts/snapshots/<timestamp>_post.json — diff against pre to get Δ.
```

Expected: `local_db.telemetry_raw` Δ ≥ +20 per 15 minutes per active domain.

### 4.5 Inspect domain mix in a sample

```bash
python3 ~/.copilot/session-state/69643f49-376f-475e-bce7-aafd927eb125/files/test_artefacts/04_collect_evidence.py
# Samples the 500 most-recent local_raw docs and counts how many classify as student/healthcare/retail.
```

Expected for a healthy 3-domain run: roughly 30–40% per domain.

### 4.6 Query Loki for layer health

```bash
TOKEN=$(cat /tmp/grafana_token)
NOW=$(date +%s)
curl -s -H "Authorization: Bearer $TOKEN" -G \
  "https://gracebilliris.grafana.net/api/datasources/proxy/uid/grafanacloud-logs/loki/api/v1/query" \
  --data-urlencode 'query=sum(sum_over_time({job="data_federation_layer"} | json | __error__="" | unwrap transformSuccess [1h]))' \
  --data-urlencode "time=$NOW" \
  | python3 -m json.tool
```

Expected (1-h window after warm-up): `result[0].value[1]` ≥ 100 and equal to `count_over_time({job="data_federation_layer"} | json | transformSuccess!="" [1h])` (i.e., 100% success).

### 4.7 Render the dashboard to PNG

```bash
TOKEN=$(cat /tmp/grafana_token)
curl -sf -H "Authorization: Bearer $TOKEN" \
  "https://gracebilliris.grafana.net/render/d/dflmain/data-federation-layer?orgId=1&from=now-1h&to=now&width=1600&height=900&timeout=60&kiosk=tv&tz=Australia%2FSydney" \
  -o "DFL_$(date +%Y%m%d_%H%M%S).png"
```

## 5. Evidence captured in this campaign

### 5.1 Per-domain throughput

| Domain | Window | local_raw delta (ESL) | telemetry_raw delta (DFL) | Source |
|---|---|---:|---:|---|
| Student | 12 Jun 05:45–06:00 UTC (15 min) | +33 | **+21** | `Results_Matrix_Filled.csv` row `LT-DFL-STU` |
| Healthcare | 12 Jun 07:43–07:55 UTC (12 min) | +328 (sample 134/500 healthcare) | **+88** | `LT-DFL-HLT` + `evidence/post_healthcare_fix.md` |
| Retail | 12 Jun 08:53–09:05 UTC (12 min) | +722 (sample 143/500 retail) | **+203** | `LT-DFL-RET` + `evidence/post_retail_fix.md` |

### 5.2 Sample normalised document (Healthcare)

From `evidence/post_healthcare_fix.md`:

```json
{
  "event_id": "evt_…",
  "timestamp": "2026-06-12T07:48:…Z",
  "task_id": "discharge_patient",
  "actor_entity": { "type": "hospital_staff", "id": "hs_004" },
  "target_entity": { "type": "patient", "id": "pat_001" },
  "source_system": "EHR.csv",
  "severity_hint": "medium",
  "confidence_hint": 0.82,
  ...
}
```

Healthcare-specific source fields (`hospital_id`, `discharge_reason`, …) are mapped into the shared 24-field shape. The same schema appears for Student and Retail samples — only the *values* of `task_id` / `actor_entity.type` / `target_entity.type` differ.

### 5.3 Loki-side success metrics (15 Jun 22:15 AEST, 1-h window)

| Total | transformSuccess | errorCount | Success % |
|---:|---:|---:|---:|
| 613 | 613 | 0 | **100.00** |

### 5.4 Dashboard
`dashboard_screenshots/DFL_20260615_221510.png` — 1600×900, rendered server-side. Success 100.00 / Failure 0.00 / sum 100.

## 6. Result

**PASS — all three objectives met.**

| Objective | Result | Evidence |
|---|---|---|
| O-DFL-1 (multi-domain ingestion) | ✅ | Three positive Δ rows in §5.1 |
| O-DFL-2 (shared schema) | ✅ | Sample documents in `evidence/post_*.md` show identical 24-field shape |
| O-DFL-3 (reliable at load) | ✅ | 613/613 success in 1-h window (§5.3); zero fixes required across the entire campaign |

## 7. Discussion

The DFL was the most stable layer in the prototype. None of the fix cycles in §§17–19 of the findings touched it. This stability is consistent with the layer's narrow responsibility (schema normalisation only) and absence of external dependencies beyond Mongo.

The shared 24-field schema is the structural mechanism that lets all downstream layers be domain-agnostic. If a future iteration adds a fourth domain (e.g., finance), the only addition required is a new ESL trigger plus a Normalisation Agent prompt update; DFL's downstream contract does not change.

## 8. Limitations

- **Production data volumes not exercised.** Production-scale CSVs (190 MB, 805 MB) are present in the dataset but were not consumed end-to-end. Largest file ingested: 342 KB (EHR). Scaling to production sizes would require chunking and streaming.
- **Normalisation Agent is LLM-driven.** Field mapping accuracy is bounded by LLM context-window behaviour. No formal mapping correctness study was conducted.
- **No schema-validation gate at the DFL output.** If the agent emits a malformed event, CPL receives it. A future iteration should add a JSON Schema validator between DFL and CPL.

## 9. Traceability

| Item | File |
|---|---|
| Test cases | `Results_Matrix_Filled.csv` rows `LT-DFL-STU`, `LT-DFL-HLT`, `LT-DFL-RET` |
| Per-domain evidence | `evidence/post_healthcare_fix.md`, `evidence/post_retail_fix.md`, `evidence/post_retail_content.md`, `evidence/post_observation.md` |
| Mongo snapshots | `snapshots/<timestamp>_pre.json`, `<timestamp>_post.json` |
| Final tally | `07_Test_Run_Findings.md` §19.6 |
| Dashboard snapshot | `dashboard_screenshots/DFL_20260615_221510.png` |
| Reproduction commands | this report §4 + `20_Reproduction_Guide.md` |
