from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts import work_level_config


ROOT = Path(__file__).resolve().parents[1]


class WorkLevelConfigTests(unittest.TestCase):
    def write_config(self, workspace: Path, content: str) -> Path:
        path = workspace / "work" / "tool-shed.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
        return path

    def run_config(self, workspace: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "work_level_config.py"),
                "--workspace",
                str(workspace),
                *args,
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def test_absent_configuration_preserves_standard_alias_behavior(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            payload = work_level_config.resolve_workspace_level(workspace, "ts:ship release it")
            self.assertEqual(payload["canonical_level"], "work5")
            self.assertTrue(payload["alias_resolved"])
            self.assertFalse(payload["configured"])
            self.assertTrue(payload["run_default"])
            self.assertEqual(payload["before"], [])
            self.assertEqual(payload["after"], [])
            self.assertEqual(payload["customization_scope"], "selected-canonical-endpoint")

    def test_ordered_actions_default_suppression_and_selected_endpoint_scope(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            self.write_config(
                workspace,
                """schema_version: 1
work_model: split
development_target: staging
production_target: production
work_levels:
  work1:
    before:
      - This lower-level envelope must not repeat
  work3:
    before:
      - Run scripts/prepare.sh
      - Inspect the prepared candidate
    run_default: false
    after:
      - Run scripts/finalize.sh
""",
            )
            payload = work_level_config.resolve_workspace_level(workspace, "freeze")
            self.assertEqual(payload["canonical_level"], "work3")
            self.assertEqual(payload["work_model"], "split")
            self.assertEqual(
                payload["before"],
                ["Run scripts/prepare.sh", "Inspect the prepared candidate"],
            )
            self.assertFalse(payload["run_default"])
            self.assertEqual(payload["after"], ["Run scripts/finalize.sh"])
            self.assertNotIn("lower-level", json.dumps(payload))
            self.assertEqual(
                [item["phase"] for item in payload["execution_order"]],
                ["before", "before", "default", "after"],
            )
            self.assertEqual(payload["failure_policy"], "stop-on-first-failure")

    def test_parser_rejects_ambiguous_or_unsafe_shapes(self) -> None:
        invalid = {
            "future schema": "schema_version: 2\n",
            "unknown root": "schema_version: 1\ncommands: all\n",
            "alias key": "schema_version: 1\nwork_levels:\n  ship:\n    after:\n      - verify\n",
            "bad boolean": "schema_version: 1\nwork_levels:\n  work2:\n    run_default: sometimes\n",
            "empty replacement": "schema_version: 1\nwork_levels:\n  work4:\n    run_default: false\n",
            "inline list": "schema_version: 1\nwork_levels:\n  work2:\n    before: [one]\n",
            "nested action": "schema_version: 1\nwork_levels:\n  work2:\n    before:\n        - too deep\n",
        }
        for name, content in invalid.items():
            with self.subTest(name=name):
                with self.assertRaises(work_level_config.WorkLevelConfigError):
                    work_level_config.parse_config(content)

    def test_cli_reports_invalid_configuration_without_guessing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            self.write_config(workspace, "schema_version: 1\nwork_levels:\n  work9:\n")
            result = self.run_config(workspace, "resolve", "work2", "--json")
            payload = json.loads(result.stdout)
            self.assertEqual(result.returncode, 2)
            self.assertFalse(payload["valid"])
            self.assertIn("unknown work level", payload["error"])

    def test_installer_preserves_valid_owner_configuration_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            subprocess.run(["git", "init", "-q", str(workspace)], check=True)
            path = self.write_config(
                workspace,
                """schema_version: 1
work_levels:
  work2:
    before:
      - Run scripts/prepare.sh
    after:
      - Verify the work environment
""",
            )
            before = path.read_bytes()
            command = [
                sys.executable,
                str(ROOT / "scripts" / "install_into_workspace.py"),
                str(workspace),
                "--provider",
                "all",
            ]
            first = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.assertEqual(first.returncode, 0, first.stderr)
            guidance_before = {
                relative: (workspace / relative).read_bytes()
                for relative in (
                    "AGENTS.md",
                    "CLAUDE.md",
                    "GEMINI.md",
                    ".github/copilot-instructions.md",
                    ".cursor/rules/tool-shed.mdc",
                )
            }
            second = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual(path.read_bytes(), before)
            for relative, content in guidance_before.items():
                self.assertEqual((workspace / relative).read_bytes(), content)
                guidance = content.decode("utf-8")
                self.assertIn("work_level_config.py", guidance)
                self.assertIn("run_default: false", guidance)
                self.assertIn("stop on the first failure", guidance)

    def test_installer_rejects_invalid_configuration_before_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            path = self.write_config(workspace, "schema_version: 9\n")
            before = path.read_bytes()
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "install_into_workspace.py"),
                    str(workspace),
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Work-level configuration failed", result.stderr)
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(
                sorted(item.relative_to(workspace).as_posix() for item in workspace.rglob("*")),
                ["work", "work/tool-shed.yaml"],
            )

    def test_symlinked_configuration_is_rejected(self) -> None:
        if not hasattr(os, "symlink"):
            self.skipTest("symlinks are unavailable")
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            outside = workspace / "outside.yaml"
            outside.write_text("schema_version: 1\n", encoding="utf-8")
            path = workspace / "work" / "tool-shed.yaml"
            path.parent.mkdir()
            try:
                path.symlink_to(outside)
            except OSError as error:
                if getattr(error, "winerror", None) == 1314:
                    self.skipTest(f"Windows symlink privilege is unavailable: {error}")
                raise
            with self.assertRaises(work_level_config.WorkLevelConfigError):
                work_level_config.load_config(workspace)


if __name__ == "__main__":
    unittest.main()
