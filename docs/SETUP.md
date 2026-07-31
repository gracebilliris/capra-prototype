# CAPRA — Full setup guide

This guide walks through provisioning the runtime from scratch on a new
machine (macOS / Linux). Windows users: run the Docker commands from WSL2.

Estimated time: **45–60 min** end-to-end, most of which is waiting for the
free-tier signups.

> **Cost.** All external services used here have a free tier that covers the
> reproduction workload. The only thing that costs money is the LLM
> (Azure OpenAI or OpenAI) — expect a few USD for a full reproduction run.

---

## 1. External service accounts

Sign up for these three services if you don't already have them. Keep the
credentials — you'll paste them into n8n later.

| Service | What we use | Free-tier limits relevant to CAPRA |
|---|---|---|
| **MongoDB Atlas** — <https://www.mongodb.com/atlas/database> | Cluster stores raw telemetry, enriched telemetry, inference results, evaluation results, feedback. | 512 MB storage. Enough for a several-hour demo run; free tier fills within ~1 day of continuous scheduling. |
| **Grafana Cloud** — <https://grafana.com/products/cloud/> | Loki log ingestion + Grafana for the seven dashboards. | 50 GB Loki ingestion / month, 30-day retention. Plenty. |
| **Azure OpenAI** or **OpenAI** — <https://portal.azure.com/> | LLM calls for CPL (Telemetry Transformation), RIL (Scenario, Sim1, Sim2, Inference), E&RL (Evaluation). | Not free; pay-as-you-go. Budget a few USD per full reproduction. |

### 1.1 MongoDB Atlas

1. Create a free "M0 Sandbox" cluster in any region close to you.
2. Under **Database Access**, create a user with **Read and write to any database**. Note the username + password.
3. Under **Network Access**, add your current IP (or `0.0.0.0/0` for a demo — tighten later).
4. Under **Database → Connect → Drivers → Node.js**, copy the SRV connection string. It looks like:
   ```
   mongodb+srv://<user>:<password>@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0
   ```

### 1.2 Grafana Cloud

1. Sign up; a personal stack is created automatically (e.g. `<name>.grafana.net`).
2. **Loki push credentials.** Home → **Connections → Data sources → grafanacloud-logs → Details**. Note the *user id* (numeric) and generate an *API token* starting with `glc_`.
3. **Dashboard-editor service account.** Home → **Administration → Users and access → Service accounts → Add** with role **Admin** or **Editor**. Add a token starting with `glsa_`. You'll use this to POST dashboards.
4. **Loki datasource UID** (needed when importing the Risk Dashboard). It's usually `grafanacloud-logs` on personal stacks. Verify by opening any data source and checking the URL.

### 1.3 Azure OpenAI (or OpenAI)

Provision three deployments (or reuse one):

| Deployment name (suggested) | Model | Used by |
|---|---|---|
| `azure-openai-telemetry-model` | `gpt-4o-mini` | CPL Telemetry Transformation Agent |
| `azure-openai-scenario-model` | `gpt-4o` | RIL Scenario, Sim1, Sim2, Inference agents |
| `azure-openai-evaluation-model` | `gpt-4o-mini` | E&RL Evaluation Agent |

Note the endpoint URL and API key.

---

## 2. Local runtime

### 2.1 Install prerequisites

```bash
# macOS (Homebrew)
brew install --cask docker
brew install git python@3.11 node@22 jq

# Linux (Ubuntu/Debian)
sudo apt install docker.io docker-compose-plugin git python3 python3-pip nodejs npm jq
```

Verify:

```bash
docker version && git --version && python3 --version
```

### 2.2 Clone the repo

```bash
cd ~/Projects
git clone https://github.com/gracebilliris/capra-prototype.git
cd capra-prototype
```

### 2.3 Bring up the runtime containers

The compose file starts **n8n**, **Fuseki** (SPARQL / ontology), **Kafka +
Zookeeper** (used by DFL for the mock telemetry stream) and a local
**Mongo** helper (only used for cache — the durable stores live in Atlas).

```bash
docker compose -f docs/docker-compose.yml up -d
docker compose -f docs/docker-compose.yml ps
```

Wait for all containers to report `Up (healthy)` — typically 60–90 s.

**Sanity checks:**

```bash
# n8n
curl -sI http://localhost:5678 | head -1
# → HTTP/1.1 200 OK

# Fuseki
curl -s http://localhost:3030/$/ping
# → 2xx OK

# Kafka
docker exec context-processing-layer-prototype-kafka-1 \
  kafka-topics --bootstrap-server localhost:9092 --list
```

---

## 3. Bootstrap the Fuseki ontology dataset

```bash
# Create the 'ontology' dataset
curl -sf -u admin:admin -X POST \
  "http://localhost:3030/$/datasets?dbType=tdb2&dbName=ontology"

# Load the seed triples (privacy risk taxonomy + telemetry ontology)
curl -sf -u admin:admin -X POST \
  "http://localhost:3030/ontology/data" \
  -H "Content-Type: application/x-turtle" \
  --data-binary @docs/ontology_seed.ttl 2>/dev/null || echo "seed ttl optional"

# Verify
curl -s "http://localhost:3030/ontology/sparql?query=SELECT%20(COUNT(*)%20AS%20%3Fn)%20WHERE%20%7B%20%3Fs%20%3Fp%20%3Fo%20%7D"
```

> The ontology_seed.ttl file is optional; the workflow's Graph Importer
> nodes will populate the dataset from telemetry as it runs. Seeding just
> gives you a non-empty starting point for demos.

---

## 4. Import the n8n workflow

1. Open <http://localhost:5678> in a browser and complete the initial n8n
   owner setup.
2. **Settings → Import from file →**
   `workflows/CAPRA_Prototype_unified_patched.json`.
