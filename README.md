# CAPRA Prototype

**Context-Aware Privacy Risk Assessment (CAPRA)** — an n8n-based prototype of the five-layer reference architecture proposed in Grace Billiris's PhD Candidature Assessments 2 & 3.

CAPRA processes multi-agent telemetry through five layers — **DFL** (Data Federation), **CPL** (Context Processing), **RIL** (Risk Intelligence), **E&RL** (Evaluation & Refinement), **HIL** (Human Interaction) — to surface data-privacy risks in agentic AI systems that handle personally identifiable information (PII).

> ⚠️ **Research prototype.** Intended for reviewers reproducing the PhD evidence. Not production hardened.

---

## Table of contents

1. [Repository layout](#repository-layout)
2. [Architecture at a glance](#architecture-at-a-glance)
3. [Quick start (local, macOS/Linux)](#quick-start-local-macoslinux)
4. [Full setup on another machine](#full-setup-on-another-machine)
5. [Reproducing the Beta iteration evidence](#reproducing-the-beta-iteration-evidence)
6. [Grafana dashboards](#grafana-dashboards)
7. [Troubleshooting](#troubleshooting)
8. [Iteration status](#iteration-status)
9. [Citation and licence](#citation-and-licence)

---

## Repository layout

| Path | Contents |
|---|---|
| `workflows/` | n8n workflow JSON exports. **Import `CAPRA_Prototype_unified_patched.json` first** — it contains the full five-layer pipeline used for the Beta evidence. The per-layer JSONs (`Data Federation Layer.json`, `Context Processing Layer.json`, `Mock External System pushing Telemetry Data.json`, `2026.02.02 (WIP) Risk Intelligence Layer OG.json`) are earlier per-layer exports kept for lineage. |
| `n8n_snippets/` | Code-node snippets used inside the workflow. `RIL_Formatting_for_Grafana_patched.js` is the deterministic severity-mapping formatter; `Extract_Data_for_Graph_DB_patched.js` is the hardened SPARQL sanitiser; `format_risk_for_grafana.js` is the earlier revision retained for lineage. |
| `dashboards/` | Grafana dashboard JSON (`risk_register.json` — CAPRA — Risk Dashboard, uid `capra-risk-register`) plus `install_risk_register_dashboard.js`, a browser-console installer used when a service-account token is not available. |
| `dashboard_screenshots/` | PNGs captured for each of the five layers plus the aggregate view (Beta final state, 15 Jun 2026) and the Risk Dashboard (26 Jul 2026). Sources for Figures 5.1–5.7 in the CA3 report. |
| `test_artefacts/` | Test plan (`01`), populated DSRM evaluation (`02`), evidence helpers (`03`, `04`, `05`, `06`), test-run findings log (`07`), comparative analysis (`08`), results write-up (`09`), Grafana fixes (`10`, `11`, `12`), per-layer reports (`13`–`17`), all-layers report (`18`), DSRM evaluation report (`19`), reproduction guide (`20`), CA3 §5.2 snippet (`21`), results matrix, recording instructions. |
| `docs/` | Supplementary docs (this file plus `docs/SETUP.md` for the long-form setup). |

---

## Architecture at a glance

```
                  Mock Telemetry Source (n8n workflow)
                              │
        ┌─────────────────────┴─────────────────────┐
        │                                           │
    [DFL] Data Federation Layer  ──►  MongoDB (telemetry_raw)
        │
    [CPL] Context Processing Layer  ──►  MongoDB (enriched_telemetry_raw)
        │                             ──►  Apache Jena Fuseki (ontology / SPARQL)
        │
    [RIL] Risk Intelligence Layer  (5 agents: Scenario, Orchestrator, Sim1, Sim2, Inference)
        │                             ──►  MongoDB (risk_inference)
        │                             ──►  Grafana Loki (job=risk_intelligence_layer)
        │
    [E&RL] Evaluation & Refinement Layer
        │                             ──►  MongoDB (evaluation_results)
        │                             ──►  Grafana Loki (job=evaluation_and_refinement_layer)
        │
    [HIL] Human Interaction Layer  (two-stage n8n form)  ──►  reviewer

  Observability: Grafana Cloud — six per-layer dashboards + CAPRA — Risk Dashboard.
```

---

## Quick start (local, macOS/Linux)

**Prerequisites:** Docker Desktop, `git`, an OpenAI-compatible LLM endpoint (Azure OpenAI in the reference build), a MongoDB Atlas free-tier cluster, a free Grafana Cloud stack.

```bash
# 1. Clone
git clone https://github.com/gracebilliris/capra-prototype.git
cd capra-prototype

# 2. Bring up the runtime containers (n8n + Fuseki + Kafka + local Mongo helper)
docker compose -f docs/docker-compose.yml up -d

# 3. Open n8n and import the workflow
open http://localhost:5678
#   Settings → Import from file → workflows/CAPRA_Prototype_unified_patched.json

# 4. Wire external credentials in n8n
#   - MongoDB Atlas connection string  (used by 10 Mongo nodes)
#   - Azure OpenAI endpoint + deployment names for Telemetry/Scenario/Evaluation models
#   - Grafana Loki push credentials (username = numeric user id, password = glc_... token)

# 5. Import the Risk Dashboard into your Grafana Cloud stack
node dashboards/install_risk_register_dashboard.js   # browser-console installer
#   or POST dashboards/risk_register.json to /api/dashboards/db with a glsa_* token
```

Once the workflow is imported, **activate the schedule triggers**. Each layer emits to Loki within 10–30 s.

Full step-by-step (Fuseki bootstrap, Loki datasource, credential mapping, activation via SQL) lives in **`docs/SETUP.md`** and **`test_artefacts/20_Reproduction_Guide.md`**.

---

## Full setup on another machine

See **[`docs/SETUP.md`](docs/SETUP.md)** for a from-scratch guide covering:

1. Provisioning the external services (MongoDB Atlas, Grafana Cloud, Azure OpenAI)
2. Bringing up n8n + Fuseki via Docker Compose
3. Importing the workflow JSON and binding credentials
4. Bootstrapping the Fuseki `ontology` dataset with the shipped seed triples
5. Installing the six per-layer dashboards + the Risk Dashboard
6. Activating the schedule triggers and verifying end-to-end health
7. Running a per-domain test campaign (Student / Healthcare / Retail) with time-window filtering

Total elapsed time on a fresh laptop: **~45–60 minutes** including provisioning the free-tier external accounts.

---

## Reproducing the Beta iteration evidence

For the CA3 report evidence exactly (Figures 5.1–5.7, Table 5.2), follow **`test_artefacts/20_Reproduction_Guide.md`**. It covers:

- Boot order (Fuseki → Mongo → n8n → dashboards)
- The three "always-success" metric-emitter fixes (CPL, HIL, E&RL) — §6
- Rendering dashboards to PNG server-side (no browser needed) — §5.3, including the `capra-risk-register` render command
- Per-layer verification queries — §5.2
- Recovery procedures for the four documented infrastructure incidents — §4

The per-layer test reports (`test_artefacts/13`–`17`) each contain their own reproduction steps, objectives, results and traceability.

---

## Grafana dashboards

| UID | Slug | Purpose | Figure |
|---|---|---|---|
| `dflmain` | `data-federation-layer` | DFL health | Fig 5.1 |
| `cplmain` | `context-processing-layer` | CPL health | Fig 5.2 |
| `grpt7hn` | `risk-intelligence-layer` | RIL health | Fig 5.3 |
| `evalmain` | `evaluation-layer` | E&RL health | Fig 5.4 |
| `hilmain` | `human-interaction-layer` | HIL health | Fig 5.5 |
| `alllayers` | `all-layers-e28094-overview` | Combined | Fig 5.6 |
| `capra-risk-register` | `capra-e28094-risk-dashboard` | Substantive risk output (severity, explanation, risk name) | **Fig 5.7** |

The last dashboard's JSON is version-controlled in `dashboards/risk_register.json`. All queries include `| json | risk != ""` so RIL heartbeats (`status="skipped"`) are hidden.

---

## Troubleshooting

| Symptom | Root cause | Fix |
|---|---|---|
| RIL executions error with `Connect to localhost:3030 refused` | Fuseki container down | `docker start context-processing-layer-prototype-fuseki-1` |
| RIL executions error with `you are over your space quota, using 512 MB` | MongoDB Atlas free tier full | Delete old collections in Atlas or upgrade tier — see `docs/SETUP.md` §7 |
| Dashboard shows only CRITICAL and LOW, no HIGH/MEDIUM | Old stale data from before the integer-severity patch | Narrow time range to post-patch, or clear the `risk_intelligence_layer` Loki stream |
| Dashboard shows `domain=unknown` for all rows | CPL prompt does not propagate a `domain` label to RIL | Use time-window filtering per domain (documented behaviour — see `15_Layer_Report_RIL.md §12`) |
| Workflow "active=1" in DB but doesn't fire | n8n reads active state from `workflow_history`, not `workflow_entity` | Restart the n8n container after any DB edit (`docker restart context-processing-layer-prototype-n8n-1`) |

More detailed diagnostics in `test_artefacts/07_Test_Run_Findings.md`.

---

## Iteration status

| Iteration | Status | Reference |
|---|---|---|
| Alpha | Demonstrated end-to-end across three illustrative scenarios | `test_artefacts/13`–`17_Layer_Report_*.md` |
| Beta  | All five layers ≥ 95% per-layer reliability (combined 98.53%); substantive risk output surfaced in Risk Dashboard (30% CRIT / 49% HIGH / 15% MED / 6% LOW over the reference window) | `test_artefacts/18_AllLayers_Combined_Report.md`, `test_artefacts/07_Test_Run_Findings.md §20` |
| Gamma | Pending; will incorporate industry field survey results | — |

---

## Citation and licence

If you refer to this prototype, please cite the CA3 candidature report:

> Billiris, G. (2026). *Privacy Protection for Agentic AI Systems Processing Personally Identifiable Information* — Candidature Assessment 3 Report, University of Technology Sydney.

This work is released for academic examination. Contact the author (@gracebilliris on GitHub) for other uses.

