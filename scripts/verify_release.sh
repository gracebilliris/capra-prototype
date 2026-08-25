#!/usr/bin/env bash
set -euo pipefail

TAG="v1.0-icse-demo"
EXPECTED_SHA="022d22dddff8257e40a296048c8608cd5523cc06"
MANIFEST="RELEASE_MANIFEST.sha256"

cd "$(git rev-parse --show-toplevel)"

echo "[1/4] Verifying annotated tag if a signature is present..."
git tag --verify "$TAG" || true

echo "[2/4] Verifying tag commit SHA..."
actual_sha="$(git rev-parse "${TAG}^{commit}")"
if [[ "$actual_sha" != "$EXPECTED_SHA" ]]; then
  echo "ERROR: ${TAG} resolves to ${actual_sha}, expected ${EXPECTED_SHA}" >&2
  exit 1
fi
echo "OK: ${TAG} -> ${actual_sha}"

echo "[3/4] Selecting checksum tool..."
if command -v sha256sum >/dev/null 2>&1; then
  checksum_cmd=(sha256sum)
elif command -v shasum >/dev/null 2>&1; then
  checksum_cmd=(shasum -a 256)
else
  echo "ERROR: need sha256sum or shasum" >&2
  exit 1
fi

echo "[4/4] Writing ${MANIFEST} for workflows, dashboards, and test_artefacts..."
{
  find workflows -maxdepth 1 -type f -name '*.json' -print
  find dashboards -type f -name '*.json' -print
  find test_artefacts -type f -print
} | LC_ALL=C sort | while IFS= read -r path; do
  "${checksum_cmd[@]}" "$path"
done > "$MANIFEST"

wc -l "$MANIFEST"
echo "Manifest written: ${MANIFEST}"
echo "Review it, but do not commit it unless Grace explicitly decides to include it."
echo "Command that would stage it later: git add ${MANIFEST}"
