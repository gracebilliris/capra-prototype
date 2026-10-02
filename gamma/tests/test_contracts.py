from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ContractTests(unittest.TestCase):
    def test_exactly_six_layers_and_five_stages(self):
        contract = json.loads((ROOT / "contracts" / "contracts.json").read_text(encoding="utf-8"))
        topology = contract["topology"]
        self.assertEqual(topology["conceptual_layers"], ["DFL", "CPL", "CL", "RIL", "FRL", "HIL"])
        self.assertEqual(len(topology["executable_stages"]), 5)
        self.assertEqual(topology["external_systems"], "outside CAPRA")
        self.assertEqual(topology["shared_substrate"], "CL")

    def test_each_layer_contract_is_explicit_and_versioned(self):
        contract = json.loads((ROOT / "contracts" / "contracts.json").read_text(encoding="utf-8"))
        self.assertEqual(contract["contract_version"], "1.0.0")
        required = {
            "input", "output", "validation", "producer", "consumer",
            "error_path", "persistence", "evidence_identifier",
            "required_fields", "optional_fields",
        }
        for name, layer in contract["layers"].items():
            self.assertEqual(required - set(layer), set(), name)

    def test_normative_schemas_define_required_fields_and_controlled_states(self):
        schemas = json.loads((ROOT / "contracts" / "schemas.json").read_text(encoding="utf-8"))
        definitions = schemas["$defs"]
        self.assertEqual(
            set(definitions),
            {"source_event", "context_record", "mapping_record", "assessment_output", "review_decision"},
        )
        for name, schema in definitions.items():
            self.assertTrue(schema["required"], name)
            self.assertIn("properties", schema, name)
        confidence = definitions["context_record"]["properties"]["source_confidence"]
        self.assertIn({"const": "unknown"}, confidence["oneOf"])

    def test_registry_artefacts_have_governance_fields(self):
        registry = json.loads((ROOT / "registry" / "artefacts.json").read_text(encoding="utf-8"))
        required = {
            "artefact_id", "artefact_type", "version", "owner", "status",
            "effective_from", "effective_to", "checksum", "rationale", "supersedes",
        }
        for item in registry["artefacts"] + registry["mappings"]:
            self.assertEqual(required - set(item), set(), item["artefact_id"])


if __name__ == "__main__":
    unittest.main()
