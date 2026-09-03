#!/usr/bin/env bash
# CAPRA reviewer route — run one domain observation window and collect evidence.
#
# Activates the imported workflow for a bounded window, then deactivates it and
# records what the run produced: per-collection document deltas, n8n execution
# outcomes, the log streams that reached Loki, and which language-model provider
# was bound. Endpoint runs and Ollama-fallback runs are separate populations and
# are written to separate log files.
#
# Usage:
#   ./reviewer/scripts/run_demo.sh                       # admissions, 10 minutes
#   ./reviewer/scripts/run_demo.sh --domain retail --minutes 5

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO="$(cd "$HERE/.." && pwd)"
ENV_FILE="$HERE/.env"
DOMAIN="admissions"
MINUTES=10
SEED_EVENTS=12

while [ $# -gt 0 ]; do
  case "$1" in
    --domain) DOMAIN="$2"; shift 2 ;;
    --minutes) MINUTES="$2"; shift 2 ;;
    --seed-events) SEED_EVENTS="$2"; shift 2 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

# shellcheck disable=SC1090
set -a; . "$ENV_FILE"; set +a

PROVIDER="${CAPRA_LLM_PROVIDER:-openai-compatible}"
if [ "$PROVIDER" = "openai-compatible" ]; then
  MODEL="${OPENAI_COMPATIBLE_MODEL:-replace-with-your-model-name}"
  case "$MODEL" in
    replace-with-*|"")
      echo "The OpenAI-compatible endpoint is not configured in $ENV_FILE." >&2
      echo "Set OPENAI_COMPATIBLE_BASE_URL, OPENAI_COMPATIBLE_API_KEY, and" >&2
      echo "OPENAI_COMPATIBLE_MODEL and re-run bootstrap.sh, or switch to the" >&2
      echo "Ollama fallback with 'bootstrap.sh --host-ollama'." >&2
      exit 2 ;;
  esac
else
  MODEL="${CAPRA_OLLAMA_MODEL:-${CAPRA_LLM_MODEL:-llama3.2}}"
fi

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
LOG_DIR="$HERE/logs"
mkdir -p "$LOG_DIR"
RUN_LOG="$LOG_DIR/run_${DOMAIN}_${PROVIDER}_${STAMP}.json"

COLLECTIONS=(local_raw telemetry_raw enriched_telemetry_raw raw_ontology
  telemetry_transformation raw_scenarios scenario_simulation_results
  orchestration_agent_scenarios contextual_scoring risk_inference_results
  evaluation_results feedback_results revision_results)

counts() {
  local js="db = db.getSiblingDB('capra'); var out = {};"
  for collection in "${COLLECTIONS[@]}"; do
    js="$js out['$collection'] = db.getCollection('$collection').countDocuments({});"
  done
  js="$js print(JSON.stringify(out));"
  docker exec capra-reviewer-mongo mongosh --quiet --eval "$js"
}

exec_summary() {
  local tmp="$LOG_DIR/.n8n-db-$STAMP.sqlite"
  docker cp capra-reviewer-n8n:/home/node/.n8n/database.sqlite "$tmp" >/dev/null 2>&1 || { echo '{}'; return; }
  python3 "$HERE/scripts/summarise_executions.py" "$tmp" "$1"
  rm -f "$tmp"
}

echo "=== Regenerating the reviewer workflow for domain '$DOMAIN' ($PROVIDER) ==="
python3 "$HERE/scripts/make_reviewer_workflow.py" \
  --source "$REPO/workflows/CAPRA_Prototype_unified_patched.json" \
  --target "$HERE/workflows/CAPRA_reviewer_local.json" \
  --report "$HERE/workflows/transformation_report.json" \
  --provider "$PROVIDER" \
  --model "$MODEL" \
  --domain "$DOMAIN"

docker exec -i --user node capra-reviewer-n8n sh -c 'cat > /home/node/.capra-import-workflow.json' < "$HERE/workflows/CAPRA_reviewer_local.json"
docker exec --user node capra-reviewer-n8n n8n import:workflow --input=/home/node/.capra-import-workflow.json >/dev/null 2>&1
docker exec --user node capra-reviewer-n8n rm -f /home/node/.capra-import-workflow.json
echo "workflow imported"

if [ "$SEED_EVENTS" -gt 0 ]; then
  echo "=== Seeding the mock external system with $SEED_EVENTS synthetic events ==="
  python3 "$HERE/scripts/seed_telemetry.py" --domain "$DOMAIN" --events "$SEED_EVENTS" \
    --fixtures "$HERE/fixtures"
fi

echo "=== Baseline document counts ==="
BEFORE="$(counts)"
echo "$BEFORE"

echo "=== Activating for ${MINUTES} minute(s) ==="
START="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
docker exec capra-reviewer-n8n n8n update:workflow --id=capra-reviewer-local --active=true >/dev/null 2>&1
docker restart capra-reviewer-n8n >/dev/null
for _ in $(seq 1 60); do
  curl -sf -o /dev/null "http://localhost:${CAPRA_N8N_PORT}/healthz" && break
  sleep 5
done
echo "n8n restarted with the workflow active at $START"

sleep $((MINUTES * 60))

echo "=== Deactivating ==="
docker exec capra-reviewer-n8n n8n update:workflow --id=capra-reviewer-local --active=false >/dev/null 2>&1
docker restart capra-reviewer-n8n >/dev/null
END="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
for _ in $(seq 1 60); do
  curl -sf -o /dev/null "http://localhost:${CAPRA_N8N_PORT}/healthz" && break
  sleep 5
done

echo "=== Final document counts ==="
AFTER="$(counts)"
echo "$AFTER"

echo "=== Execution outcomes ==="
EXEC_SUMMARY="$(exec_summary "$START")"
echo "$EXEC_SUMMARY"

echo "=== Loki streams ==="
LOKI_JOBS="$(curl -sG "http://localhost:${CAPRA_LOKI_PORT}/loki/api/v1/label/job/values" \
  --data-urlencode "start=$(python3 -c 'import sys,datetime;print(int(datetime.datetime.strptime(sys.argv[1],"%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc).timestamp()*1_000_000_000))' "$START")" \
  --data-urlencode "end=$(date +%s)000000000" || echo '{}')"
echo "$LOKI_JOBS"

python3 - "$RUN_LOG" "$DOMAIN" "$START" "$END" "$BEFORE" "$AFTER" "$LOKI_JOBS" "$EXEC_SUMMARY" "$PROVIDER" "$MODEL" <<'PY'
import json, sys
path, domain, start, end, before, after, loki, execs, provider, model = sys.argv[1:11]
before_d, after_d = json.loads(before), json.loads(after)
delta = {k: after_d.get(k, 0) - before_d.get(k, 0) for k in after_d}
try:
    loki_d = json.loads(loki)
except json.JSONDecodeError:
    loki_d = {"raw": loki}
record = {
    "domain": domain,
    # Recorded so that endpoint runs and Ollama-fallback runs stay separate
    # populations and are never averaged together.
    "llm_provider": provider,
    "llm_model": model,
    "window_start_utc": start,
    "window_end_utc": end,
    "counts_before": before_d,
    "counts_after": after_d,
    "counts_delta": delta,
    "loki_job_labels": loki_d.get("data", loki_d),
    "n8n_executions": json.loads(execs) if execs.strip().startswith("{") else {},
}
with open(path, "w", encoding="utf-8") as handle:
    json.dump(record, handle, indent=2)
    handle.write("\n")
print(json.dumps(delta, indent=2))
print(f"run log written to {path}")
PY
