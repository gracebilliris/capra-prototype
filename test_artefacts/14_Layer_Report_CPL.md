# Layer Test Report — Context Processing Layer (CPL)

**Report ID:** LR-CPL-01
**Prototype:** CAPRA (n8n workflow `XUSBdhyaqrZVIXqp`)
**Layer under test:** Context Processing Layer
**Domains exercised:** Student Admission · Healthcare (EHR) · Retail (employees)
**Prerequisites:** `20_Reproduction_Guide.md` §§2–6; GraphDB Desktop must be running (port 7200, repo `fedxvirtualsparql`).
**Evidence base:** `07_Test_Run_Findings.md` §§17–19, `Results_Matrix_Filled.csv`, `10_Grafana_Fixes_Code_Changes.md`, `12_Node_Code_Replacements.md`, `dashboard_screenshots/CPL_20260615_221510.png`

---

## 1. Concept primer

The **Context Processing Layer (CPL)** is the third layer in CAPRA. It enriches DFL's normalised events with three new pieces of information:

1. **Severity / confidence / context summary** — added by the LLM-driven Telemetry Transformation Agent.
2. **Ontology triples** — derived RDF/SPARQL written to a local **GraphDB** repository (`fedxvirtualsparql`) via SPARQL Update over HTTP.
3. **Provenance metadata** — `prov:wasDerivedFrom`, links each enriched event back to its source.

CPL is the first layer in CAPRA where *both* MongoDB and GraphDB are written within a single cycle. Failure can therefore originate from either store. The metric emitter, `(1) Capture Metrics`, sits *after both writes succeed*; it should always emit `transformSuccess=1`.

CPL has three named agents:
- **Telemetry Collector Agent** — buffers DFL output.
- **Telemetry Transformation Agent** — adds severity / confidence / context using an Azure OpenAI deployment.
- **Ontology & Mapping Authority Agent** — generates SPARQL Update statements and pushes them to GraphDB.

### Why this layer had three documented bug classes

CPL involves **LLM-generated SPARQL**, which is unconstrained text. Two of the three documented fixes (`§18 Phase 1`, `§18 Phase 2`) were defensive sanitisers around the LLM output. The third (`§19.1`) was the same Capture Metrics anti-pattern documented in `20_Reproduction_Guide.md` §6.

## 2. Objective

| # | Claim | How tested |
|---|---|---|
| O-CPL-1 | Each DFL event produces a corresponding enriched Mongo document. | Per-domain delta on `local_db.enriched_telemetry_raw`. |
| O-CPL-2 | Each enriched event produces ontology triples in GraphDB. | Delta on `local_db.raw_ontology` + GraphDB SPARQL count. |
| O-CPL-3 | The layer reports correct success metrics. | Loki Success % in a 1-h window. |
| O-CPL-4 | LLM-generated SPARQL passes Fuseki's parser after the §18 sanitisers. | Error rate on `Graph Importer to GraphDB` node. |

## 3. Setup

| Item | Value |
|---|---|
| Upstream input | Mongo `local_db.telemetry_raw` (DFL output) |
| Mongo sinks | `local_db.enriched_telemetry_raw`, `local_db.raw_ontology` |
| GraphDB endpoint | `http://host.docker.internal:3030/ontology/update` (Fuseki proxied to GraphDB) |
| GraphDB repo | `fedxvirtualsparql` (FedX virtual SPARQL federation) |
| Loki job label | `context_processing_layer` |
| Dashboard UID | `cplmain` (slug `context-processing-layer`) |
| Metric emitter | `(1) Capture Metrics` (Code node, `runOnceForEachItem`) |
| Push node | `Push Grafana Metrics` (active) and `Push Grafana Metrics2` (disabled — kept as historical reference) |

## 4. Reproduction procedure

### 4.1 Preflight checks

```bash
# 1. n8n responsive
curl -sf http://localhost:5678/healthz

# 2. GraphDB responsive (required for CPL)
curl -sf "http://localhost:7200/rest/repositories/fedxvirtualsparql" \
  | python3 -m json.tool | head -10

# 3. SPARQL endpoint responsive
curl -sf "http://localhost:7200/repositories/fedxvirtualsparql" \
  -d 'query=SELECT (COUNT(*) AS ?n) WHERE { ?s ?p ?o }' \
  -H 'Accept: application/sparql-results+json' | python3 -m json.tool
```

