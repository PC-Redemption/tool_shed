from __future__ import annotations

from pathlib import Path
from unittest import mock
import tempfile
import sys
import unittest


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import project_projection  # noqa: E402


class ProjectProjectionTests(unittest.TestCase):
    def executive_fixture(self) -> dict[str, object]:
        artifact = {
            "artifact_id": "artifact-1", "visible_id": "CAMP-0001",
            "artifact_type": "campaign", "title": "Finish the view",
            "document_lifecycle": "working", "outcome_lifecycle": "open",
            "outcome_disposition": "open", "reconciliation_state": "open",
            "parent_ids": ["PRM-0001"], "produces_ids": [],
            "planning_position": None, "planning_readiness": "working",
            "closure_status": {"effective_closed": False, "local_closure": "open"},
            "updated_at": "2026-09-11T00:00:00Z",
        }
        return {
            "schema_version": 1, "kind": "tool-shed-project-executive-view",
            "authority": {"authority": "sqlite", "state": "hybrid"},
            "source_revision": 4, "source_digest": "source", "state_digest": "state",
            "latest_source_update": "2026-09-11T00:00:00Z",
            "state": {
                "working_count": 1, "ready_count": 0, "blocked_count": 0,
                "active_idea_count": 0, "open_outcome_count": 1,
                "unreconciled_outcome_count": 0, "closure_debt_count": 0,
                "active_loop_finding_count": 0,
            },
            "complete_accounting": True,
            "inventory": {"total_count": 1, "truncated": False, "artifacts": [artifact]},
            "focus_coverage": {
                "catalog_state": "approved", "areas": [], "unassigned_campaigns": [],
                "decisions_needed": [],
            },
            "release_horizon": {"available": True, "base_tag": "v1.0.0", "active_cohorts": []},
            "attention": [], "recommendations": [artifact], "recent_changes": [artifact],
            "loop_findings": {"total_active_count": 0, "findings": []},
            "writes_performed": False,
        }

    def test_build_resolves_authority_once_and_shares_the_exact_decision(self) -> None:
        workspace = Path("/fixture")
        authority = {
            "state": "qualified-shadow",
            "authority": "file",
            "reason": "fixture",
            "feature_limits": ["bounded-fixture"],
        }

        loop_projection = {"total_active_count": 3, "findings": []}

        def summary(candidate: Path) -> dict[str, int]:
            self.assertEqual(workspace, candidate)
            return {"active_idea_count": 2}

        def inventory(candidate: Path, decision: dict[str, object]) -> dict[str, object]:
            self.assertEqual(workspace, candidate)
            self.assertIs(authority, decision)
            return {"total_count": 2, "truncated": False, "artifacts": []}

        with mock.patch.object(
            project_projection.authority_resolver, "resolve", return_value=authority
        ) as resolved, mock.patch.object(
            project_projection.loop_findings, "report_projection", return_value=loop_projection
        ) as projected_loops, mock.patch.object(
            project_projection, "_file_summary", side_effect=summary
        ) as summarized, mock.patch.object(
            project_projection, "_inventory", side_effect=inventory
        ) as inventoried:
            result = project_projection.build(workspace)

        resolved.assert_called_once_with(workspace)
        projected_loops.assert_called_once_with(workspace)
        summarized.assert_called_once_with(workspace)
        inventoried.assert_called_once_with(workspace, authority)
        self.assertEqual(2, result["schema_version"])
        self.assertEqual("tool-shed-project-projection", result["kind"])
        self.assertEqual("file", result["authority"]["authority"])
        self.assertEqual(["bounded-fixture"], result["authority"]["feature_limits"])
        self.assertIs(loop_projection, result["loop_findings"])
        self.assertFalse(result["writes_performed"])

    def test_build_refuses_unknown_authority_before_reading_consumers(self) -> None:
        authority = {"state": "invalid", "authority": "none", "reason": "split truth"}
        with mock.patch.object(
            project_projection.authority_resolver, "resolve", return_value=authority
        ), mock.patch.object(project_projection, "_file_summary") as summarized, mock.patch.object(
            project_projection, "_inventory"
        ) as inventoried:
            with self.assertRaisesRegex(project_projection.ProjectProjectionError, "split truth"):
                project_projection.build(Path("/fixture"))
        summarized.assert_not_called()
        inventoried.assert_not_called()

    def test_render_is_deterministic_and_contains_concise_and_complete_sections(self) -> None:
        view = self.executive_fixture()
        first = project_projection.render_executive(view)
        second = project_projection.render_executive(view)
        self.assertEqual(first, second)
        self.assertTrue(first.startswith(project_projection.EXECUTIVE_MARKER))
        self.assertIn("## Executive Review", first)
        self.assertIn("## Complete Strategic Ledger", first)
        self.assertIn("`CAMP-0001`", first)
        self.assertNotIn("Generated at", first)

    def test_refresh_check_and_manual_edit_protection(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            expected = project_projection.render_executive(self.executive_fixture())
            with mock.patch.object(
                project_projection,
                "expected_executive_markdown",
                return_value=(self.executive_fixture(), expected),
            ):
                refreshed = project_projection.refresh_executive(workspace)
                self.assertTrue(refreshed["writes_performed"])
                self.assertEqual("current", project_projection.check_executive(workspace)["state"])
                path = workspace / project_projection.EXECUTIVE_RELATIVE
                path.write_text(expected + "manual\n", encoding="utf-8")
                self.assertEqual("stale", project_projection.check_executive(workspace)["state"])
                path.write_text("owner-authored\n", encoding="utf-8")
                with self.assertRaisesRegex(
                    project_projection.ProjectProjectionError, "non-generated"
                ):
                    project_projection.refresh_executive(workspace)


if __name__ == "__main__":
    unittest.main()
