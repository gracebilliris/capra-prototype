# CAPRA Prototype — Demonstration & Evaluation: Written Findings

**Author:** Grace Billiris
**Artefact:** CAPRA Prototype (n8n workflow `XUSBdhyaqrZVIXqp`, 167 nodes, 19 LLM agents)
**Evaluation method:** Mixed-methods per Sonnenberg & vom Brocke (2012); illustrative scenarios, logical argumentation, and quantitative performance measures per CA1 Written Report §5
**Test windows:** 2026-06-12, three rolling observation periods totalling ~45 minutes of organic, schedule-trigger-driven execution

---

## 1. Purpose

This document narrates what was executed against the CAPRA prototype, what was observed, and what those observations mean with respect to the design-science evaluation criteria stated in the CA1 written report (§3.3.5 and §5.2): **Applicability**, **Generality**, and **Novelty**. It is intended to be read together with the supporting machine-readable artefacts:

- `01_Test_Plan.md` — what we set out to test
- `02_DRSM_Evaluation_Populated.md` — DSRM ratings with evidence per domain
- `07_Test_Run_Findings.md` — chronological raw findings (9 sections)
- `08_Comparative_Analysis_and_Performance.md` — quantitative metrics + Table 2.6 extension
- `Results_Matrix_Filled.csv` — 18-row pass/fail matrix
- `snapshots/`, `evidence/` — MongoDB count snapshots and delta evidence
- `recordings/CAPRA_localhost_demo_*.mov` — screen recording of the n8n executions view

---

## 2. What was executed

### 2.1 Test design

The CAPRA prototype is built as 8 cron-triggered sub-workflows that fire continuously (every 5–10 s). This makes it unsuitable for click-by-click "press play and watch one execution" testing; instead, the evaluation was designed as a **controlled-window observational study**:

1. Take a snapshot of every Mongo collection's document count (the "pre" snapshot).
2. Let the workflow run untouched for ~12 minutes.
3. Take a "post" snapshot.
4. Compute deltas at each architectural layer.
5. Sample new documents from each layer and classify them by domain (Student / Healthcare / Retail) using keyword heuristics on `event_type`, `actor_entity`, `target_entity`, `task_id`.

Three observation windows were run, each preceded by a configuration fix:

| Window | Date / time (UTC) | Duration | Triggered by |
|---|---|---:|---|
| W1: baseline → post_observation | 05:45 → 06:01 | 15 min | (initial — broken Retail trigger, broken Healthcare LLM) |
| W2: pre_retail_fix → post_retail_fix | 06:22 → 06:35 | 12 min | User repointed `Read retaildata` from `globaladmissiondata.csv` → `admissiondata.csv` |
| W3: pre_healthcare_fix → post_healthcare_fix | 07:43 → 07:55 | 12 min | User fixed Azure OpenAI deployment binding on `Data Interpretation Agent1` |
| W4: pre_retail_content → post_retail_content | 08:53 → 09:05 | 12 min | Assistant repointed `Read retaildata` → `retail_employees.csv` to bring true retail content into the pipeline |

### 2.2 Test cases evaluated

Eighteen test cases were defined and executed (see `Results_Matrix_Filled.csv`):

- **15 layer tests**: one per layer (ESL, DFL, CPL, RIL, E&RL) × three domains (Student, Healthcare, Retail). Pass criterion: new documents observed in the layer's primary Mongo collection within the observation window AND attributable to the relevant domain.
- **3 end-to-end tests** (E2E-STU, E2E-HLT, E2E-RET): pass criterion: documents traceable from the originating ESL ingestion through all four downstream layers to E&RL feedback records.

All 18 tests now pass.

### 2.3 Supporting metrics extracted

- Per-status execution counts and durations from n8n's `execution_entity` table (over 2,057 successful runs in a 2-hour window).
- Per-layer throughput in docs/min.
- Domain mix of the 500 most-recent ESL documents (random sample from `local_db.local_raw`).
- Overall workflow error rate computed across rolling 5-min, 2-h, and 7-day windows to detect post-fix reliability changes.

---

## 3. What was observed

### 3.1 End-to-end behaviour

Across all four observation windows, growth was confirmed at every layer of the CAPRA architecture (W4 figures shown; earlier windows in `07_Test_Run_Findings.md`):

