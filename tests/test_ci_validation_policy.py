from __future__ import annotations

import unittest

from scripts import ci_validation_policy


class CiValidationPolicyTests(unittest.TestCase):
    def test_document_and_database_state_collateral_use_one_focused_job(self) -> None:
        result = ci_validation_policy.classify(
            ["docs/commands.md", "work/state/checkpoints/state-v2.json"]
        )
        self.assertEqual(result["profile"], "focused")
        self.assertFalse(result["full_matrix"])
        self.assertEqual(result["shard_count"], 1)
        self.assertEqual(len(result["matrix"]["include"]), 1)

    def test_product_schema_test_and_workflow_changes_require_full_matrix(self) -> None:
        for path in (
            "scripts/outcome_reconciliation.py",
            "schemas/outcome-reconciliation/v1/fixture.json",
            "tests/test_outcome_reconciliation.py",
            ".github/workflows/validate.yml",
        ):
            with self.subTest(path=path):
                result = ci_validation_policy.classify([path])
                self.assertEqual(result["profile"], "release")
                self.assertTrue(result["full_matrix"])
                self.assertEqual(result["shard_count"], 8)
                self.assertEqual(len(result["matrix"]["include"]), 32)

    def test_empty_input_and_override_fail_safe_to_full(self) -> None:
        self.assertTrue(ci_validation_policy.classify([])["full_matrix"])
        forced = ci_validation_policy.classify(["README.md"], force_full=True)
        self.assertTrue(forced["full_matrix"])
        self.assertIn("override", forced["reason"])

    def test_validation_performance_surfaces_request_benchmark(self) -> None:
        result = ci_validation_policy.classify(["scripts/validate_tool_shed.py"])
        self.assertTrue(result["performance"])


if __name__ == "__main__":
    unittest.main()
