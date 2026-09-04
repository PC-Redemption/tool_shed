from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import lifecycle_qualification as qualification  # noqa: E402
import closure_lineage  # noqa: E402
import document_store  # noqa: E402
import hybrid_state  # noqa: E402
from project_identity import binding_token  # noqa: E402


class LifecycleQualificationTests(unittest.TestCase):
    def scenario(self, name: str) -> dict[str, object]:
        return qualification.load_json(
            ROOT / "schemas/lifecycle-qualification/v1/scenarios" / f"{name}.json",
            label="scenario",
        )

    def local_fixture(self, root: Path) -> tuple[Path, str]:
        workspace = root / "fixture"
        workspace.mkdir()
        subprocess.run(["git", "init", "--quiet", "-b", "main"], cwd=workspace, check=True)
        subprocess.run(["git", "config", "user.name", "Qualification Fixture"], cwd=workspace, check=True)
        subprocess.run(["git", "config", "user.email", "fixture@example.invalid"], cwd=workspace, check=True)
        project_id = str(uuid.uuid4())
        identity = workspace / "work/tool-shed-project.json"
        identity.parent.mkdir(parents=True)
        identity.write_text(json.dumps({"schema_version": 1, "project_id": project_id, "project_name": "qualification-fixture"}) + "\n", encoding="utf-8")
        (workspace / ".gitignore").write_text("/.tool-shed/\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=workspace, check=True)
        subprocess.run(["git", "commit", "--quiet", "-m", "fixture"], cwd=workspace, check=True)
        return workspace, project_id

    def test_manifest_identity_is_content_derived_and_input_sensitive(self) -> None:
        scenario = self.scenario("QH-002")
        first = qualification.seal_manifest(
            scenario,
            candidate_commit="a" * 40,
            candidate_version="0.43.0",
            platform_name="linux-x86_64",
            project_id="project",
            instance_id="instance",
            serial=1,
            seed=7,
            target_environment="development",
            baseline_digest="b" * 64,
        )
        repeated = qualification.seal_manifest(
            scenario,
            candidate_commit="a" * 40,
            candidate_version="0.43.0",
            platform_name="linux-x86_64",
            project_id="project",
            instance_id="instance",
            serial=1,
            seed=7,
            target_environment="development",
            baseline_digest="b" * 64,
        )
        changed = qualification.seal_manifest(
            scenario,
            candidate_commit="a" * 40,
            candidate_version="0.43.0",
            platform_name="linux-x86_64",
            project_id="project",
            instance_id="instance",
            serial=2,
            seed=7,
            target_environment="development",
            baseline_digest="b" * 64,
        )
        qualification.validate_manifest(first)
        self.assertEqual(first, repeated)
        self.assertNotEqual(first["run_id"], changed["run_id"])
        self.assertEqual(first["scenario"]["checkpoint_id"], "terminal-clean-tail")

    def test_manifest_rejects_unknown_checkpoint_selector(self) -> None:
        with self.assertRaisesRegex(qualification.QualificationError, "checkpoint selector"):
            qualification.seal_manifest(
                self.scenario("QH-002"), candidate_commit="a" * 40, candidate_version="0.43.0",
                platform_name="linux-x86_64", project_id="project", instance_id="instance",
                serial=1, seed=0, target_environment="development", baseline_digest="b" * 64,
                checkpoint_id="not-declared",
            )

    def test_qualification_root_uses_sealed_fixture_platform(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace, project_id = self.local_fixture(Path(directory))
            manifest = qualification.seal_manifest(
                self.scenario("QH-009"),
                candidate_commit="a" * 40,
                candidate_version="0.43.0",
                platform_name="linux-x86_64",
                project_id=project_id,
                instance_id="fixture-instance",
                serial=1,
                seed=0,
                target_environment="development",
                baseline_digest="b" * 64,
            )

            root = qualification.qualification_run_manifest(workspace, manifest)

            self.assertEqual(root["platform"], "linux-x86_64")
            self.assertEqual(root["instance"]["platform"], "linux-x86_64")

    def test_journal_is_hash_chained_and_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "journal.jsonl"
            first = qualification.append_journal(path, {"run_id": "tsqh-" + "a" * 24, "action": "create", "state": "passed", "logical_tick": 1, "idempotency_key": "one", "payload_digest": "b" * 64})
            repeated = qualification.append_journal(path, {"run_id": "tsqh-" + "a" * 24, "action": "create", "state": "passed", "logical_tick": 1, "idempotency_key": "one", "payload_digest": "b" * 64})
            second = qualification.append_journal(path, {"run_id": "tsqh-" + "a" * 24, "action": "close", "state": "passed", "logical_tick": 2, "idempotency_key": "two", "payload_digest": "c" * 64})
            self.assertEqual(first, repeated)
            self.assertEqual(second["sequence"], 2)
            self.assertEqual(second["prior_event_digest"], first["event_digest"])
            self.assertEqual(len(path.read_text(encoding="utf-8").splitlines()), 2)

    def test_qh001_rejects_visible_seed_or_extra_project(self) -> None:
        scenario = self.scenario("QH-001")
        clean = {
            "projects": [
                {"external_id": "linux", "name": "ts_linux_test_bed", "is_hidden": False},
                {"external_id": "windows", "name": "ts_windows_test_bed", "is_hidden": False},
                {"external_id": next(iter(qualification.SEED_PROJECT_IDS)), "name": "seed", "is_hidden": True},
            ],
            "instances": [
                {"external_id": "linux-instance", "project_external_id": "linux"},
                {"external_id": "windows-instance", "project_external_id": "windows"},
            ],
        }
        self.assertTrue(all(item["passed"] for item in qualification.evaluate_qh001(scenario, clean)))
        clean["projects"][-1]["is_hidden"] = False
        checks = qualification.evaluate_qh001(scenario, clean)
        self.assertFalse(next(item for item in checks if item["id"] == "QH001-SEEDS-NOT-OPERATIONAL")["passed"])
        self.assertFalse(next(item for item in checks if item["id"] == "QH001-EXACT-PROJECT-SET")["passed"])

    def test_qh007_proves_outage_classification_and_exact_convergence(self) -> None:
        scenario = self.scenario("QH-007")
        manifest = qualification.seal_manifest(
            scenario, candidate_commit="a" * 40, candidate_version="0.45.0",
            platform_name="hosted-development", project_id="project", instance_id="instance",
            serial=1, seed=0, target_environment="development", baseline_digest="b" * 64,
        )
        artifact = {
            "artifact_id": "artifact", "visible_id": "IDEA-0001", "artifact_type": "idea-brief",
            "title": "Fixture", "document_lifecycle": "active", "outcome_lifecycle": "working",
            "outcome_disposition": "open", "reconciliation_state": "open", "parent_ids": [],
            "produces_ids": [], "closure_status": {"effective_closed": False, "evaluated_at": "2026-09-03T00:00:00Z"},
        }
        transport = {
            "run_id": manifest["run_id"], "project_id": "project", "instance_id": "instance",
            "project_name": "fixture", "queued": [{"sequence": 2}, {"sequence": 3}],
            "outage": {"status": "unavailable", "pending_count": 2, "hosted_sequence": 1, "latest_sequence": 3, "browser_freshness": "stale"},
            "delivery": {"pending_count": 0, "submissions": [
                {"sequence": 3, "status": "accepted"}, {"sequence": 3, "status": "duplicate"},
                {"sequence": 2, "status": "stale"},
            ]},
            "accepted_idempotency_keys": ["baseline", "newer", "final"],
            "latest_payload": {"sequence": 4, "work_inventory": {"total_count": 1, "artifacts": [artifact]}},
        }
        dashboard = {
            "instances": [{"project_external_id": "project", "external_id": "instance", "last_sequence": 4, "work_inventory_sequence": 4, "work_inventory_total": 1}],
            "work_artifacts": [{
                "project_external_id": "project", "instance_external_id": "instance",
                "artifact_external_id": "artifact", **{key: value for key, value in artifact.items() if key != "artifact_id"},
            }],
            "ingest_receipts": [{"instance_external_id": "instance", "idempotency_key": key} for key in ("baseline", "newer", "final")],
        }
        dashboard["work_artifacts"][0]["closure_status"]["evaluated_at"] = "2026-09-03T00:00:00+00:00"
        browser = {"links_ok": True, "projects": [{"name": "fixture", "freshness": "fresh", "attention_state": "working", "work_artifact_ids": ["IDEA-0001"]}]}
        checks = qualification.evaluate_qh007(transport, dashboard, browser, manifest)
        self.assertTrue(all(item["passed"] for item in checks), checks)
        dashboard["work_artifacts"][0]["closure_status"] = {"effective_closed": True}
        checks = qualification.evaluate_qh007(transport, dashboard, browser, manifest)
        self.assertFalse(next(item for item in checks if item["id"] == "QH007-HOSTED-FIELD-PARITY")["passed"])

    def test_qualification_namespace_requires_root_lineage_scope_absence_and_separate_visibility(self) -> None:
        project_id = str(uuid.uuid4())
        instance_id = str(uuid.uuid4())
        manifest = qualification.seal_manifest(
            self.scenario("QH-009"),
            candidate_commit="a" * 40,
            candidate_version="0.45.0",
            platform_name="linux-x86_64",
            project_id=project_id,
            instance_id=instance_id,
            serial=1,
            seed=0,
            target_environment="development",
            baseline_digest="b" * 64,
        )
        artifact_id = str(uuid.uuid4())
        transport = {
            "run_id": manifest["run_id"],
            "project_id": project_id,
            "instance_id": instance_id,
            "project_name": "qh009-qualification",
            "credential_scope": "qualification:write",
            "qualification_run_id": manifest["run_id"],
            "accepted_idempotency_keys": ["receipt-one"],
            "latest_payload": {
                "sequence": 4,
                "work_inventory": {
                    "total_count": 1,
                    "artifacts": [{"artifact_id": artifact_id}],
                }
            },
        }
        dashboard = {
            "qualification_runs": [{
                "run_id": manifest["run_id"],
                "manifest_digest": manifest["manifest_digest"],
                "candidate_commit": manifest["candidate"]["commit"],
                "scenario_id": "QH-009",
                "environment": "development",
                "status": "active",
                "project_ids": [project_id],
            }],
            "projects": [{"external_id": project_id, "qualification_run_id": manifest["run_id"]}],
            "instances": [{
                "external_id": instance_id,
                "project_external_id": project_id,
                "last_sequence": 4,
                "work_inventory_sequence": 4,
                "work_inventory_total": 1,
            }],
            "work_artifacts": [{
                "artifact_external_id": artifact_id,
                "project_external_id": project_id,
                "instance_external_id": instance_id,
            }],
            "ingest_receipts": [{"instance_external_id": instance_id, "idempotency_key": "receipt-one"}],
        }
        browser = {
            "project_names": ["ts_linux_test_bed", "ts_windows_test_bed"],
            "qualification_runs": [{"run_id": manifest["run_id"]}],
            "requested_qualification_run_visible": True,
        }
        checks = qualification.evaluate_qualification_namespace(
            transport, dashboard, browser, manifest, prefix="QH009"
        )
        self.assertTrue(all(item["passed"] for item in checks), checks)
        browser["project_names"].append("qh009-qualification")
        checks = qualification.evaluate_qualification_namespace(
            transport, dashboard, browser, manifest, prefix="QH009"
        )
        self.assertFalse(next(item for item in checks if item["id"] == "QH009-OPERATIONAL-ABSENCE")["passed"])

    def test_independent_oracle_detects_projection_divergence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "fixture.sqlite3"
            connection = sqlite3.connect(database)
            connection.row_factory = sqlite3.Row
            connection.executescript(
                """
                CREATE TABLE closure_element(id TEXT PRIMARY KEY,role TEXT,element_kind TEXT,artifact_id TEXT,cycle_id TEXT,requirement_id TEXT,subject_revision INTEGER);
                CREATE TABLE requirement(id TEXT PRIMARY KEY,cycle_id TEXT,disposition TEXT);
                CREATE TABLE lineage_claim(id TEXT PRIMARY KEY,child_element_id TEXT,parent_element_id TEXT,parent_requirement_id TEXT,relationship_type TEXT,retired_revision INTEGER);
                CREATE TABLE closure_record(id TEXT PRIMARY KEY,element_id TEXT,method TEXT,evidence_health TEXT,created_revision INTEGER,superseded_revision INTEGER);
                CREATE TABLE recovery_case(id TEXT PRIMARY KEY,element_id TEXT,reason_code TEXT,state TEXT);
                CREATE TABLE closure_rollup(element_id TEXT PRIMARY KEY,local_closure TEXT,evidence_health TEXT,graph_health TEXT,effective_closed INTEGER,reason_codes_json TEXT,open_descendants INTEGER,unknown_descendants INTEGER,invalid_descendants INTEGER);
                INSERT INTO closure_element VALUES('cycle','cycle','document','artifact','cycle',NULL,1);
                INSERT INTO closure_element VALUES('requirement','obligation','requirement','artifact',NULL,'requirement',1);
                INSERT INTO requirement VALUES('requirement','cycle','accepted');
                INSERT INTO closure_record VALUES('closed','requirement','closed-loop','current',1,NULL);
                INSERT INTO closure_record VALUES('cycle-closed','cycle','closed-loop','current',1,NULL);
                INSERT INTO closure_rollup VALUES('requirement','closed-loop','current','valid',1,'[]',0,0,0);
                INSERT INTO closure_rollup VALUES('cycle','closed-loop','current','valid',0,'[]',0,0,0);
                """
            )
            oracle = qualification.independent_closure(connection)
            self.assertTrue(oracle["elements"]["cycle"]["effective_closed"])
            mismatch = qualification.compare_closure_projection(connection, oracle)
            self.assertEqual(mismatch[0]["element_id"], "cycle")
            self.assertEqual(mismatch[0]["field"], "effective_closed")
            connection.close()

    def test_independent_oracle_loads_closure_records_in_one_query(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "fixture.sqlite3"
            connection = sqlite3.connect(database)
            connection.row_factory = sqlite3.Row
            connection.executescript(
                """
                CREATE TABLE closure_element(id TEXT PRIMARY KEY,role TEXT,element_kind TEXT,artifact_id TEXT,cycle_id TEXT,requirement_id TEXT,subject_revision INTEGER);
                CREATE TABLE requirement(id TEXT PRIMARY KEY,cycle_id TEXT,disposition TEXT);
                CREATE TABLE lineage_claim(id TEXT PRIMARY KEY,child_element_id TEXT,parent_element_id TEXT,parent_requirement_id TEXT,relationship_type TEXT,retired_revision INTEGER);
                CREATE TABLE closure_record(id TEXT PRIMARY KEY,element_id TEXT,method TEXT,evidence_health TEXT,created_revision INTEGER,superseded_revision INTEGER);
                CREATE TABLE recovery_case(id TEXT PRIMARY KEY,element_id TEXT,reason_code TEXT,state TEXT);
                """
            )
            for index in range(20):
                connection.execute(
                    "INSERT INTO closure_element VALUES(?,?,?,?,?,?,?)",
                    (f"element-{index}", "obligation", "requirement", "artifact", None, f"requirement-{index}", 1),
                )
                connection.execute(
                    "INSERT INTO requirement VALUES(?,?,?)",
                    (f"requirement-{index}", f"cycle-{index}", "accepted"),
                )
                connection.execute(
                    "INSERT INTO closure_record VALUES(?,?,?,?,?,NULL)",
                    (f"record-{index}", f"element-{index}", "closed-loop", "current", 1),
                )
            statements: list[str] = []
            connection.set_trace_callback(statements.append)
            oracle = qualification.independent_closure(connection)
            closure_selects = [
                statement for statement in statements
                if "FROM closure_record" in statement
            ]
            self.assertEqual(len(oracle["elements"]), 20)
            self.assertEqual(len(closure_selects), 1, closure_selects)
            connection.close()

    def test_result_digest_covers_verdict_and_checks(self) -> None:
        manifest = qualification.seal_manifest(
            self.scenario("QH-001"), candidate_commit="a" * 40, candidate_version="0.43.0",
            platform_name="hosted-development", project_id="project", instance_id="instance",
            serial=1, seed=0, target_environment="development", baseline_digest="b" * 64,
        )
        result = qualification.result_summary(manifest, [{"id": "exact", "passed": True}], evidence=[], replay=["replay"])
        qualification.validate_result(result)
        self.assertEqual(result["verdict"], "PASS")
        result["checks"][0]["passed"] = False
        with self.assertRaisesRegex(qualification.QualificationError, "digest"):
            qualification.validate_result(result)

    def test_qh002_rejects_missing_run_cycle_projection(self) -> None:
        local = {
            "documents": [
                {"artifact_id": f"artifact-{index}", "type": document_type, "lifecycle": "completed"}
                for index, document_type in enumerate(("idea-brief", "project-map", "program-roadmap", "campaign"))
            ],
            "cycles": [
                {
                    "id": f"cycle-{index}",
                    "lifecycle_state": "terminal",
                    "verdict": {"disposition": "satisfied"},
                    "reconciliation": {"state": "reconciled"},
                }
                for index in range(4)
            ],
            "relationships": [],
            "closure": {"available": True, "elements": {}, "projection_mismatches": []},
        }
        checks = qualification.evaluate_qh002(self.scenario("QH-002"), local)
        projection = next(item for item in checks if item["id"] == "QH002-CLOSURE-PROJECTION-PARITY")
        self.assertFalse(projection["passed"])
        self.assertEqual(projection["actual"]["missing_cycles"], [f"cycle-{index}" for index in range(4)])

    def test_qh002_hosted_requires_exact_terminal_run_projection(self) -> None:
        document_types = ("idea-brief", "project-map", "program-roadmap", "campaign")
        local = {
            "documents": [
                {"artifact_id": f"artifact-{index}", "type": document_type}
                for index, document_type in enumerate(document_types)
            ]
        }
        manifest = {"fixture": {"project_id": "project", "instance_id": "instance"}}
        dashboard = {
            "work_artifacts": [
                {
                    "artifact_external_id": f"artifact-{index}",
                    "artifact_type": document_type,
                    "project_external_id": "project",
                    "instance_external_id": "instance",
                    "document_lifecycle": "completed",
                    "outcome_lifecycle": "terminal",
                    "outcome_disposition": "satisfied",
                    "reconciliation_state": "reconciled",
                    "closure_status": {"effective_closed": True},
                }
                for index, document_type in enumerate(document_types)
            ]
        }
        checks = qualification.evaluate_qh002_hosted(self.scenario("QH-002"), local, dashboard, manifest)
        self.assertTrue(all(item["passed"] for item in checks))
        dashboard["work_artifacts"][0]["outcome_lifecycle"] = "working"
        checks = qualification.evaluate_qh002_hosted(self.scenario("QH-002"), local, dashboard, manifest)
        self.assertFalse(next(item for item in checks if item["id"] == "QH002-HOSTED-TERMINAL-CLOSED")["passed"])

    def test_qh002_driver_completes_schema2_outcome_chain(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            subprocess.run(["git", "init", "--quiet", "-b", "main"], cwd=workspace, check=True)
            subprocess.run(["git", "config", "user.name", "Qualification Fixture"], cwd=workspace, check=True)
            subprocess.run(["git", "config", "user.email", "fixture@example.invalid"], cwd=workspace, check=True)
            identity = workspace / "work/tool-shed-project.json"
            identity.parent.mkdir(parents=True)
            identity.write_text(json.dumps({"schema_version": 1, "project_id": str(uuid.uuid4()), "project_name": "qualification-fixture"}) + "\n", encoding="utf-8")
            (workspace / ".gitignore").write_text("/.tool-shed/\n/tool_shed/\n", encoding="utf-8")
            scenario_target = workspace / "tool_shed/schemas/lifecycle-qualification/v1/scenarios/QH-002.json"
            scenario_target.parent.mkdir(parents=True)
            shutil.copy2(ROOT / "schemas/lifecycle-qualification/v1/scenarios/QH-002.json", scenario_target)
            subprocess.run(["git", "add", "."], cwd=workspace, check=True)
            subprocess.run(["git", "commit", "--quiet", "-m", "fixture"], cwd=workspace, check=True)
            binding = binding_token(workspace, operation="hybrid-state")
            hybrid_state.initialize(workspace, project_binding=binding)
            document_store.migrate(workspace, project_binding=binding)
            manifest = qualification.seal_manifest(
                self.scenario("QH-002"), candidate_commit="a" * 40, candidate_version="0.43.0",
                platform_name="linux-x86_64", project_id="project", instance_id="instance",
                serial=1, seed=0, target_environment="development",
                baseline_digest=document_store.audit(workspace)["domain_digest"],
            )
            driven = qualification.drive_qh002(workspace, manifest, project_binding=binding)
            by_id = {item["id"]: item for item in driven["checks"]}
            self.assertTrue(by_id["QH002-OUTCOMES-TERMINAL-RECONCILED"]["passed"])
            self.assertTrue(by_id["QH002-PROPAGATED-CHAIN"]["passed"])
            self.assertTrue(by_id["QH002-NO-ACTIVE-RUN-RESIDUE"]["passed"])
            self.assertFalse(by_id["QH002-CLOSURE-PROJECTION-PARITY"]["passed"])

    def test_qh002_driver_enrolls_and_closes_new_schema3_elements(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            subprocess.run(["git", "init", "--quiet", "-b", "main"], cwd=workspace, check=True)
            subprocess.run(["git", "config", "user.name", "Qualification Fixture"], cwd=workspace, check=True)
            subprocess.run(["git", "config", "user.email", "fixture@example.invalid"], cwd=workspace, check=True)
            identity = workspace / "work/tool-shed-project.json"
            identity.parent.mkdir(parents=True)
            identity.write_text(json.dumps({"schema_version": 1, "project_id": str(uuid.uuid4()), "project_name": "qualification-fixture"}) + "\n", encoding="utf-8")
            (workspace / ".gitignore").write_text("/.tool-shed/\n/tool_shed/\n", encoding="utf-8")
            scenario_target = workspace / "tool_shed/schemas/lifecycle-qualification/v1/scenarios/QH-002.json"
            scenario_target.parent.mkdir(parents=True)
            shutil.copy2(ROOT / "schemas/lifecycle-qualification/v1/scenarios/QH-002.json", scenario_target)
            subprocess.run(["git", "add", "."], cwd=workspace, check=True)
            subprocess.run(["git", "commit", "--quiet", "-m", "fixture"], cwd=workspace, check=True)
            binding = binding_token(workspace, operation="hybrid-state")
            hybrid_state.initialize(workspace, project_binding=binding)
            document_store.migrate(workspace, project_binding=binding)
            migration = closure_lineage.prepare_migration(workspace)
            closure_lineage.apply_migration(
                workspace,
                migration,
                expected_token=migration["manifest_token"],
                project_binding=binding,
            )
            manifest = qualification.seal_manifest(
                self.scenario("QH-002"), candidate_commit="a" * 40, candidate_version="0.43.0",
                platform_name="linux-x86_64", project_id="project", instance_id="instance",
                serial=1, seed=0, target_environment="development",
                baseline_digest=document_store.audit(workspace)["domain_digest"],
            )
            driven = qualification.drive_qh002(workspace, manifest, project_binding=binding)
            by_id = {item["id"]: item for item in driven["checks"]}
            self.assertTrue(by_id["QH002-CLOSURE-PROJECTION-PARITY"]["passed"])
            self.assertTrue(all(item["passed"] for item in driven["checks"]))

    def test_qh002_driver_resumes_after_terminal_transition_before_document_completion(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace, project_id = self.local_fixture(Path(directory))
            scenario_target = workspace / "tool_shed/schemas/lifecycle-qualification/v1/scenarios/QH-002.json"
            scenario_target.parent.mkdir(parents=True)
            shutil.copy2(ROOT / "schemas/lifecycle-qualification/v1/scenarios/QH-002.json", scenario_target)
            binding = binding_token(workspace, operation="hybrid-state")
            hybrid_state.initialize(workspace, project_binding=binding)
            document_store.migrate(workspace, project_binding=binding)
            migration = closure_lineage.prepare_migration(workspace)
            closure_lineage.apply_migration(
                workspace, migration, expected_token=migration["manifest_token"], project_binding=binding
            )
            manifest = qualification.seal_manifest(
                self.scenario("QH-002"), candidate_commit="a" * 40, candidate_version="0.46.0",
                platform_name="linux-x86_64", project_id=project_id, instance_id="fixture-instance",
                serial=77, seed=0, target_environment="development",
                baseline_digest=document_store.audit(workspace)["domain_digest"],
            )
            original = document_store.set_lifecycle
            calls = 0

            def interrupt(*args: object, **kwargs: object) -> dict[str, object]:
                nonlocal calls
                calls += 1
                if calls == 1:
                    raise KeyboardInterrupt("sealed interruption")
                return original(*args, **kwargs)

            with mock.patch.object(document_store, "set_lifecycle", side_effect=interrupt):
                with self.assertRaises(KeyboardInterrupt):
                    qualification.drive_qh002(workspace, manifest, project_binding=binding)
            resumed = qualification.drive_qh002(workspace, manifest, project_binding=binding)
            self.assertTrue(resumed["resumed"])
            self.assertTrue(all(item["passed"] for item in resumed["checks"]), resumed)

    def test_qh002_driver_resumes_after_three_document_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace, project_id = self.local_fixture(Path(directory))
            scenario_target = workspace / "tool_shed/schemas/lifecycle-qualification/v1/scenarios/QH-002.json"
            scenario_target.parent.mkdir(parents=True)
            shutil.copy2(ROOT / "schemas/lifecycle-qualification/v1/scenarios/QH-002.json", scenario_target)
            binding = binding_token(workspace, operation="hybrid-state")
            hybrid_state.initialize(workspace, project_binding=binding)
            document_store.migrate(workspace, project_binding=binding)
            migration = closure_lineage.prepare_migration(workspace)
            closure_lineage.apply_migration(
                workspace, migration, expected_token=migration["manifest_token"], project_binding=binding
            )
            manifest = qualification.seal_manifest(
                self.scenario("QH-002"), candidate_commit="a" * 40, candidate_version="0.46.0",
                platform_name="windows-amd64", project_id=project_id, instance_id="fixture-instance",
                serial=78, seed=0, target_environment="development",
                baseline_digest=document_store.audit(workspace)["domain_digest"],
            )
            original = document_store.create_document
            calls = 0

            def interrupt(*args: object, **kwargs: object) -> dict[str, object]:
                nonlocal calls
                calls += 1
                if calls == 4:
                    raise KeyboardInterrupt("sealed document-prefix interruption")
                return original(*args, **kwargs)

            with mock.patch.object(document_store, "create_document", side_effect=interrupt):
                with self.assertRaises(KeyboardInterrupt):
                    qualification.drive_qh002(workspace, manifest, project_binding=binding)
            resumed = qualification.drive_qh002(workspace, manifest, project_binding=binding)
            self.assertTrue(resumed["resumed"])
            self.assertTrue(all(item["passed"] for item in resumed["checks"]), resumed)

    def test_m2_local_scenario_contracts_are_sealable(self) -> None:
        for scenario_id in ("QH-003", "QH-004", "QH-005", "QH-006", "QH-007", "QH-008", "QH-009", "QH-010"):
            scenario = self.scenario(scenario_id)
            qualification.validate_scenario(scenario)
            manifest = qualification.seal_manifest(
                scenario,
                candidate_commit="a" * 40,
                candidate_version="0.44.0",
                platform_name="hosted-development" if scenario_id == "QH-007" else "linux-x86_64",
                project_id=str(uuid.uuid4()),
                instance_id="fixture-instance",
                serial=1,
                seed=0,
                target_environment="development",
                baseline_digest="b" * 64,
            )
            self.assertEqual(manifest["scenario"]["id"], scenario_id)

    def test_m2_local_database_corpus_passes_and_replays_idempotently(self) -> None:
        original_state_root = os.environ.get("TOOL_SHED_STATE_ROOT")
        for serial, scenario_id in enumerate(("QH-003", "QH-004", "QH-005", "QH-006", "QH-008", "QH-009", "QH-010"), start=1):
            with self.subTest(scenario=scenario_id), tempfile.TemporaryDirectory() as directory:
                workspace, project_id = self.local_fixture(Path(directory))
                manifest = qualification.seal_manifest(
                    self.scenario(scenario_id),
                    candidate_commit="a" * 40,
                    candidate_version="0.44.0",
                    platform_name="linux-x86_64",
                    project_id=project_id,
                    instance_id="fixture-instance",
                    serial=serial,
                    seed=0,
                    target_environment="development",
                    baseline_digest="b" * 64,
                )
                driven = qualification.drive_local_corpus(workspace, manifest)
                self.assertTrue(all(item["passed"] for item in driven["checks"]), driven)
                repeated = qualification.drive_local_corpus(workspace, manifest)
                self.assertTrue(repeated["resumed"])
                self.assertEqual(driven["checks"], repeated["checks"])
                self.assertEqual(os.environ.get("TOOL_SHED_STATE_ROOT"), original_state_root)


if __name__ == "__main__":
    unittest.main()
