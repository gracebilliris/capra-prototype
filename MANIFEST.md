# ICSE Tool Demo Release Artefact Manifest

New reviewer-facing files prepared for the `v1.0-icse-demo` closeout:

| Path | Purpose |
|---|---|
| `RELEASE_CHECKLIST.md` | Manual Zenodo DOI minting and release-closeout runbook. |
| `CITATION.cff` | Citation File Format metadata with placeholder DOI slot. |
| `.github/RELEASE_TEMPLATE.md` | Exact GitHub Release body for tag `v1.0-icse-demo`. |
| `scripts/verify_release.sh` | Non-destructive tag/SHA and checksum manifest verifier. |
| `scripts/build_release_archive.sh` | Non-destructive source archive builder for release review. |
| `MANIFEST.md` | This file. |

Generated runtime files intentionally not staged for release by default:

- `RELEASE_MANIFEST.sha256`
- `capra-prototype-v1.0-icse-demo.tar.gz`