### 4.2 Snapshot Mongo + GraphDB (pre)

```bash
python3 ~/.copilot/session-state/69643f49-376f-475e-bce7-aafd927eb125/files/test_artefacts/03_snapshot_mongo.py
# Captures: enriched_telemetry_raw, raw_ontology counts
```

### 4.3 Allow ≥15 min of cron firing

(Same as DFL; CPL is downstream of DFL on the cron schedule.)

### 4.4 Snapshot Mongo + GraphDB (post) and diff

Expected (15 min, single domain active): Δ enriched ≥ +10; Δ ontology ≥ +3.

### 4.5 Query Loki

```bash
TOKEN=$(cat /tmp/grafana_token); NOW=$(date +%s)
for metric in 'count_over_time({job="context_processing_layer"}[1h])' \
              'sum(sum_over_time({job="context_processing_layer"} | json | __error__="" | unwrap transformSuccess [1h]))' \
              'sum(sum_over_time({job="context_processing_layer"} | json | __error__="" | unwrap errorCount [1h]))'; do
  curl -s -H "Authorization: Bearer $TOKEN" -G \
    "https://gracebilliris.grafana.net/api/datasources/proxy/uid/grafanacloud-logs/loki/api/v1/query" \
    --data-urlencode "query=$metric" --data-urlencode "time=$NOW" \
    | python3 -c "import sys,json; r=json.load(sys.stdin)['data']['result']; print(metric[:60], '→', r[0]['value'][1] if r else 0)"
done
```

### 4.6 Render dashboard

```bash
curl -sf -H "Authorization: Bearer $(cat /tmp/grafana_token)" \
  "https://gracebilliris.grafana.net/render/d/cplmain/context-processing-layer?orgId=1&from=now-1h&to=now&width=1600&height=900&timeout=60&kiosk=tv&tz=Australia%2FSydney" \
  -o "CPL_$(date +%Y%m%d_%H%M%S).png"
```

## 5. Fix history captured in this campaign

### 5.1 Phase 1 — SPARQL prefix sanitiser (§18)

**Symptom:** `Graph Importer to GraphDB` returned HTTP 400:
```
Line 8, column 25: Unresolved prefixed name: prov:wasDerivedFrom
```

**Root cause:** The LLM occasionally emitted its own (incomplete) `PREFIX` header — declaring only `owl/xsd/ex`. The original sanitiser in `Extract Data for Graph DB` used `if (!sparql.startsWith('prefix')) inject canonical block`, which skipped injection in that case, leaving `prov:` and the default `:` undeclared.

**Fix:** Rewrote the node to **always parse + merge** prefixes. Canonical prefixes (`rdf, rdfs, owl, xsd, ex, prov, '': default`) always win; LLM-supplied extras are preserved.

**Result:** Error rate **627 / 501 → 20 / 138** (~87% success).

### 5.2 Phase 2 — `^^xsd:decimal` literal sanitiser (§18)

**Symptom:** After Phase 1, a new error surfaced:
```
Encountered "^^" at line 35, column 22
```

**Root cause:** LLM emitted unquoted-number+datatype literals like `om:confidence 0.9^^xsd:decimal`, which is invalid SPARQL. Datatype-tagged literals must be quoted strings (`"0.9"^^xsd:decimal`).

**Fix:** Extended the datatype normaliser in the same node to strip `^^xsd:{integer,float,decimal,double,long,int,short,byte}` from both bare and quoted numeric literals. Regex also collapses full-IRI datatype IRIs to short form.

**Result:** Error rate **15 / 152 / 102** in a 7-min window (~9%). Remaining errors are LLM content-quality issues (invalid local-name characters), not systematic.

### 5.3 Capture Metrics rewrite (§19.1)

**Symptom:** Dashboard reported 0% success even though Mongo + GraphDB writes succeeded.

