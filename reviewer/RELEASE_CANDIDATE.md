# CAPRA ICSE 2027 Tool Demonstration — release candidate

**Prepared:** 2 September 2026
**Status:** engineering record for the submission candidate. It does not
replace `v1.0-icse-demo`, which remains the verified historical tag for the
evidence campaigns reported in the paper.

This file records four things the submission needs: what the candidate is, why
the reviewer route is built the way it is, what the domain-input audit
concluded, and what a clean-environment run actually produced.

---

## 1. Candidate identity

| Property | Value |
|---|---|
| Base commit | `0c5858f` on `main` |
| Working branch | `icse-demo-rc` |
| Historical release, unchanged | `v1.0-icse-demo` at commit `022d22d` |
| Licence | MIT, unchanged |
| Reviewer route | `reviewer/` |
| Source workflow export | `workflows/CAPRA_Prototype_unified_patched.json`, SHA-256 `2179651e0bf3df7044c8b15b2c0caba58b2d3b52b101ba14f8f58fce6a0ed9ee` |
| Derived reviewer workflow | `reviewer/workflows/CAPRA_reviewer_local.json`, regenerated deterministically by `reviewer/scripts/make_reviewer_workflow.py` |
| Ontology seed | `reviewer/ontology/capra_seed.ttl`, SHA-256 `4742562a4377a9d6dbda96688875dc9120b46a205255084f7fcf0a962e97a900` |

### Container images

| Service | Image | Digest |
|---|---|---|
| Orchestration engine | `n8nio/n8n:2.6.4` | pinned by tag; the released compose file pinned `1.108.0` |
| Document store | `mongo:7` | `sha256:340c1c56fb10e95cf79ff547f8664b96bc6ead9909bc355238cbf865a9695a6f` |
| Ontology store | `stain/jena-fuseki:5.0.0` | `sha256:9fb2bfb4a21e7332009d0f19e574e609ed9f3accbe9fae7433c7b4601ed3d7ec` |
| Language model runtime | `ollama/ollama:0.12.3` | `sha256:c622a7adec67cf5bd7fe1802b7e26aa583a955a54e91d132889301f50c3e0bd0` |
| Log store | `grafana/loki:3.1.1` | `sha256:e689cc634841c937de4d7ea6157f17e29cf257d6a320f1c293ab18d46cfea986` |
| Dashboards | `grafana/grafana:11.2.0` | `sha256:408afb9726de5122b00a2576763a8a57a3c86d5b0eff5305bc994ceb3eb96c3f` |

### Model and prompt configuration

| Property | Value |
|---|---|
| Reference build (campaigns) | Azure OpenAI, `gpt-4o` for scenario, simulation, and inference agents; `gpt-4o-mini` for transformation and evaluation agents |
| Reviewer route | Ollama `llama3.2` (3B, 4-bit), served locally |
| Prompts | unchanged from the published export; the transformation touches no `systemMessage`, no code node, and no output parser |
| Determinism | none. Both builds are non-deterministic, and the two models produce different content for the same input |

### Verification host

Docker Engine 29.2.0 with Compose v2 5.0.2, Python 3.9.6, Ollama 0.20.0,
macOS on Apple silicon, 8 CPUs and 8 GB allocated to the Docker virtual
machine.

---

## 2. Reviewer-route decision

### Requirement

The ICSE 2027 Tool Demonstration and Data Showcase call requires the tool to be
publicly available in an easy-to-use form with usage instructions, and requires
that reviewers do not have to build the code.

### What the published route actually required

Running `docs/SETUP.md` end to end demanded three externally provisioned
accounts (a managed MongoDB cluster, a Grafana Cloud stack, and an
OpenAI-compatible model endpoint), manual credential binding across 31 nodes, a
manual Fuseki bootstrap, and per-node re-binding in the n8n editor. Its own
estimate was 45 to 60 minutes and "a few USD". Three further dependencies were
not documented at all and are recorded here because they would each have
stopped a reviewer:

1. Two SPARQL read nodes pointed at a GraphDB repository on
   `host.docker.internal:7200` that the released compose file never provisions
   and the setup guide never mentions.
2. One node polled a Kafka REST proxy on `host.docker.internal:8082`, also
   never provisioned.
3. The released compose file pinned `n8nio/n8n:1.108.0`, but the released
   workflow export uses node type versions that 1.108.0 does not implement
   (`agent` v3, `scheduleTrigger` v1.3, `formTrigger` v2.5, `if` v2.3,
   `gmail` v2.2 — 30 nodes in total). On the pinned image every activation
   attempt fails with `Cannot read properties of undefined (reading
   'execute')`. **The released package could not run its own workflow.**

A further disclosure issue: the released workflow contains a Gmail node with a
hard-coded personal address.

### Options considered

| Option | Assessment |
|---|---|
| Hosted deployment the reviewers share | Rejected. It needs infrastructure that must stay live and credentialed through the review period, exposes an operator account, and gives reviewers no way to inspect the stack. |
| Preconfigured virtual-machine image | Rejected. A multi-gigabyte image is awkward to host, hard to verify, and opaque compared with a compose file the reviewer can read. |
| **No-build Docker route with local services** | **Chosen.** Every dependency becomes a published container image or a locally installed model runtime. No account, no API key, no paid service, no source build. |

### What the chosen route changes, and why

`reviewer/scripts/make_reviewer_workflow.py` derives the reviewer workflow from
the published export by a fixed, auditable transformation and writes a
machine-readable report of every change to
`reviewer/workflows/transformation_report.json`. It makes 71 changes in seven
classes, and no change touches stage logic, prompts, code nodes, or stored
schemas:

| Class | Count | Change |
|---|---:|---|
| `rebound-credential` | 24 | four managed-cluster MongoDB credentials collapse onto one local credential (`mongodb://mongo:27017`, database `capra`) |
| `retargeted-model` | 19 | Azure OpenAI chat-model nodes become Ollama chat-model nodes on a local endpoint |
| `retargeted-endpoint` | 11 | six Grafana Cloud Loki push URLs become the local Loki service; two GraphDB SPARQL reads and three Fuseki updates move to the provisioned Fuseki service |
| `slowed-cadence` | 8 | schedule triggers move from a ten-second cadence to one or five minutes |
| `disabled` | 3 | the unprovisioned Kafka REST poll, plus the two domain triggers not selected for the run |
| `repointed-input` | 3 | domain inputs point at the mounted synthetic fixtures |
| `compat-shim` | 2 | restores the expanded JSON-LD array shape the released code node expects, after the knowledge-store query moved from the unprovisioned GraphDB repository to the provisioned Fuseki dataset |
| `removed` | 1 | the Gmail node, which needed an OAuth account and carried a personal address |

Two further route decisions sit outside the workflow file:

- **n8n image.** Pinned to `2.6.4`, the earliest locally verified image whose
  node type versions cover the export exactly. Verified by comparing every
  `type`/`typeVersion` pair in the export against the image's own
  `types/nodes.json`: 30 unsatisfied pairs on `1.108.0`, zero on `2.6.4`.
- **Knowledge-store access policy.** Fuseki's stock policy restricts SPARQL
  update to the admin account, so the workflow's Graph Importer nodes returned
  `401`. Rather than ship a password for the workflow to use, the route
  installs `reviewer/fuseki/shiro.ini`, which opens query, update, and Graph
  Store Protocol on the local demonstration dataset while keeping the server
  administration endpoints behind the admin account that the bootstrap uses.
- **Language-model host.** Docker Desktop on macOS cannot pass the Apple GPU
  into a container. Measured on the verification host, the containerised model
  produced 0.13 tokens per second against 8.59 from the same model on the host
  runtime, a 66-fold difference. The route therefore supports both and
  `bootstrap.sh --host-ollama` selects the host runtime. Both are
  credential-free; only the container route needs no host install.

### Credential position

