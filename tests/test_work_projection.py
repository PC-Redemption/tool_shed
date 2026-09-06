from __future__ import annotations

import unittest
from types import SimpleNamespace

from dashboard.fleet.work_projection import build_tree, command_actions, is_remaining


def item(
    visible_id: str,
    *,
    parents: list[str] | None = None,
    artifact_type: str = "campaign",
    lifecycle: str = "active",
    outcome: str = "working",
    disposition: str = "open",
    reconciliation: str = "open",
    readiness: str = "ready",
    closed: bool = False,
) -> SimpleNamespace:
    return SimpleNamespace(
        visible_id=visible_id,
        artifact_type=artifact_type,
        title=visible_id,
        document_lifecycle=lifecycle,
        outcome_lifecycle=outcome,
        outcome_disposition=disposition,
        reconciliation_state=reconciliation,
        parent_ids=parents or [],
        produces_ids=[],
        planning_position=None,
        planning_readiness=readiness,
        closure_status={"effective_closed": closed},
        release_chain=None,
        local_findings=[],
    )


class WorkProjectionTests(unittest.TestCase):
    def test_only_explicitly_complete_work_leaves_remaining(self) -> None:
        complete = item(
            "CAMP-0001",
            lifecycle="completed",
            outcome="terminal",
            disposition="satisfied",
            reconciliation="reconciled",
            readiness="terminal",
            closed=True,
        )
        self.assertFalse(is_remaining(complete))
        complete.release_chain = {"stage": "awaiting-work5"}
        self.assertTrue(is_remaining(complete))
        complete.release_chain = None
        complete.reconciliation_state = "open"
        self.assertTrue(is_remaining(complete))

    def test_unknown_legacy_fields_do_not_create_remaining_work(self) -> None:
        for lifecycle in ("completed", "superseded", "abandoned", "deferred"):
            legacy = item(
                f"MAP-{lifecycle}",
                artifact_type="project-map",
                lifecycle=lifecycle,
                outcome="unknown",
                disposition="unknown",
                reconciliation="unknown",
            )
            legacy.closure_status = {
                "effective_closed": False,
                "reason_codes": ["CLOSURE_NOT_AVAILABLE"],
                "counts": {"open": 0, "unknown": 1, "invalid": 0},
            }
            self.assertFalse(is_remaining(legacy), lifecycle)

    def test_explicit_obligations_remain_visible(self) -> None:
        cases = (
            item("IDEA-0001", artifact_type="idea-brief", lifecycle="active", outcome="unknown", disposition="unknown", reconciliation="unknown"),
            item("CAMP-0001", lifecycle="completed", outcome="working", disposition="unknown", reconciliation="unknown"),
            item("CAMP-0002", lifecycle="completed", outcome="terminal", disposition="open", reconciliation="unknown"),
            item("CAMP-0003", lifecycle="completed", outcome="terminal", disposition="satisfied", reconciliation="open"),
        )
        closure_debt = item(
            "CAMP-0004",
            lifecycle="completed",
            outcome="terminal",
            disposition="satisfied",
            reconciliation="reconciled",
        )
        closure_debt.closure_status = {
            "effective_closed": False,
            "reason_codes": ["DESCENDANT_OPEN"],
            "counts": {"open": 1, "unknown": 0, "invalid": 0},
        }
        for value in (*cases, closure_debt):
            self.assertTrue(is_remaining(value), value.visible_id)

    def test_completed_ancestor_is_context_only_for_remaining_descendant(self) -> None:
        root = item(
            "MAP-0001",
            artifact_type="project-map",
            lifecycle="completed",
            outcome="unknown",
            disposition="unknown",
            reconciliation="unknown",
        )
        root.closure_status = {
            "effective_closed": False,
            "reason_codes": ["CLOSURE_NOT_AVAILABLE"],
            "counts": {"open": 0, "unknown": 1, "invalid": 0},
        }
        child = item("CAMP-0001", parents=["MAP-0001"])

        projection = build_tree([root, child], scope="remaining")

        self.assertEqual(projection["match_count"], 1)
        self.assertEqual([row.visible_id for row in projection["rows"]], ["MAP-0001", "CAMP-0001"])
        self.assertTrue(root.tree_context)
        self.assertFalse(child.tree_context)

    def test_multiple_and_cyclic_parentage_are_bounded_needs_placement(self) -> None:
        rows = [
            item("IDEA-0001", artifact_type="idea-brief"),
            item("IDEA-0002", artifact_type="idea-brief"),
            item("CAMP-0001", parents=["IDEA-0001", "IDEA-0002"]),
            item("CAMP-0002", parents=["CAMP-0003"]),
            item("CAMP-0003", parents=["CAMP-0002"]),
        ]
        projection = build_tree(rows, scope="remaining")
        self.assertEqual(projection["match_count"], 5)
        self.assertEqual(projection["placement_count"], 3)
        placement = next(group for group in projection["root_groups"] if group["needs_placement"])
        reasons = {row.visible_id: row.tree_placement_reason for row in placement["rows"]}
        self.assertEqual(reasons["CAMP-0001"], "multiple owning parents")
        self.assertEqual(reasons["CAMP-0002"], "cyclic parent relationship")
        self.assertEqual(reasons["CAMP-0003"], "cyclic parent relationship")

    def test_command_allowlist_uses_only_stable_identifiers(self) -> None:
        campaign = item("CAMP-0169")
        campaign.title = "$(unsafe) secret /path"
        commands = {action["command"] for action in command_actions(campaign)}
        self.assertEqual(commands, {"ts: next camp 0169", "ts: status"})
        self.assertTrue(all("unsafe" not in command for command in commands))

    def test_root_groups_keep_complete_branches_as_pagination_units(self) -> None:
        rows = [
            item("IDEA-0001", artifact_type="idea-brief"),
            item("MAP-0001", artifact_type="project-map", parents=["IDEA-0001"]),
            item("CAMP-0001", parents=["MAP-0001"]),
            item("IDEA-0002", artifact_type="idea-brief"),
        ]
        projection = build_tree(rows, scope="remaining")
        groups = projection["root_groups"]
        self.assertEqual([[row.visible_id for row in group["rows"]] for group in groups], [
            ["IDEA-0001", "MAP-0001", "CAMP-0001"],
            ["IDEA-0002"],
        ])


if __name__ == "__main__":
    unittest.main()