3. You'll see a red banner: "Missing credentials". This is expected — the
   workflow references credential IDs, not credential values. Bind them:

| Credential type | Where to enter | Value |
|---|---|---|
| MongoDB — "Telemetry DB" | Credentials → New → MongoDB | Paste the Atlas SRV string; database name `telemetry_db`. |
| MongoDB — "Risk Intelligence DB" | Same as above, database `risk_intelligence_db`. | |
| MongoDB — "Feedback and Refinement DB" | Same, database `feedback_and_refinement_db`. | |
| Grafana Loki | Credentials → New → HTTP Header Auth | Header name `Authorization`, value `Basic <base64(userid:glc_token)>`. |
| Azure OpenAI — Telemetry Model | Credentials → New → Azure OpenAI | Endpoint + key + deployment name from §1.3. |
| Azure OpenAI — Scenario Model | Same, different deployment. | |
| Azure OpenAI — Evaluation Model | Same, different deployment. | |

4. Open each red node in the workflow and re-bind it to the corresponding
   credential (n8n won't do this automatically because the imported IDs
   don't exist in your instance).

---

## 5. Install the Grafana dashboards

You need to import seven dashboards. The Risk Dashboard is shipped in this
repo (`dashboards/risk_register.json`). The six per-layer dashboards are
referenced by UID inside the workflow and are seeded on your Grafana Cloud
stack by importing the exports linked in `test_artefacts/11_README_grafana_migration.md`.

**Risk Dashboard install (server-side, recommended):**

```bash
GLSA_TOKEN="glsa_your_token_here"
GRAFANA_HOST="your-name.grafana.net"

python3 <<PY
import json, urllib.request
d = json.load(open("dashboards/risk_register.json"))
payload = json.dumps({"dashboard": d, "overwrite": True,
                      "message": "Initial import"}).encode()
req = urllib.request.Request(
    f"https://$GRAFANA_HOST/api/dashboards/db",
    data=payload,
    headers={"Authorization": "Bearer $GLSA_TOKEN",
             "Content-Type": "application/json"})
print(urllib.request.urlopen(req).read().decode())
PY
```

**Or via browser console** (if you don't have a `glsa_` token):

1. Log into Grafana.
2. Open DevTools → Console.
3. Paste the contents of `dashboards/install_risk_register_dashboard.js`.
4. Follow the prompts.

---

## 6. Activate the workflow and verify

### 6.1 Activate

```bash
# Toggle "Active" ON in the n8n UI, OR via SQL for scripted setup:
docker exec context-processing-layer-prototype-n8n-1 sh -c \
  "sqlite3 /home/node/.n8n/database.sqlite \
   \"UPDATE workflow_entity SET active=1 WHERE name='CAPRA Prototype (risk register patch)'\""
docker restart context-processing-layer-prototype-n8n-1
```

The restart is required — n8n reads active state from the on-disk workflow
history at startup, so a DB edit alone is a silent no-op.

### 6.2 Verify each layer

Watch executions in the n8n UI, or query the DB:

```bash
docker exec context-processing-layer-prototype-n8n-1 sh -c \
  "sqlite3 /home/node/.n8n/database.sqlite \
   \"SELECT status, COUNT(*) FROM execution_entity WHERE startedAt > datetime('now','-2 minutes') GROUP BY status\""
```

Verify data is reaching Loki:

```bash
LOKI_USER="1234567:glc_..."   # your grafana user_id:token
curl -sG --user "$LOKI_USER" \
  https://logs-prod-XXX.grafana.net/loki/api/v1/label/job/values \
  --data-urlencode "start=$(($(date +%s)-300))000000000" \
  --data-urlencode "end=$(date +%s)000000000"
# → should include: risk_intelligence_layer, evaluation_and_refinement_layer, ...
```

Open <https://your-name.grafana.net/d/capra-risk-register> — within
2–3 minutes you should see substantive risk records populating the panels.

---

## 7. Per-domain test campaign

The Beta iteration was validated with three illustrative scenarios
(Student Admission, Healthcare EHR, Retail). Because the current CPL prompt
does not propagate a `domain` label to RIL, per-domain evidence is captured
by **time-window filtering**:

1. Deactivate the workflow.
2. Push the first domain's telemetry only (edit `Read <domain>data` node's
   `fileSelector` to point at the domain CSV, activate for ~5 min).
3. Note the timestamp range.
4. Deactivate; repeat for domain 2 and domain 3.
5. In Grafana, use absolute time ranges to isolate each domain's records.

See `test_artefacts/13`–`17_Layer_Report_*.md` for per-layer verification
queries and expected outputs.

**Housekeeping.** After each activation cycle, deactivate promptly — the
n8n `execution_entity` table grows ~6,000 rows / 15 min at 10-s schedule
cadence, which will consume Atlas storage quickly if you also keep n8n's
`execution_data` retention on the default.

---

## 8. Cleanup

```bash
# Stop the runtime (keeps data)
docker compose -f docs/docker-compose.yml stop

# Nuke everything (removes containers + volumes — will need to reseed Fuseki)
docker compose -f docs/docker-compose.yml down -v
```

Free up MongoDB Atlas storage by dropping the largest collections in the
Atlas UI (`enriched_telemetry_raw` is usually the biggest).

---

## 9. Where to go next

- **Test evidence and per-layer results:** `test_artefacts/07_Test_Run_Findings.md`
- **Reproduction commands / runbook:** `test_artefacts/20_Reproduction_Guide.md`
- **DSRM evaluation criteria walk-through:** `test_artefacts/19_DSRM_Evaluation_Report.md`
- **CA3 report section 5.2 (paste-ready):** `test_artefacts/21_CA3_Section_5_2_Risk_Dashboard.md`
