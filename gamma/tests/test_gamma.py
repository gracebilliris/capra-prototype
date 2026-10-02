from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

GAMMA = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GAMMA))

from capra_gamma import GammaEngine, GammaError  # noqa: E402


class GammaTestCase(unittest.TestCase):
    def setUp(self):
        self.engine = GammaEngine()
        self.source = json.loads(
            (GAMMA / "fixtures" / "admissions_event.json").read_text(encoding="utf-8")
        )

    def federated(self):
        return self.engine.federate(copy.deepcopy(self.source))

    def contextualised(self, **kwargs):
        return self.engine.contextualise(self.federated(), **kwargs)

    def confirmed(self):
        context = self.contextualised()
        return self.engine.validate_context(
            context,
            decision="Confirm",
            reviewer_role="context_curator",
            reviewer_id="curator-01",
            rationale="Controlled fixture confirmation.",
        )

    def assessed(self):
        return self.engine.assess(self.confirmed())

    def test_valid_source_is_minimised_and_lineage_is_stable(self):
        event = self.federated()
        self.assertTrue(event["origin_event_id"].startswith("origin-"))
        self.assertNotIn("email", event["payload"])
        self.assertNotIn("free_text", event["payload"])
        self.assertEqual(event["redaction_count"], 2)

    def test_invalid_source_is_quarantined(self):
        del self.source["adapter_id"]
        with self.assertRaisesRegex(GammaError, "quarantined"):
            self.engine.federate(self.source)
        self.assertEqual(self.engine.quarantine[0]["reason"], "missing required fields: adapter_id")

    def test_untrusted_source_is_quarantined(self):
        self.source["trusted_source"] = False
        with self.assertRaisesRegex(GammaError, "untrusted"):
            self.engine.federate(self.source)
        self.assertEqual(self.engine.quarantine[0]["reason"], "untrusted source")

    def test_unknown_confidence_does_not_default_to_perfect(self):
        del self.source["payload"]["source_confidence"]
        context = self.contextualised()
        self.assertEqual(context["source_confidence"], "unknown")
        self.assertNotEqual(context["source_confidence"], 1.0)

    def test_active_approved_mapping_is_selected(self):
        mapping = self.engine.select_mapping("admissions-purpose")
        self.assertEqual(mapping["status"], "active")
        self.assertIsNotNone(mapping["approved_by"])

    def test_unapproved_mapping_cannot_be_selected(self):
        with self.assertRaisesRegex(GammaError, "no active approved mapping"):
            self.engine.select_mapping("admissions-purpose-draft-only")

    def test_complete_context_can_be_confirmed(self):
        context = self.confirmed()
        self.assertEqual(context["validation_status"], "human_confirmed")
        self.assertEqual(context["validation_actor"], "curator-01")

    def test_missing_context_can_be_corrected_and_versioned(self):
        del self.source["payload"]["data_subject_location"]
        context = self.contextualised()
        self.assertEqual(context["validation_status"], "review_required")
        corrected = self.engine.validate_context(
            context,
            decision="Correct",
            reviewer_role="context_curator",
            reviewer_id="curator-01",
            rationale="Restore the fixture's asserted subject location.",
            corrections={"data_subject_location": "EU", "jurisdiction": ["AU-NSW", "EU"]},
        )
        self.assertEqual(corrected["validation_status"], "human_confirmed")
        self.assertEqual(corrected["supersedes"], context["context_version_id"])
        self.assertNotEqual(corrected["context_version_id"], context["context_version_id"])

    def test_rejected_context_cannot_be_assessed(self):
        context = self.contextualised()
        rejected = self.engine.validate_context(
            context,
            decision="Reject",
            reviewer_role="context_curator",
            reviewer_id="curator-01",
            rationale="Fixture state rejected for negative control.",
        )
        with self.assertRaisesRegex(GammaError, "not human_confirmed"):
            self.engine.assess(rejected)

    def test_deferred_context_cannot_be_assessed(self):
        context = self.contextualised()
        deferred = self.engine.validate_context(
            context,
            decision="Defer",
            reviewer_role="context_curator",
            reviewer_id="curator-01",
            rationale="More context requested.",
        )
        with self.assertRaisesRegex(GammaError, "not human_confirmed"):
            self.engine.assess(deferred)

    def test_stale_context_is_blocked(self):
        context = self.contextualised(effective_to="2026-09-30T00:00:00Z")
        self.assertEqual(context["validation_status"], "expired")
        with self.assertRaisesRegex(GammaError, "expired or conflicting"):
            self.engine.validate_context(
                context,
                decision="Confirm",
                reviewer_role="context_curator",
                reviewer_id="curator-01",
                rationale="Attempted confirmation.",
            )

    def test_conflicting_context_retains_assertions_and_is_blocked(self):
        context = self.contextualised(conflict_assertions=[
            {"source": "source-a", "field": "business_purpose", "value": "admission-assessment"},
            {"source": "source-b", "field": "business_purpose", "value": "marketing"},
        ])
        self.assertTrue(context["conflict"])
        self.assertEqual(len(context["conflict_assertions"]), 2)
        with self.assertRaisesRegex(GammaError, "expired or conflicting"):
            self.engine.validate_context(
                context,
                decision="Confirm",
                reviewer_role="context_curator",
                reviewer_id="curator-01",
                rationale="Attempted confirmation.",
            )

    def test_assessment_envelope_cites_versions_evidence_and_validation(self):
        assessment = self.assessed()
        self.assertEqual(assessment["validation_status"], "human_confirmed")
        self.assertTrue(assessment["mapping_version_ids"])
        self.assertTrue(assessment["assessment_manifest"]["artefacts"])
        self.assertEqual(assessment["assessment_manifest"]["gamma_label"], "Gamma")
        self.assertEqual(assessment["confidence"], "unknown")
        self.assertNotIn("compliant", json.dumps(assessment).lower())

    def test_post_review_is_durably_linked_upstream(self):
        assessment = self.assessed()
        proposal = self.engine.propose_change(assessment, requested_by="analyst-01")
        review = self.engine.review_assessment(
            assessment,
            proposal,
            decision="Approve",
            reviewer_id="reviewer-01",
            rationale="Controlled approval.",
        )
        self.assertEqual(review["origin_event_id"], assessment["origin_event_id"])
        self.assertEqual(review["risk_id"], assessment["risk_id"])
        self.assertEqual(review["revision_id"], proposal["revision_id"])

    def test_proposer_cannot_approve_own_change(self):
        assessment = self.assessed()
        proposal = self.engine.propose_change(assessment, requested_by="same-person")
        with self.assertRaisesRegex(GammaError, "segregation"):
            self.engine.review_assessment(
                assessment,
                proposal,
                decision="Approve",
                reviewer_id="same-person",
                rationale="Attempted self approval.",
            )

    def test_unauthorised_role_cannot_apply_change(self):
        assessment = self.assessed()
        proposal = self.engine.propose_change(assessment, requested_by="analyst-01")
        self.engine.review_assessment(
            assessment,
            proposal,
            decision="Approve",
            reviewer_id="reviewer-01",
            rationale="Controlled approval.",
        )
        with self.assertRaisesRegex(GammaError, "not authorised"):
            self.engine.apply_change(proposal["revision_id"], actor="analyst-01", role="risk_analyst")

    def test_unapproved_change_cannot_be_applied(self):
        assessment = self.assessed()
        proposal = self.engine.propose_change(assessment, requested_by="analyst-01")
        with self.assertRaisesRegex(GammaError, "only an approved"):
            self.engine.apply_change(proposal["revision_id"], actor="admin-01")

    def test_apply_and_rollback_retain_history(self):
        assessment = self.assessed()
        proposal = self.engine.propose_change(assessment, requested_by="analyst-01")
        self.engine.review_assessment(
            assessment,
            proposal,
            decision="Approve",
            reviewer_id="reviewer-01",
            rationale="Controlled approval.",
        )
        applied = self.engine.apply_change(proposal["revision_id"], actor="admin-01")
        rolled_back = self.engine.rollback_change(
            proposal["revision_id"], actor="admin-01", reason="Negative-control rollback."
        )
        self.assertEqual(applied["status"], "applied")
        self.assertEqual(rolled_back["status"], "rolled_back")
        self.assertEqual(
            [item["status"] for item in rolled_back["status_history"]],
            ["proposed", "approved", "applied", "rolled_back"],
        )

    def test_retention_expiry_writes_receipt_and_preserves_legal_hold(self):
        expired = {
            "event_id": "event-expired",
            "origin_event_id": "origin-expired",
            "retention_class": "raw_telemetry",
            "expires_at": "2026-10-01T00:00:00Z",
            "legal_hold": False,
        }
        held = {**expired, "event_id": "event-held", "legal_hold": True}
        retained = self.engine.expire_records([expired, held], actor="admin-01")
        self.assertEqual(retained, [held])
        self.assertEqual(len(self.engine.deletion_receipts), 1)
        self.assertEqual(self.engine.deletion_receipts[0]["artefact_id"], "event-expired")

    def test_detailed_telemetry_requires_role_and_public_view_has_no_payload(self):
        self.federated()
        with self.assertRaisesRegex(GammaError, "authorised role"):
            self.engine.view_stage_records()
        detailed = self.engine.view_stage_records(role="reviewer")
        public = self.engine.view_stage_records(public=True)
        self.assertIn("payload", detailed[0])
        self.assertNotIn("payload", public[0])
        self.assertTrue(public[0]["synthetic_only"])

    def test_source_to_review_trace_uses_no_timestamp_heuristics(self):
        assessment = self.assessed()
        proposal = self.engine.propose_change(assessment, requested_by="analyst-01")
        self.engine.review_assessment(
            assessment,
            proposal,
            decision="Approve",
            reviewer_id="reviewer-01",
            rationale="Controlled approval.",
        )
        trace = self.engine.trace(assessment["origin_event_id"])
        self.assertTrue(trace["complete"])
        self.assertFalse(trace["timestamp_heuristics_used"])
        self.assertNotIn("unknown", {record.get("domain") for record in trace["records"]})


if __name__ == "__main__":
    unittest.main()