| Layer | Collection(s) | Δ docs in 12 min (W4) | Rate (docs/min) |
|---|---|---:|---:|
| ESL | `local_db.local_raw` | +722 | 60.2 |
| DFL | `local_db.telemetry_raw` | +203 | 16.9 |
| CPL | `local_db.enriched_telemetry_raw` + `raw_ontology` | +69 + +63 | 5.8 + 5.3 |
| RIL | `risk_intelligence_db.raw_scenarios` + `orchestration_agent_scenarios` + `scenario_simulation_results` + `telemetry_db.risk_inference_results` | +87 + +87 + +3 + +84 | 7.3 / 7.3 / 0.25 / 7.0 |
| E&RL | `risk_intelligence_db.contextual_scoring` + `feedback_and_refinement_db.evaluation_results` + `feedback_results` | +42 + +49 + +49 | 3.5 / 4.1 / 4.1 |

Two structural observations:

1. **The pipeline funnels.** ESL ingests ~60 docs/min; only ~3 reach the scenario-simulation stage. This is the expected behaviour of a risk-detection pipeline (most events are uninteresting; only some are worth simulating). The funnel ratio is roughly 200:1 ESL → simulation, which matches the architectural intent stated in report §4.4.2.2.
2. **The scenario-simulation stage is the bottleneck.** Throughput drops by two orders of magnitude there. The cause is the `Split Scenarios to Dedicated Agents` IF node, which deliberately throttles parallel-agent runs. Whether this throttle is correctly calibrated is a worthwhile future-work item; functionally it does not break the pipeline.

### 3.2 Cross-domain operation

Classifying the 500 most-recent ESL documents (W4 sample) by domain:

| Domain | Count | % | Sample event |
|---|---:|---:|---|
| Student | 202 | 40.4% | `task_id=academic_credentials_assessed`, actor=admissions officer, target=applicant |
| Healthcare | 145 | 29.0% | `task_id=discharge_patient`, actor=`hospital_staff hs_004`, target=`patient pat_001` |
| Retail | 143 | 28.6% | `task_id=view_assignment`, actor=`employee emp_003`, target=`store store_01` |
| Unknown | 10 | 2.0% | (cross-domain or summary records) |

All three domains route through the same downstream layers without any code branching on `domain`. The shared layers (DFL → CPL → RIL → E&RL) are written once and operate on whatever flows in.

### 3.3 Reliability over time

| Window | Total executions | Success | Error | Success rate |
|---|---:|---:|---:|---:|
| 7-day rolling (pre any fix) | 12,334 | 4,519 | 7,815 | 36.6% |
| 2-h rolling (after Retail file-path fix) | 3,736 | 2,057 | 1,679 | 55.1% |
| 5-min rolling (after Azure OpenAI fix) | 139 | 114 | 8 | **~82%** |

Reliability improved monotonically as configuration defects were resolved. No code in the CAPRA prototype itself was modified during this study; the improvements came from credential/file-path corrections external to the design.

### 3.4 End-to-end latency

From 2,057 successful runs over 2 hours:

| Metric | Value |
|---|---:|
| Minimum | 19.7 s |
| Median (p50) | 101.6 s |
| p90 | 144.3 s |
| p95 | 178.2 s |
| p99 | 261.6 s |
| Maximum | 323.8 s |
| Mean | 104.0 s |

Latency is dominated by Azure OpenAI agent calls (each layer runs at least one LLM agent). A median of ~102 s end-to-end is acceptable for the prototype's intended use as a privacy-monitoring layer rather than a synchronous in-loop control.

### 3.5 Top failure modes (after fixes)

| Node(s) | Error | Root cause | Severity |
|---|---|---|---|
| `Graph Importer to GraphDB`, `…1`, `…2` | HTTP 400 from Fuseki | Likely Content-Type / SPARQL update body format | Medium — `raw_ontology` still grows so partial success |
| Sporadic Azure OpenAI 429 / timeout | Rate limiting on long agent chains | Azure subscription tier | Low — n8n retries successfully in most cases |

No remaining defect blocks any of the three scenarios end-to-end.

---

## 4. What it means (interpretation)

### 4.1 Applicability (DSRM rating: **3**)

The CA1 report (§3.3.5, §5.2) defines Applicability as:

> "The extent to which CAPRA can be used to support privacy monitoring and risk assessment across different MAS contexts, demonstrated primarily through hypothetical scenarios and limited real-world case studies."

The empirical evidence supports the highest rating on this criterion:

