from __future__ import annotations

import hashlib
import json
import shutil
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


class ScriptTests(unittest.TestCase):
    def init_repository(self, root: Path, gitignore: str = "") -> None:
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        (root / ".gitignore").write_text(gitignore, encoding="utf-8")

    def test_check_shed_version_detects_equal_version_release_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            local = root / "local"
            local.mkdir()
            tracked = local / "README.md"
            tracked.write_text("snapshot\n", encoding="utf-8")
            digest = hashlib.sha256(tracked.read_bytes()).hexdigest()
            local_manifest = {
                "shed_version": "1.3.0",
                "artifact_model_version": "model-a",
                "manifest_schema_version": 2,
                "content_hashes": {"README.md": digest},
                "release_tag": "v1.3.0",
                "release_commit": None,
                "released_at": None,
            }
            (local / "SHED_VERSION.json").write_text(json.dumps(local_manifest), encoding="utf-8")
            canonical = root / "canonical.json"
            canonical.write_text(
                json.dumps(
                    {
                        "shed_version": "1.3.0",
                        "artifact_model_version": "model-a",
                        "manifest_schema_version": 2,
                        "content_hashes": {"README.md": "different-release-content"},
                        "release_tag": "v1.3.0",
                        "release_commit": None,
                        "released_at": None,
                    }
                ),
                encoding="utf-8",
            )

            result = run_script(
                "scripts/check_shed_version.py",
                "--shed",
                str(local),
                "--canonical",
                str(canonical),
                "--json",
                "--strict",
                check=False,
            )

            self.assertEqual(result.returncode, 1)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["version_relation"], "current")
            self.assertFalse(payload["canonical_manifest_match"])
            self.assertEqual(payload["state"], "release-mismatch")

    def test_manifest_writer_requires_intentional_version_increase(self) -> None:
        current_version = json.loads((ROOT / "SHED_VERSION.json").read_text(encoding="utf-8"))[
            "shed_version"
        ]
        missing = run_script("scripts/update_shed_manifest.py", "--write", check=False)
        same = run_script(
            "scripts/update_shed_manifest.py",
            "--write",
            "--version",
            current_version,
            check=False,
        )
        invalid = run_script(
            "scripts/update_shed_manifest.py",
            "--write",
            "--version",
            "banana",
            check=False,
        )

        self.assertNotEqual(missing.returncode, 0)
        self.assertIn("--version is required", missing.stderr)
        self.assertNotEqual(same.returncode, 0)
        self.assertIn("must be greater", same.stderr)
        self.assertNotEqual(invalid.returncode, 0)
        self.assertIn("expected MAJOR.MINOR.PATCH", invalid.stderr)

    def test_version_checks_fail_cleanly_for_bad_local_manifest_and_insecure_url(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            local = root / "local"
            local.mkdir()
            (local / "SHED_VERSION.json").write_text("{broken", encoding="utf-8")

            malformed = run_script(
                "scripts/check_shed_version.py",
                "--shed",
                str(local),
                "--json",
                check=False,
            )

            self.assertEqual(malformed.returncode, 2)
            self.assertEqual(json.loads(malformed.stdout)["state"], "check-failed")

        insecure = run_script(
            "scripts/check_shed_version.py",
            "--shed",
            str(ROOT),
            "--canonical",
            "http://example.com/SHED_VERSION.json",
            "--json",
            check=False,
        )
        self.assertEqual(insecure.returncode, 2)
        insecure_payload = json.loads(insecure.stdout)
        self.assertEqual(insecure_payload["state"], "check-failed")
        self.assertIn("must use HTTPS", insecure_payload["error"])

    def test_manifest_writer_rejects_invalid_release_timestamp(self) -> None:
        current_version = json.loads((ROOT / "SHED_VERSION.json").read_text(encoding="utf-8"))[
            "shed_version"
        ]
        result = run_script(
            "scripts/update_shed_manifest.py",
            "--write",
            "--version",
            current_version,
            "--allow-same-version",
            "--release-commit",
            "abcdef1",
            "--released-at",
            "not-a-date",
            check=False,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ISO 8601", result.stderr)

    def test_manifest_records_release_provenance_fields(self) -> None:
        manifest = json.loads((ROOT / "SHED_VERSION.json").read_text(encoding="utf-8"))

        self.assertEqual(manifest["manifest_schema_version"], 2)
        self.assertEqual(manifest["release_tag"], f"v{manifest['shed_version']}")
        self.assertIn("release_commit", manifest)
        self.assertIn("released_at", manifest)

    def test_check_shed_version_reports_older_verified_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            local = root / "local"
            local.mkdir()
            tracked = local / "README.md"
            tracked.write_text("snapshot\n", encoding="utf-8")
            digest = hashlib.sha256(tracked.read_bytes()).hexdigest()
            (local / "SHED_VERSION.json").write_text(
                json.dumps(
                    {
                        "shed_version": "1.2.0",
                        "artifact_model_version": "model-a",
                        "manifest_schema_version": 2,
                        "content_hashes": {"README.md": digest},
                        "release_tag": "v1.2.0",
                        "release_commit": None,
                        "released_at": None,
                    }
                ),
                encoding="utf-8",
            )
            canonical = root / "canonical.json"
            canonical.write_text(
                json.dumps(
                    {
                        "shed_version": "1.3.0",
                        "artifact_model_version": "model-a",
                        "manifest_schema_version": 2,
                        "content_hashes": {"README.md": "canonical"},
                        "release_tag": "v1.3.0",
                        "release_commit": None,
                        "released_at": None,
                    }
                ),
                encoding="utf-8",
            )

            result = run_script(
                "scripts/check_shed_version.py",
                "--shed",
                str(local),
                "--canonical",
                str(canonical),
                "--json",
                "--strict",
                check=False,
            )

            self.assertEqual(result.returncode, 1)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["local_integrity"], "verified")
            self.assertEqual(payload["version_relation"], "older")
            self.assertEqual(payload["state"], "older")

    def test_check_shed_version_prioritizes_local_modification(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            local = root / "local"
            local.mkdir()
            (local / "README.md").write_text("modified\n", encoding="utf-8")
            (local / "SHED_VERSION.json").write_text(
                json.dumps(
                    {
                        "shed_version": "1.3.0",
                        "artifact_model_version": "model-a",
                        "manifest_schema_version": 2,
                        "content_hashes": {"README.md": "not-the-hash"},
                        "release_tag": "v1.3.0",
                        "release_commit": None,
                        "released_at": None,
                    }
                ),
                encoding="utf-8",
            )
            canonical = root / "canonical.json"
            canonical.write_text(
                json.dumps(
                    {
                        "shed_version": "1.3.0",
                        "artifact_model_version": "model-a",
                        "manifest_schema_version": 2,
                        "content_hashes": {"README.md": "canonical"},
                        "release_tag": "v1.3.0",
                        "release_commit": None,
                        "released_at": None,
                    }
                ),
                encoding="utf-8",
            )

            result = run_script(
                "scripts/check_shed_version.py",
                "--shed",
                str(local),
                "--canonical",
                str(canonical),
                "--json",
            )

            payload = json.loads(result.stdout)
            self.assertEqual(payload["version_relation"], "current")
            self.assertEqual(payload["state"], "modified")
            self.assertEqual(payload["modified"], ["README.md"])

    def test_operator_help_is_packaged_and_routed(self) -> None:
        guide = (ROOT / "docs" / "operator-guide.md").read_text(encoding="utf-8")
        skill = (ROOT / "skills" / "tool-shed" / "SKILL.md").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("ts: help", guide)
        self.assertIn("## Common Use Cases", guide)
        self.assertIn("docs/operator-guide.md", skill)
        self.assertIn("artifacts for a help-only request.", skill)
        self.assertIn("[Tool Shed operator guide](docs/operator-guide.md)", readme)
        self.assertIn("ts: version", skill)
        self.assertIn("ts: check for updates", guide)

    def test_review_work_state_reports_drift_as_json_and_strict_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            work = workspace / "work"
            (work / "maps").mkdir(parents=True)
            (work / "spikes").mkdir(parents=True)
            (work / "tickets").mkdir(parents=True)
            (work / "maps" / "map-demo.md").write_text(
                """# Project Map: Demo

Status: active
Type: project-map
Updated: 2026-07-24
Next Action: review the old spike

Related spike: work/spikes/spike-old.md

- [ ] Resolve work/spikes/spike-old.md
""",
                encoding="utf-8",
            )
            (work / "spikes" / "spike-old.md").write_text(
                """# Spike: Old

Status: complete
Type: spike
Updated: 2026-06-01
Next Action: none
Parent: work/maps/map-missing.md
Disposition: pending
Produces:
""",
                encoding="utf-8",
            )
            (work / "tickets" / "ticket-orphan.md").write_text(
                """# Ticket: Orphan

Status: active
Type: ticket
Updated: 2026-06-01
Next Action: implement it
Parent: work/...
""",
                encoding="utf-8",
            )
            (work / "tickets" / "ticket-broken-parent.md").write_text(
                """# Ticket: Broken parent

Status: active
Type: ticket
Updated: 2026-07-24
Next Action: reconnect it
Parent: work/maps/map-missing.md
""",
                encoding="utf-8",
            )

            result = run_script(
                "scripts/review_work_state.py",
                "--workspace",
                str(workspace),
                "--today",
                "2026-07-24",
                "--stale-days",
                "30",
                "--json",
                "--strict",
                check=False,
            )

            self.assertEqual(result.returncode, 1)
            payload = json.loads(result.stdout)
            codes = {finding["code"] for finding in payload["findings"]}
            self.assertEqual(
                codes,
                {"BROKEN_PARENT", "ORPHAN_ACTIVE", "PLAN_DRIFT", "STALE_ACTIVE", "UNDISPOSED_SPIKE"},
            )
            self.assertEqual(payload["summary"], {"errors": 2, "total": 5, "warnings": 3})

    def test_review_work_state_allows_historical_and_related_finished_links(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            work = workspace / "work"
            (work / "maps").mkdir(parents=True)
            (work / "tickets").mkdir(parents=True)
            (work / "maps" / "map-demo.md").write_text(
                """# Project Map: Demo

Status: active
Type: project-map
Updated: 2026-07-24
Next Action: continue current delivery

## Historical Context

- Completed work: work/tickets/ticket-done.md

## Related Artifacts

- Ticket: work/tickets/ticket-done.md
""",
                encoding="utf-8",
            )
            (work / "tickets" / "ticket-done.md").write_text(
                """# Ticket: Done

Status: complete
Type: ticket
Updated: 2026-07-24
Next Action: none
Parent: work/maps/map-demo.md
""",
                encoding="utf-8",
            )

            result = run_script(
                "scripts/review_work_state.py",
                "--workspace",
                str(workspace),
                "--today",
                "2026-07-24",
                "--strict",
            )

            self.assertEqual(result.returncode, 0)
            self.assertIn("Work state is reconciled.", result.stdout)

    def test_review_work_state_accepts_connected_work_and_disposed_spike(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            work = workspace / "work"
            (work / "maps").mkdir(parents=True)
            (work / "spikes").mkdir(parents=True)
            (work / "tickets").mkdir(parents=True)
            (work / "maps" / "map-demo.md").write_text(
                """# Project Map: Demo

Status: active
Type: project-map
Updated: 2026-07-24
Next Action: deliver the ticket
""",
                encoding="utf-8",
            )
            (work / "tickets" / "ticket-demo.md").write_text(
                """# Ticket: Demo

Status: active
Type: ticket
Updated: 2026-07-24
Next Action: implement it
Parent: work/maps/map-demo.md
""",
                encoding="utf-8",
            )
            (work / "spikes" / "spike-demo.md").write_text(
                """# Spike: Demo

Status: complete
Type: spike
Updated: 2026-07-24
Next Action: none
Parent: work/maps/map-demo.md
Disposition: planned
Produces: work/tickets/ticket-demo.md
""",
                encoding="utf-8",
            )

            result = run_script(
                "scripts/review_work_state.py",
                "--workspace",
                str(workspace),
                "--today",
                "2026-07-24",
                "--strict",
            )

            self.assertEqual(result.returncode, 0)
            self.assertIn("Work state is reconciled.", result.stdout)

    def test_repository_policy_accepts_tracked_work(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            self.init_repository(workspace)
            (workspace / "work").mkdir()
            (workspace / "work" / "evidence.md").write_text("tracked evidence\n", encoding="utf-8")

            result = run_script(
                "scripts/review_work_state.py",
                "--workspace",
                str(workspace),
                "--strict",
            )

            self.assertEqual(result.returncode, 0)
            self.assertIn("Work state is reconciled.", result.stdout)

    def test_repository_policy_reports_stale_root_work_ignore_and_preserves_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            self.init_repository(workspace, "/work/\n")
            (workspace / "work").mkdir()
            evidence = workspace / "work" / "evidence.bin"
            original = b"preserve-me"
            evidence.write_bytes(original)

            install = run_script(
                "scripts/install_into_workspace.py",
                str(workspace),
                check=False,
            )
            review = run_script(
                "scripts/review_work_state.py",
                "--workspace",
                str(workspace),
                "--json",
                "--strict",
                check=False,
            )

            self.assertEqual(install.returncode, 1)
            self.assertIn(".gitignore:1: '/work/'", install.stdout)
            self.assertIn("Trackability preview:", install.stdout)
            self.assertIn("file(s)", install.stdout)
            self.assertEqual(evidence.read_bytes(), original)
            self.assertEqual(review.returncode, 1)
            finding = json.loads(review.stdout)["findings"][0]
            self.assertEqual(finding["code"], "UNDOCUMENTED_WORK_IGNORE")
            self.assertIn(".gitignore:1: '/work/'", finding["message"])

    def test_repository_policy_accepts_explicit_documented_exception(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            self.init_repository(workspace, "/work/\n")
            (workspace / ".tool-shed-policy.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "work_git_policy": {
                            "ignore": True,
                            "reason": "Owner-only planning contains sensitive incident details.",
                        },
                    }
                ),
                encoding="utf-8",
            )

            install = run_script("scripts/install_into_workspace.py", str(workspace))
            review = run_script(
                "scripts/review_work_state.py",
                "--workspace",
                str(workspace),
                "--strict",
            )

            self.assertIn("Documented exception in .tool-shed-policy.json", install.stdout)
            self.assertEqual(review.returncode, 0)

    def test_repository_policy_ignores_nested_and_unrelated_rules(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            self.init_repository(workspace, "/packages/demo/work/\n/cache/work/\n*.tmp\n")
            (workspace / "work").mkdir()
            (workspace / "work" / "evidence.md").write_text("track me\n", encoding="utf-8")

            result = run_script(
                "scripts/review_work_state.py",
                "--workspace",
                str(workspace),
                "--strict",
            )

            self.assertEqual(result.returncode, 0)
            self.assertIn("Work state is reconciled.", result.stdout)

    def test_repository_policy_accepts_ignored_snapshot_with_tracked_work(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            self.init_repository(workspace, "/tool_shed/\n")
            (workspace / "tool_shed").mkdir()
            (workspace / "tool_shed" / "README.md").write_text("snapshot\n", encoding="utf-8")
            (workspace / "work").mkdir()
            (workspace / "work" / "evidence.md").write_text("track me\n", encoding="utf-8")

            install = run_script("scripts/install_into_workspace.py", str(workspace))
            review = run_script(
                "scripts/review_work_state.py",
                "--workspace",
                str(workspace),
                "--strict",
            )

            self.assertIn("root work/ is trackable", install.stdout)
            self.assertEqual(review.returncode, 0)

    def test_fleet_inventory_classifies_current_and_stale_snapshots(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            search_root = Path(temp)
            shed = search_root / "project" / "tool_shed"
            for relative in (
                "SHED_VERSION.json",
                "README.md",
                "selection.md",
                "conventions.md",
                "existing-projects.md",
                "skills/tool-shed/SKILL.md",
            ):
                destination = shed / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / relative, destination)

            current = run_script(
                "scripts/inventory_tool_shed_fleet.py",
                "--root",
                str(search_root),
                "--json",
            )
            current_payload = json.loads(current.stdout)
            self.assertEqual(current_payload["hosts"][0]["sheds"][0]["state"], "current")

            (shed / "conventions.md").write_text("stale\n", encoding="utf-8")
            stale = run_script(
                "scripts/inventory_tool_shed_fleet.py",
                "--root",
                str(search_root),
                "--json",
            )
            stale_payload = json.loads(stale.stdout)
            self.assertEqual(stale_payload["hosts"][0]["sheds"][0]["state"], "stale")
            self.assertEqual(stale_payload["hosts"][0]["sheds"][0]["changed"], ["conventions.md"])

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


if __name__ == "__main__":
    unittest.main()
