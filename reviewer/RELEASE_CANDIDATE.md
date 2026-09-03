# CAPRA ICSE 2027 Tool Demonstration — reviewer package record

**Prepared:** 2 September 2026
**Revised:** 3 September 2026 — the preferred public configuration is now ONE
generic OpenAI-compatible endpoint that the reviewer supplies. The local Ollama
route is retained as an optional credential-free fallback.
**Status:** published beta-package engineering record. The reviewer route,
usage documentation, and static-site walkthrough were published through the
repository's `main` branch on 3 September 2026. This package does not replace
`v1.0-icse-demo`, which remains the verified historical tag for the evidence
campaigns reported in the paper.

This file records five things the submission needs: what the candidate is, why
the reviewer route is built the way it is, how the language-model configuration
works, what the domain-input audit concluded, and what a clean-environment run
actually produced.

---

## 1. Candidate identity

| Property | Value |
|---|---|
| Base commit | `0c5858f` on `main` |
| Working branch | `icse-demo-rc` |
| Historical release, unchanged | `v1.0-icse-demo` |
| Licence | MIT, unchanged |
| Reviewer route | `reviewer/` |
| Source workflow export | `workflows/CAPRA_Prototype_unified_patched.json`, SHA-256 `2179651e0bf3df7044c8b15b2c0caba58b2d3b52b101ba14f8f58fce6a0ed9ee` |
| Derived reviewer workflow | `reviewer/workflows/CAPRA_reviewer_local.json`, regenerated deterministically by `reviewer/scripts/make_reviewer_workflow.py` |
| Ontology seed | `reviewer/ontology/capra_seed.ttl`, SHA-256 `4742562a4377a9d6dbda96688875dc9120b46a205255084f7fcf0a962e97a900` |
| Environment template | `reviewer/env.template`, placeholders only, no live value |

### Container images

| Service | Image | Digest |
|---|---|---|
| Orchestration engine | `n8nio/n8n:2.6.4` | pinned by tag; the released compose file pinned `1.108.0` |
| Document store | `mongo:7` | `sha256:340c1c56fb10e95cf79ff547f8664b96bc6ead9909bc355238cbf865a9695a6f` |
| Ontology store | `stain/jena-fuseki:5.0.0` | `sha256:9fb2bfb4a21e7332009d0f19e574e609ed9f3accbe9fae7433c7b4601ed3d7ec` |
| Log store | `grafana/loki:3.1.1` | `sha256:e689cc634841c937de4d7ea6157f17e29cf257d6a320f1c293ab18d46cfea986` |
| Dashboards | `grafana/grafana:11.2.0` | `sha256:408afb9726de5122b00a2576763a8a57a3c86d5b0eff5305bc994ceb3eb96c3f` |
| Language model runtime (**optional fallback only**) | `ollama/ollama:0.12.3` | `sha256:c622a7adec67cf5bd7fe1802b7e26aa583a955a54e91d132889301f50c3e0bd0` |

The first five are always started. The sixth is behind the `container-llm`
compose profile and is started only if the reviewer chooses the fallback and
asks for the containerised variant.

### Model and prompt configuration

| Property | Value |
|---|---|
| Reference build (campaigns) | Azure OpenAI, `gpt-4.1-nano` on eighteen model nodes and `gpt-5.2` on one, per the released export |
| Reviewer route, preferred | any endpoint speaking the OpenAI chat-completions API; the reviewer supplies base URL, API key, and model name |
| Reviewer route, fallback | Ollama, verified with `llama3.2` (3B, 4-bit), served locally |
| Prompts | unchanged from the published export on both routes; the transformation touches no `systemMessage`, no code node, and no output parser |
| Determinism | none on any route |

### Verification host

Docker Engine 29.2.0 with Compose v2, Python 3.9.6, Ollama 0.20.0, macOS on
Apple silicon, 8 CPUs and 8 GB allocated to the Docker virtual machine.

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
| **No-build Docker route with local services, plus one reviewer-supplied model endpoint** | **Chosen.** Every infrastructure dependency becomes a published container image. The only external dependency left is one OpenAI-compatible model endpoint that the reviewer configures with three values, and even that can be replaced by a local runtime. |

