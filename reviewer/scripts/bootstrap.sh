#!/usr/bin/env bash
# CAPRA reviewer route — one-command bootstrap.
#
# Brings up the local stack (n8n, MongoDB, Fuseki, Loki, Grafana), provisions
# the Fuseki dataset, derives the reviewer workflow, imports it with its
# credentials, and prints the reviewer URLs. Nothing is built from source; every
# component is a published container image.
#
# Language model. The preferred route binds the workflow's agents to ONE
# generic OpenAI-compatible endpoint that you supply: base URL, API key, model
# name. It is not standard-OpenAI-specific and not Azure-specific. An optional
# credential-free fallback runs a local Ollama model instead.
#
# Your endpoint values are read from reviewer/.env, which is git-ignored, and
# are written only into the local n8n credential store. This script never
# prints a key, never writes one outside reviewer/.env, and never reports the
# endpoint as working unless a live call to it succeeded.
#
# Usage:
#   ./reviewer/scripts/bootstrap.sh                     # generic endpoint (preferred)
#   ./reviewer/scripts/bootstrap.sh --configure-only    # bring the stack up with
#                                                       # placeholders still in place
#   ./reviewer/scripts/bootstrap.sh --host-ollama       # fallback, host runtime
#   ./reviewer/scripts/bootstrap.sh --container-ollama  # fallback, containerised
#   ./reviewer/scripts/bootstrap.sh --no-pull           # skip the Ollama model download

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO="$(cd "$HERE/.." && pwd)"
COMPOSE_FILE="$HERE/docker-compose.reviewer.yml"
ENV_FILE="$HERE/.env"
TEMPLATE_FILE="$HERE/env.template"
DO_PULL=1
PROVIDER=""
OLLAMA_MODE="host"
CONFIGURE_ONLY=0

PLACEHOLDER_BASE_URL="https://replace.example/v1"
PLACEHOLDER_API_KEY="replace-with-your-key"
PLACEHOLDER_MODEL="replace-with-your-model-name"

for arg in "$@"; do
  case "$arg" in
    --no-pull) DO_PULL=0 ;;
    --endpoint|--openai-compatible) PROVIDER="openai-compatible" ;;
    --host-ollama) PROVIDER="ollama"; OLLAMA_MODE="host" ;;
    --container-ollama) PROVIDER="ollama"; OLLAMA_MODE="container" ;;
    --configure-only) CONFIGURE_ONLY=1 ;;
    -h|--help) sed -n '2,28p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) echo "unknown argument: $arg" >&2; exit 2 ;;
  esac
done

step() { printf '\n=== %s ===\n' "$1"; }

step "0/8 Preconditions"
command -v docker >/dev/null || { echo "docker is required" >&2; exit 1; }
docker compose version >/dev/null || { echo "docker compose v2 is required" >&2; exit 1; }
command -v python3 >/dev/null || { echo "python3 is required" >&2; exit 1; }
command -v curl >/dev/null || { echo "curl is required" >&2; exit 1; }
echo "docker $(docker version --format '{{.Server.Version}}')"

step "1/8 Local environment file"
if [ ! -f "$ENV_FILE" ]; then
  cp "$TEMPLATE_FILE" "$ENV_FILE"
  chmod 600 "$ENV_FILE"
  echo "created $ENV_FILE from env.template"
else
  chmod 600 "$ENV_FILE"
  echo "reusing existing $ENV_FILE"
  # Add any key a later revision of the template introduced, without touching
  # values the reviewer has already set.
  while IFS= read -r key; do
    if ! grep -q "^${key}=" "$ENV_FILE"; then
      grep "^${key}=" "$TEMPLATE_FILE" >> "$ENV_FILE"
      echo "added missing key $key"
    fi
  done < <(grep -oE '^[A-Z0-9_]+=' "$TEMPLATE_FILE" | tr -d '=')
fi

# The encryption key protects only the reviewer's own local credential store.
if ! grep -qE '^N8N_ENCRYPTION_KEY=.+' "$ENV_FILE"; then
  KEY="$(python3 -c 'import secrets; print(secrets.token_hex(16))')"
  python3 - "$ENV_FILE" "$KEY" <<'PY'
import pathlib, sys
path, key = pathlib.Path(sys.argv[1]), sys.argv[2]
lines = path.read_text(encoding="utf-8").splitlines()
out = [f"N8N_ENCRYPTION_KEY={key}" if l.startswith("N8N_ENCRYPTION_KEY=") else l for l in lines]
path.write_text("\n".join(out) + "\n", encoding="utf-8")
PY
  echo "generated a local n8n encryption key"
fi

# shellcheck disable=SC1090
set -a; . "$ENV_FILE"; set +a