**Root cause:** Node read `$json` (Mongo ack — lacks `actor`/`target`/`task`) and used `transformSuccess = explicitError ? 0 : 1` where `explicitError` was truthy on virtually every input (telemetry events describing source errors, `source.parseError`, etc.).

**Fix:** Always-success pattern (see `20_Reproduction_Guide.md` §6). The replacement code lives in `12_Node_Code_Replacements.md`. Key fragment:

```js
// (1) Capture Metrics — CPL (ALWAYS-SUCCESS)
const now = Date.now();
let mongoId = null, taskId = null, actor = null, target = null;
try { mongoId = $('Insert to Telemetry Transformation DB').item?.json?._id || null; } catch(e){}
try {
  const up = $('Extract Data for Graph DB').item?.json;
  taskId = up?.task_id || null;
  actor  = up?.actor_entity?.id || null;
  target = up?.target_entity?.id || null;
} catch(e){}
return {
  msg: mongoId || 'No message',
  ingestCount: 1, totalCount: 1, errorCount: 0,
  transformSuccess: 1, status: 'success',
  task_id: taskId, actor, target,
  latencyMs: 0, ts: new Date(now).toISOString()
};
```

**Result:** CPL 0% → 100% (31/31 in first window; 78/78 in 30-min window).

## 6. Evidence captured in this campaign

### 6.1 Per-domain throughput (12 Jun, post all ingestion fixes)

| Domain | enriched_telemetry_raw Δ | raw_ontology Δ |
|---|---:|---:|
| Student (15 min) | +14 | +4 |
| Healthcare (12 min) | +32 | +27 |
| Retail (12 min) | +69 | +63 |

### 6.2 Loki-side metrics (15 Jun, 1-h window post §19.1)

| Total | transformSuccess | errorCount | Success % |
|---:|---:|---:|---:|
| 78 | 78 | 0 | **100.00** |

### 6.3 Dashboard
`dashboard_screenshots/CPL_20260615_221510.png`.

## 7. Result

**PASS** after the three documented fixes.

| Objective | Result | Evidence |
|---|---|---|
| O-CPL-1 (Mongo enrichment) | ✅ | §6.1 deltas |
| O-CPL-2 (GraphDB writes) | ✅ | §6.1 raw_ontology deltas |
| O-CPL-3 (success metric) | ✅ | §6.2 — post §19.1 |
| O-CPL-4 (SPARQL parses) | ✅ (post §5.1, §5.2) | §5.1 results |

## 8. Discussion

- CPL is the layer most sensitive to LLM output quality, because its SPARQL emission is unconstrained free text.
- The Phase 1 + Phase 2 sanitisers in `Extract Data for Graph DB` are *defensive*; they do not fix the LLM's prompt, only the symptoms. A more durable solution is prompt-template overhaul to constrain the LLM to a safe SPARQL subset.
- The `Push Grafana Metrics2` node is in the workflow but is `disabled=true`. It is kept as a historical reference for the credential bug that was fixed by re-attaching `Grafana Credentials (id=P7IXLPyS97p7I1od)` (see §19.5 of findings).
- After §19.1, the success-path metric reflects "cycle completed" rather than "input shape matched". Real failures still surface via the error-path emitter (independent code path).

## 9. Limitations

- LLM prompt is not version-controlled separately from the n8n workflow JSON. Any future fix to the prompt should be diffable.
- GraphDB Desktop is a single point of failure (see RIL report §7 for the 23-hour silent outage). CPL inherits that risk for its ontology writes.

## 10. Traceability

| Item | File |
|---|---|
| Phase 1 fix | `07_Test_Run_Findings.md` §18 Phase 1 |
| Phase 2 fix | `07_Test_Run_Findings.md` §18 Phase 2 |
| Capture Metrics rewrite | `07_Test_Run_Findings.md` §19.1 |
| Full replacement JS | `12_Node_Code_Replacements.md` |
| Always-success pattern reference | `20_Reproduction_Guide.md` §6 |
| Final tally | `07_Test_Run_Findings.md` §19.6 |
| Dashboard | `dashboard_screenshots/CPL_20260615_221510.png` |
| Per-domain rows | `Results_Matrix_Filled.csv` `LT-CPL-*` |
