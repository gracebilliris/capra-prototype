# Deterministic admissions walkthrough

The External System fixture `gamma/fixtures/admissions_event.json` is synthetic
and outside CAPRA. DFL validates the adapter and source contract, removes the
disallowed `email` and `free_text` fields, and assigns one deterministic
`origin_event_id`. CPL uses the approved `mapping-admissions-purpose@1.0.0`
Mapping Record to create a Context Record in CL. The record preserves unknown
source confidence, AU processing location, EU data-subject location, and two
candidate obligations. These are assertions for review, not legal findings.

HIL first records a `Confirm` decision from the context-curator role. RIL then
produces a versioned Assessment Output and manifest. Its result is
`review_required`, not compliant/non-compliant. FRL proposes a mapping-rationale
revision. A different HIL reviewer approves it; an administrator applies and
then rolls it back. All status transitions remain in history. The post-review
record links the source, context, assessment, risk and revision identifiers.

| Step | Layer | Stage/interface | Test/evidence | Unsupported property |
|---|---|---|---|---|
| External fixture | outside CAPRA | source contract | `source-event.json` | source authenticity |
| Validate/minimise | DFL | Federate v1 | redaction tests; `stage-records.json` | complete PII detection |
| Build context | CPL + CL | Contextualise v1 | context tests; `stage-records.json` | contextual truth |
| Early decision | HIL | context-validation v1 | Confirm/Correct/Reject/Defer tests | reviewer expertise |
| Criteria observation | RIL + CL | Assess v1 | `assessment-output.json` | legal or semantic correctness |
| Proposal | FRL + CL | Refine v1 | governance tests; `change-history.json` | improvement effectiveness |
| Durable decision | HIL | Review v1 | `post-assessment-review.json` | organisational authorisation |
| Apply/rollback | FRL + HIL | controlled administration | rollback test/history | operational reliability |

`lineage-trace.json` reconstructs the chain by `origin_event_id`; no timestamp
matching is used.
