"""Bounded, deterministic CAPRA Gamma reference implementation.

This module uses only the Python standard library. It implements governance and
traceability mechanics for controlled synthetic cases; it does not make legal,
privacy-effectiveness, semantic-correctness, reliability, or production claims.
"""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from uuid import NAMESPACE_URL, uuid5

GAMMA_LABEL = "Gamma"
FIXED_NOW = "2026-10-02T10:00:00Z"
ROLES = {"context_curator", "risk_analyst", "reviewer", "administrator"}


class GammaError(ValueError):
    """A controlled refusal or validation failure."""


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def checksum(value: Any) -> str:
    raw = value if isinstance(value, bytes) else canonical_json(value).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def stable_id(kind: str, *parts: Any) -> str:
    material = "|".join(str(part) for part in parts)
    return f"{kind}-{uuid5(NAMESPACE_URL, 'capra-gamma|' + material)}"


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class GammaEngine:
    """Five executable stages over a shared in-memory Context Layer substrate."""

    source_required = {
        "source_record_id",
        "source_system",
        "source_version",
        "adapter_id",
        "adapter_version",
        "trusted_source",
        "domain",
        "observed_at",
        "business_purpose",
        "context_owner_id",
        "payload",
    }
    payload_allowlist = {
        "application_id",
        "school_type",
        "urm",
        "score_band",
        "gpa_band",
        "decision",
        "processing_location",
        "data_subject_location",
        "candidate_obligations",
        "source_confidence",
    }
    prohibited_fields = {"name", "email", "phone", "address", "free_text", "raw_prompt"}
    role_actions = {
        "context_curator": {"validate_context", "approve_mapping"},
        "risk_analyst": {"assess", "propose_change"},
        "reviewer": {"post_review", "approve_change", "authorise_rollback"},
        "administrator": {"apply_change", "rollback_change", "expire_records"},
    }

    def __init__(self, registry_path: Optional[Path] = None, now: str = FIXED_NOW):
        root = Path(__file__).resolve().parent
        self.now = now
        self.registry_path = registry_path or root / "registry" / "artefacts.json"
        self.registry = json.loads(self.registry_path.read_text(encoding="utf-8"))
        self.context_store: Dict[str, List[Dict[str, Any]]] = {}
        self.quarantine: List[Dict[str, Any]] = []
        self.stage_records: List[Dict[str, Any]] = []
        self.reviews: List[Dict[str, Any]] = []
        self.changes: Dict[str, Dict[str, Any]] = {}
        self.redactions: List[Dict[str, Any]] = []
        self.deletion_receipts: List[Dict[str, Any]] = []

    def _require_role(self, role: str, action: str) -> None:
        if role not in ROLES or action not in self.role_actions.get(role, set()):
            raise GammaError(f"role {role!r} is not authorised for {action}")

    def _record(self, stage: str, origin_event_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
        item = {
            "stage": stage,
            "stage_contract": f"capra.gamma.{stage}.v1",
            "origin_event_id": origin_event_id,
            **copy.deepcopy(body),
        }
        self.stage_records.append(item)
        return item

    def _quarantine(self, source: Any, reason: str) -> Dict[str, Any]:
        item = {
            "quarantine_id": stable_id("quarantine", reason, checksum(source)),
            "reason": reason,
            "record_checksum": checksum(source),
            "recorded_at": self.now,
        }
        self.quarantine.append(item)
        return item

    def federate(self, source: Dict[str, Any]) -> Dict[str, Any]:
        """DFL: validate an untrusted boundary and minimise admitted telemetry."""
        missing = sorted(self.source_required - set(source))
        if missing:
            self._quarantine(source, "missing required fields: " + ",".join(missing))
            raise GammaError("source event quarantined: missing required fields")
        if not source["trusted_source"]:
            self._quarantine(source, "untrusted source")
            raise GammaError("source event quarantined: untrusted source")
        if not isinstance(source["payload"], dict):
            self._quarantine(source, "payload must be an object")
            raise GammaError("source event quarantined: invalid payload")

        payload: Dict[str, Any] = {}
        for key, value in source["payload"].items():
            if key in self.payload_allowlist:
                payload[key] = value
            elif key in self.prohibited_fields:
                self.redactions.append({
                    "field": key,
                    "action": "removed",
                    "policy_version": "telemetry-minimisation/1.0.0",
                    "source_record_id": source["source_record_id"],
                })
        origin_event_id = stable_id(
            "origin", source["source_system"], source["source_record_id"], source["source_version"]
        )
        event = {
            "event_id": stable_id("event", origin_event_id, "federated"),
            "origin_event_id": origin_event_id,
            "source_event_id": source["source_record_id"],
            "source_record_id": source["source_record_id"],
            "source_system": source["source_system"],
            "source_version": source["source_version"],
            "adapter_id": source["adapter_id"],
            "adapter_version": source["adapter_version"],
            "domain": source["domain"],
            "observed_at": source["observed_at"],
            "ingested_at": self.now,
            "business_purpose": source["business_purpose"],
            "context_owner_id": source["context_owner_id"],
            "provenance_method": "deterministic-adapter",
            "telemetry_policy_version": "telemetry-minimisation/1.0.0",
            "payload": payload,
            "redaction_count": len([
                r for r in self.redactions if r["source_record_id"] == source["source_record_id"]
            ]),
            "retention_class": "raw_telemetry",
            "expires_at": "2026-10-09T10:00:00Z",
            "legal_hold": False,
        }
        return self._record("federate", origin_event_id, event)

    def select_mapping(self, mapping_type: str, at: Optional[str] = None) -> Dict[str, Any]:
        at_time = parse_time(at or self.now)
        candidates = []
        for mapping in self.registry["mappings"]:
            if mapping["mapping_type"] != mapping_type:
                continue
            if mapping["status"] != "active" or not mapping.get("approved_by"):
                continue
            if parse_time(mapping["effective_from"]) <= at_time and (
                mapping["effective_to"] is None or at_time < parse_time(mapping["effective_to"])
            ):
                candidates.append(mapping)
        if not candidates:
            raise GammaError(f"no active approved mapping for {mapping_type}")
        return sorted(candidates, key=lambda item: item["version"])[-1]

    def contextualise(
        self,
        event: Dict[str, Any],
        *,
        conflict_assertions: Optional[List[Dict[str, Any]]] = None,
        effective_to: Optional[str] = "2026-12-31T23:59:59Z",
    ) -> Dict[str, Any]:
        """CPL + CL: create a canonical governed Context Record."""
        mapping = self.select_mapping("admissions-purpose")
        payload = event["payload"]
        confidence = payload.get("source_confidence", "unknown")
        conflicts = conflict_assertions or []
        missing = [
            key for key in ("processing_location", "data_subject_location", "candidate_obligations")
            if not payload.get(key)
        ]
        stale = effective_to is not None and parse_time(effective_to) <= parse_time(self.now)
        conflict = len(conflicts) > 1 and len({canonical_json(x["value"]) for x in conflicts}) > 1
        if stale:
            validation_status = "expired"
        elif conflict or missing:
            validation_status = "review_required"
        else:
            validation_status = "inferred"
        origin = event["origin_event_id"]
        version = len(self.context_store.get(origin, [])) + 1
        record = {
            "context_record_id": stable_id("context", origin),
            "context_version_id": stable_id("context-version", origin, version),
            "version": f"1.0.{version - 1}",
            "origin_event_id": origin,
            "source_event_id": event["source_event_id"],
            "domain": event["domain"],
            "context_owner_id": event["context_owner_id"],
            "observed_at": event["observed_at"],
            "ingested_at": event["ingested_at"],
            "effective_from": event["observed_at"],
            "effective_to": effective_to,
            "context_schema_version": "context-record/1.0.0",
            "source_version": event["source_version"],
            "provenance_method": event["provenance_method"],
            "prov_was_derived_from": event["event_id"],
            "business_purpose": event["business_purpose"],
            "purpose_owner": "admissions-office",
            "processing_location": payload.get("processing_location"),
            "data_subject_location": payload.get("data_subject_location"),
            "jurisdiction": sorted(set(filter(None, [
                payload.get("processing_location"), payload.get("data_subject_location")
            ]))),
            "candidate_obligations": payload.get("candidate_obligations", []),
            "applicability_basis": "fixture assertion; reviewer confirmation required",
            "applicability_status": "candidate",
            "mapping_refs": [{"mapping_id": mapping["artefact_id"], "version": mapping["version"]}],
            "source_confidence": confidence,
            "transformation_confidence": "deterministic",
            "uncertainty_type": "missing" if missing else ("conflict" if conflict else "unvalidated"),
            "uncertainty_note": "Controlled metadata state; not a calibrated probability.",
            "missing_context_fields": missing,
            "validation_status": validation_status,
            "validation_actor": None,
            "validation_time": None,
            "conflict": conflict,
            "conflict_assertions": conflicts,
            "supersedes": self.context_store.get(origin, [{}])[-1].get("context_version_id"),
            "retention_class": "enriched_context",
            "expires_at": "2027-01-02T10:00:00Z",
            "legal_hold": False,
        }
        self.context_store.setdefault(origin, []).append(record)
        return self._record("contextualise", origin, record)

    def validate_context(
        self,
        context: Dict[str, Any],
        *,
        decision: str,
        reviewer_role: str,
        reviewer_id: str,
        rationale: str,
        corrections: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """HIL pre-assessment checkpoint: Confirm, Correct, Reject, or Defer."""
        self._require_role(reviewer_role, "validate_context")
        if decision not in {"Confirm", "Correct", "Reject", "Defer"}:
            raise GammaError("invalid context validation decision")
        origin = context["origin_event_id"]
        review = {
            "context_review_id": stable_id("context-review", origin, len(self.reviews) + 1),
            "origin_event_id": origin,
            "decision": decision,
            "reviewer_id": reviewer_id,
            "reviewer_role": reviewer_role,
            "rationale": rationale,
            "reviewed_at": self.now,
            "input_context_version_id": context["context_version_id"],
            "field_corrections": corrections or {},
        }
        updated = copy.deepcopy(context)
        if decision == "Correct":
            if not corrections:
                raise GammaError("Correct requires field corrections")
            updated.update(corrections)
            updated["version"] = f"1.0.{len(self.context_store[origin])}"
            updated["context_version_id"] = stable_id("context-version", origin, len(self.context_store[origin]) + 1)
            updated["supersedes"] = context["context_version_id"]
            updated["missing_context_fields"] = [
                field for field in context["missing_context_fields"] if field not in corrections
            ]
            updated["conflict"] = False if corrections else context["conflict"]
            updated["validation_status"] = "human_confirmed"
        elif decision == "Confirm":
            if context["validation_status"] == "expired" or context["conflict"]:
                raise GammaError("expired or conflicting context must be corrected, rejected, or deferred")
            updated["validation_status"] = "human_confirmed"
        elif decision == "Reject":
            updated["validation_status"] = "rejected"
        else:
            updated["validation_status"] = "deferred"
        updated["validation_actor"] = reviewer_id
        updated["validation_time"] = self.now
        if decision == "Correct":
            self.context_store[origin].append(updated)
        else:
            self.context_store[origin][-1] = updated
        review["output_context_version_id"] = updated["context_version_id"]
        self.reviews.append(review)
        self._record("context-validation", origin, review)
        return updated

    def assessment_manifest(self, context: Dict[str, Any]) -> Dict[str, Any]:
        selected = [
            item for item in self.registry["artefacts"]
            if item["status"] == "active" and item["artefact_type"] in {
                "schema", "criteria_set", "risk_model", "prompt", "ontology", "telemetry_policy"
            }
        ]
        mapping_ids = {ref["mapping_id"] for ref in context["mapping_refs"]}
        selected.extend(item for item in self.registry["mappings"] if item["artefact_id"] in mapping_ids)
        return {
            "manifest_id": stable_id("assessment-manifest", context["context_version_id"]),
            "gamma_label": GAMMA_LABEL,
            "artefacts": [{
                "artefact_id": item["artefact_id"],
                "artefact_type": item["artefact_type"],
                "version": item["version"],
                "checksum": item["checksum"],
            } for item in sorted(selected, key=lambda x: x["artefact_id"])],
            "model": {
                "provider": "capra-deterministic-reference",
                "identifier": "ruleset-admissions-v1",
                "reproducibility": "deterministic standard-library rules",
            },
            "contains_secrets": False,
        }

    def assess(self, context: Dict[str, Any], role: str = "risk_analyst") -> Dict[str, Any]:
        """RIL: emit a bounded Assessment Output envelope."""
        self._require_role(role, "assess")
        if context["validation_status"] != "human_confirmed":
            raise GammaError("assessment blocked: context is not human_confirmed")
        if context["conflict"] or (
            context["effective_to"] and parse_time(context["effective_to"]) <= parse_time(self.now)
        ):
            raise GammaError("assessment blocked: context is stale or conflicting")
        manifest = self.assessment_manifest(context)
        origin = context["origin_event_id"]
        assessment_id = stable_id("assessment", origin, context["context_version_id"])
        output = {
            "assessment_id": assessment_id,
            "risk_id": stable_id("risk", assessment_id, "purpose-and-attribute-use"),
            "origin_event_id": origin,
            "domain": context["domain"],
            "context_version_ids": [context["context_version_id"]],
            "mapping_version_ids": [
                f"{item['mapping_id']}@{item['version']}" for item in context["mapping_refs"]
            ],
            "criteria_set_version": "criteria-admissions/1.0.0",
            "risk_model_version": "risk-rules/1.0.0",
            "prompt_version": "bounded-explanation/1.0.0",
            "model_identifier": manifest["model"]["identifier"],
            "generated_at": self.now,
            "validation_status": context["validation_status"],
            "confidence": "unknown" if context["source_confidence"] == "unknown" else "bounded",
            "uncertainty": context["uncertainty_note"],
            "criteria_observations": [{
                "candidate_obligation": item,
                "status": "review_required",
                "source": "synthetic fixture assertion",
            } for item in context["candidate_obligations"]],
            "risk_level": "review_required",
            "explanation": (
                "The controlled fixture combines a protected-attribute flag with an admissions "
                "purpose. This is a criteria observation for human review, not a legal conclusion."
            ),
            "evidence": {
                "context_version_id": context["context_version_id"],
                "source_event_id": context["source_event_id"],
                "manifest_id": manifest["manifest_id"],
            },
            "review_status": "pending",
            "assessment_manifest": manifest,
            "retention_class": "assessment",
            "expires_at": "2027-10-02T10:00:00Z",
            "legal_hold": False,
        }
        return self._record("assess", origin, output)

    def propose_change(
        self, assessment: Dict[str, Any], requested_by: str, role: str = "risk_analyst"
    ) -> Dict[str, Any]:
        """FRL: create a proposal; proposal is not approval or application."""
        self._require_role(role, "propose_change")
        revision_id = stable_id("revision", assessment["assessment_id"], "mapping-clarification")
        change = {
            "revision_id": revision_id,
            "origin_event_id": assessment["origin_event_id"],
            "assessment_id": assessment["assessment_id"],
            "risk_id": assessment["risk_id"],
            "requested_by": requested_by,
            "reviewed_by": None,
            "approved_by": None,
            "approval_time": None,
            "rationale": "Clarify the mapping rationale exposed to the reviewer.",
            "evidence_refs": [assessment["evidence"]["manifest_id"], assessment["risk_id"]],
            "impacted_contracts": ["capra.gamma.contextualise.v1"],
            "previous_version": "mapping-admissions-purpose/1.0.0",
            "new_version": "mapping-admissions-purpose/1.1.0",
            "effective_at": None,
            "rollback_target": "mapping-admissions-purpose/1.0.0",
            "rollback_reason": None,
            "application_status": "not_applied",
            "status": "proposed",
            "status_history": [{"status": "proposed", "actor": requested_by, "at": self.now}],
        }
        self.changes[revision_id] = change
        return self._record("refine", assessment["origin_event_id"], change)

    def review_assessment(
        self,
        assessment: Dict[str, Any],
        proposal: Dict[str, Any],
        *,
        decision: str,
        reviewer_id: str,
        role: str = "reviewer",
        rationale: str,
    ) -> Dict[str, Any]:
        """HIL post-assessment durable decision linked to all upstream identifiers."""
        self._require_role(role, "post_review")
        if decision not in {"Approve", "Reject", "Defer"}:
            raise GammaError("invalid post-assessment decision")
        review = {
            "review_id": stable_id("review", assessment["assessment_id"], reviewer_id, decision),
            "origin_event_id": assessment["origin_event_id"],
            "risk_id": assessment["risk_id"],
            "assessment_id": assessment["assessment_id"],
            "revision_id": proposal["revision_id"],
            "input_version": proposal["previous_version"],
            "output_version": proposal["new_version"],
            "reviewer_role": role,
            "reviewer_id": reviewer_id,
            "decision": decision,
            "rationale": rationale,
            "timestamp": self.now,
            "application_status": "not_applied",
            "retention_class": "review",
            "expires_at": "2028-10-02T10:00:00Z",
            "legal_hold": False,
        }
        self.reviews.append(review)
        change = self.changes[proposal["revision_id"]]
        change["reviewed_by"] = reviewer_id
        if decision == "Approve":
            if reviewer_id == change["requested_by"]:
                raise GammaError("segregation of duties violation: proposer cannot approve")
            change["approved_by"] = reviewer_id
            change["approval_time"] = self.now
            change["status"] = "approved"
            change["status_history"].append({"status": "approved", "actor": reviewer_id, "at": self.now})
        else:
            change["status"] = decision.lower()
            change["status_history"].append({
                "status": decision.lower(), "actor": reviewer_id, "at": self.now
            })
        return self._record("review", assessment["origin_event_id"], review)

    def apply_change(self, revision_id: str, actor: str, role: str = "administrator") -> Dict[str, Any]:
        self._require_role(role, "apply_change")
        change = self.changes[revision_id]
        if change["status"] != "approved" or not change["approved_by"]:
            raise GammaError("only an approved change can be applied")
        change["status"] = "applied"
        change["application_status"] = "applied"
        change["effective_at"] = self.now
        change["status_history"].append({"status": "applied", "actor": actor, "at": self.now})
        return copy.deepcopy(change)

    def rollback_change(
        self, revision_id: str, actor: str, reason: str, role: str = "administrator"
    ) -> Dict[str, Any]:
        self._require_role(role, "rollback_change")
        change = self.changes[revision_id]
        if change["status"] != "applied":
            raise GammaError("only an applied change can be rolled back")
        change["status"] = "rolled_back"
        change["application_status"] = "rolled_back"
        change["rollback_reason"] = reason
        change["status_history"].append({"status": "rolled_back", "actor": actor, "at": self.now})
        return copy.deepcopy(change)

    def expire_records(
        self, records: Iterable[Dict[str, Any]], actor: str, role: str = "administrator"
    ) -> List[Dict[str, Any]]:
        """Apply configurable lifecycle rules while preserving held records."""
        self._require_role(role, "expire_records")
        retained = []
        for record in records:
            if record.get("legal_hold") or not record.get("expires_at"):
                retained.append(record)
            elif parse_time(record["expires_at"]) <= parse_time(self.now):
                self.deletion_receipts.append({
                    "receipt_id": stable_id("deletion", record.get("origin_event_id"), checksum(record)),
                    "artefact_id": record.get("assessment_id") or record.get("context_version_id")
                    or record.get("event_id") or record.get("review_id"),
                    "record_checksum": checksum(record),
                    "retention_class": record.get("retention_class"),
                    "deleted_at": self.now,
                    "actor": actor,
                })
            else:
                retained.append(record)
        return retained

    def view_stage_records(self, role: Optional[str] = None, public: bool = False) -> List[Dict[str, Any]]:
        """Return detailed authorised evidence or a payload-free synthetic public view."""
        if public:
            return [{
                "stage": item["stage"],
                "origin_event_id": item["origin_event_id"],
                "domain": item.get("domain", "admissions"),
                "synthetic_only": True,
            } for item in self.stage_records]
        if role not in {"context_curator", "risk_analyst", "reviewer", "administrator"}:
            raise GammaError("authorised role required for detailed telemetry")
        return copy.deepcopy(self.stage_records)

    def trace(self, origin_event_id: str) -> Dict[str, Any]:
        records = [r for r in self.stage_records if r["origin_event_id"] == origin_event_id]
        return {
            "origin_event_id": origin_event_id,
            "stages": [record["stage"] for record in records],
            "records": records,
            "timestamp_heuristics_used": False,
            "complete": all(stage in {r["stage"] for r in records} for stage in (
                "federate", "contextualise", "context-validation", "assess", "refine", "review"
            )),
        }
