from __future__ import annotations

from pathlib import Path
from unittest import mock
import json
import sqlite3
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
            "metadata_role": None,
            "document_lifecycle": "working", "outcome_lifecycle": "open",
            "outcome_disposition": "open", "reconciliation_state": "open",
            "parent_ids": ["PRM-0001"], "produces_ids": [],
            "planning_position": None, "planning_readiness": "working",
            "closure_status": {"effective_closed": False, "local_closure": "open"},
            "updated_at": "2026-09-11T00:00:00Z",
        }
        return {
            "schema_version": 3, "kind": "tool-shed-project-executive-view",
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
            "executive_intent": {
                "state": "current", "identity": "DEC-0001", "revision": 2,
                "updated_at": "2026-09-10T00:00:00Z",
                "north_star": "Keep the whole project pointed at the owner outcome.",
                "completion_horizon": "Finish the current reliable release.",
                "strategic_context": "Reliability is the limiting condition.",
                "priorities": ["Finish the view."],
                "non_goals": ["Do not start unrelated work."],
                "decisions_needed": ["Choose the next release candidate."],
                "review_triggers": ["Review after each release."],
                "missing_sections": [],
            },
            "focus_coverage": {
                "catalog_state": "approved", "areas": [], "unassigned_campaigns": [],
                "decisions_needed": [],
            },
            "release_horizon": {"available": True, "base_tag": "v1.0.0", "active_cohorts": []},
            "attention": [], "recommendations": [artifact], "executive_directives": [],
            "recent_changes": [artifact],
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

    def test_render_is_deterministic_and_keeps_complete_ledger_as_drill_down(self) -> None:
        view = self.executive_fixture()
        first = project_projection.render_executive(view)
        second = project_projection.render_executive(view)
        self.assertEqual(first, second)
        self.assertTrue(first.startswith(project_projection.EXECUTIVE_MARKER))
        self.assertIn("## Executive Review", first)
        self.assertIn("## North Star", first)
        self.assertIn("## Executive Directives", first)
        self.assertIn("`ts: 100k add <directive>`", first)
        self.assertIn("## Decisions And Attention", first)
        self.assertIn("## Accounting And Drill-Down", first)
        self.assertNotIn("## Complete Strategic Ledger", first)
        self.assertIn("`CAMP-0001`", first)
        self.assertNotIn("Generated at", first)
        ledger = project_projection.render_ledger(view)
        self.assertIn("## Complete Strategic Ledger", ledger)
        self.assertIn("`CAMP-0001`", ledger)
        self.assertNotIn(project_projection.EXECUTIVE_MARKER, ledger)

    def test_render_shows_ceo_directive_and_subordinate_handoff(self) -> None:
        view = self.executive_fixture()
        directive = {
            "artifact_id": "directive-1",
            "visible_id": "IDEA-0030",
            "artifact_type": "idea-brief",
            "title": "Make releases boring",
            "metadata_role": project_projection.EXECUTIVE_DIRECTIVE_ROLE,
            "document_lifecycle": "active",
            "outcome_lifecycle": "working",
            "outcome_disposition": "open",
            "reconciliation_state": "open",
            "parent_ids": [],
            "produces_ids": ["MAP-0038"],
            "planning_position": 1,
            "planning_readiness": "working",
            "closure_status": {"effective_closed": False, "local_closure": "open"},
            "updated_at": "2026-09-12T00:00:00Z",
            "directive_stage": "delegated",
            "subordinate_handoff": ["MAP-0038"],
        }
        view["executive_directives"] = [directive]
        rendered = project_projection.render_executive(view)
        self.assertIn("`IDEA-0030` — Make releases boring", rendered)
        self.assertIn("delegated", rendered)
        self.assertIn("`MAP-0038`", rendered)
        self.assertIn("subordinate cycles continue", rendered)
        self.assertNotIn("operator must explicitly choose", rendered)

    def test_file_inventory_marks_executive_directive_role(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            path = workspace / "work/ideas/directive-reliable-release.md"
            path.parent.mkdir(parents=True)
            path.write_text(
                "# Executive Directive: Reliable release\n\n"
                "Status: ready-for-prm\nType: idea-brief\n"
                f"Role: {project_projection.EXECUTIVE_DIRECTIVE_ROLE}\n"
                "Updated: 2026-09-12\n",
                encoding="utf-8",
            )
            with mock.patch.object(
                project_projection.planning_order,
                "file_projection",
                return_value={"items": []},
            ), mock.patch.object(
                project_projection.authority_resolver,
                "file_artifact_id",
                return_value="directive-1",
            ):
                inventory = project_projection._inventory(
                    workspace, {"authority": "file"}
                )
        self.assertEqual(
            project_projection.EXECUTIVE_DIRECTIVE_ROLE,
            inventory["artifacts"][0]["metadata_role"],
        )

    @staticmethod
    def intent_body(*, role: bool = True) -> str:
        role_header = f"Role: {project_projection.EXECUTIVE_INTENT_ROLE}\n" if role else ""
        return (
            "# Project Executive Intent\n\nStatus: active\nType: decision\n"
            f"{role_header}Updated: 2026-09-12\n\n"
            "## North Star\n\nMake the owner outcome visible.\n\n"
            "## Current Completion Horizon\n\nFinish the trusted cockpit.\n\n"
            "## Strategic Context\n\nThe report currently hides intent.\n\n"
            "## Current Priorities\n\n- Restore orientation.\n\n"
            "## Deliberate Non-Goals\n\n- Do not invent strategy.\n\n"
            "## Decisions Needed\n\n- Confirm the next horizon.\n\n"
            "## Review Triggers\n\n- Review after material outcomes.\n"
        )

    def test_file_executive_intent_uses_fixed_role_and_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            path = workspace / project_projection.EXECUTIVE_INTENT_RELATIVE
            path.parent.mkdir(parents=True)
            path.write_text(self.intent_body(), encoding="utf-8")
            result = project_projection._executive_intent(
                workspace, {"authority": "file"}
            )
            self.assertEqual("current", result["state"])
            self.assertEqual("Make the owner outcome visible.", result["north_star"])
            self.assertEqual(["Restore orientation."], result["priorities"])
            path.write_text(self.intent_body(role=False), encoding="utf-8")
            with self.assertRaisesRegex(project_projection.ProjectProjectionError, "must declare"):
                project_projection._executive_intent(workspace, {"authority": "file"})

    def test_file_inventory_rediscovers_supported_existing_project_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            work = workspace / "work"
            (work / "maps").mkdir(parents=True)
            (work / "maps" / "map-0007-existing.md").write_text(
                "# MAP-0007 Existing Direction\n\n"
                "Status: active\nType: project-map\nUpdated: 2026-09-12\n",
                encoding="utf-8",
            )
            (work / "notes.md").write_text(
                "# Notes\n\nStatus: active\nType: checklist\nUpdated: 2026-09-12\n",
                encoding="utf-8",
            )
            with mock.patch.object(
                project_projection.planning_order,
                "file_projection",
                return_value={"items": []},
            ), mock.patch.object(
                project_projection.authority_resolver,
                "file_artifact_id",
                return_value="artifact-map-7",
            ):
                inventory = project_projection._inventory(
                    workspace, {"authority": "file"}
                )

        self.assertEqual(1, inventory["total_count"])
        self.assertEqual("MAP-0007", inventory["artifacts"][0]["visible_id"])
        self.assertEqual("project-map", inventory["artifacts"][0]["artifact_type"])

    def test_sqlite_executive_intent_reuses_managed_decision_document(self) -> None:
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        connection.execute("CREATE TABLE artifact (id TEXT, type TEXT)")
        connection.execute(
            "CREATE TABLE document (id TEXT, visible_id TEXT, current_revision INTEGER, "
            "updated_at TEXT, metadata_json TEXT, lifecycle_state TEXT)"
        )
        connection.execute(
            "CREATE TABLE document_revision (document_id TEXT, revision_number INTEGER, body_markdown TEXT)"
        )
        connection.execute("INSERT INTO artifact VALUES ('a', 'decision')")
        connection.execute(
            "INSERT INTO document VALUES ('a','DEC-0001',2,'2026-09-12T00:00:00Z',?, 'active')",
            (json.dumps({"role": project_projection.EXECUTIVE_INTENT_ROLE}),),
        )
        connection.execute(
            "INSERT INTO document_revision VALUES ('a',2,?)", (self.intent_body(),)
        )
        with mock.patch.object(
            project_projection.hybrid_state, "database_path", return_value=Path("/fixture/state.sqlite3")
        ), mock.patch.object(project_projection.hybrid_state, "connect", return_value=connection):
            result = project_projection._executive_intent(
                Path("/fixture"), {"authority": "sqlite"}
            )
        self.assertEqual("DEC-0001", result["identity"])
        self.assertEqual(2, result["revision"])
        self.assertEqual("current", result["state"])

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
                self.assertEqual("current", refreshed["executive_intent_state"])
                self.assertIsNone(refreshed["next_route"])
                self.assertEqual("current", project_projection.check_executive(workspace)["state"])
                path = workspace / project_projection.EXECUTIVE_RELATIVE
                path.write_text(expected + "manual\n", encoding="utf-8")
                self.assertEqual("stale", project_projection.check_executive(workspace)["state"])
                path.write_text("owner-authored\n", encoding="utf-8")
                with self.assertRaisesRegex(
                    project_projection.ProjectProjectionError, "non-generated"
                ):
                    project_projection.refresh_executive(workspace)

    def test_refresh_migrates_the_generated_v1_view(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            path = workspace / project_projection.EXECUTIVE_RELATIVE
            path.parent.mkdir(parents=True)
            path.write_text(
                project_projection.LEGACY_EXECUTIVE_MARKERS[0] + "\nlegacy\n",
                encoding="utf-8",
            )
            expected = project_projection.render_executive(self.executive_fixture())
            with mock.patch.object(
                project_projection,
                "expected_executive_markdown",
                return_value=(self.executive_fixture(), expected),
            ):
                project_projection.refresh_executive(workspace)
            self.assertEqual(expected, path.read_text(encoding="utf-8"))

    def test_refresh_surfaces_setup_route_when_intent_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            view = self.executive_fixture()
            view["executive_intent"] = project_projection._missing_executive_intent()
            expected = project_projection.render_executive(view)
            with mock.patch.object(
                project_projection,
                "expected_executive_markdown",
                return_value=(view, expected),
            ):
                refreshed = project_projection.refresh_executive(workspace)
                checked = project_projection.check_executive(workspace)
        self.assertEqual("missing", refreshed["executive_intent_state"])
        self.assertEqual("ts: 100k setup", refreshed["next_route"])
        self.assertEqual("ts: 100k setup", checked["next_route"])

    def test_missing_intent_is_an_explicit_decision_signal(self) -> None:
        view = self.executive_fixture()
        view["executive_intent"] = project_projection._missing_executive_intent()
        rendered = project_projection.render_executive(view)
        self.assertIn("EXECUTIVE_INTENT_MISSING", rendered)
        self.assertIn("**Not established.**", rendered)
        self.assertIn("`ts: 100k setup`", rendered)

    def test_setup_discovers_evidence_but_requires_owner_acceptance(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            (workspace / "README.md").write_text("# Fixture\n", encoding="utf-8")
            (workspace / "docs").mkdir()
            (workspace / "docs" / "strategy.md").write_text("# Strategy\n", encoding="utf-8")
            view = self.executive_fixture()
            view["executive_intent"] = project_projection._missing_executive_intent()
            before = sorted(path.relative_to(workspace) for path in workspace.rglob("*"))
            setup = project_projection.executive_intent_setup(workspace, view)
            rendered = project_projection.render_intent_setup(setup)
            after = sorted(path.relative_to(workspace) for path in workspace.rglob("*"))

        self.assertEqual(before, after)
        self.assertEqual("owner-review-required", setup["state"])
        self.assertTrue(setup["owner_acceptance_required"])
        self.assertEqual(
            [heading for _, heading in project_projection.EXECUTIVE_INTENT_SECTIONS],
            setup["missing_sections"],
        )
        self.assertEqual(["README.md", "docs/strategy.md"], setup["orientation_sources"])
        self.assertEqual("CAMP-0001", setup["artifact_evidence"][0]["visible_id"])
        self.assertIn("## Acceptance Boundary", rendered)
        self.assertIn("A workspace upgrade or bare `ts: 100k` read never performs step 4.", rendered)

    def test_setup_reports_existing_intent_without_requesting_a_replacement(self) -> None:
        setup = project_projection.executive_intent_setup(
            Path("/fixture"), self.executive_fixture()
        )
        self.assertEqual("already-established", setup["state"])
        self.assertFalse(setup["owner_acceptance_required"])
        self.assertEqual([], setup["missing_sections"])

    def test_setup_preserves_existing_sections_and_proposes_only_incomplete_gaps(self) -> None:
        view = self.executive_fixture()
        intent = dict(view["executive_intent"])
        intent.update({
            "state": "incomplete",
            "decisions_needed": [],
            "missing_sections": ["Decisions Needed"],
        })
        view["executive_intent"] = intent
        setup = project_projection.executive_intent_setup(Path("/fixture"), view)
        rendered = project_projection.render_intent_setup(setup)
        self.assertEqual(["Decisions Needed"], setup["missing_sections"])
        self.assertEqual(
            "Keep the whole project pointed at the owner outcome.",
            setup["existing_values"]["north_star"],
        )
        self.assertIn("Keep the whole project pointed at the owner outcome.", rendered)
        self.assertIn("### Decisions Needed\n\n- [Owner decision required", rendered)

    def test_parser_routes_ledger_as_an_explicit_drill_down(self) -> None:
        review = project_projection.build_parser().parse_args(["100k"])
        ledger = project_projection.build_parser().parse_args(["100k", "ledger"])
        setup = project_projection.build_parser().parse_args(["100k", "setup"])
        self.assertEqual("review", review.section)
        self.assertEqual("ledger", ledger.section)
        self.assertEqual("setup", setup.section)


if __name__ == "__main__":
    unittest.main()