PROVIDER="${PROVIDER:-${CAPRA_LLM_PROVIDER:-openai-compatible}}"
case "$PROVIDER" in
  openai-compatible|ollama) ;;
  *) echo "CAPRA_LLM_PROVIDER must be 'openai-compatible' or 'ollama'" >&2; exit 2 ;;
esac

is_placeholder() {
  case "${1:-}" in
    ""|"$PLACEHOLDER_BASE_URL"|"$PLACEHOLDER_API_KEY"|"$PLACEHOLDER_MODEL") return 0 ;;
    *replace.example*|replace-with-*) return 0 ;;
    *) return 1 ;;
  esac
}

ENDPOINT_CONFIGURED=0
if [ "$PROVIDER" = "openai-compatible" ]; then
  if is_placeholder "${OPENAI_COMPATIBLE_BASE_URL:-}" \
     || is_placeholder "${OPENAI_COMPATIBLE_API_KEY:-}" \
     || is_placeholder "${OPENAI_COMPATIBLE_MODEL:-}"; then
    if [ "$CONFIGURE_ONLY" -eq 0 ]; then
      cat >&2 <<EOF

The generic OpenAI-compatible endpoint is not configured yet.

Open $ENV_FILE and replace all three placeholders with values from any endpoint
that speaks the OpenAI chat-completions API:

  OPENAI_COMPATIBLE_BASE_URL=   currently ${OPENAI_COMPATIBLE_BASE_URL:-<unset>}
  OPENAI_COMPATIBLE_API_KEY=    currently a placeholder
  OPENAI_COMPATIBLE_MODEL=      currently ${OPENAI_COMPATIBLE_MODEL:-<unset>}

Then re-run this script. Your values stay in that git-ignored file and in your
own n8n credential store.

Two other options:

  ./reviewer/scripts/bootstrap.sh --configure-only
      brings the stack up with the placeholders still in place, so you can
      inspect the packaging. The agents will not be able to call a model.

  ./reviewer/scripts/bootstrap.sh --host-ollama
      uses a local Ollama model instead. No key and no account, but see the
      model-quality warning in reviewer/QUICKSTART.md.

EOF
      exit 2
    fi
    echo "endpoint placeholders retained (--configure-only): the stack will start,"
    echo "but no model call can succeed and no health check will claim one did."
  else
    ENDPOINT_CONFIGURED=1
    echo "endpoint configured: base URL ${OPENAI_COMPATIBLE_BASE_URL}, model ${OPENAI_COMPATIBLE_MODEL}"
    echo "api key: present (not printed, not logged, not committed)"
  fi
  MODEL="${OPENAI_COMPATIBLE_MODEL:-$PLACEHOLDER_MODEL}"
  COMPOSE_PROFILE=()
else
  MODEL="${CAPRA_OLLAMA_MODEL:-${CAPRA_LLM_MODEL:-llama3.2}}"
  if [ "$OLLAMA_MODE" = "host" ]; then
    OLLAMA_URL="http://host.docker.internal:11434"
    COMPOSE_PROFILE=()
  else
    OLLAMA_URL="http://ollama:11434"
    COMPOSE_PROFILE=(--profile container-llm)
  fi
  echo "fallback provider selected: local Ollama ($OLLAMA_MODE runtime, model $MODEL)"
  echo "no API key or account is used on this route."
fi

step "2/8 Synthetic domain inputs"
python3 "$HERE/scripts/gen_synthetic_inputs.py" --out "$HERE/fixtures"

step "3/8 Reviewer workflow export"
python3 "$HERE/scripts/make_reviewer_workflow.py" \
  --source "$REPO/workflows/CAPRA_Prototype_unified_patched.json" \
  --target "$HERE/workflows/CAPRA_reviewer_local.json" \
  --report "$HERE/workflows/transformation_report.json" \
  --provider "$PROVIDER" \
  --model "$MODEL"

step "4/8 Start containers"
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" ${COMPOSE_PROFILE[@]+"${COMPOSE_PROFILE[@]}"} up -d
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" ${COMPOSE_PROFILE[@]+"${COMPOSE_PROFILE[@]}"} ps

step "5/8 Wait for services"
wait_for() {
  local label="$1" url="$2" tries="${3:-60}"
  for _ in $(seq 1 "$tries"); do
    if curl -sf -o /dev/null "$url"; then echo "$label ready"; return 0; fi
    sleep 5
  done
  echo "$label did not become ready: $url" >&2
  return 1
}
wait_for "n8n"      "http://localhost:${CAPRA_N8N_PORT}/healthz"
wait_for "fuseki"   "http://localhost:${CAPRA_FUSEKI_PORT}/\$/ping"
if [ "$PROVIDER" = "ollama" ]; then
  if [ "$OLLAMA_MODE" = "container" ]; then
    wait_for "ollama (container)" "http://localhost:${CAPRA_OLLAMA_PORT}/api/tags"
  else
    wait_for "ollama (host)" "http://localhost:11434/api/tags" 12 \
      || { echo "start the host Ollama first with 'ollama serve'" >&2; exit 1; }
  fi
