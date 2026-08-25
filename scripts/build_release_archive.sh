#!/usr/bin/env bash
set -euo pipefail

TAG="v1.0-icse-demo"
ARCHIVE="capra-prototype-v1.0-icse-demo.tar.gz"
PREFIX="capra-prototype-v1.0-icse-demo/"

cd "$(git rev-parse --show-toplevel)"

echo "Building release archive for ${TAG}..."
git archive --format=tar.gz --prefix="$PREFIX" -o "$ARCHIVE" "$TAG"

if command -v sha256sum >/dev/null 2>&1; then
  sha256sum "$ARCHIVE"
elif command -v shasum >/dev/null 2>&1; then
  shasum -a 256 "$ARCHIVE"
else
  echo "ERROR: need sha256sum or shasum" >&2
  exit 1
fi

echo "Archive written: ${ARCHIVE}"
echo "If Grace wants an external handoff copy, copy this archive manually after review."
