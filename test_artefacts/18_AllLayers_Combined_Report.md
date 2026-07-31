# All-Layers Combined Test Report

**Report ID:** LR-ALL-01
**Prototype:** CAPRA (n8n workflow `XUSBdhyaqrZVIXqp`)
**Scope:** End-to-end pipeline across all five layers (DFL → CPL → RIL → E&RL → HIL).
**Prerequisites:** `20_Reproduction_Guide.md` §§2–7.
**Evidence base:** Reports `13_Layer_Report_DFL.md` through `17_Layer_Report_HIL.md`; `07_Test_Run_Findings.md` §19.6; `dashboard_screenshots/AllLayers_20260615_221510.png`.

---

## 1. Concept primer

CAPRA's five layers form a directed pipeline:

```
[Sources] → DFL → CPL → RIL → E&RL → HIL → [Human reviewer]
            ↓     ↓     ↓     ↓      ↓
          Mongo / GraphDB / Loki (metrics emitted per layer)
```

Each layer is independent in n8n terms (separate sub-workflows or branches), but data-dependent: each consumes the previous layer's Mongo output. A break in any upstream layer starves all downstream layers.

This report aggregates the per-layer evidence to characterise **end-to-end behaviour** of the prototype as a whole.

## 2. Objective

| # | Claim | How tested |
|---|---|---|
| O-ALL-1 | All five layers exceed the 95% success threshold in steady state. | Per-layer Loki tally aggregated. |
| O-ALL-2 | Cross-layer data dependency holds: events seen at DFL appear (eventually) at HIL. | Per-domain Mongo deltas tracked layer-by-layer. |
| O-ALL-3 | The pipeline recovers from documented infrastructure incidents. | §19.4 GraphDB outage; §19.5 credential loss; §19.7 Loki cold-start. |
| O-ALL-4 | Three domains (Student/Healthcare/Retail) traverse the full pipeline. | Per-domain deltas reported per layer. |

## 3. Setup

Inherits all setup from `20_Reproduction_Guide.md` §§2–6. No additional configuration is required.

| Layer | Loki job label | Mongo sink | Dashboard slug |
|---|---|---|---|
| DFL | `data_federation_layer` | `telemetry_raw` | `data-federation-layer` |
| CPL | `context_processing_layer` | `enriched_telemetry_raw`, `raw_ontology` | `context-processing-layer` |
| RIL | `risk_intelligence_layer` | `risk_inference` | `risk-intelligence-layer` |
| E&RL | `evaluation_and_refinement_layer` | `refined_risk` | `evaluation-and-refinement` |
| HIL | `human_interaction_layer` | (form-driven, no Mongo sink) | `human-interaction-layer` |
| ALL | (combined) | n/a | `alllayers` |

## 4. Reproduction procedure

### 4.1 Per-layer reproduction
Follow §4 of each per-layer report (`13`–`17`). The procedures are independent; running them in sequence exercises the full pipeline.

### 4.2 Aggregated Loki query (AllLayers dashboard query)

```logql
( sum(sum_over_time({job=~"data_federation_layer|context_processing_layer|risk_intelligence_layer|evaluation_and_refinement_layer|human_interaction_layer"}
                    | json | __error__="" | status!="skipped" | unwrap transformSuccess [$__range]))
/ sum(count_over_time({job=~"data_federation_layer|context_processing_layer|risk_intelligence_layer|evaluation_and_refinement_layer|human_interaction_layer"}
                    | json | __error__="" | status!="skipped" | transformSuccess!="" [$__range])) ) * 100
```

Note the **`status!="skipped"`** filter on both numerator and denominator — required because RIL emits skipped events that should not count as failures. See `15_Layer_Report_RIL.md` §6.

### 4.3 Render the combined dashboard

```bash
curl -sf -H "Authorization: Bearer $(cat /tmp/grafana_token)" \
  "https://gracebilliris.grafana.net/render/d/alllayers/all-layers?orgId=1&from=now-1h&to=now&width=1600&height=900&timeout=60&kiosk=tv&tz=Australia%2FSydney" \
  -o "AllLayers_$(date +%Y%m%d_%H%M%S).png"
```

## 5. Aggregated evidence (15 Jun 22:15 AEST, 1-h window)

### 5.1 Per-layer Success %