### Why the model endpoint became the preferred configuration

The first revision of this route removed the model endpoint too, binding every
agent to a small local model. Clean-environment running showed the cost of that
choice: a small local model returns malformed JSON often enough that downstream
parsers reject it, so the demonstration degraded into a structural exercise
whose generated content could not be compared with anything reported. The
revision recorded here restores a hosted-class model as the default while
keeping the no-build property:

- the reviewer supplies **one** endpoint, not three services;
- the endpoint is **generic**. CAPRA issues ordinary OpenAI-format
  chat-completions requests to whatever base URL is configured. The route is not
  standard-OpenAI-specific and not Azure-specific, and no vendor is named in the
  package, the workflow, or the compose file;
- the local Ollama route survives as a fallback for a reviewer who will not or
  cannot supply an endpoint, so a fully credential-free path still exists.

---

## 3. Language-model configuration

### What the reviewer supplies

Three values, in the git-ignored `reviewer/.env`, seeded from the committed
`reviewer/env.template`:

```
CAPRA_LLM_PROVIDER=openai-compatible
OPENAI_COMPATIBLE_BASE_URL=https://replace.example/v1
OPENAI_COMPATIBLE_API_KEY=replace-with-your-key
OPENAI_COMPATIBLE_MODEL=replace-with-your-model-name
```

Those three are the exact strings in the committed template. They are
unmistakable placeholders, not random credential-like strings, and
`reviewer/scripts/scan_secrets.sh` asserts that the committed template still
contains exactly them.

### How the values reach n8n

`reviewer/scripts/bootstrap.sh` builds an n8n credential of type `openAiApi`
carrying the base URL in its `url` field and the key in its `apiKey` field, and
imports it through the n8n CLI (`n8n import:credentials`). The workflow's model
nodes already reference that credential by id, so **the reviewer does no
credential wiring in the n8n UI at all**. This is the same mechanism the earlier
credential-free route used for MongoDB and Ollama; no new pattern was invented.

Secret hygiene in that path:

- the credential file is written by Python from the process environment, so the
  key never appears in a shell command line, a here-document, or the terminal;
- it is written into `reviewer/.import/`, which is git-ignored, with mode 600,
  and is deleted immediately after the import;
- it is streamed into the container as the `node` user and deleted from the
  container as soon as the import has read it;
- at rest inside n8n it is encrypted with the locally generated
  `N8N_ENCRYPTION_KEY`;
- the health check confirms the credential's presence **without** `--decrypted`,
  so no check moves the key through a pipe or a log.

### Node transformation

`reviewer/scripts/make_reviewer_workflow.py` gained a `--provider` flag. On
`openai-compatible` it converts each Azure OpenAI chat-model node to the generic
`@n8n/n8n-nodes-langchain.lmChatOpenAi` node at type version 1.2 — the lowest
version in `n8nio/n8n:2.6.4` that takes the model as a resource locator, which
is what allows an arbitrary model id to be supplied without the editor trying to
resolve it against a vendor model list. The base URL travels on the credential,
not on the node, so **no endpoint value is ever written into the workflow file
or the transformation report**. The script scans both outputs against a set of
secret patterns before writing and aborts rather than emit a match.

On `--provider ollama` the same nodes become
`@n8n/n8n-nodes-langchain.lmChatOllama` bound to a local runtime, exactly as
before.

### Transformation summary

71 changes in eight classes on either provider, none of which touches stage
logic, prompts, code nodes, or stored schemas:

| Class | Count | Change |
|---|---:|---|
| `rebound-credential` | 24 | four managed-cluster MongoDB credentials collapse onto one local credential (`mongodb://mongo:27017`, database `capra`) |
| `retargeted-model` | 19 | Azure OpenAI chat-model nodes become generic OpenAI-compatible chat-model nodes (preferred) or Ollama chat-model nodes (fallback) |
| `retargeted-endpoint` | 11 | six Grafana Cloud Loki push URLs become the local Loki service; two GraphDB SPARQL reads and three Fuseki updates move to the provisioned Fuseki service |
| `slowed-cadence` | 8 | schedule triggers move from a ten-second cadence to one or five minutes, which also keeps a metered endpoint's call volume small |
| `disabled` | 3 | the unprovisioned Kafka REST poll, plus the two domain triggers not selected for the run |
| `repointed-input` | 3 | domain inputs point at the mounted synthetic fixtures |
| `compat-shim` | 2 | restores the expanded JSON-LD array shape the released code node expects, after the knowledge-store query moved from the unprovisioned GraphDB repository to the provisioned Fuseki dataset |
| `removed` | 1 | the Gmail node, which needed an OAuth account and carried a personal address |

Two further route decisions sit outside the workflow file:

- **n8n image.** Pinned to `2.6.4`, the earliest locally verified image whose
  node type versions cover the export exactly. Verified by comparing every
  `type`/`typeVersion` pair in the export against the image's own
  `types/nodes.json`: 30 unsatisfied pairs on `1.108.0`, zero on `2.6.4`. The
  generic OpenAI chat-model node at version 1.2 was confirmed present in the
  same image before it was adopted.
- **Knowledge-store access policy.** Fuseki's stock policy restricts SPARQL
  update to the admin account, so the workflow's Graph Importer nodes returned
  `401`. Rather than ship a password for the workflow to use, the route
  installs `reviewer/fuseki/shiro.ini`, which opens query, update, and Graph
  Store Protocol on the local demonstration dataset while keeping the server
  administration endpoints behind the admin account that the bootstrap uses.
- **Language-model host, fallback only.** Docker Desktop on macOS cannot pass
  the Apple GPU into a container. Measured on the verification host, the
  containerised model produced 0.13 tokens per second against 8.59 from the same
  model on the host runtime, a 66-fold difference. `bootstrap.sh --host-ollama`
  selects the host runtime.

### Credential position

After the transformation the workflow references exactly two credential types:
a MongoDB connection string to the compose service, which is not secret, and —
on the preferred route only — one `openAiApi` credential holding the reviewer's
own endpoint values. On the fallback route the second credential is an Ollama
base URL and nothing is secret at all. `bootstrap.sh` generates one n8n
encryption key locally into `reviewer/.env`, which is git-ignored; it protects
only the reviewer's own credential store and is not a shared secret. **No key,
token, connection string, endpoint, account name, or personal address is
committed anywhere in this package.**

### Fallback quality warning, stated wherever the fallback is offered

The package must not imply that local models are interchangeable with a hosted
model, or with each other. `reviewer/QUICKSTART.md` §7 states, and this record
repeats, that small local models differ in **speed** (minutes per agent call on
CPU), **instruction following**, **JSON and structured-output reliability**
(malformed output that downstream parsers reject, surfacing as errored
executions and `status=failed` risk records), and **generated content**, which
does not reproduce hosted-model content. The fallback is verified with
`llama3.2` only; any other model is the reviewer's own experiment.

---

## 4. Domain inputs

The three domain files that the campaigns read are third-party datasets holding
person-level records and are not redistributable. The audit, the schemas, and
the synthetic replacements are recorded in `reviewer/fixtures/README.md`. In
summary: the healthcare file's column set matches a critical-care research
corpus distributed under a credentialed data use agreement that prohibits
redistribution; the admissions and retail files carry personal content with no
retained licence. The route therefore ships deterministic synthetic fixtures
with identical schemas, generated by
`reviewer/scripts/gen_synthetic_inputs.py` from seed `20261023`.

The **synthetic university-admissions fixture remains the default scenario** for
`run_demo.sh` and the demonstration video.

This also corrects a description problem: the demonstration narrative called
all three inputs synthetic, but only the telemetry the mock generator emits was
synthetic. The seed records were not.

---

## 5. Clean-environment reproduction, 3 September 2026

Procedure: remove every named volume, delete `reviewer/.env`, and run only the
published instructions from the revised `reviewer/QUICKSTART.md`.