After the transformation the workflow references exactly two credential types,
both local and neither secret: a MongoDB connection string to the compose
service, and an Ollama base URL. `reviewer/scripts/bootstrap.sh` generates one
n8n encryption key locally into `reviewer/.env`, which is git-ignored; it
protects only the reviewer's own credential store and is not a shared secret.
No key, token, connection string, account name, or personal address is
committed.

---

## 3. Domain inputs

The three domain files that the campaigns read are third-party datasets holding
person-level records and are not redistributable. The audit, the schemas, and
the synthetic replacements are recorded in `reviewer/fixtures/README.md`. In
summary: the healthcare file's column set matches a critical-care research
corpus distributed under a credentialed data use agreement that prohibits
redistribution; the admissions and retail files carry personal content with no
retained licence. The route therefore ships deterministic synthetic fixtures
with identical schemas, generated by
`reviewer/scripts/gen_synthetic_inputs.py` from seed `20261023`.

This also corrects a description problem: the demonstration narrative called
all three inputs synthetic, but only the telemetry the mock generator emits was
synthetic. The seed records were not.

---

## 4. Clean-environment reproduction

Procedure: remove every named volume, delete `reviewer/.env`, and run only the
published instructions from `reviewer/QUICKSTART.md`.

### Setup

| Step | Command | Result | Elapsed |
|---|---|---|---:|
| Bootstrap from removed volumes, images cached, host model | `./reviewer/scripts/bootstrap.sh --host-ollama --no-pull` | completed; all eight steps reported success | 41.4 s |
| Bootstrap, first attempt with the released n8n pin | same | services started, workflow imported, **activation failed** | 84.8 s |
| Health check | `./reviewer/scripts/verify_route.sh` | 9 of 9 checks `ok` | under 5 s |

Health-check detail on the passing run: n8n `/healthz`, Loki `/ready`, Grafana
`/api/health`, the provisioned Loki datasource under UID `grafanacloud-logs`,
the provisioned `capra-risk-register` dashboard, 78 triples in the Fuseki
`ontology` dataset, a MongoDB ping, the language model reachable from inside
the n8n container, and the workflow present under id `capra-reviewer-local`.

No source build is required at any point. No account is created anywhere except
the reviewer's own local n8n owner sign-up.

### Failures encountered and resolved during verification

| Failure | Cause | Resolution |
|---|---|---|
| `Bind for 0.0.0.0:27018 failed` | default port already held on the verification host | ports moved into `reviewer/.env` as `CAPRA_*_PORT` overrides |
| `Cannot read properties of undefined (reading 'execute')` on every activation | released n8n pin predates the export's node type versions | image pinned to `2.6.4`; coverage verified programmatically |
| Language-model calls taking six to ten minutes each | containerised model on macOS runs CPU-only | host-runtime option added and documented |
| Executions queueing faster than they drained | published ten-second cadence assumes a hosted model | trigger cadence slowed; production concurrency capped at five |
| `There was a problem activating the workflow: "Invalid interval"` | n8n rejects a seconds interval of 60 or more | cadence emitted as a minutes interval |
| Ingestion stage producing no records inside a twelve-minute window | the whole input file becomes one prompt; the original files are too large for a local model | fixtures default to 12 rows, with `--rows` for larger sets |
| Ingestion still producing no records across a 45-minute window | the mock external system asks the model for a large nested JSON document; a small local model does not return one | `reviewer/scripts/seed_telemetry.py` seeds the ingestion collection deterministically, substituting the input simulator only |
| `401` on every knowledge-store write | Fuseki restricts SPARQL update to the admin account | local access policy installed by the bootstrap; no password ships with the workflow |
| `graph.forEach is not a function` in two code nodes | the released code expects GraphDB's expanded JSON-LD array; Fuseki returns compact JSON-LD | `compat-shim` restores the expanded array shape |

### Observation window

See `reviewer/logs/` for the raw run logs. Each log records the domain, the
window bounds, per-collection counts before and after, the delta, the n8n
execution outcomes, and the Loki job labels seen in the window.

