# CAPRA reviewer quick start

This is the route to use if you are reviewing the CAPRA tool demonstration. It
builds nothing from source: every component is a published container image, and
the whole stack comes up with one command.

You choose how the workflow's agents reach a language model:

| | Route | What you supply | Use it when |
|---|---|---|---|
| **A** | **Generic OpenAI-compatible endpoint (preferred)** | a base URL, an API key, and a model name, from any endpoint that speaks the OpenAI chat-completions API | you want the demonstration to behave like the reported build |
| B | Local Ollama fallback | nothing — no account, no key, no cost | you cannot or would rather not supply an endpoint |

Route A is **not** tied to any particular provider. CAPRA sends ordinary
OpenAI-format chat-completions requests to whatever base URL you give it. A
first-party service, a gateway, an aggregator, a self-hosted server, or a
model-serving framework all work the same way. Nothing in this package names a
vendor, ships an endpoint, or contains a key.

Route B is retained so that the package can still be exercised end to end with
no credential at all. Read the warning in section 7 before drawing any
conclusion from what it produces.

The reference stack in `docs/SETUP.md` is retained for the original evidence
campaigns. It requires three externally provisioned services and is **not** the
review route.

---

## 0. What you need

| Requirement | Version used for verification | Check |
|---|---|---|
| Docker Engine with Compose v2 | 29.2.0 | `docker compose version` |
| n8n image | `n8nio/n8n:2.6.4` (pulled automatically) | the release's own `1.108.0` pin cannot load the workflow's node versions |
| Python 3 | 3.9 or newer | `python3 --version` |
| `curl` | any | `curl --version` |
| Disk | about 4 GB for images, plus about 2 GB more if you use route B | |
| Memory | give Docker at least 6 GB | |

**Route A** additionally needs one OpenAI-compatible endpoint you can reach,
with a key and a model name. Any chat model that follows instructions and can
return JSON is suitable; the workflow's agents ask for structured output at
several stages.

**Route B** additionally needs [Ollama](https://ollama.com). On macOS install it
natively rather than using the container: Docker Desktop cannot pass the Apple
GPU through to a container, so the containerised model runs on the virtual
machine's CPUs and is impractically slow (0.13 tokens per second against 8.59
for the same model on the host runtime, measured on the verification host).

---

## 1. Get the package

```bash
git clone https://github.com/gracebilliris/capra-prototype.git
cd capra-prototype
```

An archive extraction works equally well; nothing in the route depends on Git
history.

## 2. Configure the language model

Create your local environment file from the committed template and edit it:

```bash
cp reviewer/env.template reviewer/.env
$EDITOR reviewer/.env
```

`reviewer/.env` is git-ignored. It is the only place your endpoint values are
stored, and the bootstrap copies them into your own local n8n credential store
and nowhere else.

**Route A.** Replace all three placeholders:

```
CAPRA_LLM_PROVIDER=openai-compatible
OPENAI_COMPATIBLE_BASE_URL=https://replace.example/v1
OPENAI_COMPATIBLE_API_KEY=replace-with-your-key
OPENAI_COMPATIBLE_MODEL=replace-with-your-model-name
```

The base URL is whatever your endpoint documents as its OpenAI-compatible root,
usually ending in `/v1`. The model name is whatever that endpoint calls the
model you want. The bootstrap refuses to proceed while any of the three still
reads as a placeholder, and it never reports the endpoint as working unless a
live call to it succeeded.

**Route B.** Set the provider instead, and leave the endpoint placeholders
alone:

```
CAPRA_LLM_PROVIDER=ollama
CAPRA_OLLAMA_MODEL=llama3.2
```

If you skip this step entirely, the bootstrap creates `reviewer/.env` from the
template on first run and then tells you what to fill in.

## 3. Start everything

Route A:

```bash
./reviewer/scripts/bootstrap.sh
```

Route B, using a natively installed Ollama (recommended on macOS):

```bash
ollama serve &                      # skip if Ollama already runs as a service
ollama pull llama3.2
./reviewer/scripts/bootstrap.sh --host-ollama
```

Route B, fully containerised (Linux, or if you are willing to wait):

```bash
./reviewer/scripts/bootstrap.sh --container-ollama
```

If you want to inspect the packaging before deciding on an endpoint, run
`./reviewer/scripts/bootstrap.sh --configure-only`. The stack starts with the
placeholders still in place, every local service is provisioned and checkable,
and the script states plainly that no model call can succeed.

The script is idempotent; re-running it is safe. It performs eight steps and
prints a heading for each one:

1. checks Docker, Compose, Python, and curl
2. creates or updates `reviewer/.env` from `reviewer/env.template` and
   generates a local n8n encryption key (git-ignored; it protects only your own
   credential store)
