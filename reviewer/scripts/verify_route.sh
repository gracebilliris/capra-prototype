#!/usr/bin/env bash
# CAPRA reviewer route — health check.
#
# Prints one line per component. Every line must read 'ok' before you run an
# observation window.

set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$HERE/.env"

if [ ! -f "$ENV_FILE" ]; then
  echo "reviewer/.env not found. Run reviewer/scripts/bootstrap.sh first." >&2
  exit 1
fi
# shellcheck disable=SC1090
set -a; . "$ENV_FILE"; set +a

FAILURES=0

report() {
  local label="$1" status="$2" detail="${3:-}"
  printf '%-28s %-4s %s\n' "$label" "$status" "$detail"
  [ "$status" = "ok" ] || FAILURES=$((FAILURES + 1))
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

MODEL="${CAPRA_LLM_MODEL:-llama3.2}"
if docker exec capra-reviewer-n8n sh -c \
    "wget -q -O - http://ollama:11434/api/tags 2>/dev/null || wget -q -O - http://host.docker.internal:11434/api/tags 2>/dev/null" \
    2>/dev/null | grep -q "$MODEL"; then
  report "language model" "ok" "$MODEL reachable from n8n"
else
  report "language model" "FAIL" "$MODEL not reachable from the n8n container"
fi

if docker exec capra-reviewer-n8n n8n list:workflow 2>/dev/null | grep -q "capra-reviewer-local"; then
  report "workflow imported" "ok" "capra-reviewer-local"
else
  report "workflow imported" "FAIL" "run bootstrap.sh step 8"
fi

echo
if [ "$FAILURES" -eq 0 ]; then
  echo "All checks passed. Run ./reviewer/scripts/run_demo.sh next."
else
  echo "$FAILURES check(s) failed. See reviewer/QUICKSTART.md, Failure guidance."
  exit 1
fi
