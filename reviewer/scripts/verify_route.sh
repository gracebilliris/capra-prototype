#!/usr/bin/env bash
# CAPRA reviewer route — health check.
#
# Prints one line per component. Statuses are exact:
#
#   ok    the check ran and passed
#   FAIL  the check ran and failed
#   SKIP  the check could not run, and nothing is claimed either way
#
# A SKIP is never counted as a pass. In particular, the generic
# OpenAI-compatible endpoint is reported SKIP while reviewer/.env still holds
# placeholders: this script does not fabricate a successful endpoint check.

set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$HERE/.env"

if [ ! -f "$ENV_FILE" ]; then
  echo "reviewer/.env not found. Run reviewer/scripts/bootstrap.sh first." >&2
  exit 1
fi
# shellcheck disable=SC1090
set -a; . "$ENV_FILE"; set +a

PROVIDER="${CAPRA_LLM_PROVIDER:-openai-compatible}"
FAILURES=0
SKIPPED=0

report() {
  local label="$1" status="$2" detail="${3:-}"
  printf '%-28s %-5s %s\n' "$label" "$status" "$detail"
  case "$status" in
    ok) ;;
    SKIP) SKIPPED=$((SKIPPED + 1)) ;;
    *) FAILURES=$((FAILURES + 1)) ;;
  esac
}

check_http() {
  local label="$1" url="$2" expect="${3:-}"
  local body
  body="$(curl -sf --max-time 10 "$url" 2>/dev/null)" || { report "$label" "FAIL" "$url unreachable"; return; }
  if [ -n "$expect" ] && ! printf '%s' "$body" | grep -q "$expect"; then
    report "$label" "FAIL" "unexpected response from $url"
    return
  fi
  report "$label" "ok" "$url"
}

check_http "n8n"              "http://localhost:${CAPRA_N8N_PORT}/healthz" "ok"
check_http "loki"             "http://localhost:${CAPRA_LOKI_PORT}/ready"
check_http "grafana"          "http://localhost:${CAPRA_GRAFANA_PORT}/api/health" "database"
check_http "grafana datasource" "http://localhost:${CAPRA_GRAFANA_PORT}/api/datasources" "grafanacloud-logs"
check_http "risk dashboard"   "http://localhost:${CAPRA_GRAFANA_PORT}/api/search?query=CAPRA" "capra-risk-register"

TRIPLES="$(curl -sf --max-time 10 -H 'Accept: application/sparql-results+json' \
  --data-urlencode 'query=SELECT (COUNT(*) AS ?n) WHERE {?s ?p ?o}' \
  "http://localhost:${CAPRA_FUSEKI_PORT}/ontology/sparql" 2>/dev/null \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["results"]["bindings"][0]["n"]["value"])' 2>/dev/null)"
if [ -n "${TRIPLES:-}" ] && [ "$TRIPLES" -gt 0 ] 2>/dev/null; then
  report "fuseki ontology" "ok" "$TRIPLES triples"
else
  report "fuseki ontology" "FAIL" "dataset missing or empty"
fi

if docker exec capra-reviewer-mongo mongosh --quiet --eval 'db.runCommand({ping:1}).ok' 2>/dev/null | grep -q 1; then
  report "mongodb" "ok" "capra-reviewer-mongo"
else
  report "mongodb" "FAIL" "ping failed"
fi

# ---------------------------------------------------------------------------
# Language model
# ---------------------------------------------------------------------------
is_placeholder() {
  case "${1:-}" in
    ""|*replace.example*|replace-with-*) return 0 ;;
    *) return 1 ;;
  esac
}

if [ "$PROVIDER" = "openai-compatible" ]; then
  if is_placeholder "${OPENAI_COMPATIBLE_BASE_URL:-}" \
     || is_placeholder "${OPENAI_COMPATIBLE_API_KEY:-}" \
     || is_placeholder "${OPENAI_COMPATIBLE_MODEL:-}"; then
    report "llm endpoint" "SKIP" "not configured; placeholders still in reviewer/.env"
  elif docker exec -e CAPRA_KEY="$OPENAI_COMPATIBLE_API_KEY" \
         -e CAPRA_BASE="$OPENAI_COMPATIBLE_BASE_URL" capra-reviewer-n8n \
         sh -c 'wget -q -O /dev/null --header="Authorization: Bearer $CAPRA_KEY" "$CAPRA_BASE/models"' 2>/dev/null; then
    report "llm endpoint" "ok" "${OPENAI_COMPATIBLE_BASE_URL}/models reachable from n8n"
  else
    report "llm endpoint" "FAIL" "${OPENAI_COMPATIBLE_BASE_URL}/models not reachable from n8n"
  fi

  # Confirms the credential exists by id. Deliberately NOT --decrypted: the
  # check must never move the reviewer's key through a pipe or a log.
  if docker exec capra-reviewer-n8n sh -c \
      'n8n export:credentials --all --output=/home/node/.capra-cred-check.json >/dev/null 2>&1 \
       && grep -q capra-openai-compatible /home/node/.capra-cred-check.json; \
       rc=$?; rm -f /home/node/.capra-cred-check.json; exit $rc' 2>/dev/null; then
    report "llm credential" "ok" "CAPRA OpenAI-Compatible Endpoint imported (encrypted at rest)"
  else
    report "llm credential" "FAIL" "not present; run bootstrap.sh step 8"
  fi
else
  MODEL="${CAPRA_OLLAMA_MODEL:-${CAPRA_LLM_MODEL:-llama3.2}}"
  if docker exec capra-reviewer-n8n sh -c \
      "wget -q -O - http://ollama:11434/api/tags 2>/dev/null || wget -q -O - http://host.docker.internal:11434/api/tags 2>/dev/null" \
      2>/dev/null | grep -q "$MODEL"; then
    report "llm fallback (ollama)" "ok" "$MODEL reachable from n8n"
  else
    report "llm fallback (ollama)" "FAIL" "$MODEL not reachable from the n8n container"
  fi
fi

if docker exec capra-reviewer-n8n n8n list:workflow 2>/dev/null | grep -q "capra-reviewer-local"; then
  report "workflow imported" "ok" "capra-reviewer-local"
else
  report "workflow imported" "FAIL" "run bootstrap.sh step 8"
fi

if [ -f "$HERE/workflows/transformation_report.json" ]; then
  BOUND="$(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(d.get("provider","?"))' \
    "$HERE/workflows/transformation_report.json" 2>/dev/null)"
  if [ "$BOUND" = "$PROVIDER" ]; then
    report "workflow provider" "ok" "$BOUND matches reviewer/.env"
  else
    report "workflow provider" "FAIL" "workflow built for '$BOUND', .env selects '$PROVIDER'; re-run bootstrap.sh"
  fi
else
  report "workflow provider" "FAIL" "transformation report missing"
fi

echo
if [ "$FAILURES" -eq 0 ] && [ "$SKIPPED" -eq 0 ]; then
  echo "All checks passed. Run ./reviewer/scripts/run_demo.sh next."
elif [ "$FAILURES" -eq 0 ]; then
  echo "$SKIPPED check(s) SKIPPED and nothing was assumed about them; every check that"
  echo "could run passed. The stack is correctly configured, but the language-model"
  echo "endpoint has NOT been verified, so the workflow cannot yet complete a stage."
  echo "Configure the endpoint in reviewer/.env, or use the Ollama fallback."
  exit 3
else
  echo "$FAILURES check(s) failed, $SKIPPED skipped. See reviewer/QUICKSTART.md, Failure guidance."
  exit 1
fi
