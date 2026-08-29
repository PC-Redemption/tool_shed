from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import document_store  # noqa: E402
import hybrid_state  # noqa: E402
import work_orchestration  # noqa: E402
from project_identity import binding_token  # noqa: E402


class WorkOrchestrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temporary.name)
        subprocess.run(["git", "init", "--quiet"], cwd=self.workspace, check=True)
        subprocess.run(
            ["git", "config", "user.name", "Tool Shed Tests"], cwd=self.workspace, check=True
        )
        subprocess.run(
            ["git", "config", "user.email", "tests@example.invalid"],
            cwd=self.workspace,
            check=True,
        )
        project = {
            "schema_version": 1,
            "project_id": str(uuid.uuid4()),
            "project_name": "orchestration-fixture",
        }
        files = {
            ".gitignore": "/.tool-shed/\n",
            "work/tool-shed-project.json": json.dumps(project, indent=2) + "\n",
            "work/tool-shed.yaml": (
                "schema_version: 1\n"
                "work_model: split\n"
                "development_target: staging\n"
                "production_target: production\n"
                "work_levels:\n"
                "  work2:\n"
                "    before: []\n"
                "    run_default: true\n"
                "    after: []\n"
            ),
            "scripts/validate_tool_shed.py": "raise SystemExit(0)\n",
        }
        for relative, content in files.items():
            path = self.workspace / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=self.workspace, check=True)
        subprocess.run(["git", "commit", "--quiet", "-m", "fixture"], cwd=self.workspace, check=True)
        hybrid_binding = binding_token(self.workspace, operation="hybrid-state")
        hybrid_state.initialize(
            self.workspace,
            project_binding=hybrid_binding,
            target=self.workspace / ".tool-shed/state.sqlite3",
        )
        document_store.migrate(
            self.workspace,
            project_binding=hybrid_binding,
            database=self.workspace / ".tool-shed/state.sqlite3",
        )
        self.binding = binding_token(self.workspace, operation="work-orchestration")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_plan_freezes_authority_and_skip_classes(self) -> None:
        plan = work_orchestration.build_plan(
            self.workspace,
            endpoint="work2",
            stage="closeout",
            commit="HEAD",
            origin_cycle=str(uuid.uuid4()),
        )
        phase_classes = {item["id"]: item["skip_class"] for item in plan["phases"]}
        self.assertEqual(phase_classes["target-evidence"], "current-external-evidence")
        self.assertEqual(phase_classes["strict-doctor"], "always-run")
        self.assertIn("declare an owning outcome satisfied", plan["authority"]["script_may_not"])
        self.assertFalse(plan["writes_performed"])

    def test_plan_state_token_rejects_stale_state(self) -> None:
        plan = work_orchestration.build_plan(
            self.workspace, endpoint="work1", stage="prepare", changed_paths=["docs/readme.md"]
        )
        with self.assertRaisesRegex(work_orchestration.WorkOrchestrationError, "stale"):
            work_orchestration._verify_plan(plan, "wrong-token")

    def test_resume_skips_only_exact_completed_phase(self) -> None:
        calls = []

        def action() -> dict[str, bool]:
            calls.append(True)
            return {"ok": True}

        first, _ = work_orchestration._run_phase(
            self.workspace,
            run_id="run-resume",
            phase_id="exact-step",
            input_material={"state": 1},
            action=action,
            resume=True,
        )
        second, _ = work_orchestration._run_phase(
            self.workspace,
            run_id="run-resume",
            phase_id="exact-step",
            input_material={"state": 1},
            action=action,
            resume=True,
        )
        third, _ = work_orchestration._run_phase(
            self.workspace,
            run_id="run-resume",
            phase_id="exact-step",
            input_material={"state": 2},
            action=action,
            resume=True,
        )
        self.assertEqual((first.result, second.result, third.result), ("passed", "skipped", "passed"))
        self.assertEqual(len(calls), 2)

    def test_duplicate_run_lock_fails_closed(self) -> None:
        with work_orchestration._exclusive_run(self.workspace, "first"):
            with self.assertRaisesRegex(
                work_orchestration.WorkOrchestrationError, "another orchestration run"
            ):
                with work_orchestration._exclusive_run(self.workspace, "second"):
                    pass

    def test_dead_same_host_lock_is_recovered(self) -> None:
        lock = self.workspace / work_orchestration.LOCK_RELATIVE
        lock.parent.mkdir(parents=True, exist_ok=True)
        lock.write_text(
            json.dumps(
                {
                    "run_id": "interrupted",
                    "pid": 999_999_999,
                    "hostname": work_orchestration.socket.gethostname(),
                    "started_at": datetime.now(timezone.utc).isoformat(),
                }
            ),
            encoding="utf-8",
        )
        with work_orchestration._exclusive_run(self.workspace, "recovered"):
            owner = json.loads(lock.read_text(encoding="utf-8"))
            self.assertEqual(owner["run_id"], "recovered")
        self.assertFalse(lock.exists())

    def test_windows_invalid_pid_lock_is_recovered(self) -> None:
        lock = self.workspace / work_orchestration.LOCK_RELATIVE
        lock.parent.mkdir(parents=True, exist_ok=True)
        lock.write_text(
            json.dumps(
                {
                    "run_id": "interrupted",
                    "pid": 999_999_999,
                    "hostname": work_orchestration.socket.gethostname(),
                    "started_at": datetime.now(timezone.utc).isoformat(),
                }
            ),
            encoding="utf-8",
        )
        missing_pid = OSError("invalid process identifier")
        missing_pid.winerror = 87
        with mock.patch.object(work_orchestration.os, "kill", side_effect=missing_pid):
            with work_orchestration._exclusive_run(self.workspace, "recovered"):
                owner = json.loads(lock.read_text(encoding="utf-8"))
                self.assertEqual(owner["run_id"], "recovered")
        self.assertFalse(lock.exists())

    def test_target_evidence_requires_current_exact_target(self) -> None:
        path = self.workspace / ".tool-shed/evidence/work2.json"
        path.parent.mkdir(parents=True)
        payload = {
            "schema_version": 1,
            "kind": "tool-shed-target-evidence",
            "endpoint": "work2",
            "target": "staging",
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "checks": [{"id": "health", "status": "passed", "reference": "https:status/200"}],
        }
        path.write_text(json.dumps(payload), encoding="utf-8")
        result = work_orchestration.validate_target_evidence(
            self.workspace,
            Path(".tool-shed/evidence/work2.json"),
            endpoint="work2",
            expected_target="staging",
        )
        self.assertEqual(result["check_count"], 1)
        payload["checked_at"] = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
        path.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaisesRegex(work_orchestration.WorkOrchestrationError, "not current"):
            work_orchestration.validate_target_evidence(
                self.workspace,
                Path(".tool-shed/evidence/work2.json"),
                endpoint="work2",
                expected_target="staging",
            )

    def test_exact_provider_usage_and_gui_proxies_remain_separate(self) -> None:
        work_orchestration.record_event(
            self.workspace,
            run_id="measured",
            phase_id="provider-recovery",
            classification="recovery-retry",
            result="passed",
            duration_ms=100,
            tool_calls=1,
            output_bytes=200,
            retry_count=1,
            input_tokens=80,
            output_tokens=20,
        )
        work_orchestration.record_event(
            self.workspace,
            run_id="gui",
            phase_id="local-closeout",
            classification="deterministic-script",
            result="passed",
            duration_ms=50,
            tool_calls=1,
            output_bytes=40,
        )
        report = work_orchestration.efficiency_report(self.workspace)
        self.assertEqual(report["remedial_tokens_actual"], 100)
        self.assertEqual(report["remedial_token_coverage"], 0.5)
        self.assertEqual(report["remedial_tokens_estimated"], 210)
        self.assertEqual(report["remedial_tokens_estimate_range"], {"low": 171, "high": 276})
        self.assertEqual(report["remedial_token_estimation"]["confidence"], "low")
        self.assertEqual(
            report["remedial_token_estimation"]["calibration_state"],
            "provider-samples-present",
        )
        self.assertEqual(report["remedial_proxy"]["interactions"], 2)
        self.assertEqual(report["measurement_state"], "partial")

    def test_unmeasured_tokens_are_null_not_zero(self) -> None:
        work_orchestration.record_event(
            self.workspace,
            run_id="gui",
            phase_id="local-closeout",
            classification="deterministic-script",
            result="passed",
            duration_ms=10,
            tool_calls=1,
            output_bytes=25,
        )
        report = work_orchestration.efficiency_report(self.workspace)
        self.assertIsNone(report["remedial_tokens_actual"])
        self.assertEqual(report["remedial_token_coverage"], 0.0)
        self.assertEqual(report["remedial_tokens_estimated"], 107)
        self.assertEqual(report["remedial_tokens_estimate_range"], {"low": 69, "high": 172})
        self.assertEqual(
            report["remedial_token_estimation"]["id"], "proxy-calibration-v1"
        )
        self.assertEqual(report["measurement_state"], "unmeasured")

    def test_estimate_is_deterministic_and_full_measurement_has_high_confidence(self) -> None:
        work_orchestration.record_event(
            self.workspace,
            run_id="measured",
            phase_id="provider-recovery",
            classification="recovery-retry",
            result="passed",
            duration_ms=100,
            tool_calls=1,
            output_bytes=200,
            retry_count=1,
            input_tokens=80,
            output_tokens=20,
        )
        report = work_orchestration.efficiency_report(self.workspace)
        self.assertEqual(report["remedial_tokens_actual"], 100)
        self.assertEqual(report["remedial_tokens_estimated"], 100)
        self.assertEqual(report["remedial_tokens_estimate_range"], {"low": 100, "high": 100})
        self.assertEqual(report["remedial_token_estimation"]["confidence"], "high")

    def test_dashboard_aggregate_is_sanitized(self) -> None:
        work_orchestration.record_event(
            self.workspace,
            run_id="privacy",
            phase_id="stable-phase-id",
            classification="reasoning-required",
            result="passed",
            duration_ms=1,
            tool_calls=1,
            output_bytes=2,
        )
        output = Path(".tool-shed/reports/report.json")
        report = work_orchestration.efficiency_report(self.workspace, output=output)
        serialized = json.dumps(report)
        self.assertNotIn(str(self.workspace), serialized)
        self.assertNotIn("stable-phase-id", serialized)
        self.assertTrue(all(value is False for value in report["privacy"].values()))
        self.assertTrue((self.workspace / output).is_file())

    def test_reset_changes_epoch_and_requires_confirmation(self) -> None:
        original = work_orchestration._counter_epoch(self.workspace)
        with self.assertRaisesRegex(work_orchestration.WorkOrchestrationError, "confirm-reset"):
            work_orchestration.reset_telemetry(
                self.workspace, project_binding=self.binding, confirmed=False
            )
        result = work_orchestration.reset_telemetry(
            self.workspace, project_binding=self.binding, confirmed=True
        )
        self.assertNotEqual(result["counter_epoch"], original)

    def test_prepare_compacts_validator_output(self) -> None:
        plan = work_orchestration.build_plan(
            self.workspace,
            endpoint="work1",
            stage="prepare",
            changed_paths=["docs/operator.md"],
        )
        with mock.patch.object(
            work_orchestration,
            "_subprocess_payload",
            return_value={"returncode": 0, "stdout_bytes": 90000, "stderr_bytes": 0, "output_digest": "a" * 64},
        ):
            result = work_orchestration.prepare(
                self.workspace,
                endpoint="work1",
                expected=plan["state_token"],
                project_binding=self.binding,
                changed_paths=["docs/operator.md"],
                run_id="prepare-compact",
                resume=False,
            )
        rendered = json.dumps(result)
        self.assertEqual(result["status"], "passed")
        self.assertNotIn("90000 bytes of validator output", rendered)
        self.assertLess(len(rendered), 4000)

    def test_clean_logical_checkpoint_is_idempotent(self) -> None:
        hybrid_binding = binding_token(self.workspace, operation="hybrid-state")
        first = work_orchestration._logical_checkpoint(
            self.workspace, project_binding=hybrid_binding
        )
        before = (self.workspace / work_orchestration.CHECKPOINT_RELATIVE).read_bytes()
        second = work_orchestration._logical_checkpoint(
            self.workspace, project_binding=hybrid_binding
        )
        self.assertTrue(first["writes_performed"])
        self.assertFalse(second["writes_performed"])
        self.assertTrue(second["idempotent"])
        self.assertEqual(
            (self.workspace / work_orchestration.CHECKPOINT_RELATIVE).read_bytes(), before
        )

    def test_checkpoint_commit_includes_only_referenced_content_objects(self) -> None:
        hybrid_binding = binding_token(self.workspace, operation="hybrid-state")
        document_store.create_document(
            self.workspace,
            project_binding=hybrid_binding,
            document_type="ticket",
            title="Checkpoint object",
            body="# Checkpoint object\n\nDurable body.\n",
            lifecycle="active",
            metadata={},
            actor="fixture",
            reason="checkpoint commit test",
        )
        checkpoint = work_orchestration._logical_checkpoint(
            self.workspace, project_binding=hybrid_binding
        )
        result = work_orchestration._checkpoint_commit(
            self.workspace, "Checkpoint exact logical state"
        )
        self.assertTrue(result["created"])
        self.assertGreaterEqual(result["path_count"], 2)
        tracked = subprocess.run(
            ["git", "show", "--pretty=format:", "--name-only", result["commit"]],
            cwd=self.workspace,
            text=True,
            stdout=subprocess.PIPE,
            check=True,
        ).stdout.splitlines()
        self.assertIn(work_orchestration.CHECKPOINT_RELATIVE.as_posix(), tracked)
        self.assertTrue(set(tracked) <= {
            work_orchestration.CHECKPOINT_RELATIVE.as_posix(), *checkpoint["objects"]
        })

    def test_checkpoint_commit_refuses_unrelated_change(self) -> None:
        hybrid_binding = binding_token(self.workspace, operation="hybrid-state")
        work_orchestration._logical_checkpoint(
            self.workspace, project_binding=hybrid_binding
        )
        unrelated = self.workspace / "unrelated.txt"
        unrelated.write_text("owner work\n", encoding="utf-8")
        with self.assertRaisesRegex(work_orchestration.WorkOrchestrationError, "unrelated"):
            work_orchestration._checkpoint_commit(self.workspace, "must refuse")

    def test_strict_doctor_failure_is_an_exception(self) -> None:
        with mock.patch.object(
            work_orchestration.doctor,
            "inspect",
            return_value={"verdict": "INVALID", "findings": [{"code": "STATE_DRIFT"}]},
        ):
            with self.assertRaisesRegex(
                work_orchestration.WorkOrchestrationError, "STATE_DRIFT"
            ):
                work_orchestration._strict_doctor(self.workspace)

    def test_benchmark_proves_same_corpus_thresholds(self) -> None:
        result = work_orchestration.benchmark(
            ROOT / "tests/fixtures/work-orchestration-baseline-v1.json"
        )
        self.assertTrue(result["passed"])
        self.assertTrue(
            all(item["deterministic_interaction_percent"] < 15 for item in result["cases"])
        )
        self.assertTrue(all(item["known_retry_count"] == 0 for item in result["cases"]))


if __name__ == "__main__":
    unittest.main()