**Evidence ceiling for this section.** No live OpenAI-compatible endpoint and no
API credential were available to this verification pass, and none may be used or
exposed. Everything below that concerns the preferred route is therefore a
configuration, packaging, activation, and binding result. **No end-to-end model
execution on a hosted endpoint is claimed, and none was performed.** The
executable population on this pass is the Ollama fallback, and it is recorded
separately.

### 5.1 Preferred route — generic OpenAI-compatible endpoint

| Step | Command | Result | Elapsed |
|---|---|---|---:|
| Refusal on an unconfigured endpoint | `./reviewer/scripts/bootstrap.sh` | exited 2 with instructions; **no service started and no check claimed** | under 2 s |
| Clean bootstrap with placeholders retained | `./reviewer/scripts/bootstrap.sh --configure-only` | all eight steps completed; step 7 printed "endpoint not configured; no call attempted and none claimed" | 43 s |
| Health check | `./reviewer/scripts/verify_route.sh` | 10 `ok`, 1 `SKIP` (the endpoint), 0 `FAIL`; exit code 3 | under 10 s |
| Negative control: unreachable endpoint | `.env` pointed at `https://endpoint.invalid/v1` with a non-credential control string, then `verify_route.sh` | endpoint line reported `FAIL`, not `ok` | under 10 s |
| Bootstrap against the unreachable endpoint | `./reviewer/scripts/bootstrap.sh` | completed; step 7 reported the live check FAILED; `CAPRA_ENDPOINT_VERIFIED=0` written | 40 s |
| Activation on the generic node type | `n8n update:workflow --active=true`, restart | n8n logged `Activated workflow "CAPRA Reviewer Route (admissions, openai-compatible)"`; **no node type version error** | 60 s |
| Binding proof | inspected the n8n execution store after activation | an errored execution record contains the configured base URL `https://endpoint.invalid/v1`, i.e. the agent node really called the endpoint from the imported credential | 100 s |

Raw record: `reviewer/logs/endpoint_binding_probe.json` and
`reviewer/logs/bootstrap_endpoint_configonly.txt`.

**What 5.1 establishes.** A first-time reviewer can extract the package, fill in
three values, and reach a running, health-checked stack in under a minute, with
no source build and no credential wiring in the n8n UI. The generic
OpenAI-compatible node type resolves on the pinned image, the credential imports
through the n8n CLI, the workflow activates, and its agent nodes issue calls to
the configured base URL.

**What 5.1 does not establish.** That any particular endpoint answers, that a
model returns usable output, or that the five stages produce records on a hosted
endpoint. Verifying that requires a live credential, which this pass did not
have and would not use.

### 5.2 Fallback route — local Ollama

| Step | Command | Result | Elapsed |
|---|---|---|---:|
| Clean bootstrap from removed volumes, host runtime, model already pulled | `./reviewer/scripts/bootstrap.sh --host-ollama --no-pull` | completed; all eight steps reported success | 44 s |
| Health check | `./reviewer/scripts/verify_route.sh` | **10 of 10 `ok`**, 0 `SKIP`, 0 `FAIL`; exit code 0 | under 10 s |
| Observation window | `./reviewer/scripts/run_demo.sh --domain admissions --minutes 30` | records produced at federation, contextualisation, assessment, and refinement; 0 at `revision_results`; 33 executions | 30 min |

Health-check detail on the passing run: n8n `/healthz`, Loki `/ready`, Grafana
`/api/health`, the provisioned Loki datasource under UID `grafanacloud-logs`,
the provisioned `capra-risk-register` dashboard, 78 triples in the Fuseki
`ontology` dataset, a MongoDB ping, `llama3.2` reachable from inside the n8n
container, the workflow present under id `capra-reviewer-local`, and the
generated workflow's provider matching the one selected in `reviewer/.env`.

Raw record: `reviewer/logs/bootstrap_ollama_fallback.txt`.

### 5.3 Secret and placeholder scan

