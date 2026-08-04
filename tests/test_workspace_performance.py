from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import profile_workspace_performance as profiler  # noqa: E402
import workspace_preflight  # noqa: E402


class WorkspacePerformanceTests(unittest.TestCase):
    def init_repository(self, root: Path, gitignore: str = "") -> None:
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        (root / ".gitignore").write_text(gitignore, encoding="utf-8")

    def commit_all(self, root: Path) -> None:
        subprocess.run(["git", "add", "."], cwd=root, check=True)
        subprocess.run(
            [
                "git", "-c", "user.name=Profiler Tests", "-c", "user.email=tests@example.invalid",
                "commit", "-qm", "fixture",
            ],
            cwd=root,
            check=True,
        )

    def worktree_metadata(self, root: Path) -> dict[str, tuple[int, int, int]]:
        result: dict[str, tuple[int, int, int]] = {}
        for current_text, dirs, files in os.walk(root):
            current = Path(current_text)
            dirs[:] = [name for name in dirs if name != ".git"]
            for name in files:
                path = current / name
                details = path.lstat()
                result[path.relative_to(root).as_posix()] = (
                    details.st_size,
                    details.st_mtime_ns,
                    stat.S_IMODE(details.st_mode),
                )
        return result

    def test_json_report_is_sanitized_and_workspace_is_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp) / "Secret Customer Alice Repository"
            workspace.mkdir()
            self.init_repository(workspace, "ignored-secret/\n")
            work = workspace / "work" / "tickets"
            work.mkdir(parents=True)
            (work / "ticket-secret-project-codename.md").write_text(
                "\n".join(
                    [
                        "# Ticket: Secret Project Codename",
                        "",
                        "Status: active",
                        "Type: ticket",
                        "Updated: 2026-08-03",
                        "Next Action: contact alice@example.invalid",
                        "Parent: work/maps/map-sensitive-client.md",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            maps = workspace / "work" / "maps"
            maps.mkdir()
            (maps / "map-sensitive-client.md").write_text(
                "# Project Map: Sensitive Client\n\nStatus: active\nType: project-map\nUpdated: 2026-08-03\nNext Action: secret\n",
                encoding="utf-8",
            )
            (workspace / "tracked-secret-token.txt").write_text("credential-like-value\n", encoding="utf-8")
            ignored = workspace / "ignored-secret"
            ignored.mkdir()
            (ignored / "hostname-private.bin").write_bytes(b"private")
            self.commit_all(workspace)
            (workspace / "untracked-private-name.log").write_text("private log\n", encoding="utf-8")

            status_before = subprocess.run(
                ["git", "status", "--porcelain=v1", "--untracked-files=all"],
                cwd=workspace,
                check=True,
                text=True,
                stdout=subprocess.PIPE,
            ).stdout
            metadata_before = self.worktree_metadata(workspace)
            index = workspace / ".git" / "index"
            index_before = (index.read_bytes(), index.stat().st_mtime_ns)

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "profile_workspace_performance.py"),
                    "--workspace",
                    str(workspace),
                    "--profile-id",
                    "12345678-1234-5678-1234-567812345678",
                    "--rounds",
                    "1",
                    "--timeout",
                    "10",
                    "--seed",
                    "17",
                    "--json",
                ],
                cwd=ROOT,
                check=True,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            payload = json.loads(result.stdout)
            serialized = json.dumps(payload, sort_keys=True)

            self.assertEqual(payload["schema_version"], 1)
            self.assertEqual(payload["profile_id"], "12345678-1234-5678-1234-567812345678")
            self.assertEqual(payload["tool_shed_work"]["files"], 2)
            for forbidden in (
                str(workspace),
                "Secret Customer Alice",
                "secret-project-codename",
                "alice@example.invalid",
                "tracked-secret-token",
                "untracked-private-name",
                "hostname-private",
                "credential-like-value",
            ):
                self.assertNotIn(forbidden, serialized)

            self.assertEqual((index.read_bytes(), index.stat().st_mtime_ns), index_before)
            status_after = subprocess.run(
                ["git", "status", "--porcelain=v1", "--untracked-files=all"],
                cwd=workspace,
                check=True,
                text=True,
                stdout=subprocess.PIPE,
            ).stdout
            self.assertEqual(status_after, status_before)
            self.assertEqual(self.worktree_metadata(workspace), metadata_before)

    def test_report_validator_rejects_unknown_nested_fields(self) -> None:
        profile_id = "12345678-1234-5678-1234-567812345678"
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            self.init_repository(workspace)
            self.commit_all(workspace)
            report = profiler.build_report(workspace, profile_id=profile_id, rounds=1, timeout=10, seed=1)
            report["repository"]["private_path"] = "/sensitive/path"
            with self.assertRaisesRegex(ValueError, "unknown=.*private_path"):
                profiler.validate_report(report)

    def test_percentile_timeout_and_unsupported_probe_statuses(self) -> None:
        self.assertEqual(profiler.nearest_rank_p95([1.0, 2.0, 3.0, 4.0, 5.0]), 5.0)
        with mock.patch.object(
            profiler,
            "probe_command",
            return_value=[sys.executable, "-c", "import time; time.sleep(2)"],
        ):
            _duration, status = profiler.one_probe("filesystem_inventory", ROOT, 1)
            self.assertEqual(status, "timeout")
        with mock.patch.object(profiler, "probe_command", return_value=["missing-profiler-command"]):
            _duration, status = profiler.one_probe("filesystem_inventory", ROOT, 1)
            self.assertEqual(status, "unsupported")
        with mock.patch.object(
            profiler,
            "probe_command",
            return_value=[sys.executable, "-c", "raise SystemExit(3)"],
        ):
            _duration, status = profiler.one_probe("filesystem_inventory", ROOT, 1)
            self.assertEqual(status, "error")

    def test_filesystem_inventory_does_not_follow_symlink_directories(self) -> None:
        if not hasattr(os, "symlink"):
            self.skipTest("symlinks are unavailable")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "workspace"
            outside = Path(temp) / "outside"
            root.mkdir()
            outside.mkdir()
            (root / "inside.txt").write_text("inside\n", encoding="utf-8")
            (outside / "outside.bin").write_bytes(b"outside")
            try:
                (root / "linked-outside").symlink_to(outside, target_is_directory=True)
            except OSError as error:
                self.skipTest(f"symlink creation is unavailable: {error}")

            summary = profiler.filesystem_summary(root)

            self.assertEqual(sum(summary["content_classes"].values()), 1)
            self.assertGreaterEqual(summary["skipped_boundaries"], 1)

    def test_filesystem_inventory_prunes_other_device_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            mounted = root / "mounted-device"
            mounted.mkdir()
            (mounted / "must-not-count.txt").write_text("outside boundary\n", encoding="utf-8")
            root_device = root.stat().st_dev
            original_stat = Path.stat

            def device_aware_stat(path: Path, *args: object, **kwargs: object) -> os.stat_result | object:
                if path == mounted and kwargs.get("follow_symlinks", True) is not False:
                    return mock.Mock(st_dev=root_device + 1)
                return original_stat(path, *args, **kwargs)

            with mock.patch.object(Path, "stat", device_aware_stat):
                summary = profiler.filesystem_summary(root)

            self.assertEqual(sum(summary["content_classes"].values()), 0)
            self.assertGreaterEqual(summary["skipped_boundaries"], 1)

    def test_completed_artifact_and_evidence_scaling_fixtures(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            self.init_repository(workspace)
            completed = workspace / "work" / "wp" / "completed"
            completed.mkdir(parents=True)
            expected = 0
            for target in (0, 100, 1_000, 5_000):
                for number in range(expected, target):
                    (completed / f"wp-scale-{number:05d}.md").write_text(
                        "\n".join(
                            [
                                f"# Workpackage {number}",
                                "",
                                "Status: complete",
                                "Type: workpackage",
                                "Updated: 2026-08-03",
                                "Next Action: none",
                                "",
                            ]
                        ),
                        encoding="utf-8",
                    )
                expected = target
                summary = profiler.artifact_summary(workspace, profiler.date(2026, 8, 3))
                self.assertEqual(summary["files"], target)
                self.assertEqual(summary["by_lifecycle"]["finished"], target)

        for target in (0, 10, 100):
            with tempfile.TemporaryDirectory() as temp:
                workspace = Path(temp)
                self.init_repository(workspace)
                evidence = workspace / "work" / "evidence"
                evidence.mkdir(parents=True)
                for number in range(target):
                    (evidence / f"sample-{number:03d}.log").write_text("sample\n", encoding="utf-8")
                profile = workspace_preflight.workspace_profile(workspace, {})
                self.assertEqual(profile["evidence"]["untracked_count"], target)


if __name__ == "__main__":
    unittest.main()
