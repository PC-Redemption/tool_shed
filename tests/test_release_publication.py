from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ReleasePublicationTests(unittest.TestCase):
    def create_release(self, root: Path, *, change_extra_file: bool = False) -> tuple[Path, str]:
        repository = root / "repository"
        repository.mkdir()
        subprocess.run(["git", "init", "--quiet"], cwd=repository, check=True)
        subprocess.run(
            ["git", "config", "user.name", "Tool Shed Tests"], cwd=repository, check=True
        )
        subprocess.run(
            ["git", "config", "user.email", "tests@example.invalid"],
            cwd=repository,
            check=True,
        )
        manifest = {
            "shed_version": "1.2.3",
            "release_tag": "v1.2.3",
            "release_commit": None,
            "released_at": None,
            "notes": "Exercise deterministic GitHub Release publication",
        }
        (repository / "SHED_VERSION.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )
        (repository / "payload.txt").write_text("released content\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=repository, check=True)
        subprocess.run(["git", "commit", "--quiet", "-m", "Release content"], cwd=repository, check=True)
        content_commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repository, text=True
        ).strip()
        manifest["release_commit"] = content_commit
        manifest["released_at"] = "2026-08-17T20:00:00Z"
        (repository / "SHED_VERSION.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )
        if change_extra_file:
            (repository / "payload.txt").write_text("unexpected provenance change\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=repository, check=True)
        subprocess.run(
            ["git", "commit", "--quiet", "-m", "Record release provenance"],
            cwd=repository,
            check=True,
        )
        subprocess.run(
            ["git", "tag", "-a", "v1.2.3", "-m", "Tool Shed v1.2.3"],
            cwd=repository,
            check=True,
        )
        return repository, content_commit

    def run_prepare(
        self, repository: Path, *arguments: str
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "prepare_github_release.py"),
                "--repository",
                str(repository),
                "--tag",
                "v1.2.3",
                *arguments,
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def test_preparer_accepts_exact_latest_tag_and_writes_deterministic_notes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repository, content_commit = self.create_release(root)
            notes = root / "release-notes.md"

            result = self.run_prepare(repository, "--notes-file", str(notes), "--json")
            payload = json.loads(result.stdout)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(payload["valid"])
            self.assertEqual(payload["tag"], "v1.2.3")
            self.assertEqual(payload["content_commit"], content_commit)
            self.assertTrue(payload["latest"])
            notes_text = notes.read_text(encoding="utf-8")
            self.assertIn("## What changed", notes_text)
            self.assertIn(content_commit, notes_text)
            self.assertIn("v1.2.3", notes_text)

    def test_preparer_rejects_nonlatest_or_non_provenance_only_tags(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repository, _ = self.create_release(root)
            subprocess.run(
                ["git", "tag", "-a", "v1.2.4", "-m", "Newer tag"],
                cwd=repository,
                check=True,
            )
            result = self.run_prepare(repository, "--json")
            payload = json.loads(result.stdout)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("highest stable tag is v1.2.4", payload["error"])

        with tempfile.TemporaryDirectory() as temp:
            repository, _ = self.create_release(Path(temp), change_extra_file=True)
            result = self.run_prepare(repository, "--json")
            payload = json.loads(result.stdout)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("exactly SHED_VERSION.json", payload["error"])

    def test_release_workflow_and_runbook_close_the_tag_only_gap(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(
            encoding="utf-8"
        )
        runbook = (ROOT / "docs" / "releasing.md").read_text(encoding="utf-8")
        manifest_tool = (ROOT / "scripts" / "update_shed_manifest.py").read_text(
            encoding="utf-8"
        )

        self.assertIn('"v*.*.*"', workflow)
        self.assertIn("contents: write", workflow)
        self.assertIn("scripts/validate_tool_shed.py", workflow)
        self.assertIn("--profile release", workflow)
        self.assertIn("scripts/prepare_github_release.py", workflow)
        self.assertIn("gh release create", workflow)
        self.assertIn("gh release view", workflow)
        self.assertIn("--verify-tag", workflow)
        self.assertIn("--latest", workflow)
        self.assertIn("gh release edit", workflow)
        self.assertIn("releases/latest", workflow)
        self.assertIn('test "$release_state" = "false"', workflow)
        self.assertIn("tag-only publication is incomplete", runbook)
        self.assertIn("gh release view", runbook)
        self.assertIn(".github/workflows/*.yml", manifest_tool)


if __name__ == "__main__":
    unittest.main()
