# CAPRA Prototype — Test Plan (E2E + Unit/Layer)

**Artefact under test:** n8n workflow `CAPRA Prototype` (`XUSBdhyaqrZVIXqp`)
**Source document:** `13925894_CA1_Written_Report.docx`
**Author:** Grace Billiris
**Date:** 2026-06-12

---

## 1. Scope & Objectives

This test plan exercises the CAPRA (Context-Aware Privacy Risk Assessment) reference framework prototype in n8n. The plan covers:

- **Layer (unit) tests** — verify each architectural layer behaves correctly in isolation, per domain.
- **End-to-End (E2E) tests** — verify the full ingestion → reporting pipeline per domain.
- **DSRM evaluation** — map results to Applicability / Generality / Novelty (Sonnenberg & vom Brocke, 2012; report §3.3.5, §5.2).

### Architectural layers under test
Confirmed from the workflow's schedule triggers and the report (§4.4):

| # | Layer | Acronym | n8n trigger | Primary agents / nodes | Output collection(s) |
|---|---|---|---|---|---|
| 0 | External Systems Layer | ESL | `Execute ESL Admission Data`, `Execute ESL EHR Data`, `Execute ESL Retail Data` | Data Interpretation Agent, Telemetry Generator Agent (×3) | `local_db.local_raw` |
| 1 | Data Federation Layer | DFL | `Execute DFL` | Normalisation Agent | `telemetry_db.telemetry_raw` (+ Kafka topic) |
| 2 | Context Processing Layer | CPL | `Execute CPL` | Telemetry Collector Agent, Telemetry Transformation Agent, Ontology & Mapping Authority Agent | `telemetry_db.enriched_telemetry_raw`, `raw_ontology`, `telemetry_transformation` + Fuseki/GraphDB |
| 3 | Risk Intelligence Layer | RIL | `Execute RIL` | Scenario Agent, Simulation Orchestrator, Simulation Agents 1/2, Inference Agent | `risk_intelligence_db.raw_scenarios`, `orchestration_agent_scenarios`, `scenario_simulation_results`, `risk_inference_results` |
| 4 | Evaluation & Reporting Layer | E&RL | `Execute E&RL`, `Daily Summary of RIL Results` | Evaluation Agent, Feedback & Revising Agent, Feedback-to-Action Translation Agent, Contextual Risk Scoring (code), Summarise Findings | `feedback_and_refinement_db.evaluation_results`, `feedback_results`, `revision_results`; `risk_intelligence_db.contextual_scoring` |

### Domains under test (report §5.1.1–5.1.3)
1. **Student Admission** — International Students Applying to U.S. Colleges (Kaggle)
2. **Retail** — Global Fashion Retail Sales (Kaggle)
3. **Healthcare** — Electronic Health Record / ED Triage & Admission (Kaggle)

---

## 2. Test environment

| Component | Endpoint / location | Notes |
|---|---|---|
| n8n | http://localhost:5678 (Docker `n8n`) | Workflow ID `XUSBdhyaqrZVIXqp` |
| MongoDB Atlas (cluster 0a) | `<clusterA-host>.mongodb.net` | DBs: `local_db`, `telemetry_db`, `risk_intelligence_db` |
| MongoDB Atlas (cluster 0b) | `<clusterB-host>.mongodb.net` | DB: `feedback_and_refinement_db` |
| Fuseki (GraphDB write) | http://localhost:3030/ontology/update | ✅ Up |
| GraphDB Free (read) | http://localhost:7200/repositories/fedxvirtualsparql | ✅ Up |
| Grafana Loki (telemetry) | https://logs-prod-026.grafana.net | External (Grafana Cloud) |
| LLM | Azure OpenAI (per-credential) | 19 model nodes |

### Pre-conditions
- n8n container running.
- Mongo Atlas reachable from n8n.
- Fuseki + GraphDB reachable from n8n.
- Azure OpenAI quota available.
- Workflow `CAPRA Prototype` is **active** (confirmed).
- Source datasets present at file paths expected by `Read EHRdata` / equivalent file nodes.

---

## 3. Test strategy

### 3.1 Layer (unit) tests
For each layer × domain (5 × 3 = 15 test cases), verify:
1. The trigger fires successfully.
2. The agent(s) emit structurally valid output (schema check).
3. The downstream sink (Mongo collection / Fuseki / Kafka topic) receives at least one new document/row.
4. No node returns an `executionError`.

### 3.2 E2E tests
For each domain (3 test cases), trigger ESL and verify that records propagate end-to-end:
`local_raw → telemetry_raw → enriched_telemetry_raw → raw_scenarios → scenario_simulation_results → risk_inference_results → evaluation_results → contextual_scoring`.

### 3.3 Evidence collected per test
- n8n `execution_entity` row (id, status, startedAt, stoppedAt, mode).
- Document count delta per Mongo collection (pre/post).
- Sample output document per layer (1 doc, redacted where sensitive).
- Screen-recording timestamp of trigger click.

---

## 4. Test cases

### 4.1 Layer (unit) tests

> Convention: `LT-<Layer>-<Domain>` — e.g., `LT-ESL-STU`.

#### ESL — External Systems Layer
| ID | Domain | Trigger | Expected behaviour | Pass criteria |
|---|---|---|---|---|
| LT-ESL-STU | Student | `Execute ESL Admission Data` | Reads admissions dataset → Data Interpretation Agent → Telemetry Generator Agent → inserts to `local_db.local_raw` | Execution status = `success`; `local_raw` count increases by ≥1; sample doc has `domain="student_admission"` or equivalent tag |
| LT-ESL-HLT | Healthcare | `Execute ESL EHR Data` | Reads EHR dataset → Data Interpretation Agent1 → Telemetry Generator Agent1 → `local_raw` | as above for `domain="healthcare"` |
| LT-ESL-RET | Retail | `Execute ESL Retail Data` | Reads retail dataset → Data Interpretation Agent2 → Telemetry Generator Agent2 → `local_raw` | as above for `domain="retail"` |