3. regenerates the three synthetic domain input files
4. derives the reviewer workflow from the published export, bound to the
   provider you selected
5. starts n8n, MongoDB, Fuseki, Loki, and Grafana — plus Ollama only on route B
   with `--container-ollama`
6. waits for each service to answer its health endpoint
7. creates and seeds the Fuseki `ontology` dataset
8. checks language-model access, then imports the workflow and its credentials

**Expected checkpoint.** The script ends by printing five URLs and one
language-model line that states exactly what was and was not verified.

## 4. Confirm the stack is healthy

```bash
./reviewer/scripts/verify_route.sh
```

Each line reports one of three statuses, and a `SKIP` is never counted as a
pass:

| Status | Meaning |
|---|---|
| `ok` | the check ran and passed |
| `FAIL` | the check ran and failed |
| `SKIP` | the check could not run; nothing is claimed either way |

The check covers the n8n health endpoint, Loki readiness, the Grafana health
endpoint, the provisioned Grafana datasource and dashboard, the Fuseki triple
count, a MongoDB ping, the language-model binding, and the imported workflow.
On route A it also confirms that the credential was imported and that the
workflow was built for the provider your `.env` selects.

If you configured an endpoint, the language-model line performs a live
`GET <base URL>/models` **from inside the n8n container**, so it proves the
container can reach your endpoint rather than only your host. Some
OpenAI-compatible servers do not implement `/models`; if yours does not, that
line will read `FAIL` while the rest of the stack is fine, and the first agent
execution is then the real test.

## 5. Open the interfaces

| Interface | URL | First-run note |
|---|---|---|
| n8n editor | <http://localhost:5679> | Complete the local owner sign-up. Any email and password work; they are stored only in your local container. |
| Risk dashboard | <http://localhost:3002/d/capra-risk-register> | Anonymous access is enabled; no login. |
| Fuseki | <http://localhost:3031> | Dataset `ontology`. |
| Loki | <http://localhost:3101> | Queried through Grafana. |

In the n8n editor, open **CAPRA Reviewer Route (admissions,
openai-compatible)** — or `(admissions, ollama)` on route B. The five stages
appear as branches of a single workflow: federate (DFL), contextualise (CPL),
assess (RIL), refine (F&RL), and review (HIL).

You do not need to create or bind any credential in the n8n UI. The bootstrap
imports both credentials through the n8n CLI and the workflow already
references them by id.

## 6. Run one domain observation window

```bash
./reviewer/scripts/run_demo.sh --domain admissions --minutes 30
```

The synthetic university-admissions fixture is the default scenario and the one
the demonstration video uses. The script re-imports the workflow with only that
domain's ingestion trigger enabled, seeds twelve synthetic agent events,
activates the workflow, waits, deactivates it, and writes a run log to
`reviewer/logs/run_<domain>_<provider>_<timestamp>.json` containing the document
count before and after, the per-collection delta, the n8n execution outcomes,
the Loki job labels seen in the window, and which provider was bound.

Runs made against an endpoint and runs made against the Ollama fallback are
written to separate files and are separate populations. Do not average them.

### Why the run seeds events

In the published workflow the *mock external system* that stands in for a
deployed multi-agent application is itself two language-model agents: they read
a domain file and invent telemetry. That generator asks the model for a large
nested JSON document. A small local model does not reliably return one, so on
route B the five CAPRA stages would otherwise receive nothing.
`run_demo.sh` therefore seeds `local_raw` deterministically with
`reviewer/scripts/seed_telemetry.py`, which builds the same kind of event from
the same synthetic fixture.

This substitutes the *input simulator*, not the tool. The five stages
(federate, contextualise, assess, refine, review) are unchanged and still call
the language model. Pass `--seed-events 0` to run the language-model generator
instead and watch it for yourself; on a capable endpoint it usually works.

Substitute `healthcare` or `retail` for a different domain. The demonstration
isolates one domain per window because the contextualisation prompt does not
propagate a domain label to later stages; time-window separation is how the
original campaigns attributed records, and the same limitation applies here.

**Expected checkpoints during the window.**

| Stage | Where to look | What appears |
|---|---|---|
| Federate | n8n **Executions**, `local_raw` and `telemetry_raw` | normalised records with a canonical `event_id` |
| Contextualise | `raw_ontology`, `telemetry_transformation` | contextual assertions with `prov:wasDerivedFrom` links |
| Assess | `raw_scenarios`, `scenario_simulation_results`, `risk_inference_results`, and the Grafana risk dashboard | scenarios, paired simulations, and severity-labelled inferences |
| Refine | `evaluation_results`, `feedback_results` | proposals with action, target, rationale, and expected effect |
| Review | the n8n form endpoint printed by the HIL branch | an Approve or Reject form |

