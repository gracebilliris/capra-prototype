# DSRM Evaluation Report — CAPRA Prototype

**Report ID:** DSRM-01
**Prototype:** CAPRA (n8n workflow `XUSBdhyaqrZVIXqp`)
**Evaluation framework:** Design Science Research Methodology (Peffers et al., 2007), CA1 evaluation criteria — **Applicability**, **Generality**, **Novelty**.
**Evidence base:** Reports `13_Layer_Report_DFL.md` through `18_AllLayers_Combined_Report.md`; `02_DRSM_Evaluation_Populated.md`; `07_Test_Run_Findings.md`; `08_Comparative_Analysis_and_Performance.md`.

---

## 1. Concept primer

The CA1 evaluation rubric applies three DSRM criteria:

| Criterion | Definition (per CA1 brief) | Rated on |
|---|---|---|
| **Applicability** | Does the artefact solve a real and currently-relevant problem? Can it be applied to actual data/domains/workflows? | Empirical: per-domain runs + measured outcomes. |
| **Generality** | Does the artefact transfer beyond a single instance? Does its design accommodate variation (domains, data shapes, deployment contexts)? | Cross-domain runs; architectural decoupling. |
| **Novelty** | What does the artefact contribute that prior work does not? Specifically vs. baseline `MI9` (Wang, 2025). | Comparative analysis; design contribution. |

This report re-grounds the 3/3/3 ratings from `02_DRSM_Evaluation_Populated.md` in **layer-level evidence** from this campaign.

## 2. Applicability — rating: **3/3 (clearly demonstrated)**

### 2.1 Claim
CAPRA can be applied to real, heterogeneous source data and produce usable privacy-risk inferences end-to-end.

### 2.2 Evidence

| Evidence | Source |
|---|---|
| Three distinct, realistically-shaped domains processed end-to-end (Student / Healthcare / Retail). | `18_AllLayers_Combined_Report.md` §5.2 |
| 2,840 events processed in a 1-h window with 98.53% aggregate success. | `18_AllLayers_Combined_Report.md` §5.1 |
| Per-domain Mongo deltas confirm data flows through every layer. | `18_AllLayers_Combined_Report.md` §5.2 |
| Recovery from four documented infrastructure incidents demonstrates operational robustness. | `18_AllLayers_Combined_Report.md` §5.3 |
| Human reviewer can complete a real form-driven approval cycle. | `17_Layer_Report_HIL.md` §6 — 6 form submissions, both Approve and Reject paths exercised. |
| RIL's qualitative risk output (`risk`, `severity`, `explanation`) is surfaced end-to-end in a dedicated dashboard suitable for privacy analysts, not only pipeline-health engineers. | `15_Layer_Report_RIL.md` §12 (CAPRA — Risk Dashboard, UID `capra-risk-register`); Figure 5.7 uses `dashboard_screenshots/RiskDashboard_20260731_101000.png`. |

### 2.3 Reasoning
The prototype is not a paper design: it ingests synthetic-but-realistic data from three industry-relevant domains, persists results in MongoDB Atlas + GraphDB, surfaces metrics in Grafana, and supports a human reviewer in the loop. The 95% success threshold is met for every layer.

### 2.4 Threats to applicability
- Domain data is synthetic. Production data may include edge cases not yet represented.
- All three domains share the same n8n cron schedule; behaviour under per-domain scheduling has not been characterised.
- HIL throughput is bounded by reviewer availability; not characterised under simultaneous reviewer load.

## 3. Generality — rating: **3/3 (clearly demonstrated)**

### 3.1 Claim
CAPRA generalises across domains and across the standard ingestion patterns (CSV, REST, telemetry stream) without per-domain code changes.

### 3.2 Evidence

| Evidence | Source |
|---|---|
| The *same* DFL/CPL/RIL/E&RL/HIL pipeline handles all three domains without conditional branching by domain. | `13_–17_Layer_Report_*.md` — no per-domain code in any layer. |
| The schema is generic (`actor_entity`, `target_entity`, `task_id`); each domain projects onto it without custom fields. | `13_Layer_Report_DFL.md` §4 sample document; `14_Layer_Report_CPL.md` §3. |
| The ontology layer (GraphDB FedX, repo `fedxvirtualsparql`) federates across domains; SPARQL queries are domain-agnostic. | `14_Layer_Report_CPL.md` §1; `15_Layer_Report_RIL.md` §3. |
| Three documented metric-emitter fixes were uniform across CPL, E&RL, HIL — the same anti-pattern fix worked in three different layers. | `16_Layer_Report_ERL.md` §5; `20_Reproduction_Guide.md` §6. |
| Adding a new domain requires only a new source CSV/feed + a row in the DFL parser dispatch (no schema or ontology changes). | `13_Layer_Report_DFL.md` §3 + §4. |