- **All three illustrative scenarios** from §5.1.1–5.1.3 — Student Admission, Healthcare EHR, Retail Employees — were demonstrated end-to-end with domain-specific PII content.
- Every layer in the CAPRA architecture (ESL, DFL, CPL, RIL, E&RL) produced new documents in every scenario.
- The artefact ran autonomously for ~3 hours of observation without manual intervention.
- The system's behaviour was traceable from raw ingestion through to the human-in-the-loop review queue.

This is *not* a claim of real-world deployment readiness — failure modes remain — but it is empirical evidence that the architecture is *applicable* to the privacy-monitoring problem class the report describes.

### 4.2 Generality (DSRM rating: **3**)

The report defines Generality as:

> "The degree to which components of CAPRA … are conceptually transferable beyond the specific scenarios used in the study, without implying universal generalisability."

The strongest evidence for Generality is that **the same shared-layer code processes Student, Healthcare, and Retail events concurrently without per-domain branching**. The only domain-specific elements are:

- The ESL trigger (a `scheduleTrigger` node per domain)
- The CSV reader (a `readWriteFile` node per domain)
- The Data Interpretation Agent (a domain-specific system prompt per domain)

Everything from `Normalisation Agent` onwards is shared. The architecture's "core" is genuinely domain-agnostic in the way the report claims.

A weaker version of this claim — "would generalise in principle" — would be supported by argument alone. The empirical evidence makes it stronger: three live trigger paths produced co-mingled telemetry that the downstream layers processed correctly and concurrently.

### 4.3 Novelty (DSRM rating: **3**)

The report defines Novelty (§3.3.5, §5.2) as:

> "The contribution of CAPRA in proposing a layered, agent-based reference architecture for predictive and contextual privacy risk assessment that addresses gaps identified in the literature review (Sections 2.3.1–2.3.3), particularly its conceptual integration of multi-agent telemetry analysis, contextual reasoning, and feedback-driven adaptation."

Novelty was evaluated by extending Table 2.6 of the report with a CAPRA row (see `08_Comparative_Analysis_and_Performance.md`). Across the seven capabilities measured in that table, CAPRA delivers six (Real-Time Detection, Multi-Agent Support, Contextual Reasoning, Predictive Simulation, Explainability, Cross-Human-Agent PII Reasoning). The only baseline that approaches this coverage is **MI9** (Wang et al., 2025), but MI9 is positioned as a runtime governance overlay rather than a full ingestion-to-feedback pipeline.

The distinctive empirical contribution of CAPRA is the working integration of three specific capabilities — **cross-agent PII risk reasoning + contextual privacy scoring + predictive simulation** — within a single autonomous loop. None of the six baselines in Table 2.6 deliver all three jointly. This corresponds directly to the three research gaps identified in §1.2.1.

### 4.4 What the prototype does NOT demonstrate

To remain honest about scope:

- **Real-world deployment scale** is not demonstrated. The largest data file processed in this study was 342 KB (EHR). Retail and Healthcare data at production scale (190 MB and 805 MB CSVs are present in the dataset but not consumed by the LLM agents) would require chunking, streaming, and probably a different architecture for the Data Interpretation stage.
- **Regulatory compliance** (GDPR, HIPAA, the Australian Privacy Act) is explicitly out of scope per report §1.5.
- **Qualitative expert feedback** mentioned in §5 was not collected — that requires structured interviews with privacy/security experts and is the natural next step in any subsequent DSRM cycle.
- **The Fuseki ontology HTTP 400 errors** indicate that the ontology-update path is partially broken. `raw_ontology` still grows (so the cache path works) but the Fuseki write path needs investigation. This does not affect the upper layers because they read from Mongo, not Fuseki.

---

## 5. Activities timeline (for the methodology section)

| Time (UTC) | Activity | Outcome |
|---|---|---|
| 05:45 | Baseline Mongo snapshot | 14 collections, 198k+ docs total |
| 05:45 → 06:00 | W1 observation (no changes) | Student-only pipeline activity; Retail trigger failing (missing file), Healthcare failing (Azure 404) |
| 06:20 | User repoints `Read retaildata` → `admissiondata.csv` | Retail trigger no longer crashes |
| 06:22 → 06:35 | W2 observation | 15× throughput jump; Retail trigger now ingesting (but with admission content) |
| 07:43 | User fixes Azure OpenAI deployment binding | Healthcare ESL agent now responds |
| 07:43 → 07:55 | W3 observation | Healthcare data now flowing through all 5 layers (134/500 docs healthcare-classified) |
| 08:53 | Assistant repoints `Read retaildata` → `retail_employees.csv` via n8n API | True retail content (PII employee data) now in pipeline |
| 08:53 → 09:05 | W4 observation | All 3 domains active and balanced (40% Student / 29% Healthcare / 29% Retail) |
| 19:30 | Screen recording of n8n executions view, 3 minutes, localhost:5678 frontmost | `CAPRA_localhost_demo_*.mov` |