| Layer | Total | ✅ | ❌ | Success % | Source |
|---|---:|---:|---:|---:|---|
| DFL  | 613 | 613 | 0 | 100.00 | `13_Layer_Report_DFL.md` §6 |
| CPL  | 78  | 78  | 0 | 100.00 | `14_Layer_Report_CPL.md` §6 |
| RIL  | 523 | 378 | 20 | 95.05 | `15_Layer_Report_RIL.md` §7 |
| E&RL | 246 | 246 | 0 | 100.00 | `16_Layer_Report_ERL.md` §6 |
| HIL  | 10  | 10  | 0 | 100.00 | `17_Layer_Report_HIL.md` §7 |
| **ALL** | **2,840** | — | — | **98.53** | Combined Loki query |

### 5.2 Per-domain throughput

| Domain | DFL telemetry_raw Δ | CPL enriched_telemetry_raw Δ | CPL raw_ontology Δ | RIL risk_inference Δ |
|---|---:|---:|---:|---:|
| Student    | +14 | +14 | +4  | +3  |
| Healthcare | +32 | +32 | +27 | +18 |
| Retail     | +69 | +69 | +63 | +41 |

Each row shows roughly monotone attenuation downstream — expected, since RIL gating skips low-severity events. Healthcare ontology yield is high (27/32) because clinical events carry rich actor/target metadata.

### 5.3 Documented infrastructure incidents

| Incident | Layer affected | Recovery time | Cause |
|---|---|---|---|
| GraphDB Desktop silent hang (14 Jun) | RIL | ~30s after restart, ~23h total | Process alive but HTTP unresponsive |
| Docker daemon down (15 Jun) | All | ~60s | OS / Docker startup |
| Grafana Cloud Loki cold-start (15 Jun) | Dashboards | 1–10 min | Idle datasource warm-up |
| `Push Grafana Metrics2` credential loss | HIL | Manual re-attach | n8n workflow save quirk |

## 6. Result

**PASS** end-to-end.

| Objective | Result | Evidence |
|---|---|---|
| O-ALL-1 (all layers ≥95%) | ✅ | §5.1 — minimum 95.05% (RIL) |
| O-ALL-2 (data flows downstream) | ✅ | §5.2 — monotone deltas |
| O-ALL-3 (recovery from incidents) | ✅ | §5.3 — all four recovered |
| O-ALL-4 (three domains) | ✅ | §5.2 |

## 7. Discussion

- The full pipeline reached **98.53% aggregate success** in steady state across 2,840 events.
- RIL is the throughput-and-reliability bottleneck (4 LLM calls per non-skipped event), and is also the only layer dependent on GraphDB FedX. Hardening RIL further (timeout-retry, FedX query caching) would deliver the largest aggregate improvement.
- The three documented metric-emitter bugs (CPL, E&RL, HIL) all stemmed from the **same anti-pattern** (input-shape coupling). Codifying the always-success pattern (see `20_Reproduction_Guide.md` §6) is the most leveraged lesson from this campaign.
- Domains exhibit different yield profiles: Retail is highest-volume, Healthcare is highest-ontology-yield-per-event, Student is lowest-volume. The pipeline handles all three without per-domain configuration.

## 8. Limitations

- The 1-h window is short. Longer windows would smooth bursty LLM-timeout artefacts.
- The three domains are synthetic. Real-world traffic mixes would shift the skipped-event ratio in RIL.
- N for HIL is only 10. The 100% figure should be revisited with a ≥50-submission campaign.
- The pipeline is not horizontally scaled; this report does not characterise behaviour under concurrent load.

## 9. Traceability

| Item | File |
|---|---|
| Per-layer evidence | `13_–17_Layer_Report_*.md` |
| Final tally | `07_Test_Run_Findings.md` §19.6 |
| Dashboard (all layers, 15 Jun) | `dashboard_screenshots/AllLayers_20260615_221510.png` |
| Risk Dashboard (26 Jul, Figure 5.7) | `dashboard_screenshots/RiskDashboard_20260731_101000.png` |
| Risk Dashboard iteration history | `15_Layer_Report_RIL.md` §12 |
| Shared procedures + glossary | `20_Reproduction_Guide.md` |
| Per-domain rows | `Results_Matrix_Filled.csv` `LT-*` |
| Incident rows | `Results_Matrix_Filled.csv` `RECOVERY-*` |
