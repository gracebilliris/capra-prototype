#!/usr/bin/env python3
"""Run the Gamma suite and retain a deterministic validation summary."""

from __future__ import annotations

import hashlib
import io
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EVIDENCE = ROOT / "evidence" / "gamma-admissions-2026-10-02"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern="test_*.py")
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    output = stream.getvalue()
    sys.stdout.write(output)
    report = {
        "validation_id": "gamma-validation-2026-10-02",
        "evaluated_at": "2026-10-02T10:00:00Z",
        "command": "/usr/bin/python3 gamma/validate_gamma.py",
        "tests_run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "skipped": len(result.skipped),
        "status": "passed" if result.wasSuccessful() else "failed",
        "claim_boundary": "Passing tests support only the controlled mechanics they exercise.",
    }
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    report_path = EVIDENCE / "validation-report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    manifest_path = EVIDENCE / "release-manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["evidence_files"]["validation-report.json"] = sha256(report_path)
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    lines = [
        f"{sha256(path)}  {path.name}"
        for path in sorted(EVIDENCE.glob("*.json"))
    ]
    (EVIDENCE / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
