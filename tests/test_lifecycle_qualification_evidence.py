from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import lifecycle_qualification_evidence as evidence  # noqa: E402


class LifecycleQualificationEvidenceTests(unittest.TestCase):
    def manifest_result(self, verdict: str = "PASS") -> tuple[dict[str, object], dict[str, object]]:
        manifest = {
            "run_id": "tsqh-" + "a" * 24,
            "manifest_digest": "b" * 64,
            "candidate": {"commit": "c" * 40},
            "scenario": {"id": "QH-002"},
            "fixture": {"platform": "linux-x86_64"},
        }
        result = {
            "run_id": manifest["run_id"],
            "manifest_digest": manifest["manifest_digest"],
            "result_digest": "d" * 64,
            "verdict": verdict,
            "first_divergence": "broken",
            "replay": ["python3 /private/work/run.py --token hidden"],
        }
        return manifest, result

    def test_seal_redacts_before_hashing_and_keeps_failure_window(self) -> None:
        manifest, result = self.manifest_result("PRODUCT-FAIL")
        records = [
            {"id": "old", "body_markdown": "private prose"},
            {"id": "prior", "value": "Bearer abc.def"},
            {"id": "broken", "password": "dont-save", "actual": "sk-secretvalue"},
            {"id": "later", "value": "must not be captured"},
        ]
        bundle = evidence.seal_bundle(manifest, result, records, created_at="2026-09-03T00:00:00Z")
        encoded = json.dumps(bundle)
        self.assertNotIn("private prose", encoded)
        self.assertNotIn("dont-save", encoded)
        self.assertNotIn("secretvalue", encoded)
        self.assertNotIn("--token hidden", encoded)
        self.assertNotIn("must not be captured", encoded)
        self.assertEqual([item["id"] for item in bundle["records"]], ["prior", "broken"])
        self.assertEqual(bundle["records"][1]["password"], "[REDACTED]")

    def test_retention_is_verdict_specific_and_product_failure_is_protected(self) -> None:
        manifest, result = self.manifest_result("PASS")
        passing = evidence.seal_bundle(manifest, result, [], created_at="2026-01-01T00:00:00Z")
        now = datetime(2026, 2, 1, tzinfo=timezone.utc)
        self.assertFalse(evidence.retention_state(passing, now=now)["eligible"])
        self.assertTrue(
            evidence.retention_state(
                passing, now=now, newer_accepted_at=datetime(2026, 1, 2, tzinfo=timezone.utc)
            )["eligible"]
        )
        result["verdict"] = "PRODUCT-FAIL"
        failing = evidence.seal_bundle(manifest, result, [], created_at="2026-01-01T00:00:00Z")
        self.assertTrue(evidence.retention_state(failing, now=now)["protected"])
        fixed = evidence.retention_state(
            failing, now=datetime(2026, 3, 1, tzinfo=timezone.utc),
            fixing_pass_at=datetime(2026, 1, 15, tzinfo=timezone.utc),
        )
        self.assertFalse(fixed["protected"])
        self.assertTrue(fixed["eligible"])

    def test_reclaim_plan_selects_only_expired_passes_and_never_deletes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, verdict in (("old-pass", "PASS"), ("failure", "PRODUCT-FAIL")):
                path = root / name / "bundle.json"
                path.parent.mkdir()
                path.write_text(json.dumps({"created_at": "2020-01-01T00:00:00Z", "verdict": verdict}))
            policy = evidence.load_policy()
            incoming = int(policy["capture"]["per_fixture_bytes"])
            blocked = evidence.reclaim_plan(root, incoming_bytes=incoming, now=datetime(2026, 1, 1, tzinfo=timezone.utc))
            self.assertEqual(blocked["verdict"], "INFRA-BLOCKED")
            plan = evidence.reclaim_plan(
                root,
                incoming_bytes=incoming,
                now=datetime(2026, 1, 1, tzinfo=timezone.utc),
                newer_accepted_at=datetime(2025, 12, 1, tzinfo=timezone.utc),
            )
            self.assertEqual([item["relative_path"] for item in plan["eligible"]], ["old-pass"])
            self.assertTrue((root / "old-pass/bundle.json").exists())
            self.assertTrue((root / "failure/bundle.json").exists())

    def test_minimizer_requires_sealed_isolated_failure_and_exact_three_of_three_signature(self) -> None:
        signature = {"invariant_id": "X", "layer": "authoritative", "selector": "count", "reason_code": "EXTRA"}
        actions = [
            {"id": "setup", "mandatory": True},
            {"id": "noise-a"},
            {"id": "trigger", "depends_on": ["setup"], "failure_signature": signature},
            {"id": "after"},
        ]

        def replay(candidate: list[dict[str, object]]) -> dict[str, object]:
            return signature if {item["id"] for item in candidate} >= {"setup", "trigger"} else {"other": True}

        with self.assertRaisesRegex(evidence.EvidenceError, "sealed"):
            evidence.minimize(actions, signature=signature, replay=replay, original_sealed=False, isolated_copy=True)
        with self.assertRaisesRegex(evidence.EvidenceError, "isolated"):
            evidence.minimize(actions, signature=signature, replay=replay, original_sealed=True, isolated_copy=False)
        result = evidence.minimize(actions, signature=signature, replay=replay, original_sealed=True, isolated_copy=True)
        self.assertTrue(result["stable"])
        self.assertEqual(result["minimum_action_ids"], ["setup", "trigger"])
        self.assertTrue(result["original_retained"])
        self.assertGreaterEqual(result["attempts"], 2)


if __name__ == "__main__":
    unittest.main()
