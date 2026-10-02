#!/usr/bin/env python3
"""Run the deterministic CAPRA Gamma admissions walkthrough and retain evidence."""

from __future__ import annotations

import json
from pathlib import Path

from capra_gamma import FIXED_NOW, GammaEngine, checksum


ROOT = Path(__file__).resolve().parent
EVIDENCE = ROOT / "evidence" / "gamma-admissions-2026-10-02"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    engine = GammaEngine()
    source = read_json(ROOT / "fixtures" / "admissions_event.json")
    federated = engine.federate(source)
    context = engine.contextualise(federated)
    context = engine.validate_context(
        context,
        decision="Confirm",
        reviewer_role="context_curator",
        reviewer_id="curator-gamma-01",
        rationale="Synthetic fixture fields are complete for this controlled walkthrough.",
    )
    assessment = engine.assess(context)
    proposal = engine.propose_change(assessment, requested_by="analyst-gamma-01")
    review = engine.review_assessment(
        assessment,
        proposal,
        decision="Approve",
        reviewer_id="reviewer-gamma-01",
        rationale="Approve governance-mechanics demonstration; no effectiveness claim is made.",
    )
    applied = engine.apply_change(proposal["revision_id"], actor="admin-gamma-01")
    rolled_back = engine.rollback_change(
        proposal["revision_id"],
        actor="admin-gamma-01",
        reason="Exercise deterministic rollback while retaining immutable status history.",
    )
    review["application_status"] = rolled_back["application_status"]
    trace = engine.trace(federated["origin_event_id"])

    EVIDENCE.mkdir(parents=True, exist_ok=True)
    outputs = {
        "source-event.json": source,
        "stage-records.json": engine.stage_records,
        "assessment-output.json": assessment,
        "post-assessment-review.json": review,
        "change-history.json": rolled_back,
        "lineage-trace.json": trace,
        "redaction-log.json": engine.redactions,
        "quarantine-log.json": engine.quarantine,
    }
    for name, value in outputs.items():
        write_json(EVIDENCE / name, value)

    source_paths = [
        ROOT / "capra_gamma.py",
        ROOT / "run_gamma.py",
        ROOT / "validate_gamma.py",
        ROOT / "README.md",
        ROOT / "implementation-trace.csv",
        ROOT / "contracts" / "contracts.json",
        ROOT / "contracts" / "schemas.json",
        ROOT / "registry" / "artefacts.json",
        ROOT / "fixtures" / "admissions_event.json",
        ROOT / "docs" / "WORKED_SCENARIO.md",
        ROOT / "docs" / "TELEMETRY_THREAT_MODEL.md",
        ROOT / "tests" / "test_contracts.py",
        ROOT / "tests" / "test_gamma.py",
    ]
    release = {
        "release_id": "capra-gamma-2026-10-02",
        "iteration_label": "Gamma",
        "generated_at": FIXED_NOW,
        "base_commit": "9510cc093e69c41d38cf10985f555d84ba47a31a",
        "worktree_note": "Generated while integrating around declared pre-existing user changes; no clean-tree claim.",
        "topology": {
            "conceptual_layers": ["DFL", "CPL", "CL", "RIL", "FRL", "HIL"],
            "executable_stages": ["Federate", "Contextualise", "Assess", "Refine", "Review"],
            "context_layer_role": "shared substrate, not a serial stage",
            "external_systems": "outside CAPRA",
        },
        "source_files": {
            str(path.relative_to(ROOT.parent)): checksum(path.read_bytes()) for path in source_paths
        },
        "evidence_files": {
            name: checksum((EVIDENCE / name).read_bytes()) for name in sorted(outputs)
        },
        "claim_boundaries": [
            "research prototype only",
            "no production-readiness claim",
            "no legal-compliance or legal-validity claim",
            "no privacy-effectiveness claim",
            "no semantic-correctness claim",
            "no operational-reliability claim",
        ],
    }
    write_json(EVIDENCE / "release-manifest.json", release)
    hash_lines = []
    for path in sorted(EVIDENCE.glob("*.json")):
        hash_lines.append(f"{checksum(path.read_bytes())}  {path.name}")
    (EVIDENCE / "SHA256SUMS").write_text("\n".join(hash_lines) + "\n", encoding="utf-8")
    print(f"Gamma walkthrough complete: {trace['origin_event_id']}")
    print(f"Stages retained: {', '.join(trace['stages'])}")
    print(f"Complete identifier trace: {str(trace['complete']).lower()}")
    print(f"Evidence: {EVIDENCE.relative_to(ROOT.parent)}")
    print(f"Evidence files before validation report: {len(outputs) + 2}")


if __name__ == "__main__":
    main()
