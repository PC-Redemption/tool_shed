from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = str(ROOT / "scripts")
if SCRIPTS not in os.sys.path:
    os.sys.path.insert(0, SCRIPTS)

import snapshot_upgrade_state as state
import update_shed_manifest
import update_snapshot


class SnapshotUpgradeStateTests(unittest.TestCase):
    def test_focused_client_smoke_installs_all_provider_surfaces(self) -> None:
        source_manifest = json.loads((ROOT / "SHED_VERSION.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as temporary:
            release = Path(temporary) / "release"
            release.mkdir()
            for relative in source_manifest["content_hashes"]:
                source = ROOT / relative
                destination = release / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, destination)
            manifest = dict(source_manifest)
            manifest["release_commit"] = "a" * 40
            manifest["released_at"] = "2026-08-24T00:00:00Z"
            manifest["release_qualification"] = None
            (release / "SHED_VERSION.json").write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                [sys.executable, "-B", str(release / "scripts" / "validate_snapshot_client.py")],
                cwd=release,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
            self.assertIn("focused client installation smoke passed", result.stdout)

    def test_validation_cache_requires_every_identity_dimension(self) -> None:
        with tempfile.TemporaryDirectory() as temporary, mock.patch.dict(
            os.environ,
            {"TOOL_SHED_STATE_ROOT": temporary},
        ):
            cache = state.ValidationCache()
            identity = state.validation_identity(
                release_commit="a" * 40,
                validator_sha256="b" * 64,
            )
            self.assertFalse(cache.lookup(identity))
            cache.store_success(identity, mode="full-local-validation")
            self.assertTrue(cache.lookup(identity))
            for field in ("release_commit", "validator_sha256", "platform", "architecture", "python"):
                changed = dict(identity)
                changed[field] += "-changed"
                self.assertFalse(cache.lookup(changed), field)
            if os.name != "nt":
                self.assertEqual(cache.path.stat().st_mode & 0o777, 0o600)
                os.chmod(cache.path, 0o644)
                self.assertFalse(cache.lookup(identity))

    def test_workspace_lock_fails_closed_and_recovers_dead_owner(self) -> None:
        with tempfile.TemporaryDirectory() as temporary, mock.patch.dict(
            os.environ,
            {"TOOL_SHED_STATE_ROOT": str(Path(temporary) / "state")},
        ):
            workspace = Path(temporary) / "workspace"
            workspace.mkdir()
            first = state.WorkspaceTransactionLock(workspace, "first")
            first.acquire()
            with self.assertRaises(state.ConcurrentUpgradeError):
                state.WorkspaceTransactionLock(workspace, "second").acquire()
            first.release()

            stale = state.WorkspaceTransactionLock(workspace, "stale")
            stale.acquire()
            payload = json.loads(stale._lock.path.read_text(encoding="utf-8"))
            payload["pid"] = 999_999_999
            stale._lock.path.write_text(json.dumps(payload), encoding="utf-8")
            recovered = state.WorkspaceTransactionLock(workspace, "recovered")
            recovered.acquire()
            recovered.release()

    def test_transaction_record_is_sanitized_and_phase_timed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary, mock.patch.dict(
            os.environ,
            {"TOOL_SHED_STATE_ROOT": temporary},
        ):
            recorder = state.TransactionRecorder(
                "transaction-test",
                updater={
                    "schema_version": 1,
                    "shed_version": "0.27.0",
                    "protocol": 3,
                    "script_sha256": "a" * 64,
                },
            )
            recorder.phase("release-validation")
            recorder.finish(
                "failed",
                failed_stage="release-validation",
                error_class="timeout",
                rollback_outcome="not-started",
                metadata={"selected_version": "1.2.3"},
            )
            payload = json.loads(recorder.path.read_text(encoding="utf-8"))
            self.assertEqual(payload["error_class"], "timeout")
            self.assertEqual(payload["issue_code"], "TSU-201")
            self.assertEqual(payload["rollback_outcome"], "not-started")
            self.assertEqual(payload["updater"]["shed_version"], "0.27.0")
            self.assertIn("release-validation", payload["stage_durations_seconds"])
            serialized = json.dumps(payload)
            self.assertNotIn(str(Path.home()), serialized)
            self.assertNotIn("prompt", serialized.lower())
            self.assertNotIn("credential", serialized.lower())

    def test_issue_code_registry_is_stable_and_rollback_failure_wins(self) -> None:
        self.assertEqual(len(state.ISSUE_CODE_REGISTRY), len(set(state.ISSUE_CODE_REGISTRY)))
        self.assertEqual(
            state.issue_code_for(
                state="installed",
                error_class=None,
                rollback_outcome="not-required",
            ),
            "TSU-000",
        )
        for error_class, expected in state.ERROR_CLASS_ISSUE_CODES.items():
            self.assertEqual(
                state.issue_code_for(
                    state="failed",
                    error_class=error_class,
                    rollback_outcome="not-started",
                ),
                expected,
            )
        self.assertEqual(
            state.issue_code_for(
                state="failed",
                error_class="validation",
                rollback_outcome="not-restored",
            ),
            "TSU-901",
        )

    def test_validation_stage_classifies_opaque_failure(self) -> None:
        error_class = state.classify_error(
            RuntimeError("command exited with status 1"),
            stage="post-install-validation",
        )

        self.assertEqual(error_class, "validation")
        self.assertEqual(
            state.issue_code_for(
                state="failed",
                error_class=error_class,
                rollback_outcome="restored",
            ),
            "TSU-501",
        )

    def test_heartbeat_keeps_a_long_phase_visible(self) -> None:
        stream = io.StringIO()
        heartbeat = state.ProgressHeartbeat(stream, interval_seconds=0.02)
        heartbeat.start()
        heartbeat.update("release validation")
        time.sleep(0.055)
        heartbeat.stop()
        self.assertIn("still working: release validation", stream.getvalue())

    def test_only_exact_official_attestation_selects_focused_smoke(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            release = Path(temporary)
            paths = (
                "scripts/validate_tool_shed.py",
                "scripts/validate_snapshot_client.py",
                ".github/workflows/validate.yml",
                ".github/workflows/release.yml",
            )
            hashes: dict[str, str] = {}
            for relative in paths:
                path = release / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(relative, encoding="utf-8")
                hashes[relative] = update_snapshot.hashlib.sha256(path.read_bytes()).hexdigest()
            commit = "c" * 40
            released_at = "2026-08-24T00:00:00Z"
            manifest = {
                "released_at": released_at,
                "content_hashes": hashes,
                "release_qualification": {
                    "schema_version": 1,
                    "subject_commit": commit,
                    "attested_at": released_at,
                    "full_validator": {
                        "path": paths[0],
                        "sha256": hashes[paths[0]],
                    },
                    "client_smoke": {
                        "path": paths[1],
                        "sha256": hashes[paths[1]],
                    },
                    "required_ci": [
                        {"path": paths[2], "sha256": hashes[paths[2]]},
                        {"path": paths[3], "sha256": hashes[paths[3]]},
                    ],
                },
            }
            mode, _, _, reason = update_snapshot.release_validation_plan(
                update_snapshot.DEFAULT_REPOSITORY,
                release,
                manifest,
                commit,
            )
            self.assertEqual(mode, "attested-focused-smoke")
            self.assertEqual(reason, "official-attestation")

            mode, _, _, reason = update_snapshot.release_validation_plan(
                str(release),
                release,
                manifest,
                commit,
            )
            self.assertEqual(mode, "full-local-validation")
            self.assertEqual(reason, "repository-override")

    def test_release_manifest_attestation_binds_commit_validators_and_ci(self) -> None:
        hashes = {
            path: str(index) * 64
            for index, path in enumerate(update_shed_manifest.QUALIFICATION_PATHS, start=1)
        }
        qualification = update_shed_manifest.release_qualification(
            hashes,
            release_commit="a" * 40,
            released_at="2026-08-24T00:00:00Z",
        )
        self.assertIsNotNone(qualification)
        self.assertEqual(qualification["subject_commit"], "a" * 40)
        self.assertEqual(
            qualification["client_smoke"]["sha256"],
            hashes["scripts/validate_snapshot_client.py"],
        )
        self.assertEqual(len(qualification["required_ci"]), 2)


if __name__ == "__main__":
    unittest.main()