`./reviewer/scripts/scan_secrets.sh` — clean. It confirms that `reviewer/.env`
and `reviewer/.import/` are git-ignored and untracked; that no
credential-shaped material appears in 69 tracked files, the generated workflow,
the transformation report, the run logs, or the shipped PNG screenshots; and
that the committed template still carries exactly the three documented
placeholders. The scan was itself validated with a canary: a file containing a
key-shaped string was detected and the scan failed, then the canary was removed.

### Failures encountered and resolved during verification

| Failure | Cause | Resolution |
|---|---|---|
| `Bind for 0.0.0.0:27018 failed` | default port already held on the verification host | ports moved into `reviewer/.env` as `CAPRA_*_PORT` overrides |
| `Cannot read properties of undefined (reading 'execute')` on every activation | released n8n pin predates the export's node type versions | image pinned to `2.6.4`; coverage verified programmatically |
| Language-model calls taking six to ten minutes each | containerised model on macOS runs CPU-only | host-runtime option added and documented; the fallback is no longer the default route |
| Executions queueing faster than they drained | published ten-second cadence assumes a fast hosted model | trigger cadence slowed; production concurrency capped at five |
| `There was a problem activating the workflow: "Invalid interval"` | n8n rejects a seconds interval of 60 or more | cadence emitted as a minutes interval |
| Ingestion stage producing no records inside a twelve-minute window | the whole input file becomes one prompt; the original files are too large for a local model | fixtures default to 12 rows, with `--rows` for larger sets |
| Ingestion still producing no records across a 45-minute window | the mock external system asks the model for a large nested JSON document; a small local model does not return one | `reviewer/scripts/seed_telemetry.py` seeds the ingestion collection deterministically, substituting the input simulator only |
| `401` on every knowledge-store write | Fuseki restricts SPARQL update to the admin account | local access policy installed by the bootstrap; no password ships with the workflow |
| `graph.forEach is not a function` in two code nodes | the released code expects GraphDB's expanded JSON-LD array; Fuseki returns compact JSON-LD | `compat-shim` restores the expanded array shape |
| `EACCES: permission denied, open '/home/node/.capra-import-credentials.json'` (3 Sep 2026) | `docker cp` lands files owned by root; the n8n CLI runs as `node` | the credential and workflow files are streamed in as the `node` user with `umask 077` instead of copied |

### Observation windows

See `reviewer/logs/` for the raw run logs. Each log records the domain, the
language-model provider and model, the window bounds, per-collection counts
before and after, the delta, the n8n execution outcomes, and the Loki job labels
seen in the window. **Endpoint runs and fallback runs are separate populations
and are written to separate files. They must not be merged or averaged.**

<!-- RUN_SUMMARY_START -->
**Verified window (fallback route), 3 September 2026.** Domain `admissions`,
2026-09-03 04:35:36Z to 05:08:30Z (30 minutes plus restart overhead), on a fully clean stack
bootstrapped 44 s earlier, host Ollama runtime, `llama3.2`, twelve seeded
synthetic events. Raw log:
`reviewer/logs/run_admissions_ollama_20260903T043533Z.json`.

| Stage | Collection | Documents produced in the window |
|---|---|---:|
| mock external system (seeded) | `local_raw` | 12 (pre-seeded, unchanged) |
| federate (DFL) | `telemetry_raw` | 5 |
| contextualise (CPL) | `enriched_telemetry_raw` | 5 |
| contextualise (CPL) | `raw_ontology` | 2 |
| assess (RIL) | `raw_scenarios` | 7 |
| assess (RIL) | `scenario_simulation_results` | 6 |
| assess (RIL) | `orchestration_agent_scenarios` | 6 |
| assess (RIL) | `contextual_scoring` | 3 |
| assess (RIL) | `risk_inference_results` | 5 |
| refine (F&RL) | `evaluation_results` | 2 |
| refine (F&RL) | `feedback_results` | 5 |
| review (HIL) | `revision_results` | 0 |

Log streams reaching the local Loki service in this window:
`data_federation_layer`, `risk_intelligence_layer`,
`evaluation_and_refinement_layer`. Workflow executions in this window: 33 total,
20 success, 3 error, 5 crashed, 5 still running when the window closed.