fi
wait_for "loki"     "http://localhost:${CAPRA_LOKI_PORT}/ready" 90 || echo "loki still warming up; dashboards will fill once it is ready"
wait_for "grafana"  "http://localhost:${CAPRA_GRAFANA_PORT}/api/health"

step "6/8 Fuseki ontology dataset"
# The workflow writes to /ontology/update. Fuseki's stock policy restricts that
# to the admin account, which would force the package to ship a password for the
# workflow to use. Install the local policy instead. The image's entrypoint
# rewrites shiro.ini on start, so copy it in rather than bind-mounting it.
if ! docker exec capra-reviewer-fuseki cmp -s /fuseki/shiro.ini /dev/stdin < "$HERE/fuseki/shiro.ini"; then
  docker cp "$HERE/fuseki/shiro.ini" capra-reviewer-fuseki:/fuseki/shiro.ini
  docker restart capra-reviewer-fuseki >/dev/null
  wait_for "fuseki (restarted)" "http://localhost:${CAPRA_FUSEKI_PORT}/\$/ping"
  echo "local Fuseki access policy installed"
fi
if curl -sf -o /dev/null "http://localhost:${CAPRA_FUSEKI_PORT}/ontology"; then
  echo "dataset 'ontology' already present"
else
  curl -sf -u "admin:capra-local-demo" -X POST \
    "http://localhost:${CAPRA_FUSEKI_PORT}/\$/datasets?dbType=tdb2&dbName=ontology" \
    && echo "dataset 'ontology' created"
fi
curl -sf -u "admin:capra-local-demo" -X POST \
  "http://localhost:${CAPRA_FUSEKI_PORT}/ontology/data" \
  -H "Content-Type: text/turtle" \
  --data-binary "@$HERE/ontology/capra_seed.ttl" >/dev/null \
  && echo "seed triples loaded"

step "7/8 Language model access"
ENDPOINT_VERIFIED=0
if [ "$PROVIDER" = "openai-compatible" ]; then
  if [ "$ENDPOINT_CONFIGURED" -eq 1 ]; then
    # A live call, made from inside the n8n container so that it proves the
    # container can reach the endpoint, not just the host. The key is passed
    # through the environment, never on the command line, and the response body
    # is not printed.
    echo "checking $OPENAI_COMPATIBLE_BASE_URL/models from inside the n8n container"
    if docker exec -e CAPRA_KEY="$OPENAI_COMPATIBLE_API_KEY" \
         -e CAPRA_BASE="$OPENAI_COMPATIBLE_BASE_URL" capra-reviewer-n8n \
         sh -c 'wget -q -O /dev/null --header="Authorization: Bearer $CAPRA_KEY" "$CAPRA_BASE/models"' 2>/dev/null; then
      ENDPOINT_VERIFIED=1
      echo "endpoint reachable and the key was accepted on /models"
    else
      echo "endpoint check FAILED: the n8n container could not list models at" >&2
      echo "  ${OPENAI_COMPATIBLE_BASE_URL}/models" >&2
      echo "Not every OpenAI-compatible server implements /models. If yours does" >&2
      echo "not, the stack is still correctly configured; the agents will tell" >&2
      echo "you on the first execution. Nothing here assumes success." >&2
    fi
  else
    echo "endpoint not configured; no call attempted and none claimed."
  fi
else
  if [ "$OLLAMA_MODE" = "container" ]; then
    if [ "$DO_PULL" -eq 1 ]; then
      echo "pulling $MODEL into the ollama container (first run downloads about 2 GB)"
      docker exec capra-reviewer-ollama ollama pull "$MODEL"
    fi
    docker exec capra-reviewer-ollama ollama list
    cat <<'NOTE'

Note. Docker Desktop on macOS gives containers no access to the Apple GPU, so
the containerised model runs on the virtual machine's CPUs and is very slow.
On macOS, install Ollama natively, pull the model, and re-run this script with
--host-ollama.
NOTE
  else
    if [ "$DO_PULL" -eq 1 ]; then
      echo "pulling $MODEL into the host ollama"
      ollama pull "$MODEL"
    fi
    ollama list
  fi
fi