<!-- RUN_SUMMARY_START -->
**Verified window.** Domain `admissions`, 2026-09-02 14:21:12Z to 14:51:23Z
(30 minutes), on the fully clean stack bootstrapped 41.4 s earlier, host
language-model runtime, `llama3.2`, twelve seeded synthetic events. Raw log:
`reviewer/logs/run_admissions_20260902T142109Z.json`.

| Stage | Collection | Documents produced in the window |
|---|---|---:|
| mock external system (seeded) | `local_raw` | 12 (pre-seeded, unchanged) |
| federate (DFL) | `telemetry_raw` | 13 |
| contextualise (CPL) | `enriched_telemetry_raw` | 7 |
| contextualise (CPL) | `raw_ontology` | 5 |
| assess (RIL) | `raw_scenarios` | 9 |
| assess (RIL) | `scenario_simulation_results` | 9 |
| assess (RIL) | `orchestration_agent_scenarios` | 9 |
| assess (RIL) | `contextual_scoring` | 4 |
| assess (RIL) | `risk_inference_results` | 8 |
| refine (F&RL) | `evaluation_results` | 4 |
| refine (F&RL) | `feedback_results` | 7 |
| review (HIL) | `revision_results` | 0 |

Log streams reaching the local Loki service in the window:
`data_federation_layer`, `risk_intelligence_layer`,
`evaluation_and_refinement_layer`. The provisioned risk dashboard renders these
records without any further configuration.

Workflow executions in the window: 38 total, 27 success, 6 error, 5 still
running when the window closed.

**What this run does and does not show.**

- It shows that a first-time reviewer can start the package, pass a health
  check, and observe records appearing at the federation, contextualisation,
  assessment, and refinement stages, with no account, no key, and no source
  build.
- The zero at `revision_results` is consistent with the existing not-measurable
  finding for decision persistence and with the released results matrix, where
  the revision path is gated by an acceptance condition. This run neither
  confirms nor contradicts that finding: the human-review form was not
  submitted during this scripted window.
- The six errors and some `status=failed` risk records come from the small local
  model returning output the downstream parsers reject. That is a property of
  the substituted model, not of the packaging, and it is why the route is
  documented as a structural demonstration rather than a reproduction of the
  campaign results.
- Counts from this window are reviewer-route observations. They are separate
  from, and must not be merged with, the three-domain campaigns or the
  common-window campaign reported in the paper.
<!-- RUN_SUMMARY_END -->

---

## 5. What this candidate does not establish

Unchanged from the paper's evidence ceiling, and not weakened or strengthened
by any of the work above:

- No same-event traversal across all stores.
- No durable persistence of a human decision.
- No downstream propagation or applied mitigation.
- No end-to-end latency measure.
- No semantic correctness, privacy effectiveness, usability, or production
  performance claim.

Two limits are specific to this route and must be stated wherever it is
demonstrated:

- The reviewer route substitutes a small local model for the hosted model used
  in the campaigns. It exercises the same stages and the same stored schemas,
  but it does not reproduce the reported campaign results, and its generated
  content differs.
- The ontology seed is a minimal starting graph so that the taxonomy and
  context queries return something on a fresh machine. It is not the
  privacy-risk taxonomy used in the campaigns.

---

## 6. Remaining gates before submission

| Gate | Owner | Status |
|---|---|---|
| Publish the candidate tag and release assets on the public repository | author | outstanding; requires an authenticated push |
| Capture the 180–300 second demonstration video against this route | author | outstanding; requires screen and audio capture |
| Publish the video on YouTube and put its URL at the end of the abstract | author | outstanding; requires a public account action |
| Mint the archival DOI from the waiting deposition | author | outstanding; requires a Publish action |
| Confirm an ORCID for each author | all authors | outstanding |
| Co-author approval of the frozen paper, tool, and video package | all authors | outstanding |
| Recheck the live call and portal, then upload | author | outstanding; the portal reported submissions closed on 2 September 2026 |
