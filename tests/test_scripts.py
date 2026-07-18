from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run_script(*args: str, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=str(cwd or ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=check,
    )


def make_fake_tool_shed_snapshot(
    root: Path,
    *,
    validation_exit: int = 0,
    install_exit: int = 0,
    marker: str = "new snapshot",
) -> None:
    root.mkdir(parents=True)
    for name in ["README.md", "selection.md", "conventions.md", "existing-projects.md"]:
        (root / name).write_text(f"# {name}\n", encoding="utf-8")
    (root / "templates").mkdir()
    (root / "scripts").mkdir()
    (root / ".git").mkdir()
    (root / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (root / "MARKER.txt").write_text(marker, encoding="utf-8")
    (root / "scripts" / "validate_tool_shed.py").write_text(
        f"""from __future__ import annotations

import sys

print("fake validation")
raise SystemExit({validation_exit})
""",
        encoding="utf-8",
    )
    (root / "scripts" / "install_into_workspace.py").write_text(
        f"""from __future__ import annotations

import sys
from pathlib import Path

workspace = Path(sys.argv[1]).resolve()
(workspace / "work").mkdir(exist_ok=True)
readme = workspace / "work" / "README.md"
if not readme.exists():
    readme.write_text("# Work\\n", encoding="utf-8")
raise SystemExit({install_exit})
""",
        encoding="utf-8",
    )


class ScriptTests(unittest.TestCase):
    def test_complete_workpackage_moves_and_refreshes_indexes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            source = workspace / "work" / "wp" / "active" / "wp-demo.md"
            source.parent.mkdir(parents=True)
            source.write_text(
                """# Workpackage: Demo

Status: active
Type: workpackage
Updated: 2026-07-01
Next Action: finish the thing
Project Map: work/maps/map-demo.md
""",
                encoding="utf-8",
            )
            (workspace / "work" / "maps").mkdir(parents=True)
            (workspace / "work" / "maps" / "map-demo.md").write_text(
                "Package: [demo](work/wp/active/wp-demo.md)\n",
                encoding="utf-8",
            )

            result = run_script(
                "scripts/complete_workpackage.py",
                "work/wp/active/wp-demo.md",
                "--workspace",
                str(workspace),
                "--next-action",
                "none",
            )

            destination = workspace / "work" / "wp" / "completed" / "wp-demo.md"
            self.assertFalse(source.exists())
            self.assertTrue(destination.exists())
            text = destination.read_text(encoding="utf-8")
            self.assertIn("Status: complete", text)
            self.assertIn("Next Action: none", text)
            self.assertIn("work/wp/completed/wp-demo.md", result.stdout)
            self.assertIn("Stale-path findings are warnings.", result.stdout)
            payload = json.loads((workspace / "work" / "index.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["artifacts"][0]["path"], "work/maps/map-demo.md")
            self.assertEqual(payload["artifacts"][1]["path"], "work/wp/completed/wp-demo.md")

    def test_complete_workpackage_strict_stale_check_fails_on_stale_links(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            source = workspace / "work" / "wp" / "active" / "wp-demo.md"
            source.parent.mkdir(parents=True)
            source.write_text(
                """# Workpackage: Demo

Status: active
Type: workpackage
Updated: 2026-07-01
Next Action: finish the thing
""",
                encoding="utf-8",
            )
            (workspace / "work" / "maps").mkdir(parents=True)
            (workspace / "work" / "maps" / "map-demo.md").write_text(
                "Package: [demo](work/wp/active/wp-demo.md)\n",
                encoding="utf-8",
            )

            result = run_script(
                "scripts/complete_workpackage.py",
                "work/wp/active/wp-demo.md",
                "--workspace",
                str(workspace),
                "--strict-stale-check",
                check=False,
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn("active workpackage path is stale", result.stdout)

    def test_update_work_index_writes_markdown_and_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            artifact = workspace / "work" / "maps" / "map-demo.md"
            artifact.parent.mkdir(parents=True)
            artifact.write_text(
                """# Project Map: Demo

Status: active
Type: project-map
Updated: 2026-07-05
Next Action: keep going
""",
                encoding="utf-8",
            )

            run_script("scripts/update_work_index.py", "--workspace", str(workspace))

            index_md = workspace / "work" / "index.md"
            index_json = workspace / "work" / "index.json"
            self.assertIn("work/maps/map-demo.md", index_md.read_text(encoding="utf-8"))
            payload = json.loads(index_json.read_text(encoding="utf-8"))
            self.assertEqual(payload["schema_version"], 1)
            self.assertEqual(payload["summary"]["active_artifacts"], 1)
            self.assertEqual(payload["artifacts"][0]["path"], "work/maps/map-demo.md")

    def test_check_stale_paths_detects_moved_workpackage(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            (workspace / "work" / "maps").mkdir(parents=True)
            (workspace / "work" / "wp" / "completed").mkdir(parents=True)
            (workspace / "work" / "maps" / "map-demo.md").write_text(
                "See [old package](work/wp/active/wp-demo.md)\n",
                encoding="utf-8",
            )
            (workspace / "work" / "wp" / "completed" / "wp-demo.md").write_text("# Demo\n", encoding="utf-8")

            result = run_script("scripts/check_stale_paths.py", "--workspace", str(workspace), check=False)

            self.assertEqual(result.returncode, 1)
            self.assertIn("work/wp/completed/wp-demo.md", result.stdout)

    def test_check_stale_paths_passes_current_repo(self) -> None:
        result = run_script("scripts/check_stale_paths.py", "--workspace", str(ROOT))
        self.assertEqual(result.returncode, 0)
        self.assertIn("No stale work paths found.", result.stdout)

    def test_new_artifact_refreshes_indexes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)

            run_script(
                "scripts/new_artifact.py",
                "checklist",
                "Runtime Closeout",
                "--workspace",
                str(workspace),
                "--shed",
                str(ROOT),
            )

            artifact = workspace / "work" / "checklists" / "checklist-runtime-closeout.md"
            self.assertTrue(artifact.exists())
            self.assertTrue((workspace / "work" / "wp" / "active").is_dir())
            self.assertIn(
                "complete_workpackage.py",
                (workspace / "work" / "README.md").read_text(encoding="utf-8"),
            )
            payload = json.loads((workspace / "work" / "index.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["artifacts"][0]["path"], "work/checklists/checklist-runtime-closeout.md")

    def test_install_work_readme_mentions_completion_helper(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)

            run_script("scripts/install_into_workspace.py", str(workspace))

            readme = (workspace / "work" / "README.md").read_text(encoding="utf-8")
            self.assertIn("complete_workpackage.py", readme)

    def test_onboard_existing_project_refreshes_indexes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)

            run_script(
                "scripts/onboard_existing_project.py",
                "Index Test",
                "--workspace",
                str(workspace),
                "--shed",
                str(ROOT),
            )

            self.assertTrue((workspace / "work" / "maps" / "map-index-test.md").exists())
            self.assertTrue((workspace / "work" / "inventories" / "inventory-index-test-surfaces.md").exists())
            payload = json.loads((workspace / "work" / "index.json").read_text(encoding="utf-8"))
            paths = {item["path"] for item in payload["artifacts"]}
            self.assertIn("work/maps/map-index-test.md", paths)
            self.assertIn("work/inventories/inventory-index-test-surfaces.md", paths)
            readme = (workspace / "work" / "README.md").read_text(encoding="utf-8")
            self.assertIn("complete_workpackage.py", readme)

    def test_install_tool_shed_from_local_snapshot_fresh_install(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            source = temp_root / "source"
            workspace = temp_root / "workspace"
            make_fake_tool_shed_snapshot(source)
            workspace.mkdir()
            (workspace / ".gitignore").write_text("logs/\n/tool_shed/\n/tool_shed/\n", encoding="utf-8")

            run_script(
                "scripts/install_tool_shed_from_github.py",
                str(workspace),
                "--source",
                str(source),
            )

            self.assertTrue((workspace / "tool_shed" / "MARKER.txt").exists())
            self.assertFalse((workspace / "tool_shed" / ".git").exists())
            self.assertTrue((workspace / "work" / "README.md").exists())
            gitignore_lines = (workspace / ".gitignore").read_text(encoding="utf-8").splitlines()
            self.assertEqual(gitignore_lines.count("/tool_shed/"), 1)
            self.assertIn("logs/", gitignore_lines)

    def test_install_tool_shed_update_preserves_existing_work(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            source = temp_root / "source"
            workspace = temp_root / "workspace"
            make_fake_tool_shed_snapshot(source, marker="replacement")
            (workspace / "tool_shed").mkdir(parents=True)
            (workspace / "tool_shed" / "OLD.txt").write_text("old tooling\n", encoding="utf-8")
            work_artifact = workspace / "work" / "maps" / "map-existing.md"
            work_artifact.parent.mkdir(parents=True)
            work_artifact.write_text("keep me\n", encoding="utf-8")

            run_script(
                "scripts/install_tool_shed_from_github.py",
                str(workspace),
                "--source",
                str(source),
            )

            self.assertFalse((workspace / "tool_shed" / "OLD.txt").exists())
            self.assertEqual((workspace / "tool_shed" / "MARKER.txt").read_text(encoding="utf-8"), "replacement")
            self.assertEqual(work_artifact.read_text(encoding="utf-8"), "keep me\n")

    def test_install_tool_shed_validation_failure_stops_before_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            source = temp_root / "source"
            workspace = temp_root / "workspace"
            make_fake_tool_shed_snapshot(source, validation_exit=7)
            (workspace / "tool_shed").mkdir(parents=True)
            (workspace / "tool_shed" / "OLD.txt").write_text("old tooling\n", encoding="utf-8")

            result = run_script(
                "scripts/install_tool_shed_from_github.py",
                str(workspace),
                "--source",
                str(source),
                check=False,
            )

            self.assertEqual(result.returncode, 7)
            self.assertTrue((workspace / "tool_shed" / "OLD.txt").exists())
            self.assertFalse((workspace / "tool_shed" / "MARKER.txt").exists())

    def test_install_tool_shed_rolls_back_when_workspace_install_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            source = temp_root / "source"
            workspace = temp_root / "workspace"
            make_fake_tool_shed_snapshot(source, install_exit=9)
            (workspace / "tool_shed").mkdir(parents=True)
            (workspace / "tool_shed" / "OLD.txt").write_text("old tooling\n", encoding="utf-8")
            (workspace / ".gitignore").write_text("build/\n", encoding="utf-8")

            result = run_script(
                "scripts/install_tool_shed_from_github.py",
                str(workspace),
                "--source",
                str(source),
                check=False,
            )

            self.assertEqual(result.returncode, 9)
            self.assertTrue((workspace / "tool_shed" / "OLD.txt").exists())
            self.assertFalse((workspace / "tool_shed" / "MARKER.txt").exists())
            self.assertEqual((workspace / ".gitignore").read_text(encoding="utf-8"), "build/\n")


if __name__ == "__main__":
    unittest.main()