## 7. What each route does and does not show

The published campaigns used a hosted GPT-4o-class endpoint. Stage structure,
prompts, and stored schemas are identical on both routes; only the model
binding differs.

**Route A, generic endpoint.** Content quality tracks the model you point at.
A capable instruction-following model with reliable JSON output will produce
scenarios, inferences, and proposals comparable in kind to the reported ones.
It is still not a reproduction: the campaigns used a specific model at a
specific time, both builds are non-deterministic, and no output this package
produces is a validated privacy assessment.

**Route B, local Ollama fallback.** Treat it as a structural demonstration
only. Local models are not interchangeable, and the differences are not
cosmetic:

- **Speed.** Small models on CPU take minutes per agent call. A thirty-minute
  window may complete only a few dozen executions.
- **Instruction following.** Smaller models drift from the prompt, answer a
  different question, or pad the response with commentary.
- **Structured output.** The workflow's agents request JSON at several stages.
  Small models return malformed or partially quoted JSON often enough that
  downstream parsers reject it, which appears as errored executions and
  `status=failed` risk records. That is a property of the substituted model,
  not of the packaging.
- **Content.** Generated scenarios, inferences, and proposals differ from the
  campaign outputs and should not be compared with them.

Do not read route B as evidence that "Ollama works". Some Ollama models
complete the path acceptably and others do not finish a single stage. The
route is verified with `llama3.2`; other models are your own experiment.

Neither route reproduces the reported campaign results, and neither produces a
validated privacy assessment. To try a different local model on route B, set
`CAPRA_OLLAMA_MODEL` in `reviewer/.env`, pull it, and re-run the bootstrap.

## 8. Inspect the human-review step

The review form is served by n8n itself at the form-trigger path shown on the
**Human in the Loop - Review (1)** node. Submitting it resumes the waiting
execution. Note the boundary the paper states: a submission is observed form
interaction. The prototype does not durably persist the decision in a way the
retained evidence can confirm, and it applies no downstream change.

## 9. Check that nothing leaked

```bash
./reviewer/scripts/scan_secrets.sh
```

This scans the package for credential-shaped material in tracked files,
workflow JSON, the transformation report, run logs, and shipped images; it
confirms that `reviewer/.env` and `reviewer/.import/` are git-ignored and
untracked; and it confirms that the committed template still carries only
placeholders. Run it before you share anything from this directory, including
screenshots and log bundles.

## 10. Stop and clean up

```bash
# stop, keep data
docker compose -f reviewer/docker-compose.reviewer.yml --env-file reviewer/.env stop

# remove containers and volumes
docker compose -f reviewer/docker-compose.reviewer.yml --env-file reviewer/.env \
  --profile container-llm down -v

# remove your endpoint values
rm reviewer/.env
```

---

## Failure guidance

| Symptom | Cause | Action |
|---|---|---|
| Bootstrap exits saying the endpoint is not configured | `reviewer/.env` still holds placeholders | fill in all three `OPENAI_COMPATIBLE_*` values, or pass `--configure-only`, or switch to `--host-ollama` |
| `llm endpoint FAIL ... /models not reachable` | wrong base URL, wrong key, no network route from the container, or a server that does not implement `/models` | re-check the base URL exactly as your provider documents it; if `/models` is genuinely unimplemented, continue and let the first agent execution be the test |
| `workflow provider FAIL: workflow built for 'ollama', .env selects 'openai-compatible'` | the provider changed after the workflow was generated | re-run `./reviewer/scripts/bootstrap.sh` |
| `Bind for 0.0.0.0:PORT failed: port is already allocated` | another service holds a default port | edit the `CAPRA_*_PORT` values in `reviewer/.env` and re-run the bootstrap |
| `ollama (host) did not become ready` | the host Ollama is not running | run `ollama serve`, then re-run the bootstrap |
| Risk dashboard panels stay empty | Loki has no data yet, or the run window was too short | confirm `verify_route.sh` reports Loki `ok`, then run a longer window |
| Language-model nodes time out | route B on a containerised model on macOS | re-run the bootstrap with `--host-ollama`, or use route A |
| Agent nodes emit text that later nodes cannot parse | the bound model does not reliably return strict JSON | expected on small local models; see section 7 |
| `n8n` restarts but the workflow does not fire | n8n reads active state at start-up | `run_demo.sh` already restarts the container; if you activated in the UI instead, restart it yourself |
| Fuseki reports `no dataset` | the dataset creation step was skipped | re-run the bootstrap; step 7 is idempotent |
