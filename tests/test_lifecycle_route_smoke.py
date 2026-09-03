from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import lifecycle_route_smoke as smoke  # noqa: E402


class LifecycleRouteSmokeTests(unittest.TestCase):
    candidate = {
        "manifest_sha256": "b" * 64,
        "shed_version": "0.43.0",
        "tracked_files": 275,
        "integrity": "verified",
        "missing": [],
        "modified": [],
    }

    def test_structural_oracle_accepts_exact_idempotent_route(self) -> None:
        idea = {"artifact_id": "idea", "visible_id": "IDEA-0001", "type": "idea-brief", "title": "run", "lifecycle": "completed", "revision": 3, "body_sha256": "new", "metadata": {}}
        provenance = {"reviewed_idea_artifact_id": "idea", "reviewed_idea_document_revision": 2, "reviewed_idea_body_sha256": "old", "readiness_gate_ids": ["G1"]}
        project_map = {"artifact_id": "map", "visible_id": "MAP-0001", "type": "project-map", "title": "run", "lifecycle": "completed", "revision": 2, "body_sha256": "m", "metadata": dict(provenance)}
        roadmap = {"artifact_id": "prm", "visible_id": "PRM-0001", "type": "program-roadmap", "title": "run", "lifecycle": "completed", "revision": 2, "body_sha256": "p", "metadata": dict(provenance)}
        campaign = {"artifact_id": "camp", "visible_id": "CAMP-0001", "type": "campaign", "title": "run", "lifecycle": "completed", "revision": 2, "body_sha256": "c", "metadata": {}}
        docs = [idea, project_map, roadmap, campaign]
        relations = []
        for parent, child in zip(docs, docs[1:]):
            relations.extend([
                {"from_artifact_id": parent["artifact_id"], "relation_type": "produces", "to_artifact_id": child["artifact_id"]},
                {"from_artifact_id": child["artifact_id"], "relation_type": "outcome-parent", "to_artifact_id": parent["artifact_id"]},
            ])
        cycles = [{"id": name, "lifecycle_state": "terminal", "verdict": {"disposition": "satisfied"}, "reconciliation": {"state": "reconciled"}} for name in ("ci", "cm", "cp", "cc")]
        readiness = [{"idea": {"artifact_id": "idea", "document_revision": 2, "body_sha256": "old"}, "verdict": "READY-WITH-PRM-GATES", "prm_gates": [{"id": "G1"}]}]
        completed = {"run_tag": "route-1", "candidate_snapshot": self.candidate, "database_revision": 20, "domain_digest": "d", "documents": docs, "relationships": relations, "cycles": cycles, "readiness_results": readiness, "closure_elements": {name: {"effective_closed": True} for name in ("ci", "cm", "cp", "cc")}, "projection_mismatches": []}
        result = smoke.evaluate(
            {"database_revision": 1, "candidate_snapshot": self.candidate}, completed, dict(completed), provider="openai", model="gpt", effort="low", turns=5, duration_seconds=10, adapter_version="1", platform_name="linux-x86_64", candidate_commit="a" * 40, candidate_manifest_sha256="b" * 64
        )
        self.assertEqual(result["verdict"], "PASS", result)

    def test_structural_oracle_rejects_duplicate_and_replay_write(self) -> None:
        completed = {"run_tag": "route-1", "candidate_snapshot": self.candidate, "database_revision": 20, "domain_digest": "d", "documents": [], "relationships": [], "cycles": [], "readiness_results": [], "closure_elements": {}, "projection_mismatches": []}
        replayed = {**completed, "database_revision": 21, "domain_digest": "changed"}
        result = smoke.evaluate(
            {"database_revision": 1, "candidate_snapshot": self.candidate}, completed, replayed, provider="openai", model="gpt", effort="low", turns=5, duration_seconds=10, adapter_version="1", platform_name="windows-amd64", candidate_commit="a" * 40, candidate_manifest_sha256="b" * 64
        )
        self.assertEqual(result["verdict"], "PRODUCT-FAIL")
        self.assertEqual(result["first_divergence"], "ROUTE-CARDINALITY")

    def test_structural_oracle_rejects_candidate_snapshot_drift(self) -> None:
        completed = {"run_tag": "route-1", "candidate_snapshot": self.candidate, "database_revision": 20, "domain_digest": "d", "documents": [], "relationships": [], "cycles": [], "readiness_results": [], "closure_elements": {}, "projection_mismatches": []}
        replayed = {**completed, "candidate_snapshot": {**self.candidate, "manifest_sha256": "c" * 64}}
        result = smoke.evaluate(
            {"database_revision": 1, "candidate_snapshot": self.candidate}, completed, replayed, provider="openai", model="gpt", effort="low", turns=5, duration_seconds=10, adapter_version="1", platform_name="windows-amd64", candidate_commit="a" * 40, candidate_manifest_sha256="b" * 64
        )
        self.assertEqual(result["first_divergence"], "ROUTE-CANDIDATE-BINDING")


if __name__ == "__main__":
    unittest.main()