#### DFL — Data Federation Layer
| ID | Domain | Trigger | Expected behaviour | Pass criteria |
|---|---|---|---|---|
| LT-DFL-STU | Student | `Execute DFL` (after LT-ESL-STU) | Normalisation Agent reads recent `local_raw` student docs → writes `telemetry_db.telemetry_raw` → publishes Kafka `context-processing-layer-trigger-topic` | Insert count >0 in `telemetry_raw` with student-tagged docs; Kafka publish node = success |
| LT-DFL-HLT | Healthcare | `Execute DFL` (after LT-ESL-HLT) | as above for healthcare docs | as above |
| LT-DFL-RET | Retail | `Execute DFL` (after LT-ESL-RET) | as above for retail docs | as above |

#### CPL — Context Processing Layer
| ID | Domain | Trigger | Expected behaviour | Pass criteria |
|---|---|---|---|---|
| LT-CPL-STU | Student | `Execute CPL` | Telemetry Collector → Transformation → Ontology & Mapping agents enrich student telemetry → write `enriched_telemetry_raw`, `raw_ontology`, `telemetry_transformation`; push to Fuseki | Inserts in all 3 collections; Fuseki `ontology` graph contains new triples; agents return JSON-LD without parse errors |
| LT-CPL-HLT | Healthcare | `Execute CPL` | as above; ontology should reference health-related classes (e.g., diagnosis, admission) | as above |
| LT-CPL-RET | Retail | `Execute CPL` | as above; ontology should reference retail-related classes (e.g., transaction, customer) | as above |

#### RIL — Risk Intelligence Layer
| ID | Domain | Trigger | Expected behaviour | Pass criteria |
|---|---|---|---|---|
| LT-RIL-STU | Student | `Execute RIL` | Scenario Agent generates scenarios from enriched student telemetry → Simulation Orchestrator routes → Simulation Agents 1/2 → Inference Agent infers risk → writes `raw_scenarios`, `orchestration_agent_scenarios`, `scenario_simulation_results`, `risk_inference_results` | All 4 collections show new docs tagged to student; inference output contains `risk_score`/`risk_label` fields |
| LT-RIL-HLT | Healthcare | `Execute RIL` | as above with healthcare-relevant risk scenarios | as above |
| LT-RIL-RET | Retail | `Execute RIL` | as above with retail-relevant risk scenarios | as above |

#### E&RL — Evaluation & Reporting Layer
| ID | Domain | Trigger | Expected behaviour | Pass criteria |
|---|---|---|---|---|
| LT-ERL-STU | Student | `Execute E&RL` | Evaluation Agent evaluates inference results → Feedback & Revising Agent → Feedback-to-Action Translation; Contextual Risk Scoring produces score; Gmail summary node sends report | `evaluation_results`, `feedback_results`, `contextual_scoring` show new student docs; Gmail node = success |
| LT-ERL-HLT | Healthcare | `Execute E&RL` | as above | as above |
| LT-ERL-RET | Retail | `Execute E&RL` | as above | as above |

### 4.2 E2E tests

> Convention: `E2E-<Domain>`. Strictly sequential per domain to keep attribution clean.

| ID | Domain | Sequence | Pass criteria |
|---|---|---|---|
| E2E-STU | Student | LT-ESL-STU → wait for active executions to settle → LT-DFL-STU → LT-CPL-STU → LT-RIL-STU → LT-ERL-STU | All 5 layer tests pass; at least 1 doc traceable from `local_raw` through to `contextual_scoring` & `feedback_results` for a student record |
| E2E-HLT | Healthcare | analogous | as above for healthcare |
| E2E-RET | Retail | analogous | as above for retail |

### 4.3 Test execution order
```
1. Snapshot baseline counts (script: 03_snapshot_mongo.py)
2. Start screen recording
3. Trigger ESL — Student → wait for executions to finish
4. Trigger DFL → CPL → RIL → E&RL (Student)
5. Repeat 3–4 for Healthcare, then Retail
6. Stop screen recording
7. Snapshot final counts; export sample docs (script: 04_collect_evidence.py)
8. Populate results into `02_DRSM_Evaluation.md` and `Results_Matrix.csv`
```

---

## 5. Risks & assumptions

- **LLM non-determinism** — agent outputs will vary run-to-run. Tests assess *structural* correctness, not exact string matches.
- **Cost/quota** — full E2E across 3 domains exercises 19 Azure OpenAI agents. Budget for ≥30 min runtime + token spend.
- **Shared collections** — collections are shared across domains; tagging by `domain` field (or by `executionId` / `_id` timestamp window) is the reliable way to attribute results. Snapshot counts before each domain run.
- **Kafka / Mongo / Fuseki** must be reachable for the duration of the test.

---

## 6. Deliverables produced by this test suite

| File | Purpose |
|---|---|
| `01_Test_Plan.md` | This document |
| `02_DRSM_Evaluation.md` | DSRM Applicability / Generality / Novelty assessment per domain |
| `03_snapshot_mongo.py` | Helper script: capture pre-run doc counts |
| `04_collect_evidence.py` | Helper script: post-run delta counts + sample docs |
| `Results_Matrix.csv` | Per-test-case pass/fail + counts |
| `Recording_Instructions.md` | macOS screen-recording how-to |
| `recordings/CAPRA_workflow_demo_*.mov` | Screen recording artefact (produced by user) |
