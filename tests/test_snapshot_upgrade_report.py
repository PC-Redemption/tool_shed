from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = str(ROOT / "scripts")
if SCRIPTS not in os.sys.path:
    os.sys.path.insert(0, SCRIPTS)

import snapshot_upgrade_state as state


class SnapshotUpgradeReportTests(unittest.TestCase):
    def create_transaction(self, state_root: Path, transaction_id: str = "report-test") -> Path:
        with mock.patch.dict(os.environ, {"TOOL_SHED_STATE_ROOT": str(state_root)}):
            recorder = state.TransactionRecorder(
                transaction_id,
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
                metadata={
                    "selected_tag": "v0.27.0",
                    "selected_version": "0.27.0",
                    "content_commit": "b" * 40,
                    "release_validation": {
                        "mode": "attested-focused-smoke",
                        "selection_reason": "official-attestation",
                        "cache": "stored",
                        "identity": {
                            "release_commit": "b" * 40,
                            "validator_sha256": "c" * 64,
                            "platform": platform.system().lower(),
                            "architecture": platform.machine().lower(),
                            "python": f"{platform.python_implementation()}-{platform.python_version()}",
                        },
                    },
                },
            )
            return recorder.path

    def run_report(self, state_root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
        environment = dict(os.environ)
        environment["TOOL_SHED_STATE_ROOT"] = str(state_root)
        return subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "snapshot_upgrade_report.py"), *arguments],
            cwd=ROOT,
            env=environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def test_latest_transaction_renders_sanitized_markdown_and_json(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state_root = Path(temporary) / "private-state"
            path = self.create_transaction(state_root)
            markdown = self.run_report(state_root)
            self.assertEqual(markdown.returncode, 0, markdown.stderr)
            self.assertIn("Suggested title: [Tool Shed upgrade TSU-201]", markdown.stdout)
            self.assertIn("Validation cache: `stored`", markdown.stdout)
            self.assertIn("does not create or modify any GitHub issue", markdown.stdout)
            self.assertNotIn(str(state_root), markdown.stdout)
            self.assertNotIn(str(Path.home()), markdown.stdout)

            structured = self.run_report(state_root, path.stem, "--json")
            self.assertEqual(structured.returncode, 0, structured.stderr)
            payload = json.loads(structured.stdout)
            self.assertEqual(payload["issue"]["code"], "TSU-201")
            self.assertFalse(payload["publication"]["automatic"])
            self.assertTrue(payload["publication"]["review_required"])
            self.assertNotIn("identity", payload["transaction"]["release"]["validation"])

    def test_report_rejects_unknown_sensitive_fields_and_wrong_issue_code(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state_root = Path(temporary) / "private-state"
            path = self.create_transaction(state_root)
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["raw_output"] = "credential=secret C:/Users/operator/private"
            path.write_text(json.dumps(payload), encoding="utf-8")
            if os.name != "nt":
                os.chmod(path, 0o600)
            result = self.run_report(state_root, path.stem)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("unsupported fields", result.stderr)
            self.assertNotIn("credential=secret", result.stderr)

            payload.pop("raw_output")
            payload["issue_code"] = "TSU-000"
            path.write_text(json.dumps(payload), encoding="utf-8")
            if os.name != "nt":
                os.chmod(path, 0o600)
            result = self.run_report(state_root, path.stem)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("does not match", result.stderr)

    def test_report_rejects_foreign_platform_and_malformed_or_symlinked_records(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state_root = Path(temporary) / "private-state"
            path = self.create_transaction(state_root)
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["platform"] = "foreign-os"
            path.write_text(json.dumps(payload), encoding="utf-8")
            if os.name != "nt":
                os.chmod(path, 0o600)
            result = self.run_report(state_root, path.stem)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("does not match", result.stderr)

            path.write_text("{malformed", encoding="utf-8")
            if os.name != "nt":
                os.chmod(path, 0o600)
            result = self.run_report(state_root, path.stem)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("malformed", result.stderr)

            if hasattr(os, "symlink"):
                target = path.with_name("target.json")
                target.write_text("{}", encoding="utf-8")
                path.unlink()
                try:
                    path.symlink_to(target)
                except OSError:
                    return
                result = self.run_report(state_root, path.stem)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("protected regular file", result.stderr)

    def test_read_only_route_does_not_create_missing_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state_root = Path(temporary) / "missing-state"
            result = self.run_report(state_root)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(state_root.exists())

    @unittest.skipIf(os.name == "nt", "POSIX permission mode check")
    def test_report_rejects_permission_exposed_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state_root = Path(temporary) / "private-state"
            self.create_transaction(state_root)
            os.chmod(state_root, 0o755)
            result = self.run_report(state_root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("permissions are not private", result.stderr)


if __name__ == "__main__":
    unittest.main()
