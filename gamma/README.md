# CAPRA Gamma reference implementation

Gamma is the completed, bounded research-prototype iteration of CAPRA. It is a
self-contained Python standard-library implementation and does not require
n8n, MongoDB, Fuseki, Grafana, Ollama, an LLM, or network access.

CAPRA retains exactly six conceptual layers: Data Federation (DFL), Context
Processing (CPL), the shared Context Layer substrate (CL), Risk Intelligence
(RIL), Feedback & Refinement (FRL), and Human Interaction (HIL). Five
executable stages—Federate, Contextualise, Assess, Refine, and Review—operate
over CL. External Systems are outside CAPRA. There is no seventh compliance,
governance, or jurisdiction layer.

## Run

From the repository root:

```bash
/usr/bin/python3 gamma/run_gamma.py
gamma/run_tests.sh
```

The walkthrough is deterministic and rewrites
`gamma/evidence/gamma-admissions-2026-10-02/` byte-for-byte. `SHA256SUMS`
checks every retained JSON artefact. The test command also writes
`validation-report.json` and refreshes the evidence hashes.

## Implemented profile

- a deterministic admissions walkthrough, distinct from the retained
  `reviewer/fixtures/environmental_air_quality.csv` Beta stress fixture;
- versioned layer/stage contracts and governed artefact registry;
- normative source, Context Record, Mapping Record, Assessment Output and
  Review Decision schemas with required fields and controlled states;
- canonical Context Record with provenance, effective time, ownership,
  candidate obligations, business purpose, uncertainty, missingness and
  explicit validation state;
- approved/active Mapping Record selection and refusal of drafts;
- source boundary validation, telemetry allowlist, redaction and quarantine;
- `origin_event_id` lineage from source through durable review;
- freshness/conflict handling and Confirm/Correct/Reject/Defer context review;
- Assessment Output and manifest with exact IDs, versions and checksums;
- distinct proposal, approval, application and rollback roles with immutable
  status history;
- role-gated detailed evidence, payload-free synthetic public view, and
  configurable retention expiry, legal hold and deletion receipts;
- deterministic admissions walkthrough and automated negative controls.

## Survey-informed refinement

The completed expert survey included 41 valid responses. All 15 criterion
items met the predefined consensus rule, with agreement ranging from 82.9% to
97.6%. This agreement is design feedback, not validation or operational
effectiveness evidence. It informed Gamma refinements to terminology,
interfaces, governed context, provenance and uncertainty, human review,
versioned change governance, telemetry controls, and the visibility of the
worked scenario and evidence chain.

## Claim boundary

Gamma demonstrates these mechanics for controlled synthetic records. It is not
production-ready and does not establish legal compliance, legal applicability,
privacy effectiveness, semantic correctness, calibrated confidence, source
authenticity, reviewer expertise, organisational authorisation, or operational
reliability. Candidate obligations are reviewer-defined context and every
criteria observation remains `review_required`.

Historical Alpha/Beta reports remain historical evidence. Their metrics and
the 20-case no-op stress package are not Gamma results; the latter supports
trigger/instrumentation continuity only.

These files describe the completed local Gamma research iteration. Editing
repository and website source does not establish that Gamma has been publicly
deployed or that a public release has been published.
