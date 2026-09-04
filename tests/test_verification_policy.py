from __future__ import annotations

from pathlib import Path
import sys
import unittest


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import verification_policy


class VerificationPolicyTests(unittest.TestCase):
    def context(self, **changes: object) -> dict[str, object]:
        value: dict[str, object] = {
            "schema_version": 1,
            "kind": "tool-shed-verification-policy-input",
            "changed_paths": ["docs/operator-guide.md"],
            "components": ["documentation"],
            "side_effect_classes": ["none"],
            "target_class": "development",
            "protected_boundaries": [],
            "behavior_neutral": True,
            "requested_profile": "mechanical",
            "parent_minimum_profile": "mechanical",
        }
        value.update(changes)
        return value

    def test_mechanical_is_classified_but_not_automatically_lowered(self) -> None:
        decision = verification_policy.classify(self.context())
        self.assertEqual(decision["classified_profile"], "mechanical")
        self.assertEqual(decision["effective_profile"], "high-risk")
        self.assertFalse(decision["automatic_lowering_enabled"])
        self.assertIn("automatic-lowering-disabled", decision["reason_codes"])
        self.assertEqual(
            decision["required_recipe_set"],
            [
                "edit",
                "targeted-verification",
                "applicable-tests",
                "diff-review",
                "recursive-closure",
                "independent-verification",
            ],
        )

    def test_normal_code_and_high_risk_migration_are_deterministic(self) -> None:
        normal = verification_policy.classify(
            self.context(
                changed_paths=["scripts/example.py"],
                components=["known-worker"],
                behavior_neutral=False,
                requested_profile="normal",
                parent_minimum_profile="normal",
            )
        )
        high = verification_policy.classify(
            self.context(
                changed_paths=["scripts/schema_migration.py"],
                components=["database"],
                behavior_neutral=False,
                requested_profile="normal",
                parent_minimum_profile="normal",
            )
        )
        self.assertEqual(normal["classified_profile"], "normal")
        self.assertEqual(high["classified_profile"], "high-risk")
        self.assertEqual(high, verification_policy.classify(high["inputs"]))

    def test_parent_floor_and_protected_boundary_cannot_be_lowered(self) -> None:
        parent = verification_policy.classify(self.context(parent_minimum_profile="normal"))
        self.assertIn(
            {"from": "mechanical", "to": "normal", "reason": "parent-minimum-floor"},
            parent["escalation_history"],
        )
        protected = verification_policy.classify(
            self.context(protected_boundaries=["security"], target_class="production")
        )
        self.assertEqual(protected["classified_profile"], "high-risk")
        self.assertEqual(protected["effective_profile"], "high-risk")
        self.assertIn("protected-boundary-floor", protected["reason_codes"])

    def test_unknown_mixed_and_unexpected_scope_fail_closed(self) -> None:
        unknown = verification_policy.classify(
            self.context(
                changed_paths=[],
                components=[],
                side_effect_classes=["none"],
                behavior_neutral=False,
            )
        )
        mixed = verification_policy.classify(
            self.context(
                changed_paths=["docs/label.md", "scripts/database_migration.py"],
                components=["documentation", "database"],
                behavior_neutral=False,
            )
        )
        unexpected = verification_policy.classify(self.context(unexpected_scope=True))
        self.assertEqual(unknown["classified_profile"], "high-risk")
        self.assertIn("unknown-scope", unknown["reason_codes"])
        self.assertEqual(mixed["classified_profile"], "high-risk")
        self.assertEqual(unexpected["classified_profile"], "high-risk")
        self.assertIn("unexpected-scope", unexpected["reason_codes"])

    def test_policy_and_input_digests_are_stable_and_distinct(self) -> None:
        first = verification_policy.classify(self.context())
        repeated = verification_policy.classify(self.context())
        changed = verification_policy.classify(self.context(failed_checks=True))
        self.assertEqual(first["policy_digest"], repeated["policy_digest"])
        self.assertEqual(first["decision_digest"], repeated["decision_digest"])
        self.assertNotEqual(first["decision_digest"], changed["decision_digest"])
        self.assertEqual(verification_policy.validate_decision(first), first)
        with self.assertRaises(verification_policy.VerificationPolicyError):
            verification_policy.validate_decision({**first, "effective_profile": "mechanical"})


if __name__ == "__main__":
    unittest.main()
