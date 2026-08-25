# CAPRA ICSE Tool Demo Release Checklist

This is a manual, non-destructive runbook for Grace to mint the Zenodo DOI for tag `v1.0-icse-demo`. Do not push, retag, or publish until each verification box is checked.

## 0. Local pre-flight

1. Confirm the checkout is clean except for release-preparation files:
   ```bash
   git -C ~/Projects/capra-prototype status --short
   ```
2. Confirm the expected tag object resolves to commit `022d22dddff8257e40a296048c8608cd5523cc06`:
   ```bash
   git -C ~/Projects/capra-prototype rev-parse v1.0-icse-demo^{commit}
   git -C ~/Projects/capra-prototype tag --verify v1.0-icse-demo || true
   ```
   The current local tag is annotated but not GPG-signed; `no signature found` is acceptable if this is intentional.
3. Generate the release manifest locally:
   ```bash
   cd ~/Projects/capra-prototype
   scripts/verify_release.sh
   scripts/build_release_archive.sh
   ```

## 1. Enable the GitHub-Zenodo repository webhook

1. Open <https://zenodo.org/account/settings/github/>.
2. Sign in with the GitHub account that owns or administers `gracebilliris/capra-prototype`.
3. Find `gracebilliris/capra-prototype` in the repository list.
4. Toggle the repository **ON** for Zenodo archiving.
5. Wait until Zenodo reports the hook as enabled before drafting the GitHub Release.

## 2. Verify `.zenodo.json` metadata renders cleanly

1. Open `.zenodo.json` locally and check that it remains valid JSON:
   ```bash
   cd ~/Projects/capra-prototype
   python3 -m json.tool .zenodo.json >/dev/null
   ```
2. Compare field names with the Zenodo deposition metadata API: <https://developers.zenodo.org/#depositions>.
3. The file already uses the required/expected deposition fields:
   - `title`
   - `description`
   - `creators`
   - `contributors`
   - `keywords`
   - `license`
   - `upload_type`
   - `access_right`
   - `communities`
   - `related_identifiers`
4. Confirm Grace's creator metadata is rendered as:
   - `Billiris, Grace`
   - `University of Technology Sydney`
   - ORCID `0009-0001-3122-9985`

## 3. Draft the GitHub Release

1. Open <https://github.com/gracebilliris/capra-prototype/releases/new>.
2. Choose existing tag: `v1.0-icse-demo`.
3. Release title:
   ```text
   CAPRA prototype v1.0 — ICSE 2027 Tool Demonstration artefact
   ```
4. Paste the following body, also stored in `.github/RELEASE_TEMPLATE.md`:

---

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


---

5. Leave as draft until the local scripts and metadata checks have passed.
6. Publish the GitHub Release only after Zenodo webhook is enabled.

## 4. Confirm Zenodo DOI mint

1. After publishing the GitHub Release, return to <https://zenodo.org/account/settings/github/> or open the new Zenodo upload listed for `gracebilliris/capra-prototype`.
2. Confirm Zenodo has created a deposition for tag `v1.0-icse-demo`.
3. Copy the returned DOI and badge Markdown from Zenodo.
4. Confirm the badge resolves publicly before updating repository metadata.

## 5. README DOI badge update draft

After the DOI is minted, add this Markdown line near the top of `README.md`, replacing the placeholder DOI:

```markdown
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.TODO.svg)](https://doi.org/10.5281/zenodo.TODO)
```

## 6. `CITATION.cff` update draft

Replace the placeholder DOI in `CITATION.cff` with the minted DOI. The intended full YAML is:

```yaml
cff-version: 1.2.0
title: "CAPRA: Context-Aware Privacy Risk Assessment prototype"
message: "If you use this software artefact, please cite it using the metadata from this file."
type: software
authors:
  - family-names: Billiris
    given-names: Grace
    orcid: "https://orcid.org/0009-0001-3122-9985"
    affiliation: "University of Technology Sydney"
repository-code: "https://github.com/gracebilliris/capra-prototype"
url: "https://github.com/gracebilliris/capra-prototype"
license: MIT
version: "1.0-icse-demo"
date-released: "2026-08-25"
doi: "10.5281/zenodo.TODO" # TODO after mint
abstract: >
  CAPRA is an n8n-based prototype of a six-layer Context-Aware Privacy Risk
  Assessment reference architecture for agentic AI systems processing
  personally identifiable information. The artefact includes workflow exports,
  dashboards, per-layer evidence, and reproduction documentation for the ICSE
  Tool Demonstration submission.
keywords:
  - privacy
  - privacy risk assessment
  - context-aware
  - agentic AI
  - multi-agent systems
  - reference architecture
  - n8n
  - reproducibility
preferred-citation:
  type: software
  title: "CAPRA: Context-Aware Privacy Risk Assessment prototype"
  authors:
    - family-names: Billiris
      given-names: Grace
      orcid: "https://orcid.org/0009-0001-3122-9985"
      affiliation: "University of Technology Sydney"
  repository-code: "https://github.com/gracebilliris/capra-prototype"
  license: MIT
  version: "1.0-icse-demo"
  date-released: "2026-08-25"
  doi: "10.5281/zenodo.TODO" # TODO after mint

```

## 7. `.zenodo.json` `related_identifiers` update draft

After the DOI is minted, update `.zenodo.json` so the `related_identifiers` array includes both the GitHub repository and the DOI. Replace the placeholder DOI below:

```json
"related_identifiers": [
  {
    "identifier": "https://github.com/gracebilliris/capra-prototype",
    "relation": "isSupplementTo",
    "scheme": "url"
  },
  {
    "identifier": "10.5281/zenodo.TODO",
    "relation": "isIdenticalTo",
    "scheme": "doi"
  }
]
```

## 8. Post-mint checks

1. Verify DOI badge loads in a browser.
2. Verify the Zenodo record lists the correct authors, ORCID, title, licence, and GitHub source archive.
3. Create a follow-up commit only for DOI metadata updates (`README.md`, `CITATION.cff`, `.zenodo.json`) after Grace reviews the minted DOI.
