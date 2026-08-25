# Cross-Stage Identifier Mapping — CAPRA Prototype

**Report ID:** LR-XSTAGE-01
**Prototype:** CAPRA (n8n workflow `XUSBdhyaqrZVIXqp`)
**Coverage:** DFL → CPL → RIL → FRL (E&RL) → HIL
**Purpose:** Document every identifier retained across stages so any event's provenance can be reconstructed from the raw evidence bundle (`04_collect_evidence.py` outputs + Loki + n8n `execution_entity`).
**Evidence base:** `04_collect_evidence.py`, `07_Test_Run_Findings.md` §§7, 10, 19.7, `13_Layer_Report_DFL.md` §5 (canonical 24-field schema), `14_Layer_Report_CPL.md` §7 (provenance), `15_Layer_Report_RIL.md` §12 (domain propagation), `n8n_snippets/RIL_Formatting_for_Grafana_patched.js`, `n8n_snippets/format_risk_for_grafana.js`.

---

## 1. Identifier catalogue

| Identifier | Origin | Type | First materialised in | Persisted where | Used to join |
|---|---|---|---|---|---|
| `workflow_id` | n8n | string | `XUSBdhyaqrZVIXqp` (constant) | n8n `execution_entity.workflowId` | Filters all `execution_entity` rows for this pipeline. |
| `execution_id` | n8n | integer | `execution_entity.id` | n8n SQLite `execution_entity`; surfaced through the API (`GET /executions/<id>`) | Cross-links any Loki record → the exact n8n execution that produced it; also joins to §HIL waiting-execution table. |
| `_id` (Mongo) | MongoDB per collection | ObjectId | Per-collection insert | Every Mongo collection: `local_db.local_raw`, `telemetry_raw`, `enriched_telemetry_raw`, `risk_inference`, `evaluation_results`, `feedback_results`, `revision_results` | Deterministic ordering + provenance chain via `_id` timestamp windows; each downstream doc records the upstream `_id` in `prov:wasDerivedFrom` (CPL) or in an explicit foreign-key field (RIL, FRL). |
| `event_id` | DFL | string, `evt_<n>` | DFL Data Interpretation → `local_db.telemetry_raw` | telemetry_raw; enriched_telemetry_raw (retained verbatim); RIL scenario body | Primary cross-stage key. Every downstream layer keeps the origin `event_id` in its emitted payload. |
| `session_id` | DFL | string, `sess_<domain>_<n>` | DFL canonical schema | telemetry_raw; propagated to enriched_telemetry_raw | Groups per-session events; used by RIL scenario aggregation. |
| `task_id` | DFL / upstream ESL | string (e.g. `discharge_patient`, `academic_credentials_assessed`, `view_assignment`) | ESL "Telemetry Generator" → DFL 24-field schema | telemetry_raw, enriched_telemetry_raw, `risk_inference`, `evaluation_results`, `feedback_results`; emitted as a JSON body field (not a Loki label) by every Formatting-for-Grafana node | Semantic anchor across all five layers. Domain heuristics attribute events to Student/Healthcare/Retail via `task_id` prefixes (see `07_Test_Run_Findings.md` §§2, 7). |
| `span_id` / `parent_span_id` | DFL canonical schema | string | DFL 24-field schema | telemetry_raw; enriched_telemetry_raw | Intra-execution trace hierarchy inside a single origin event. |
| `actor_entity` (`entity_type`, `entity_id`) | DFL | object | DFL canonical schema | All layers | Joins to CPL enrichment triples and RIL scenario actor. |
| `target_entity` (`entity_type`, `entity_id`) | DFL | object | DFL canonical schema | All layers | As above. |
| `data_entity` / `destination_entity` | DFL | object | DFL canonical schema | All layers | Supports lineage of the PII payload. |
| `domain` | DFL / heuristic | enum `student_admission` / `healthcare` / `retail` | Not always emitted upstream — CPL currently does not propagate a `domain` label to RIL (documented in `15_Layer_Report_RIL.md` §12) | telemetry_raw when tagged; reconstructed downstream by heuristic on `task_id` / `actor_entity` / `event_type` (see `07_Test_Run_Findings.md` §§2, 7, 8) | Per-domain time-window filtering. **Known gap** — RIL and FRL Grafana rows may show `domain=unknown`; workaround is absolute-time-range filtering per campaign. |
| `prov:wasDerivedFrom` | CPL | RDF triple | CPL "Extract Data for Graph DB" (SPARQL update) → Fuseki `ontology` dataset | Fuseki triple store | Formal provenance link from enriched event → source telemetry event, queryable by SPARQL. |
| `scenario_id` | RIL Scenario Agent | string | RIL Scenario Agent output | `risk_inference`; **moved into JSON body** (not a Loki label) by `RIL_Formatting_for_Grafana_patched.js` to avoid Loki cardinality blow-up (`12_Node_Code_Replacements.md` §5) | Joins across the two Simulation Agents and the Inference Agent. |
| `simulation_run_id` | RIL Simulation Orchestrator | string | RIL Simulation Orchestrator output | `risk_inference`; also JSON-body only | Aggregates the two independent simulations into one inference. |
| `risk_id` | RIL Inference Agent | string, `<scenario_id>-<ingestTime>` or `ril-<ingestTime>` fallback | `RIL_Formatting_for_Grafana_patched.js` line 42–43 | `risk_inference`; JSON-body only in Loki | Uniquely identifies each risk record surfaced by the Risk Dashboard. |
| `revision_id` | FRL (Evaluation & Refinement) | string | Feedback-to-Action Translation Agent → "Insert to Feedback Results" | `revision_results`, `feedback_results` | Joins reviewer decisions (HIL) back to the specific FRL refinement they authorise. |
| `reviewer_form_execution_id` | HIL | integer | Same as n8n `execution_id`, captured at `POST /form/<webhookId>` | n8n execution DB (state=`waiting`) | Second form (`POST /form-waiting/<webhookId>`) matches by execution id; see `17_Layer_Report_HIL.md` §§3, 4. |