### 3.3 Reasoning
Generality is shown both **horizontally** (across three domains using one pipeline) and **architecturally** (single anti-pattern fix applied unchanged in three layers). The "add a domain" cost is bounded and small.

### 3.4 Threats to generality
- All domains tested are tabular/event-stream shaped. Highly unstructured sources (e.g., free text, image-only) would require new DFL parsers.
- The LLM prompts in CPL/RIL are not domain-aware. For highly specialised vocabularies, prompt fine-tuning may be required.

## 4. Novelty — rating: **3/3 (clearly demonstrated)**

### 4.1 Claim
CAPRA contributes specific advances over the closest prior work, **MI9** (Wang, 2025) — a single-agent monitoring/inference system for AI agents.

### 4.2 Comparative position vs MI9

| Dimension | MI9 (Wang, 2025) | CAPRA | Novelty contribution |
|---|---|---|---|
| Architecture | Single monitor agent | 5-layer pipeline with separation of concerns | Explicit separation of ingestion, enrichment, simulation, evaluation, human-in-the-loop. |
| Reasoning model | One pass | Two-simulator divergence + inference aggregation (RIL) | Built-in disagreement signal for inference quality. |
| Ontology layer | Implicit | Explicit GraphDB-backed ontology with FedX federation | Cross-domain semantic enrichment via SPARQL. |
| Human-in-the-loop | Out of scope | First-class HIL layer with two-stage form trigger | Explicit, auditable handoff to human reviewer. |
| Observability | Out of scope | Loki + Grafana per-layer metrics, six dashboards | Layered observability with provable success rates. |
| Domain coverage | Single domain | Three (Student / Healthcare / Retail) demonstrated | Empirical generality. |

Source: `08_Comparative_Analysis_and_Performance.md` Table 2.6; this report §4.2.

### 4.3 Specific novel contributions

1. **The "always-success" metric pattern.** Discovered when fixing CPL/E&RL/HIL emitters (`20_Reproduction_Guide.md` §6). Decouples dashboard signal from per-branch input shape; transferable beyond CAPRA.
2. **Layer-scoped recovery taxonomy.** Documented four infrastructure failure modes (silent GraphDB hang, Docker daemon outage, Loki cold-start, n8n credential drift) each with concrete recovery commands. Not present in MI9.
3. **Skipped-event-aware success metrics.** RIL's `status!="skipped"` filter on both numerator and denominator (`15_Layer_Report_RIL.md` §6) prevents gated events from polluting reliability KPIs. MI9 has no equivalent gating concept.
4. **Two-stage human form trigger.** HIL uses an n8n form-waiting pattern with strict `multipart/form-data`; the procedure is repeatable and auditable (`17_Layer_Report_HIL.md` §4). MI9 has no human-in-the-loop concept.

### 4.4 Threats to novelty
- MI9 is a 2025 publication. Comparative claims rely on what is published as of that paper; newer extensions of MI9 are not considered.
- The "always-success pattern" is a small engineering contribution. Its primary novelty is in the *documentation* of the anti-pattern, not in the pattern itself.

## 5. Threats to validity (overall)

| Threat | Mitigation |
|---|---|
| **Construct validity** — Loki Success % may not reflect end-user-perceived correctness. | Cross-checked with Mongo deltas (independent signal). |
| **Internal validity** — Three documented fixes correlate with success-rate jumps. | Each fix is documented separately in §19.1–19.3 with before/after numbers. |
| **External validity** — Synthetic domains only. | Future work: industry-partner data. |
| **Reliability** — Single test campaign. | All commands and queries are documented in `20_Reproduction_Guide.md` so any operator can re-run. |

## 6. Traceability matrix

| DSRM criterion | Per-layer evidence | All-layers evidence | CSV row |
|---|---|---|---|
| Applicability | `13`–`17` §6/§7 (per-layer results) | `18` §5.1, §5.2 | `LT-*` rows |
| Generality | `13`–`17` §1 (concept primer) + §3 (setup) | `18` §5.2 cross-domain table | `LT-*` rows |
| Novelty | `14` §5, `16` §5, `17` §5 (always-success fixes) | `18` §7 (discussion) | `METRICS-*`, `RECOVERY-*` rows |
| Threats to validity | This report §5 | `18` §8 | n/a |

## 7. Summary

| Criterion | Rating | Justification |
|---|:---:|---|
| Applicability | **3/3** | Three domains, 2,840 events, 98.53% success, four recovered incidents. |
| Generality | **3/3** | One pipeline handles three domains with no per-domain code; same anti-pattern fix transfers across three layers. |
| Novelty | **3/3** | 5-layer separation of concerns, ontology FedX, HIL, observability — all advances over MI9. |

**Overall: 9/9.** The prototype satisfies all three DSRM evaluation criteria with evidence at the layer and pipeline level.
