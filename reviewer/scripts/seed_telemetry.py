#!/usr/bin/env python3
"""Seed the reviewer route's ingestion collection with synthetic agent telemetry.

Scope. This replaces the *mock external system*, not a CAPRA stage. In the
published workflow the mock external system is itself two language-model agents
that read a domain file and invent telemetry. That generator asks a model for a
large nested JSON document, and a small local model does not reliably return
one, so on the reviewer route the downstream stages receive nothing. This script
produces the same kind of input deterministically from the same synthetic
fixture, so the five CAPRA stages (federate, contextualise, assess, refine,
review) run on real input rather than on nothing.

The five stages themselves are untouched and still use the language model.

Documents are written to `capra.local_raw` in the shape the federation stage
reads, `{"results": {"item": <event>}}`, with an `ingestTimestamp` used by the
federation stage's sort.

Usage:
    python3 reviewer/scripts/seed_telemetry.py --domain admissions --events 12
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import pathlib
import random
import subprocess
import sys
import time

DOMAIN_FIXTURES = {
    "admissions": "admissiondata.csv",
    "healthcare": "EHR.csv",
    "retail": "retail_employees.csv",
}

DOMAIN_PROFILE = {
    "admissions": {
        "source_system": "university-admissions-platform",
        "actors": ["admissions-agent", "financial-aid-agent", "peer-student-agent"],
        "tools": ["applicant-record-reader", "aid-eligibility-calculator", "cohort-report-writer"],
        "data_categories": ["academic-record", "protected-attribute", "free-text-statement"],
        "purposes": ["admission-assessment", "financial-aid-assessment", "cohort-reporting"],
        "recipients": ["admissions-committee", "financial-aid-office", "external-analytics-service"],
    },
    "healthcare": {
        "source_system": "clinical-records-platform",
        "actors": ["care-coordination-agent", "billing-agent", "research-export-agent"],
        "tools": ["encounter-reader", "discharge-summariser", "cohort-export-writer"],
        "data_categories": ["health-record", "demographic-attribute", "admission-diagnosis"],
        "purposes": ["care-coordination", "billing-reconciliation", "secondary-research"],
        "recipients": ["care-team", "billing-provider", "external-research-partner"],
    },
    "retail": {
        "source_system": "store-operations-platform",
        "actors": ["rostering-agent", "loss-prevention-agent", "marketing-agent"],
        "tools": ["staff-record-reader", "shift-planner", "segment-builder"],
        "data_categories": ["employment-record", "contact-detail", "location-assignment"],
        "purposes": ["shift-planning", "loss-prevention-review", "marketing-segmentation"],
        "recipients": ["store-manager", "regional-office", "external-marketing-service"],
    },
}

ACTIONS = ["read", "transform", "transmit", "aggregate", "export"]


def build_events(domain: str, rows: list[dict], count: int) -> list[dict]:
    profile = DOMAIN_PROFILE[domain]
    seed = int(hashlib.sha256(domain.encode()).hexdigest()[:8], 16)
    rng = random.Random(seed)
    base_ms = 1_767_225_600_000  # fixed base so identifiers are reproducible
    events = []
    for index in range(count):
        row = rows[index % len(rows)] if rows else {}
        row_key = next(iter(row.values()), str(index)) if row else str(index)
        event_id = "evt-{}-{:04d}".format(
            hashlib.sha256(f"{domain}:{row_key}:{index}".encode()).hexdigest()[:10], index
        )
        actor = profile["actors"][index % len(profile["actors"])]
        recipient = profile["recipients"][index % len(profile["recipients"])]
        events.append({
            "event_id": event_id,
            "source_event_id": f"{profile['source_system']}:{index:06d}",
            "source_system": profile["source_system"],
            "domain": domain,
            "timestamp": base_ms + index * 15_000,
            "actor": {"id": actor, "role": actor.replace("-agent", ""), "type": "software-agent"},
            "action": ACTIONS[index % len(ACTIONS)],
            "tool": {"name": profile["tools"][index % len(profile["tools"])], "invocation": f"inv-{index:04d}"},
            "data_object": {
                "id": f"rec-{index:06d}",
                "category": profile["data_categories"][index % len(profile["data_categories"])],
                "fields_touched": sorted(row.keys())[:5],
            },
            "transmission": {"recipient": recipient, "channel": "internal-api" if index % 3 else "external-api"},
            "purpose": profile["purposes"][index % len(profile["purposes"])],
            "synthetic": True,
            "generator": "reviewer/scripts/seed_telemetry.py",
            "nonce": rng.randrange(10**6),
        })
    return events


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--domain", default="admissions", choices=sorted(DOMAIN_FIXTURES))
    parser.add_argument("--events", type=int, default=12)
    parser.add_argument("--fixtures", default="reviewer/fixtures")
    parser.add_argument("--container", default="capra-reviewer-mongo")
    parser.add_argument("--database", default="capra")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    fixture = pathlib.Path(args.fixtures) / DOMAIN_FIXTURES[args.domain]
    rows: list[dict] = []
    if fixture.exists():
        with fixture.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
    else:
        print(f"fixture not found, seeding without row context: {fixture}", file=sys.stderr)

    events = build_events(args.domain, rows, args.events)
    now_ms = int(time.time() * 1000)
    documents = [
        {"results": {"item": event}, "ingestTimestamp": now_ms + index}
        for index, event in enumerate(events)
    ]

    if args.dry_run:
        print(json.dumps(documents[:2], indent=2))
        print(f"{len(documents)} documents would be inserted into {args.database}.local_raw")
        return 0

    script = (
        f"db = db.getSiblingDB({json.dumps(args.database)});\n"
        f"var docs = {json.dumps(documents)};\n"
        "var res = db.local_raw.insertMany(docs);\n"
        "print(JSON.stringify({inserted: Object.keys(res.insertedIds).length, "
        "total: db.local_raw.countDocuments({})}));\n"
    )
    completed = subprocess.run(
        ["docker", "exec", "-i", args.container, "mongosh", "--quiet"],
        input=script,
        text=True,
        capture_output=True,
        check=False,
    )
    sys.stdout.write(completed.stdout)
    if completed.returncode != 0:
        sys.stderr.write(completed.stderr)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