## 2. Per-stage retention matrix

Cells show which identifiers are **explicitly written** by each stage's persistence and telemetry output. `→` = passed through unchanged, `+` = originated here, `↔` = joined with upstream via that field.

| Identifier | ESL | DFL | CPL | RIL | FRL | HIL |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| `event_id` | + | → | → | ↔ | ↔ | — |
| `session_id` | + | → | → | ↔ | — | — |
| `task_id` | + | → | → | → | → | ↔ (may be null when triggered manually) |
| `span_id` / `parent_span_id` | — | + | → | — | — | — |
| `actor_entity` / `target_entity` | + | → | → | ↔ | ↔ | — |
| `_id` (Mongo) | + | + | + | + | + | + |
| `prov:wasDerivedFrom` | — | — | + | — | — | — |
| `scenario_id` | — | — | — | + | ↔ | — |
| `simulation_run_id` | — | — | — | + | — | — |
| `risk_id` | — | — | — | + | ↔ | ↔ |
| `revision_id` | — | — | — | — | + | ↔ |
| `execution_id` (n8n) | + | + | + | + | + | + |
| `domain` | ~ | ~ | ~ | ⚠ often unknown | ⚠ | — |

## 3. Reconstructing an event end-to-end

Given a single row on the Risk Dashboard (`capra-risk-register`, evidence Fig 5.7):

1. Read `risk_id`, `scenario_id`, and `task_id` from the row's JSON body (they are body fields, not Loki labels — deliberate, per `12_Node_Code_Replacements.md` §5).
2. Query Mongo `local_db.risk_inference` for the doc with that `risk_id`; that doc carries the origin `event_id`.
3. Query `local_db.enriched_telemetry_raw` for the doc with matching `event_id` → CPL enrichment record.
4. Query the Fuseki `ontology` dataset by `prov:wasDerivedFrom` on the CPL record → back to the source telemetry triple.
5. Query `local_db.telemetry_raw` for the doc with matching `event_id` → DFL canonical event, including `actor_entity`, `target_entity`, `span_id`, and the ESL-supplied `task_id`.
6. Query n8n `execution_entity` (via `docker exec n8n node -e "..."` in `04_collect_evidence.py`) for the execution(s) whose start/stop window brackets the `_id` timestamps of the docs found in steps 2–5.
7. If a reviewer decision exists, query `local_db.revision_results` by `revision_id` and cross-reference the HIL execution via the same `execution_id`.

Every step is fully deterministic; no heuristics required once `risk_id` is known.

## 4. Known linkage gaps

| Gap | Impact | Mitigation |
|---|---|---|
| CPL prompt does not always propagate `domain` downstream (documented in `15_Layer_Report_RIL.md` §12). | RIL / FRL rows on the Risk Dashboard can read `domain=unknown`. | Per-domain evaluation windows are attributed by absolute time-range filtering per campaign (`07_Test_Run_Findings.md` §20). |
| Legacy `simulation_run_id`, `scenario_id`, `risk_type_1`, `contributing_factor_1` values still occupy Loki labels for streams older than the `RIL_Formatting_for_Grafana_patched.js` cut-over. | Elevates Loki stream cardinality; forces the RIL dashboard's P95 latency panel to use `max_over_time` rather than `quantile_over_time` (`07_Test_Run_Findings.md` §10.2). | Will resolve as legacy streams age out of retention. Post-cut-over evidence should be filtered to `time >= 2026-07-26 21:10 AEST`. |
| HIL manually-triggered form executions may have null `task_id`/`revision_id` (`07_Test_Run_Findings.md` §19.7). | Those HIL executions cannot be joined back to a specific upstream event. | Trigger HIL only from the two-stage form path documented in `17_Layer_Report_HIL.md` §§3, 4; do not fire the webhook directly for evidence-grade runs. |
| `event_id` allocation is monotonic within a source CSV but not globally unique across ESL sources; two sources firing on the same schedule tick can share a numeric suffix. | Cross-source joins by `event_id` alone are ambiguous. | Always join on `(event_id, actor_entity.entity_id)` or on `_id` timestamp windows. |

## 5. How this document is regenerated

The evidence bundle underlying every claim in this document is produced by:

```
python3 03_snapshot_mongo.py <label>_pre
# run pipeline for the campaign
python3 03_snapshot_mongo.py <label>_post
python3 04_collect_evidence.py <label>_pre <label>_post
```

Outputs land in `test_artefacts/evidence/<label>_post.{md,json}`. This mapping document is the human-readable overlay on top of that bundle; the bundle itself is the ground truth.