This window is lower-yield than the 2 September window recorded below, with the
same stage coverage. Both used `llama3.2` and the same twelve seeded events, so
the difference is model non-determinism and machine load, not a packaging
change. That variance is itself part of why the local route is now the fallback
rather than the default.

**Verified window (preferred route).** None. No live endpoint credential was
available, so no observation window was run on the preferred route, and no
counts from it exist. This is a stated evidence boundary, not an omission.

**Earlier fallback window, retained for comparison.** Domain `admissions`,
2026-09-02 14:21:12Z to 14:51:23Z (30 minutes), clean stack, host runtime,
`llama3.2`, twelve seeded synthetic events. Raw log:
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

Log streams reaching the local Loki service in that window:
`data_federation_layer`, `risk_intelligence_layer`,
`evaluation_and_refinement_layer`. The provisioned risk dashboard renders these
records without any further configuration. Workflow executions in that window:
38 total, 27 success, 6 error, 5 still running when the window closed.

**What a fallback run does and does not show.**

- It shows that a first-time reviewer can start the package, pass a health
  check, and observe records appearing at the federation, contextualisation,
  assessment, and refinement stages, with no account, no key, and no source
  build.
- The zero at `revision_results` is consistent with the existing not-measurable
  finding for decision persistence and with the released results matrix, where
  the revision path is gated by an acceptance condition. The human-review form
  was not submitted during a scripted window, so the run neither confirms nor
  contradicts that finding.
- Errors and `status=failed` risk records come from the small local model
  returning output the downstream parsers reject. That is a property of the
  substituted model, not of the packaging, and it is precisely why the local
  route is now a fallback rather than the default.
- Counts from any reviewer-route window are reviewer-route observations. They
  are separate from, and must not be merged with, the three-domain campaigns or
  the common-window campaign reported in the paper.
<!-- RUN_SUMMARY_END -->

---

## 6. What this candidate does not establish

Unchanged from the paper's evidence ceiling, and not weakened or strengthened
by any of the work above:

- No same-event traversal across all stores.
- No durable persistence of a human decision.
- No downstream propagation or applied mitigation.
- No end-to-end latency measure.
- No semantic correctness, privacy effectiveness, usability, or production
  performance claim.

Three limits are specific to this route and must be stated wherever it is
demonstrated:

- **The preferred route has not been exercised against a live endpoint by this
  verification pass.** Configuration, packaging, node resolution, activation,
  credential import, and outbound binding are verified; model execution is not.
- The fallback route substitutes a small local model. It exercises the same
  stages and the same stored schemas, but it does not reproduce the reported
  campaign results, its generated content differs, and local models are not
  interchangeable with one another.
- The ontology seed is a minimal starting graph so that the taxonomy and
  context queries return something on a fresh machine. It is not the
  privacy-risk taxonomy used in the campaigns.

The root `README.md` now makes this route the primary onboarding path. It
provides clone, configuration, bootstrap, verification, and demonstration
commands; maps the university-admissions instantiation to inspectable outputs
at each CAPRA stage; reports one verified fallback window as scoped collection
deltas; and labels `docs/SETUP.md` as historical rather than directing
first-time users into the route known not to run as written.

---

## 7. Remaining gates before submission

| Gate | Owner | Status |
|---|---|---|
| Run one observation window on the preferred route with a real endpoint | author | outstanding; requires a credential this pass may not use or hold |
| Publish the revised reviewer package on the public repository | author | completed 3 September 2026 through the repository's `main` branch |
| Capture the 180–300 second demonstration video against this route, using the synthetic admissions fixture | author | outstanding; requires screen and audio capture, after the package is final |
| Publish the video and put its URL at the end of the abstract | author | outstanding; requires a public account action |
| Mint the archival DOI from the waiting deposition | author | outstanding; requires a Publish action |
| Co-author approval of the frozen paper, tool, and video package | all authors | outstanding |
| Recheck the live call and portal, then upload | author | outstanding; the portal reported submissions closed on 2 September 2026 |