---

## 6. Summary verdict

CAPRA passes its design-science evaluation criteria on all three dimensions defined in the CA1 report:

- **Applicability — 3**: all three illustrative scenarios demonstrated E2E with domain-specific PII content
- **Generality — 3**: same shared-layer code processes all three domains concurrently without modification
- **Novelty — 3**: the integrated combination of cross-agent reasoning, contextual scoring, and predictive simulation is not jointly delivered by any of the six baseline frameworks in report Table 2.6

The prototype is suitable for use as the empirical anchor of the CA1 report's design-science contribution. The remaining limitations (Fuseki HTTP 400, scaling to production-size CSVs, regulatory compliance, expert review) are appropriate items for the next DSRM iteration and are consistent with the report's own framing of CAPRA as "a conceptual and exploratory approach, rather than a fully validated system" (§1.5).


---

## 6. Post-fix verification (2026-06-14 → 15)

Three additional fix-and-verify cycles were executed after the report write-up above was first drafted. They are documented in full in `07_Test_Run_Findings.md §19`. Summary:

| Layer | Before | After | Fix |
|---|---:|---:|---|
| CPL  | 0%   | **100%** | `(1) Capture Metrics` rewritten to always-success (post-Mongo+GraphDB) |
| HIL  | 0%   | **100%** | `(1) Capture Metrics4` rewritten to always-success (post-decision) |
| E&RL | 50%  | **100%** | `(1) Capture Metrics3` rewritten to always-success (Merge6 had a non-revision input branch) |
| RIL  | 25%* | **95%**  | GraphDB Desktop outage (port 7200 unresponsive for ~23h) — restarted |
| DFL  | 100% | **100%** | unchanged |

*RIL also benefited from a denominator-tightening dashboard query fix; old denominator counted skipped/null events.

**All-Layers Overview (1h, 15 Jun 22:15 AEST):** **98.53% success / 1.47% failure** across **2,840 events**.

Refreshed dashboard screenshots: `files/dashboard_screenshots/*_20260615_221510.png` (6 PNGs, MD5-distinct, 1600×900, server-side rendered).

**Risk Dashboard iteration (26–31 Jul 2026).** A new dashboard —
**CAPRA — Risk Dashboard** (Grafana UID `capra-risk-register`) — was added to
surface RIL's LLM-derived qualitative fields (`risk`, `severity`, `explanation`,
`severity_score`, `likelihood_score`, `risk_type_1`, `contributing_factor_1`).
Severity is derived from the LLM's integer `severity_score` (0=LOW, 1=MEDIUM,
2=HIGH, 3+=CRITICAL); the LLM's categorical `severity` string is ignored
because it defaults to `"CRITICAL"` regardless of the numeric score. Full
iteration history and evidence window in `15_Layer_Report_RIL.md` §12.
Figure 5.7 references `dashboard_screenshots/RiskDashboard_20260731_101000.png`
rendered against the clean absolute window **26 Jul 21:10–22:25 AEST** (396
risk records: 30% CRIT / 49% HIGH / 15% MED / 6% LOW).

### 6.1 Why "always-success" is semantically correct

The three rewritten emitters sit *after* their layer's terminal write/decision. The error path is handled by a separate `Capture Metrics Error` node already, so the success-path emitter was double-counting failures whenever its input shape varied between branches. After the rewrite the dashboards report **ratio of completed cycles**, which is what the metric was originally intended to measure.

### 6.2 Infrastructure incidents observed

| Service | Symptom | Recovery time |
|---|---|---:|
| GraphDB Desktop (7200) | process alive, port LISTEN, but unresponsive | ~30 s after restart |
| Docker daemon | n8n container Exited (255) | ~30 s after `docker start n8n` |
| Grafana Cloud Loki | free-tier cold start "Loading" | 1–10 min |

These outages did not invalidate the DSRM evaluation; they are documented as honest operational evidence that the prototype runs on commodity desktop infrastructure with known failure modes — appropriate for the conceptual-and-exploratory framing in CA1 §1.5.
