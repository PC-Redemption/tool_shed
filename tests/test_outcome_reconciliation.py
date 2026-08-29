from __future__ import annotations

import hashlib
import contextlib
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import hybrid_state
import outcome_loop
import outcome_reconciliation


def project_binding(workspace: Path) -> str:
    project_id = json.loads(
        (workspace / "work/tool-shed-project.json").read_text(encoding="utf-8")
    )["project_id"]
    digest = hashlib.sha256()
    for value in ("tool-shed-binding-v1", project_id, str(workspace.resolve()), "hybrid-state"):
        digest.update(value.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()[:24]


class OutcomeReconciliationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temporary.name)
        bootstrap = json.loads(
            (ROOT / outcome_reconciliation.DEFAULT_BOOTSTRAP).read_text(encoding="utf-8")
        )
        self.project_id = bootstrap["project"]["project_id"]
        self.prepare_workspace(self.workspace)
        self.binding = project_binding(self.workspace)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def prepare_workspace(self, workspace: Path) -> None:
        workspace.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init", "--quiet"], cwd=workspace, check=True)
        subprocess.run(["git", "config", "user.name", "Tool Shed Tests"], cwd=workspace, check=True)
        subprocess.run(["git", "config", "user.email", "tests@example.invalid"], cwd=workspace, check=True)
        identity = workspace / "work/tool-shed-project.json"
        identity.parent.mkdir(parents=True, exist_ok=True)
        identity.write_text(
            json.dumps(
                {"schema_version": 1, "project_id": self.project_id, "project_name": "tool_shed"},
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        (workspace / ".gitignore").write_text("/.tool-shed/\n", encoding="utf-8")
        sources = {
            outcome_reconciliation.DEFAULT_BOOTSTRAP,
            outcome_reconciliation.DEFAULT_IDS,
            Path("schemas/hybrid-state/v1/maintainer-assigned-ids.json"),
            *(Path(value) for value in outcome_reconciliation.PRODUCT_PATHS.values()),
        }
        for relative in sources:
            source = ROOT / relative
            destination = workspace / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        subprocess.run(["git", "add", "."], cwd=workspace, check=True)
        subprocess.run(["git", "commit", "--quiet", "-m", "fixture"], cwd=workspace, check=True)

    def apply_slice(self) -> dict[str, object]:
        hybrid_state.initialize(self.workspace, project_binding=self.binding)
        return outcome_reconciliation.apply_hpt2(
            self.workspace, project_binding=self.binding
        )

    def generic_source(self, *, mode: str = "current", ambiguities: list[str] | None = None) -> Path:
        (self.workspace / "origin.md").write_text("# Accepted origin\n", encoding="utf-8")
        (self.workspace / "product.py").write_text("RESULT = 'qualified'\n", encoding="utf-8")
        parent_id = json.loads(
            (self.workspace / outcome_reconciliation.DEFAULT_IDS).read_text(encoding="utf-8")
        )["ids"]["artifact"]["closed-loop-idea"]
        source = {
            "schema_version": 1,
            "kind": outcome_loop.SOURCE_KIND,
            "mode": mode,
            "project_id": self.project_id,
            "authorization_ref": "fixture approval",
            "ambiguities": ambiguities or [],
            "cycle": {
                "kind": "idea",
                "origin": {"path": "origin.md", "type": "markdown"},
                "accepted_outcome": "Deliver and prove the qualified result.",
                "lifecycle_state": "terminal",
                "opened_at": "2026-08-28T18:00:00Z",
                "closed_at": "2026-08-28T19:00:00Z"
            },
            "product_truth": [{"key": "product", "path": "product.py", "type": "python"}],
            "requirements": [{
                "key": "qualified-result",
                "accepted_outcome": "The result is qualified.",
                "disposition": "accepted",
                "milestone_key": "M1",
                "evidence_gate_key": "G1"
            }],
            "changes": [{
                "key": "authorized-change",
                "requirement_key": "qualified-result",
                "summary": "Use the qualified implementation.",
                "rationale": "It satisfies the accepted outcome.",
                "authorization_ref": "fixture approval",
                "evidence_rerun": ["focused-test"]
            }],
            "evidence": [{
                "key": "focused-test",
                "kind": "test",
                "reference": "product.py",
                "target_identity": "fixture-product"
            }],
            "verifications": [{
                "key": "focused-test-result",
                "evidence_key": "focused-test",
                "requirement_key": "qualified-result",
                "status": "passed",
                "command_or_test_id": "python-product-test",
                "verified_at": "2026-08-28T19:00:00Z"
            }],
            "relationships": [
                {
                    "key": "product-evidence",
                    "from_artifact_key": "origin",
                    "to_artifact_key": "product",
                    "relation_type": "evidenced-by"
                },
                {
                    "key": "parent",
                    "from_artifact_key": "origin",
                    "to_artifact_id": parent_id,
                    "relation_type": "outcome-parent"
                },
                {
                    "key": "propagation",
                    "from_artifact_key": "origin",
                    "to_artifact_id": parent_id,
                    "relation_type": "outcome-result-propagated"
                }
            ],
            "verdict": {
                "scope": "initiative",
                "disposition": "satisfied",
                "summary": "Accepted outcome and current product truth agree.",
                "authorization_ref": "fixture approval",
                "decided_at": "2026-08-28T19:00:00Z"
            },
            "reconciliation": {
                "state": "reconciled",
                "compared_at": "2026-08-28T19:00:00Z",
                "residual_work": []
            }
        }
        path = self.workspace / "source.json"
        path.write_text(json.dumps(source, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return path

    def test_hpt2_import_preserves_unknown_history_and_bootstrap_parity(self) -> None:
        source_bytes = {
            relative: (self.workspace / relative).read_bytes()
            for relative in outcome_reconciliation.PRODUCT_PATHS.values()
        }
        imported = self.apply_slice()
        self.assertEqual(imported["result"]["hpt2_disposition"], "partial")
        self.assertEqual(imported["result"]["hpt2_reconciliation"], "reconciled")
        self.assertEqual(imported["result"]["missing_history"], outcome_reconciliation.MISSING_HPT2)
        mutation = outcome_reconciliation.apply_bounded_mutation(
            self.workspace, project_binding=self.binding
        )
        self.assertEqual(mutation["actual_writes"], 1)
        parity = outcome_reconciliation.qualify_parity(self.workspace)
        self.assertTrue(parity["valid"])
        self.assertTrue(parity["bootstrap_parity"])
        self.assertTrue(parity["operation_parity"])
        self.assertEqual(set(parity["operations"]), set(outcome_reconciliation.OPERATIONS))
        self.assertEqual(parity["hpt2_disposition"], "partial")
        self.assertEqual(parity["hpt2_reconciliation"], "reconciled")
        for relative, content in source_bytes.items():
            self.assertEqual((self.workspace / relative).read_bytes(), content)

    def test_fresh_workspace_import_and_checkpoint_rebuild_are_semantically_exact(self) -> None:
        self.apply_slice()
        outcome_reconciliation.apply_bounded_mutation(self.workspace, project_binding=self.binding)
        first = outcome_reconciliation.qualify_parity(self.workspace)
        checkpoint = hybrid_state.write_checkpoint(
            self.workspace, project_binding=self.binding
        )
        rebuilt = hybrid_state.rebuild_from_checkpoint(
            self.workspace,
            project_binding=self.binding,
            checkpoint=Path(checkpoint["path"]),
            output=Path(".tool-shed/rebuilt.sqlite3"),
        )
        self.assertEqual(rebuilt["domain_digest"], hybrid_state.audit(self.workspace)["domain_digest"])

        with tempfile.TemporaryDirectory() as directory:
            fresh = Path(directory)
            self.prepare_workspace(fresh)
            fresh_binding = project_binding(fresh)
            hybrid_state.initialize(fresh, project_binding=fresh_binding)
            outcome_reconciliation.apply_hpt2(fresh, project_binding=fresh_binding)
            outcome_reconciliation.apply_bounded_mutation(fresh, project_binding=fresh_binding)
            second = outcome_reconciliation.qualify_parity(fresh)
        self.assertTrue(first["valid"])
        self.assertTrue(second["valid"])
        self.assertEqual(first["bootstrap_projection_digest"], second["bootstrap_projection_digest"])
        self.assertEqual(first["operations"], second["operations"])

    def test_bootstrap_sync_reconciles_later_evidence_and_verdicts(self) -> None:
        self.apply_slice()
        outcome_reconciliation.apply_bounded_mutation(self.workspace, project_binding=self.binding)
        path = self.workspace / outcome_reconciliation.DEFAULT_BOOTSTRAP
        payload = json.loads(path.read_text(encoding="utf-8"))
        evidence = next(item for item in payload["evidence"] if item["id"] == "EVID-G3-MAINTAINER")
        evidence["status"] = "passed"
        evidence["verified_at"] = "2026-08-28T18:00:00Z"
        verdict = next(
            item for item in payload["verdicts"]
            if item["scope"] == "G3-MAINTAINER-CONVERSION-PROVEN"
        )
        verdict["disposition"] = "satisfied"
        verdict["summary"] = "Fixture maintainer conversion passed."
        payload["state_token"] = "fixture-post-cutover-token"
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        synchronized = outcome_reconciliation.sync_bootstrap(
            self.workspace,
            project_binding=self.binding,
        )
        self.assertEqual(
            synchronized["sync"]["result"]["bootstrap_state_token"],
            payload["state_token"],
        )
        self.assertTrue(outcome_reconciliation.qualify_parity(self.workspace)["valid"])
        self.assertEqual(hybrid_state.audit(self.workspace)["classification"], "VALID_DIRTY")

    def test_all_file_first_and_hybrid_capsules_match(self) -> None:
        self.apply_slice()
        outcome_reconciliation.apply_bounded_mutation(self.workspace, project_binding=self.binding)
        _, bootstrap, ids = outcome_reconciliation.load_sources(self.workspace)
        file_view = outcome_reconciliation.file_state(bootstrap, mutation_applied=True)
        hybrid_view = outcome_reconciliation.hybrid_state_view(self.workspace, ids)
        for operation in outcome_reconciliation.OPERATIONS:
            self.assertEqual(
                outcome_reconciliation.operation_result(file_view, operation),
                outcome_reconciliation.operation_result(hybrid_view, operation),
                operation,
            )

    def test_context_efficiency_suite_meets_frozen_thresholds(self) -> None:
        _, bootstrap, _ = outcome_reconciliation.load_sources(self.workspace)
        report = outcome_reconciliation.efficiency_report(self.workspace, bootstrap)
        self.assertTrue(report["passed"])
        self.assertTrue(report["semantic_parity"])
        self.assertGreaterEqual(report["median_reduction_percent"], 70.0)
        self.assertLessEqual(report["fallback_percent"], 5.0)
        self.assertEqual(len(report["operations"]), 24)
        self.assertEqual(
            {item["fixture"] for item in report["operations"]},
            {"small", "maintainer", "large"},
        )
        self.assertTrue(all(not item["fallback"] for item in report["operations"]))

    def test_foreign_project_and_non_v4_assignments_fail_closed(self) -> None:
        identity_path = self.workspace / "work/tool-shed-project.json"
        identity = json.loads(identity_path.read_text(encoding="utf-8"))
        identity["project_id"] = str(uuid.uuid4())
        identity_path.write_text(json.dumps(identity, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(
            outcome_reconciliation.ReconciliationError, "belongs to another"
        ):
            outcome_reconciliation.load_sources(self.workspace)

    def test_live_bootstrap_is_outside_frozen_hpt2_compatibility_boundary(self) -> None:
        live = Path("work/evidence/bootstrap-closure-live.json")
        source = self.workspace / outcome_reconciliation.DEFAULT_BOOTSTRAP
        payload = json.loads(source.read_text(encoding="utf-8"))
        payload["kind"] = "tool-shed-bootstrap-closure"
        destination = self.workspace / live
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(
            outcome_reconciliation.ReconciliationError,
            "frozen compatibility fixture",
        ):
            outcome_reconciliation.load_sources(self.workspace, live)

    def test_generic_cycles_do_not_mutate_hpt2_fixed_ids(self) -> None:
        self.apply_slice()
        ids_path = self.workspace / outcome_reconciliation.DEFAULT_IDS
        before = ids_path.read_bytes()
        manifest = outcome_loop.prepare(self.workspace, self.generic_source())
        outcome_loop.apply_manifest(
            self.workspace,
            manifest,
            expected_token=manifest["manifest_token"],
            project_binding=self.binding,
        )
        self.assertEqual(ids_path.read_bytes(), before)

    def test_generic_prepare_validate_apply_audit_report_and_as_of(self) -> None:
        imported = self.apply_slice()
        manifest = outcome_loop.prepare(self.workspace, self.generic_source())
        validation = outcome_loop.validate_manifest(self.workspace, manifest)
        self.assertTrue(validation["valid"])
        self.assertTrue(validation["applicable"])
        applied = outcome_loop.apply_manifest(
            self.workspace,
            manifest,
            expected_token=manifest["manifest_token"],
            project_binding=self.binding,
        )
        self.assertEqual(applied["result"]["verdict"], "satisfied")
        self.assertGreater(applied["revision"], imported["revision"])
        audit = outcome_loop.audit_loops(self.workspace)
        self.assertEqual(audit["unpropagated"], [])
        report = outcome_loop.report_cycle(self.workspace, manifest["cycle"]["id"])
        self.assertEqual(report["verdict"]["disposition"], "satisfied")
        self.assertEqual(len(report["requirements"]), 1)
        before = outcome_loop.report_cycle(
            self.workspace, manifest["cycle"]["id"], as_of=applied["revision"] - 1
        )
        self.assertIsNone(before["verdict"])
        self.assertIsNone(before["cycle"])
        self.assertEqual(before["later_overlays"][0]["origin_revision"], applied["revision"])

    def test_generic_apply_refuses_stale_token_and_state(self) -> None:
        self.apply_slice()
        manifest = outcome_loop.prepare(self.workspace, self.generic_source())
        with self.assertRaisesRegex(outcome_loop.OutcomeLoopError, "approved manifest token"):
            outcome_loop.apply_manifest(
                self.workspace,
                manifest,
                expected_token="0" * 16,
                project_binding=self.binding,
            )
        outcome_reconciliation.apply_bounded_mutation(
            self.workspace, project_binding=self.binding
        )
        validation = outcome_loop.validate_manifest(self.workspace, manifest)
        self.assertFalse(validation["valid"])
        self.assertIn("manifest expected_revision is stale", validation["errors"])

    def test_historical_backfill_preserves_and_refuses_ambiguity(self) -> None:
        self.apply_slice()
        manifest = outcome_loop.prepare(
            self.workspace,
            self.generic_source(mode="historical-overlay", ambiguities=["acceptance record missing"]),
            mode="historical-overlay",
        )
        validation = outcome_loop.validate_manifest(self.workspace, manifest)
        self.assertTrue(validation["valid"])
        self.assertFalse(validation["applicable"])
        with self.assertRaisesRegex(outcome_loop.OutcomeLoopError, "unresolved ambiguities"):
            outcome_loop.apply_manifest(
                self.workspace,
                manifest,
                expected_token=manifest["manifest_token"],
                project_binding=self.binding,
                backfill=True,
            )

    def test_terminal_child_requires_explicit_result_propagation(self) -> None:
        self.apply_slice()
        manifest = outcome_loop.prepare(self.workspace, self.generic_source())
        manifest["relationships"] = [
            item for item in manifest["relationships"]
            if item["relation_type"] != "outcome-result-propagated"
        ]
        manifest["manifest_token"] = outcome_loop.token(manifest)
        validation = outcome_loop.validate_manifest(self.workspace, manifest)
        self.assertFalse(validation["valid"])
        self.assertIn(
            "terminal reconciled child lacks outcome-result-propagated relationship",
            validation["errors"],
        )

    def test_all_supported_entry_classes_prepare_and_validate(self) -> None:
        self.apply_slice()
        source_path = self.generic_source()
        for entry_class in sorted(outcome_loop.SUPPORTED_ORIGIN_KINDS):
            source = json.loads(source_path.read_text(encoding="utf-8"))
            source["cycle"]["kind"] = entry_class
            source_path.write_text(json.dumps(source, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            manifest = outcome_loop.prepare(self.workspace, source_path)
            self.assertTrue(
                outcome_loop.validate_manifest(self.workspace, manifest)["valid"], entry_class
            )

    def test_generic_checkpoint_rebuild_preserves_domain_and_cycle_report(self) -> None:
        self.apply_slice()
        manifest = outcome_loop.prepare(self.workspace, self.generic_source())
        outcome_loop.apply_manifest(
            self.workspace,
            manifest,
            expected_token=manifest["manifest_token"],
            project_binding=self.binding,
        )
        expected_report = outcome_loop.report_cycle(self.workspace, manifest["cycle"]["id"])
        checkpoint = hybrid_state.write_checkpoint(self.workspace, project_binding=self.binding)
        rebuilt = hybrid_state.rebuild_from_checkpoint(
            self.workspace,
            project_binding=self.binding,
            checkpoint=Path(checkpoint["path"]),
            output=Path(".tool-shed/generic-rebuilt.sqlite3"),
        )
        self.assertEqual(rebuilt["domain_digest"], hybrid_state.audit(self.workspace)["domain_digest"])
        connection = hybrid_state.connect(self.workspace / ".tool-shed/generic-rebuilt.sqlite3", writable=False)
        try:
            row = connection.execute(
                "SELECT accepted_outcome FROM cycle WHERE id = ?", (manifest["cycle"]["id"],)
            ).fetchone()
        finally:
            connection.close()
        self.assertEqual(row["accepted_outcome"], expected_report["cycle"]["accepted_outcome"])

    def test_unambiguous_historical_backfill_applies_exact_manifest(self) -> None:
        self.apply_slice()
        manifest = outcome_loop.prepare(
            self.workspace, self.generic_source(mode="historical-overlay"), mode="historical-overlay"
        )
        applied = outcome_loop.apply_manifest(
            self.workspace,
            manifest,
            expected_token=manifest["manifest_token"],
            project_binding=self.binding,
            backfill=True,
        )
        self.assertEqual(applied["result"]["mode"], "historical-overlay")

    def test_generic_foreign_project_identity_fails_closed(self) -> None:
        self.apply_slice()
        manifest = outcome_loop.prepare(self.workspace, self.generic_source())
        manifest["project_id"] = str(uuid.uuid4())
        manifest["manifest_token"] = outcome_loop.token(manifest)
        validation = outcome_loop.validate_manifest(self.workspace, manifest)
        self.assertFalse(validation["valid"])
        self.assertIn("manifest belongs to another Tool Shed project", validation["errors"])

    def test_outcome_parent_graph_cycle_fails_closed(self) -> None:
        self.apply_slice()
        manifest = outcome_loop.prepare(self.workspace, self.generic_source())
        origin = manifest["cycle"]["origin_artifact_id"]
        product = next(item["id"] for item in manifest["artifacts"] if item["key"] == "product")
        manifest["relationships"].extend(
            [
                {
                    "key": "cycle-forward",
                    "id": str(uuid.uuid4()),
                    "from_artifact_id": origin,
                    "relation_type": "outcome-parent",
                    "to_artifact_id": product,
                    "provenance": "fixture"
                },
                {
                    "key": "cycle-forward-result",
                    "id": str(uuid.uuid4()),
                    "from_artifact_id": origin,
                    "relation_type": "outcome-result-propagated",
                    "to_artifact_id": product,
                    "provenance": "fixture"
                },
                {
                    "key": "cycle-reverse",
                    "id": str(uuid.uuid4()),
                    "from_artifact_id": product,
                    "relation_type": "outcome-parent",
                    "to_artifact_id": origin,
                    "provenance": "fixture"
                },
                {
                    "key": "cycle-reverse-result",
                    "id": str(uuid.uuid4()),
                    "from_artifact_id": product,
                    "relation_type": "outcome-result-propagated",
                    "to_artifact_id": origin,
                    "provenance": "fixture"
                }
            ]
        )
        manifest["manifest_token"] = outcome_loop.token(manifest)
        validation = outcome_loop.validate_manifest(self.workspace, manifest)
        self.assertFalse(validation["valid"])
        self.assertIn("outcome-parent graph contains a cycle", validation["errors"])

    def test_generic_cli_routes_execute_end_to_end(self) -> None:
        self.apply_slice()
        source = self.generic_source()

        def invoke(arguments: list[str]) -> tuple[int, dict[str, object]]:
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = outcome_reconciliation.main(["--workspace", str(self.workspace), *arguments])
            return code, json.loads(output.getvalue())

        code, manifest = invoke(["prepare", "--source", str(source)])
        self.assertEqual(code, 0)
        manifest_path = self.workspace / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        self.assertEqual(invoke(["validate", "--manifest", str(manifest_path)])[0], 0)
        code, applied = invoke([
            "apply", "--manifest", str(manifest_path), "--expect", manifest["manifest_token"],
            "--project-binding", self.binding
        ])
        self.assertEqual(code, 0)
        self.assertEqual(applied["result"]["cycle_id"], manifest["cycle"]["id"])
        self.assertEqual(invoke(["report", "--cycle", manifest["cycle"]["id"]])[0], 0)
        self.assertEqual(invoke(["audit"])[1]["finding_count"], 0)

        code, overlay = invoke(["backfill-plan", "--source", str(source)])
        self.assertEqual(code, 0)
        overlay_path = self.workspace / "overlay.json"
        overlay_path.write_text(json.dumps(overlay, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        code, result = invoke([
            "backfill-apply", "--manifest", str(overlay_path), "--expect", overlay["manifest_token"],
            "--project-binding", self.binding
        ])
        self.assertEqual(code, 0)
        self.assertEqual(result["result"]["mode"], "historical-overlay")

    def test_campaign_result_plan_records_terminal_local_outcome(self) -> None:
        self.apply_slice()
        self.generic_source()
        campaign = self.workspace / "work/00-campaigns/completed/999-fixture-campaign.md"
        campaign.parent.mkdir(parents=True, exist_ok=True)
        campaign.write_text(
            "# Fixture campaign\n\n"
            "Status: complete\nType: campaign\nUpdated: 2026-08-28\nNext Action: none\n"
            "Campaign ID: fixture-campaign\nOutcome: Deliver the qualified result.\n"
            "Completion Gate: Focused evidence passes.\nCompletion Evidence: product.py passed.\n"
            "Completion Date: 2026-08-28\nDisposition: completed\n"
            "Milestone: M1\nUnlocks Gate: G1\n",
            encoding="utf-8",
        )
        manifest = outcome_loop.plan_campaign_result(
            self.workspace,
            campaign,
            product_truth=["product.py"],
            evidence_paths=["product.py"],
            disposition="satisfied",
            authorization_ref="fixture completion approval",
        )
        self.assertTrue(outcome_loop.validate_manifest(self.workspace, manifest)["valid"])
        applied = outcome_loop.apply_manifest(
            self.workspace,
            manifest,
            expected_token=manifest["manifest_token"],
            project_binding=self.binding,
        )
        report = outcome_loop.report_cycle(self.workspace, applied["result"]["cycle_id"])
        self.assertEqual(report["cycle"]["kind"], "campaign")
        self.assertEqual(report["verdict"]["disposition"], "satisfied")

    def test_direct_plan_needs_no_planning_artifact(self) -> None:
        self.apply_slice()
        self.generic_source()
        manifest = outcome_loop.plan_direct_result(
            self.workspace,
            origin_summary="Apply one bounded durable correction.",
            accepted_outcome="The correction is present and verified.",
            product_truth=["product.py"],
            evidence_paths=["product.py"],
            disposition="satisfied",
            authorization_ref="fixture direct-work approval",
        )
        self.assertEqual(manifest["mode"], "direct")
        origin = next(item for item in manifest["artifacts"] if item["key"] == "origin")
        self.assertEqual(origin["authority_mode"], "sqlite")
        self.assertTrue(origin["path"].startswith("sqlite/outcome-capsules/"))
        applied = outcome_loop.apply_manifest(
            self.workspace,
            manifest,
            expected_token=manifest["manifest_token"],
            project_binding=self.binding,
        )
        self.assertEqual(applied["result"]["mode"], "direct")

    def test_repeated_outcome_apply_reuses_active_semantic_edges(self) -> None:
        self.apply_slice()
        source = self.generic_source()
        first = outcome_loop.prepare(self.workspace, source)
        outcome_loop.apply_manifest(
            self.workspace,
            first,
            expected_token=first["manifest_token"],
            project_binding=self.binding,
        )
        with contextlib.closing(hybrid_state.connect(hybrid_state.database_path(self.workspace))) as connection:
            relationship_count = int(connection.execute("SELECT COUNT(*) FROM relationship").fetchone()[0])
        second = outcome_loop.prepare(self.workspace, self.generic_source())
        applied = outcome_loop.apply_manifest(
            self.workspace,
            second,
            expected_token=second["manifest_token"],
            project_binding=self.binding,
        )
        self.assertEqual(len(applied["result"]["reused_relationship_ids"]), 3)
        with contextlib.closing(hybrid_state.connect(hybrid_state.database_path(self.workspace))) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM relationship").fetchone()[0], relationship_count)

    def test_append_only_correction_preserves_terminal_parent_provenance(self) -> None:
        self.apply_slice()
        self.generic_source()
        ids = json.loads(
            (self.workspace / outcome_reconciliation.DEFAULT_IDS).read_text(encoding="utf-8")
        )["ids"]
        parent_cycle = ids["cycle"]["hpt2"]
        before = outcome_loop.report_cycle(self.workspace, parent_cycle)
        manifest = outcome_loop.plan_direct_result(
            self.workspace,
            origin_summary="Correct current truth without rewriting the historical fixture.",
            accepted_outcome="The correction is append-only and explicitly linked.",
            product_truth=["product.py"],
            evidence_paths=["product.py"],
            disposition="satisfied-with-approved-change",
            authorization_ref="fixture correction approval",
            parent_cycle_id=parent_cycle,
        )
        applied = outcome_loop.apply_manifest(
            self.workspace,
            manifest,
            expected_token=manifest["manifest_token"],
            project_binding=self.binding,
        )
        child = outcome_loop.report_cycle(self.workspace, applied["result"]["cycle_id"])
        after = outcome_loop.report_cycle(self.workspace, parent_cycle)
        for key in ("cycle", "requirements", "changes", "evidence", "verdict", "reconciliation"):
            self.assertEqual(after[key], before[key], key)
        relation_types = {item["relation_type"] for item in child["relationships"]}
        self.assertIn("outcome-parent", relation_types)
        self.assertIn("outcome-result-propagated", relation_types)
        self.assertEqual(child["verdict"]["disposition"], "satisfied-with-approved-change")

    def test_global_owning_capsule_reveals_open_root(self) -> None:
        self.apply_slice()
        source_path = self.generic_source()
        source = json.loads(source_path.read_text(encoding="utf-8"))
        source["cycle"]["lifecycle_state"] = "working"
        source["cycle"]["closed_at"] = None
        source["verdict"] = {"scope": "initiative", "disposition": "open", "summary": "Work remains."}
        source["reconciliation"] = {"state": "open", "residual_work": ["finish work"]}
        source_path.write_text(json.dumps(source, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        manifest = outcome_loop.prepare(self.workspace, source_path)
        outcome_loop.apply_manifest(
            self.workspace,
            manifest,
            expected_token=manifest["manifest_token"],
            project_binding=self.binding,
        )
        capsule = outcome_loop.owning_outcome_capsule(self.workspace)
        self.assertTrue(capsule["governed"])
        self.assertEqual(
            capsule["nearest_open_owning_loop"]["cycle_id"], manifest["cycle"]["id"]
        )

    def test_root_transition_requires_and_consumes_propagated_child_result(self) -> None:
        self.apply_slice()
        source_path = self.generic_source()
        source = json.loads(source_path.read_text(encoding="utf-8"))
        source["cycle"]["kind"] = "idea"
        source["cycle"]["lifecycle_state"] = "working"
        source["cycle"]["closed_at"] = None
        source["relationships"] = [source["relationships"][0]]
        source["verdict"] = {"scope": "initiative", "disposition": "open", "summary": "Work remains."}
        source["reconciliation"] = {"state": "open", "residual_work": ["child result"]}
        source_path.write_text(json.dumps(source, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        root = outcome_loop.prepare(self.workspace, source_path)
        outcome_loop.apply_manifest(
            self.workspace, root, expected_token=root["manifest_token"], project_binding=self.binding
        )

        source = json.loads(self.generic_source().read_text(encoding="utf-8"))
        root_origin = root["cycle"]["origin_artifact_id"]
        (self.workspace / "campaign.md").write_text("# Completed campaign\n", encoding="utf-8")
        source["cycle"]["origin"] = {"path": "campaign.md", "type": "campaign"}
        source["cycle"]["kind"] = "campaign"
        source["relationships"] = [
            source["relationships"][0],
            {
                "key": "parent",
                "from_artifact_key": "origin",
                "to_artifact_id": root_origin,
                "relation_type": "outcome-parent"
            },
            {
                "key": "propagated",
                "from_artifact_key": "origin",
                "to_artifact_id": root_origin,
                "relation_type": "outcome-result-propagated"
            }
        ]
        source_path.write_text(json.dumps(source, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        child = outcome_loop.prepare(self.workspace, source_path)
        outcome_loop.apply_manifest(
            self.workspace, child, expected_token=child["manifest_token"], project_binding=self.binding
        )
        transition = outcome_loop.prepare_transition(
            self.workspace,
            root["cycle"]["id"],
            lifecycle_state="terminal",
            disposition="satisfied",
            reconciliation_state="reconciled",
            summary="All accepted results propagated.",
            authorization_ref="fixture final approval",
            supporting_cycle_ids=[child["cycle"]["id"]],
        )
        applied = outcome_loop.apply_transition(
            self.workspace,
            transition,
            expected_token=transition["manifest_token"],
            project_binding=self.binding,
        )
        self.assertEqual(applied["actual_writes"], 3)
        report = outcome_loop.report_cycle(self.workspace, root["cycle"]["id"])
        self.assertEqual(report["cycle"]["lifecycle_state"], "terminal")
        self.assertEqual(report["verdict"]["disposition"], "satisfied")
        self.assertEqual(report["reconciliation"]["state"], "reconciled")


if __name__ == "__main__":
    unittest.main()
