# CAPRA prototype v1.0 — ICSE 2027 Tool Demonstration artefact

## TL;DR

This release packages the reviewer-facing CAPRA prototype: an n8n-based implementation of the six-layer Context-Aware Privacy Risk Assessment reference architecture for agentic AI systems processing PII. It is intended for ICSE Tool Demo review and reproducibility, not production deployment.

## What's in the release

- **DFL — Data Federation Layer:** normalises multi-source telemetry into a canonical event schema.
- **CPL — Context Processing Layer:** enriches events with contextual metadata and writes/reads the shared knowledge substrate.
- **CL — Context Layer:** materialised as the Apache Jena Fuseki ontology/SPARQL store used by CPL, RIL, and FRL.
- **RIL — Risk Intelligence Layer:** multi-agent risk reasoning that emits risk names, severity bands, and explanations.
- **FRL — Feedback & Refinement Layer:** evaluates outputs, captures patterns, and writes refinement signals back to CL.
- **HIL — Human Interaction Layer:** form-based reviewer approval/correction loop.

## Release contents

- Unified n8n workflow: `workflows/CAPRA_Prototype_unified_patched.json`
- Earlier per-layer workflow exports in `workflows/` for lineage
- Grafana risk-register dashboard: `dashboards/risk_register.json`
- Layer and DSRM reports: `test_artefacts/13_*` through `test_artefacts/20_Reproduction_Guide.md`
- Cross-stage identifier mapping and release metadata
- Public showcase material retained in the repository history

## Changes since `pre-copilot-strip`

- `022d22d` — add authorship, Zenodo metadata, and cross-stage identifier mapping.
- `48bfd7e` — describe CAPRA as six layers, adding CL and renaming E&RL to FRL.
- `0a50ada` — remove orphan generated site landing page and stale Pages workflow.
- `32f6521` — refresh contributor-cache state after repository unarchive.
- `dd22771` — nudge contributor-statistics regeneration for release hygiene.
- `2b3380e` — replace the anonymous-submission footer with a simple repository link.

## Reproduction time

Expected elapsed time on a fresh macOS/Linux laptop is **45–60 minutes**, including free-tier service provisioning. Once external services are provisioned and credentials are entered, the first scheduled workflow tick should emit layer metrics within **10–30 seconds** and substantive risk-dashboard rows within **2–3 minutes**.

## Hardware and service requirements

- macOS or Linux workstation
- Docker Desktop or Docker Engine with Compose
- 8 GB RAM minimum; 16 GB recommended
- `git`, `curl`, `python3`, `node`, and `jq`
- MongoDB Atlas free-tier cluster
- Grafana Cloud free-tier stack with Loki
- Azure OpenAI or compatible OpenAI endpoint for the LLM nodes

## Reproduction guide

Start with [`docs/SETUP.md`](docs/SETUP.md), then follow [`test_artefacts/20_Reproduction_Guide.md`](test_artefacts/20_Reproduction_Guide.md) for boot order, Loki queries, dashboard rendering, and known recovery procedures.

## Licence

MIT. See [`LICENSE`](LICENSE) if present in this checkout and the repository metadata for the release licence.

## Citation

Please cite Grace Billiris's CAPRA prototype artefact. A `CITATION.cff` file is included in this release; update the DOI field after Zenodo mints the release DOI.

```bibtex
@software{billiris_capra_2026,
  author = {Billiris, Grace},
  title = {CAPRA: Context-Aware Privacy Risk Assessment prototype},
  year = {2026},
  url = {https://github.com/gracebilliris/capra-prototype},
  note = {ICSE 2027 Tool Demonstration artefact}
}
```

## Known non-issues

- Docker containers are stopped by default in the archived source tree. This is expected: reviewers start them with `docker compose -f docs/docker-compose.yml up -d`.
- Imported n8n workflows show missing credentials until the reviewer creates local MongoDB, Grafana Loki, and Azure OpenAI credentials.
- The first Grafana Cloud Loki query can return a temporary loading response after idle free-tier suspension; wait and retry.
- Domain labels can appear as `unknown` in downstream risk rows; per-domain evidence is isolated by time-window filtering as documented.
