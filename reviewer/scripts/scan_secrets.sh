#!/usr/bin/env bash
# CAPRA reviewer route — targeted secret and placeholder scan.
#
# Two jobs:
#
#   1. No credential-shaped material may appear in anything the repository
#      tracks or ships: workflow JSON, transformation report, compose file,
#      scripts, docs, run logs, manifests, screenshots' sidecar files.
#   2. Every endpoint value that DOES appear in a tracked file must be an
#      unmistakable placeholder, not a plausible-looking string.
#
# Run it before packaging, and after any change to the reviewer route.
#
#   ./reviewer/scripts/scan_secrets.sh

set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO="$(cd "$HERE/.." && pwd)"
cd "$REPO"

FAILURES=0
pass() { printf '%-46s ok\n'   "$1"; }
fail() { printf '%-46s FAIL  %s\n' "$1" "$2"; FAILURES=$((FAILURES + 1)); }

# ---------------------------------------------------------------------------
# 1. Runtime files that hold real values must be ignored, and must not be tracked
# ---------------------------------------------------------------------------
for path in reviewer/.env reviewer/.import/; do
  if git check-ignore -q "$path" 2>/dev/null; then
    pass "ignored: $path"
  else
    fail "ignored: $path" "not matched by .gitignore"
  fi
  if git ls-files --error-unmatch "${path%/}" >/dev/null 2>&1; then
    fail "untracked: $path" "this file is tracked and must not be"
  else
    pass "untracked: $path"
  fi
done

# ---------------------------------------------------------------------------
# 2. Credential-shaped material in tracked files
# ---------------------------------------------------------------------------
# Deliberately narrow, so the scan means something when it passes. Each pattern
# is anchored so that documented angle-bracket placeholders such as
# "<user>:<password>@" and ordinary words such as "risk-intelligence-layer" do
# not match; a hit therefore means a real credential shape, not a false alarm.
PATTERNS=(
  '\bsk-[A-Za-z0-9]{20,}'                       # OpenAI-style key
  '\bsk-(proj|svcacct|admin)-[A-Za-z0-9_-]{20,}'
  'sk_live_[A-Za-z0-9]{8,}'
  'AKIA[0-9A-Z]{16}'                            # AWS access key id
  'gh[pousr]_[A-Za-z0-9]{20,}'                  # GitHub tokens
  'xox[baprs]-[A-Za-z0-9-]{10,}'                # Slack tokens
  '[Bb]earer [A-Za-z0-9._-]{20,}'
  'eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.' # JWT
  '[A-Za-z0-9-]+\.openai\.azure\.com'           # Azure resource host
  'api[._-]?key["'"'"' ]*[:=]["'"'"' ]*[A-Za-z0-9_-]{16,}'
  'mongodb\+srv://[^<:"[:space:]]+:[^<@"[:space:]]+@'  # Atlas string with a real password
  'https://[0-9]+:[A-Za-z0-9]+@[a-z0-9.-]*grafana\.net'
)

SCAN_TARGETS=()
while IFS= read -r f; do SCAN_TARGETS+=("$f"); done < <(
  git ls-files -- reviewer docs workflows dashboards n8n_snippets scripts \
    '*.md' '*.json' '*.yml' '*.yaml' '*.sh' '*.py' '*.cff' 2>/dev/null | sort -u
)
# Untracked reviewer artefacts are shipped too, so scan them as well.
while IFS= read -r f; do
  [ -n "$f" ] && SCAN_TARGETS+=("$f")
done < <(find reviewer/logs reviewer/workflows -type f \( -name '*.json' -o -name '*.md' \) 2>/dev/null)

if [ "${#SCAN_TARGETS[@]}" -eq 0 ]; then
  fail "scan targets" "no files resolved"
else
  pass "scan targets (${#SCAN_TARGETS[@]} files)"
fi

for pattern in "${PATTERNS[@]}"; do
  HITS="$(grep -nEI --exclude='*.png' --exclude='*.pdf' -- "$pattern" "${SCAN_TARGETS[@]}" 2>/dev/null \
          | grep -v 'reviewer/scripts/scan_secrets.sh' || true)"
  if [ -n "$HITS" ]; then
    fail "no match: $pattern" "$(printf '%s' "$HITS" | head -3 | tr '\n' ' ')"
  else
    pass "no match: $pattern"
  fi
done

# ---------------------------------------------------------------------------
# 3. Binary artefacts that ship with the package
# ---------------------------------------------------------------------------
BIN_HITS="$(find dashboard_screenshots reviewer -type f \( -name '*.png' -o -name '*.jpg' \) 2>/dev/null \
  | while IFS= read -r img; do
      if strings "$img" 2>/dev/null | grep -qE 'sk-[A-Za-z0-9_-]{16,}|[A-Za-z0-9-]+\.openai\.azure\.com'; then
        echo "$img"
      fi
    done)"
if [ -n "$BIN_HITS" ]; then
  fail "no key strings in shipped images" "$BIN_HITS"
else
  pass "no key strings in shipped images"
fi

# ---------------------------------------------------------------------------
# 4. Tracked endpoint values must be unmistakable placeholders
# ---------------------------------------------------------------------------
EXPECTED_PLACEHOLDERS=(
  'OPENAI_COMPATIBLE_BASE_URL=https://replace.example/v1'
  'OPENAI_COMPATIBLE_API_KEY=replace-with-your-key'
  'OPENAI_COMPATIBLE_MODEL=replace-with-your-model-name'
)
for expected in "${EXPECTED_PLACEHOLDERS[@]}"; do
  if grep -qF -- "$expected" reviewer/env.template; then
    pass "placeholder in env.template: ${expected%%=*}"
  else
    fail "placeholder in env.template: ${expected%%=*}" "expected exactly '$expected'"
  fi
done

# The committed template must contain no assigned value other than placeholders,
# ports, image tags, and an empty encryption key.
if grep -qE '^(OPENAI_COMPATIBLE_(BASE_URL|API_KEY|MODEL))=.*(replace)' reviewer/env.template \
   && ! grep -qE '^N8N_ENCRYPTION_KEY=.+' reviewer/env.template; then
  pass "env.template carries no live value"
else
  fail "env.template carries no live value" "a non-placeholder value is present"
fi

# The generated workflow and its report must never carry endpoint values.
for artefact in reviewer/workflows/CAPRA_reviewer_local.json reviewer/workflows/transformation_report.json; do
  if [ ! -f "$artefact" ]; then
    fail "no endpoint value in $artefact" "file missing; run bootstrap.sh"
  elif grep -qE 'apiKey|Authorization|https?://[a-z0-9.-]+/v1' "$artefact"; then
    fail "no endpoint value in $artefact" "endpoint or key material present"
  else
    pass "no endpoint value in $artefact"
  fi
done

# Run logs and captured console transcripts record counts and status, not
# configuration. An assigned key or an Authorization header in either is a leak;
# the word "API key" in prose is not.
LOG_HITS="$(grep -lE 'OPENAI_COMPATIBLE_API_KEY=[^[:space:]]|"apiKey"[[:space:]]*:[[:space:]]*"[^"]+"|Authorization: Bearer [A-Za-z0-9._-]{16,}' \
  reviewer/logs/*.json reviewer/logs/*.txt 2>/dev/null || true)"
if [ -n "$LOG_HITS" ]; then
  fail "no endpoint value in run logs" "$LOG_HITS"
else
  pass "no endpoint value in run logs"
fi

echo
if [ "$FAILURES" -eq 0 ]; then
  echo "Secret scan clean."
else
  echo "$FAILURES scan check(s) failed. Fix before packaging."
  exit 1
fi