python3 - "$ENV_FILE" "$ENDPOINT_VERIFIED" <<'PY'
import pathlib, sys
path, value = pathlib.Path(sys.argv[1]), sys.argv[2]
lines = path.read_text(encoding="utf-8").splitlines()
key = "CAPRA_ENDPOINT_VERIFIED="
if any(l.startswith(key) for l in lines):
    lines = [key + value if l.startswith(key) else l for l in lines]
else:
    lines.append(key + value)
path.write_text("\n".join(lines) + "\n", encoding="utf-8")
PY

step "8/8 Import workflow and credentials"
WORKDIR="$HERE/.import"
mkdir -p "$WORKDIR"
chmod 700 "$WORKDIR"
CRED_FILE="$WORKDIR/credentials.json"
: > "$CRED_FILE"
chmod 600 "$CRED_FILE"

# Written by Python from the environment so the key never appears in a shell
# command line, a here-document, or the terminal. The file lives in the
# git-ignored reviewer/.import directory and is deleted below.
CAPRA_PROVIDER="$PROVIDER" \
CAPRA_OLLAMA_URL="${OLLAMA_URL:-}" \
python3 - "$CRED_FILE" <<'PY'
import json, os, pathlib, sys

creds = [
    {
        "id": "capra-local-mongo",
        "name": "CAPRA Local Mongo",
        "type": "mongoDb",
        "data": {
            "configurationType": "connectionString",
            "connectionString": "mongodb://mongo:27017",
            "database": "capra",
        },
    }
]

if os.environ["CAPRA_PROVIDER"] == "openai-compatible":
    creds.append({
        "id": "capra-openai-compatible",
        "name": "CAPRA OpenAI-Compatible Endpoint",
        "type": "openAiApi",
        "data": {
            "apiKey": os.environ.get("OPENAI_COMPATIBLE_API_KEY", ""),
            "url": os.environ.get("OPENAI_COMPATIBLE_BASE_URL", ""),
        },
    })
else:
    creds.append({
        "id": "capra-local-ollama",
        "name": "CAPRA Local Ollama",
        "type": "ollamaApi",
        "data": {"baseUrl": os.environ["CAPRA_OLLAMA_URL"]},
    })

pathlib.Path(sys.argv[1]).write_text(json.dumps(creds, indent=2), encoding="utf-8")
PY

# /home/node is the n8n user's own directory inside the container. The files are
# streamed in as the 'node' user (docker cp would land them owned by root, which
# the n8n CLI cannot read) and are removed as soon as the import has read them.
CONTAINER_CRED=/home/node/.capra-import-credentials.json
CONTAINER_WF=/home/node/.capra-import-workflow.json
docker exec -i --user node capra-reviewer-n8n sh -c "umask 077; cat > $CONTAINER_CRED" < "$CRED_FILE"
docker exec -i --user node capra-reviewer-n8n sh -c "cat > $CONTAINER_WF" < "$HERE/workflows/CAPRA_reviewer_local.json"
docker exec --user node capra-reviewer-n8n n8n import:credentials --input="$CONTAINER_CRED"
docker exec --user node capra-reviewer-n8n n8n import:workflow --input="$CONTAINER_WF"
docker exec --user node capra-reviewer-n8n rm -f "$CONTAINER_CRED" "$CONTAINER_WF"
rm -rf "$WORKDIR"
echo "credential file removed from the host and from the container"

if [ "$PROVIDER" = "openai-compatible" ]; then
  LLM_LINE="OpenAI-compatible endpoint, model ${MODEL}"
  if [ "$ENDPOINT_VERIFIED" -eq 1 ]; then
    LLM_LINE="$LLM_LINE (live /models check passed)"
  elif [ "$ENDPOINT_CONFIGURED" -eq 1 ]; then
    LLM_LINE="$LLM_LINE (live check did NOT pass; see above)"
  else
    LLM_LINE="$LLM_LINE (NOT CONFIGURED; placeholders retained)"
  fi
else
  LLM_LINE="local Ollama fallback at $OLLAMA_URL, model ${MODEL}"
fi

cat <<EOF

CAPRA reviewer route is up.

  n8n editor      http://localhost:${CAPRA_N8N_PORT}
  Grafana         http://localhost:${CAPRA_GRAFANA_PORT}/d/capra-risk-register
  Fuseki          http://localhost:${CAPRA_FUSEKI_PORT}
  Loki            http://localhost:${CAPRA_LOKI_PORT}
  Language model  $LLM_LINE

Next: run ./reviewer/scripts/verify_route.sh, then open the n8n editor,
complete the local owner sign-up (any email and password; it never leaves your
machine), and follow reviewer/QUICKSTART.md from step 4.
EOF
