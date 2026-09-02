# CAPRA reviewer quick start

This is the route to use if you are reviewing the CAPRA tool demonstration.
It runs entirely on your machine, needs no account, no API key, and no paid
service, and it does not build any source code. Every component is a published
container image.

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
| Disk | about 6 GB for images plus 2 GB for the language model | |
| Memory | give Docker at least 6 GB | |

On macOS, also install [Ollama](https://ollama.com) natively and run
`ollama pull llama3.2`. Docker Desktop on macOS cannot pass the Apple GPU
through to a container, so the containerised model runs on the virtual
machine's CPUs and is impractically slow. On Linux with a GPU, or if you are
willing to wait, the containerised model needs no host install.

---

## 1. Get the package

```bash
git clone https://github.com/gracebilliris/capra-prototype.git
cd capra-prototype
git checkout <the reviewer-route tag named in the paper>
```

An archive extraction works equally well; nothing in the route depends on Git
history.

## 2. Start everything

macOS, using the natively installed Ollama:

```bash
ollama serve &                      # skip if Ollama already runs as a service
./reviewer/scripts/bootstrap.sh --host-ollama
```

Linux, or anywhere you prefer a fully containerised stack:

```bash
./reviewer/scripts/bootstrap.sh
```

The script is idempotent; re-running it is safe. It performs eight steps and
prints a heading for each one:

1. checks Docker, Compose, and Python
2. writes `reviewer/.env` with local ports and a locally generated n8n
   encryption key (git-ignored; it protects only your local credential store)
3. regenerates the three synthetic domain input files
4. derives the credential-free workflow from the published export
5. starts n8n, MongoDB, Fuseki, Loki, Grafana, and optionally Ollama
6. waits for each service to answer its health endpoint
7. creates and seeds the Fuseki `ontology` dataset
8. pulls the language model, then imports the workflow and its two local
   credentials

**Expected checkpoint.** The script ends by printing five URLs. A clean run on
the verification machine took about 90 seconds with images already cached, and
about 9 minutes including the first image download.

## 3. Confirm the stack is healthy

```bash
./reviewer/scripts/verify_route.sh
```

Every line must report `ok`. The check covers the n8n health endpoint, the
Fuseki triple count, the Loki readiness endpoint, the Grafana datasource and
provisioned dashboard, the MongoDB ping, and the language-model endpoint.

## 4. Open the interfaces

| Interface | URL | First-run note |
|---|---|---|
| n8n editor | <http://localhost:5679> | Complete the local owner sign-up. Any email and password work; they are stored only in your local container. |
| Risk dashboard | <http://localhost:3002/d/capra-risk-register> | Anonymous access is enabled; no login. |
| Fuseki | <http://localhost:3031> | Dataset `ontology`. |
| Loki | <http://localhost:3101> | Queried through Grafana. |

In the n8n editor, open **CAPRA Reviewer Route (local, credential-free,
admissions)**. The five stages appear as branches of a single workflow:
federate (DFL), contextualise (CPL), assess (RIL), refine (F&RL), and review
(HIL).

## 5. Run one domain observation window

```bash
./reviewer/scripts/run_demo.sh --domain admissions --minutes 30
```

The script re-imports the workflow with only that domain's ingestion trigger
enabled, seeds twelve synthetic agent events, activates the workflow, waits,
deactivates it, and writes a run log to
`reviewer/logs/run_<domain>_<timestamp>.json` containing the document count
before and after, the per-collection delta, the n8n execution outcomes, and the
Loki job labels seen in the window.

### Why the run seeds events

In the published workflow the *mock external system* that stands in for a
deployed multi-agent application is itself two language-model agents: they read
a domain file and invent telemetry. That generator asks the model for a large
nested JSON document, and a small local model does not reliably return one, so
on this route the five CAPRA stages would receive nothing. `run_demo.sh`
therefore seeds `local_raw` deterministically with
`reviewer/scripts/seed_telemetry.py`, which builds the same kind of event from
the same synthetic fixture.

This substitutes the *input simulator*, not the tool. The five stages
(federate, contextualise, assess, refine, review) are unchanged and still use
the language model. Pass `--seed-events 0` to run the language-model generator
instead and watch it for yourself.

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

## 6. Inspect the human-review step

The review form is served by n8n itself at the form-trigger path shown on the
**Human in the Loop - Review (1)** node. Submitting it resumes the waiting
execution. Note the boundary the paper states: a submission is observed form
interaction. The prototype does not durably persist the decision in a way the
retained evidence can confirm, and it applies no downstream change.

## 7. Stop and clean up

```bash
# stop, keep data
docker compose -f reviewer/docker-compose.reviewer.yml --env-file reviewer/.env stop

# remove containers and volumes
docker compose -f reviewer/docker-compose.reviewer.yml --env-file reviewer/.env \
  --profile container-llm down -v
```

---

## Failure guidance

| Symptom | Cause | Action |
|---|---|---|
| `Bind for 0.0.0.0:PORT failed: port is already allocated` | another service holds a default port | edit the `CAPRA_*_PORT` values in `reviewer/.env` and re-run the bootstrap |
| `ollama (host) did not become ready` | the host Ollama is not running | run `ollama serve`, then re-run the bootstrap |
| Risk dashboard panels stay empty | Loki has no data yet, or the run window was too short | confirm `verify_route.sh` reports Loki `ok`, then run a longer window |
| Language-model nodes time out | the containerised model is running on CPU | re-run the bootstrap with `--host-ollama` on macOS |
| Agent nodes emit text that later nodes cannot parse | a small local model does not always return strict JSON | expected; see the note below |
| `n8n` restarts but the workflow does not fire | n8n reads active state at start-up | `run_demo.sh` already restarts the container; if you activated in the UI instead, restart it yourself |
| Fuseki reports `no dataset` | the dataset creation step was skipped | re-run the bootstrap; step 7 is idempotent |

### Note on model substitution

The published campaigns used a hosted GPT-4o-class endpoint. The reviewer route
substitutes a small local model so that the tool can be run without an account.
Stage structure, prompts, and stored schemas are unchanged, but the *content* of
generated scenarios, inferences, and proposals differs from the campaign
outputs, and a small model returns malformed JSON more often. Structural
execution is what this route demonstrates. It is not a reproduction of the
reported campaign results, and no output it produces is a validated privacy
assessment.

To use a larger local model instead, set `CAPRA_LLM_MODEL` in `reviewer/.env`,
pull that model, and re-run `run_demo.sh`.
