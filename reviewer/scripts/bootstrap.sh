#!/usr/bin/env bash
# CAPRA reviewer route — one-command bootstrap.
#
# Brings up the local stack, provisions the Fuseki dataset, pulls the local
# language model, imports the credential-free workflow and its two local
# credentials, and prints the reviewer URLs.
#
# No account, API key, or paid service is required. Nothing in this script
# writes a secret to disk beyond a locally generated n8n encryption key, which
# stays in reviewer/.env and is git-ignored.
#
# Usage:
#   ./reviewer/scripts/bootstrap.sh            # full setup
#   ./reviewer/scripts/bootstrap.sh --no-pull  # skip the model download

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO="$(cd "$HERE/.." && pwd)"
COMPOSE_FILE="$HERE/docker-compose.reviewer.yml"
ENV_FILE="$HERE/.env"
MODEL="${CAPRA_LLM_MODEL:-llama3.2}"
DO_PULL=1
LLM_MODE="container"

for arg in "$@"; do
  case "$arg" in
    --no-pull) DO_PULL=0 ;;
    --host-ollama) LLM_MODE="host" ;;
    --container-ollama) LLM_MODE="container" ;;
    *) echo "unknown argument: $arg" >&2; exit 2 ;;
  esac
done

if [ "$LLM_MODE" = "host" ]; then
  OLLAMA_URL="http://host.docker.internal:11434"
  COMPOSE_PROFILE=()
else
  OLLAMA_URL="http://ollama:11434"
  COMPOSE_PROFILE=(--profile container-llm)
fi

step() { printf '\n=== %s ===\n' "$1"; }

step "0/8 Preconditions"
command -v docker >/dev/null || { echo "docker is required" >&2; exit 1; }
docker compose version >/dev/null || { echo "docker compose v2 is required" >&2; exit 1; }
command -v python3 >/dev/null || { echo "python3 is required" >&2; exit 1; }
echo "docker $(docker version --format '{{.Server.Version}}')"

step "1/8 Local environment file"
if [ ! -f "$ENV_FILE" ]; then
  KEY="$(python3 -c 'import secrets; print(secrets.token_hex(16))')"
  cat > "$ENV_FILE" <<EOF
# Generated locally by reviewer/scripts/bootstrap.sh. Not a shared secret and
# not committed: it only encrypts the local n8n credential store.
N8N_ENCRYPTION_KEY=$KEY
CAPRA_N8N_PORT=5679
CAPRA_MONGO_PORT=27019
CAPRA_FUSEKI_PORT=3031
CAPRA_OLLAMA_PORT=11435
CAPRA_LOKI_PORT=3101
CAPRA_GRAFANA_PORT=3002
CAPRA_LLM_MODEL=$MODEL
# The released docs/docker-compose.yml pinned n8n 1.108.0, which predates the
# node type versions in the released workflow export. 2.6.4 resolves all of them.
CAPRA_N8N_IMAGE=n8nio/n8n:2.6.4
CAPRA_CONCURRENCY=5
EOF
  echo "created $ENV_FILE"
else
  echo "reusing existing $ENV_FILE"
fi
# shellcheck disable=SC1090
set -a; . "$ENV_FILE"; set +a

step "2/8 Synthetic domain inputs"
python3 "$HERE/scripts/gen_synthetic_inputs.py" --out "$HERE/fixtures"

step "3/8 Reviewer workflow export"
python3 "$HERE/scripts/make_reviewer_workflow.py" \
  --source "$REPO/workflows/CAPRA_Prototype_unified_patched.json" \
  --target "$HERE/workflows/CAPRA_reviewer_local.json" \
  --report "$HERE/workflows/transformation_report.json" \
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
if [ "$LLM_MODE" = "container" ]; then
  wait_for "ollama (container)" "http://localhost:${CAPRA_OLLAMA_PORT}/api/tags"
else
  wait_for "ollama (host)" "http://localhost:11434/api/tags" 12 \
    || { echo "start the host Ollama first with 'ollama serve'" >&2; exit 1; }
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

step "7/8 Local language model"
if [ "$LLM_MODE" = "container" ]; then
  if [ "$DO_PULL" -eq 1 ]; then
    echo "pulling $MODEL into the ollama container (first run downloads about 2 GB)"
    docker exec capra-reviewer-ollama ollama pull "$MODEL"
  fi
  docker exec capra-reviewer-ollama ollama list
  cat <<'NOTE'

Note. Docker Desktop on macOS gives containers no access to the Apple GPU, so
the containerised model runs on the virtual machine's CPUs and is very slow.
On macOS, install Ollama natively, run "ollama pull llama3.2", and re-run this
script with --host-ollama. Both routes are credential-free.
NOTE
else
  if [ "$DO_PULL" -eq 1 ]; then
    echo "pulling $MODEL into the host ollama"
    ollama pull "$MODEL"
  fi
  ollama list
fi

step "8/8 Import workflow and local credentials"
WORKDIR="$HERE/.import"
mkdir -p "$WORKDIR"
cat > "$WORKDIR/credentials.json" <<'EOF'
[
  {
    "id": "capra-local-mongo",
    "name": "CAPRA Local Mongo",
    "type": "mongoDb",
    "data": {
      "configurationType": "connectionString",
      "connectionString": "mongodb://mongo:27017",
      "database": "capra"
    }
  },
  {
    "id": "capra-local-ollama",
    "name": "CAPRA Local Ollama",
    "type": "ollamaApi",
    "data": {
      "baseUrl": "__OLLAMA_URL__"
    }
  }
]
EOF
python3 -c 'import pathlib,sys; p=pathlib.Path(sys.argv[1]); p.write_text(p.read_text().replace("__OLLAMA_URL__", sys.argv[2]))' \
  "$WORKDIR/credentials.json" "$OLLAMA_URL"
docker cp "$WORKDIR/credentials.json" capra-reviewer-n8n:/tmp/credentials.json
docker cp "$HERE/workflows/CAPRA_reviewer_local.json" capra-reviewer-n8n:/tmp/workflow.json
docker exec capra-reviewer-n8n n8n import:credentials --input=/tmp/credentials.json
docker exec capra-reviewer-n8n n8n import:workflow --input=/tmp/workflow.json
rm -rf "$WORKDIR"

cat <<EOF

CAPRA reviewer route is up.

  n8n editor      http://localhost:${CAPRA_N8N_PORT}
  Grafana         http://localhost:${CAPRA_GRAFANA_PORT}/d/capra-risk-register
  Fuseki          http://localhost:${CAPRA_FUSEKI_PORT}
  Language model  $OLLAMA_URL ($LLM_MODE mode, model $MODEL)
  Loki            http://localhost:${CAPRA_LOKI_PORT}

Next: open the n8n editor, complete the local owner sign-up (any email and
password; it never leaves your machine), open "CAPRA Reviewer Route (local,
credential-free)", and follow reviewer/QUICKSTART.md from step 4.
EOF
