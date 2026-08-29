from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import document_contract  # noqa: E402


class DocumentContractTests(unittest.TestCase):
    def test_frozen_contract_fixture_passes(self) -> None:
        fixture = ROOT / "tests/fixtures/document-store-v1/contract-valid.json"
        result = document_contract.validate_contract(json.loads(fixture.read_text(encoding="utf-8")))
        self.assertTrue(result["valid"])
        self.assertEqual(result["generated_types"], 16)

    def test_contradictory_dual_authority_fixture_fails(self) -> None:
        fixture = ROOT / "tests/fixtures/document-store-v1/contract-invalid-dual-authority.json"
        with self.assertRaises(document_contract.ContractError):
            document_contract.validate_contract(json.loads(fixture.read_text(encoding="utf-8")))

    def test_schema_declares_fail_closed_invariants(self) -> None:
        schema = json.loads((ROOT / "schemas/document-store/v1/contract.schema.json").read_text(encoding="utf-8"))
        properties = schema["properties"]
        self.assertEqual(properties["hybrid_schema"]["const"], 2)
        self.assertFalse(properties["checkpoint"]["properties"]["live_database_tracked"]["const"])
        self.assertFalse(properties["retirement"]["properties"]["automatic"]["const"])


if __name__ == "__main__":
    unittest.main()
