from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run_script(
    *args: str,
    cwd: Path | None = None,
    check: bool = True,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=str(cwd or ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=check,
        env=env,
    )


class ScriptTests(unittest.TestCase):
    def init_repository(self, root: Path, gitignore: str = "") -> None:
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        (root / ".gitignore").write_text(gitignore, encoding="utf-8")

    def create_test_release(
        self,
        root: Path,
        version: str = "9.8.7",
        *,
        validation_exit: int = 0,
        include_stale_checker: bool = False,
    ) -> Path:
        repository = root / "release source"
        repository.mkdir()
        self.init_repository(repository)
        subprocess.run(["git", "config", "user.name", "Tool Shed Tests"], cwd=repository, check=True)
        subprocess.run(["git", "config", "user.email", "tests@example.invalid"], cwd=repository, check=True)
        for name in ("selection.md", "conventions.md", "existing-projects.md"):
            (repository / name).write_text(f"{name}\n", encoding="utf-8", newline="\n")
        (repository / "README.md").write_text("released snapshot\n", encoding="utf-8", newline="\n")
        (repository / "templates").mkdir()
        (repository / "templates" / "checklist.md").write_text("template\n", encoding="utf-8", newline="\n")
        (repository / "scripts").mkdir()
        shutil.copyfile(
            ROOT / "scripts" / "check_shed_version.py",
            repository / "scripts" / "check_shed_version.py",
        )
        if include_stale_checker:
            shutil.copyfile(
                ROOT / "scripts" / "check_stale_paths.py",
                repository / "scripts" / "check_stale_paths.py",
            )
        (repository / "scripts" / "validate_tool_shed.py").write_text(
            f"raise SystemExit({validation_exit})\n",
            encoding="utf-8",
            newline="\n",
        )
        hashed_paths = [
            "README.md",
            "selection.md",
            "conventions.md",
            "existing-projects.md",
            "templates/checklist.md",
            "scripts/check_shed_version.py",
            "scripts/validate_tool_shed.py",
        ]
        if include_stale_checker:
            hashed_paths.append("scripts/check_stale_paths.py")
        content_hashes = {
            relative: hashlib.sha256((repository / relative).read_bytes()).hexdigest()
            for relative in hashed_paths
        }
        (repository / "SHED_VERSION.json").write_text(
            json.dumps(
                {
                    "shed_version": version,
                    "manifest_schema_version": 2,
                    "artifact_model_version": "test",
                    "content_hashes": content_hashes,
                    "release_tag": f"v{version}",
                    "release_commit": None,
                    "released_at": None,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
            newline="\n",
        )
        subprocess.run(["git", "add", "."], cwd=repository, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "Release content"], cwd=repository, check=True)
        content_commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repository,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
        ).stdout.strip()
        manifest = json.loads((repository / "SHED_VERSION.json").read_text(encoding="utf-8"))
        manifest["release_commit"] = content_commit
        manifest["released_at"] = "2026-07-30T00:00:00Z"
        (repository / "SHED_VERSION.json").write_text(
            json.dumps(manifest, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        subprocess.run(["git", "add", "SHED_VERSION.json"], cwd=repository, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "Release provenance"], cwd=repository, check=True)
        subprocess.run(
            ["git", "tag", "-a", f"v{version}", "-m", f"Tool Shed v{version}"],
            cwd=repository,
            check=True,
        )
        return repository

    def create_fake_codex_catalog(self, root: Path) -> Path:
        script = root / "fake-codex.py"
        script.write_text(
            """#!/usr/bin/env python3
import json
import sys

for raw in sys.stdin:
    message = json.loads(raw)
    if message.get("method") == "initialize":
        print(json.dumps({"id": message["id"], "result": {"userAgent": "fake-codex/1.0"}}), flush=True)
    elif message.get("method") == "model/list":
        print(json.dumps({"id": message["id"], "result": {"data": [
            {
                "id": "model-current",
                "model": "model-current",
                "displayName": "Current Model",
                "defaultReasoningEffort": "medium",
                "supportedReasoningEfforts": [
                    {"reasoningEffort": "low", "description": "fast"},
                    {"reasoningEffort": "medium", "description": "balanced"},
                    {"reasoningEffort": "future-depth", "description": "new label"}
                ],
                "isDefault": True,
                "inputModalities": ["text"]
            }
        ], "nextCursor": None}}), flush=True)
""",
            encoding="utf-8",
            newline="\n",
        )
        if os.name == "nt":
            launcher = root / "fake-codex.cmd"
            launcher.write_text(
                f'@echo off\r\n"{sys.executable}" "{script}" %*\r\n',
                encoding="utf-8",
                newline="",
            )
            return launcher

        script.chmod(0o755)
        return script

    def create_update_workspace(self, root: Path, version: str = "1.0.0") -> Path:
        workspace = root / "workspace with spaces"
        workspace.mkdir()
        self.init_repository(
            workspace,
            "/tool_shed/\n/tool_shed.backup-*.tar\n",
        )
        snapshot = workspace / "tool_shed"
        snapshot.mkdir()
        (snapshot / "SHED_VERSION.json").write_text(
            json.dumps({"shed_version": version}),
            encoding="utf-8",
        )
        (snapshot / "old-marker.txt").write_text("old snapshot\n", encoding="utf-8")
        work = workspace / "work"
        work.mkdir()
        (work / "operator-data.txt").write_text("preserve exactly\n", encoding="utf-8")
        subprocess.run(["git", "config", "user.name", "Tool Shed Tests"], cwd=workspace, check=True)
        subprocess.run(["git", "config", "user.email", "tests@example.invalid"], cwd=workspace, check=True)
        subprocess.run(["git", "add", ".gitignore", "work/operator-data.txt"], cwd=workspace, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "Workspace"], cwd=workspace, check=True)
        return workspace

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
        self.assertIn("ts:ask", guide)
        self.assertIn("## Common Use Cases", guide)
        self.assertIn("docs/operator-guide.md", skill)
        self.assertIn("q&a/ask.txt", skill)
        self.assertIn("scripts/read_ask_inbox.py", skill)
        self.assertTrue((ROOT / "scripts" / "read_ask_inbox.py").is_file())
        self.assertIn("artifacts for a help-only request.", skill)
        self.assertIn("[Tool Shed operator guide](docs/operator-guide.md)", readme)
        self.assertIn("ts: version", skill)
        self.assertIn("ts: check for updates", guide)
        self.assertIn("### Reasoning Preflight", skill)
        self.assertIn("Do not run a command", skill)
        self.assertIn("ts: refresh reasoning catalog", skill)
        self.assertIn("ts: reasoning status", guide)
        self.assertIn("### **Reasoning: <model> / <effort>**", skill)
        self.assertIn("ts: recommend reasoning <task>", skill)
        self.assertIn("Do not ask for repeated confirmation for reversible, in-scope steps", skill)
        self.assertIn("One request may authorize multiple named operations", guide)
        self.assertNotIn("abstract/currently advertised tier", skill)
        self.assertIn("### **Reasoning: GPT-5.6 Terra / High**", guide)
        self.assertTrue((ROOT / "scripts" / "reasoning_catalog.py").is_file())

    def test_ask_resolver_uses_canonical_content_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            canonical = workspace / "work" / "q&a" / "ask.txt"
            fallback = workspace / "q&a" / "ask.txt"
            canonical.parent.mkdir(parents=True)
            fallback.parent.mkdir(parents=True)
            canonical.write_text("# note\nRun the canonical request.\n", encoding="utf-8")
            fallback.write_text("# placeholder only\n", encoding="utf-8")

            result = run_script(
                "scripts/read_ask_inbox.py",
                "--workspace",
                str(workspace),
                "--json",
            )
            payload = json.loads(result.stdout)
            text_result = run_script(
                "scripts/read_ask_inbox.py",
                "--workspace",
                str(workspace),
            )

            self.assertEqual(payload["status"], "canonical")
            self.assertEqual(payload["selected_path"], "work/q&a/ask.txt")
            self.assertEqual(payload["content"], "Run the canonical request.")
            self.assertEqual(payload["canonical"]["path"], "work/q&a/ask.txt")
            self.assertEqual(payload["fallback"]["path"], "q&a/ask.txt")
            self.assertIn("Using canonical inbox work/q&a/ask.txt", text_result.stdout)
            self.assertNotIn("Warning:", text_result.stdout)

    def test_ask_resolver_uses_fallback_content_only_and_reports_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            canonical = workspace / "work" / "q&a" / "ask.txt"
            fallback = workspace / "q&a" / "ask.txt"
            canonical.parent.mkdir(parents=True)
            fallback.parent.mkdir(parents=True)
            canonical.write_text("# placeholder only\n", encoding="utf-8")
            fallback.write_text("Run the fallback request.\n", encoding="utf-8")

            json_result = run_script(
                "scripts/read_ask_inbox.py",
                "--workspace",
                str(workspace),
                "--json",
            )
            text_result = run_script(
                "scripts/read_ask_inbox.py",
                "--workspace",
                str(workspace),
            )
            payload = json.loads(json_result.stdout)

            self.assertEqual(payload["status"], "fallback")
            self.assertEqual(payload["selected_path"], "q&a/ask.txt")
            self.assertEqual(payload["content"], "Run the fallback request.")
            self.assertIn("noncanonical legacy location q&a/ask.txt", text_result.stdout)
            self.assertIn("canonical inbox is work/q&a/ask.txt", text_result.stdout)

    def test_ask_resolver_reports_both_files_empty(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            result = run_script(
                "scripts/read_ask_inbox.py",
                "--workspace",
                temp,
                "--json",
            )
            payload = json.loads(result.stdout)

            self.assertEqual(payload["status"], "empty")
            self.assertIsNone(payload["selected_path"])
            self.assertIsNone(payload["content"])

    def test_ask_resolver_treats_comment_only_files_as_empty(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            canonical = workspace / "work" / "q&a" / "ask.txt"
            fallback = workspace / "q&a" / "ask.txt"
            canonical.parent.mkdir(parents=True)
            fallback.parent.mkdir(parents=True)
            canonical.write_text("\n# canonical comment\n   # indented comment\n", encoding="utf-8")
            fallback.write_text("# fallback comment\n\n", encoding="utf-8")

            result = run_script(
                "scripts/read_ask_inbox.py",
                "--workspace",
                str(workspace),
                "--json",
            )

            self.assertEqual(json.loads(result.stdout)["status"], "empty")

    def test_ask_resolver_reports_conflict_without_merging(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            canonical = workspace / "work" / "q&a" / "ask.txt"
            fallback = workspace / "q&a" / "ask.txt"
            canonical.parent.mkdir(parents=True)
            fallback.parent.mkdir(parents=True)
            canonical.write_text("Canonical request.\n", encoding="utf-8")
            fallback.write_text("Fallback request.\n", encoding="utf-8")

            result = run_script(
                "scripts/read_ask_inbox.py",
                "--workspace",
                str(workspace),
                "--json",
            )
            payload = json.loads(result.stdout)

            self.assertEqual(payload["status"], "conflict")
            self.assertIsNone(payload["selected_path"])
            self.assertIsNone(payload["content"])
            self.assertTrue(payload["canonical"]["actionable"])
            self.assertTrue(payload["fallback"]["actionable"])
            text_result = run_script(
                "scripts/read_ask_inbox.py",
                "--workspace",
                str(workspace),
            )
            self.assertIn("both work/q&a/ask.txt and q&a/ask.txt", text_result.stdout)
            self.assertIn("not merged or modified", text_result.stdout)

    def test_unified_install_or_update_guide_uses_two_commit_release_provenance(self) -> None:
        guide = ROOT / "docs" / "install-or-update-snapshot.md"
        text = guide.read_text(encoding="utf-8")
        self.assertIn("If it does not exist, select NEW INSTALLATION.", text)
        self.assertIn("select EXISTING UPDATE", text)
        self.assertIn('content_commit="$(git rev-parse "${tag_commit}^")"', text)
        self.assertIn(
            'git diff --name-only "$content_commit" "$tag_commit" reports exactly '
            "SHED_VERSION.json",
            text,
        )
        self.assertIn("release_commit must not equal tag_commit", text)
        self.assertIn("scripts/update_snapshot.py --workspace .", text)
        self.assertIn("core.autocrlf=false", text)
        self.assertNotIn("expected newest published stable tag", text.lower())
        self.assertTrue((ROOT / "scripts" / "update-tool-shed.sh").is_file())
        self.assertTrue((ROOT / "scripts" / "update-tool-shed.ps1").is_file())
        self.assertFalse((ROOT / "docs" / "installing-new-snapshot.md").exists())
        self.assertFalse((ROOT / "docs" / "updating-existing-snapshot.md").exists())

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
            self.assertNotIn(b"\r\n", index_md.read_bytes())
            self.assertNotIn(b"\r\n", index_json.read_bytes())
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

    def test_check_stale_paths_uses_git_visible_markdown_set(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            self.init_repository(workspace, ".codex-tmp/\n.codex-work/\ntmp/\n")
            (workspace / "work" / "maps").mkdir(parents=True)
            (workspace / "work" / "tickets").mkdir(parents=True)
            canonical_target = workspace / "work" / "tickets" / "ticket-real.md"
            canonical_target.write_text("# Real\n", encoding="utf-8")
            tracked = workspace / "work" / "maps" / "tracked.md"
            tracked.write_text("See [real](work/tickets/ticket-real.md)\n", encoding="utf-8")
            subprocess.run(["git", "add", ".gitignore", "work"], cwd=workspace, check=True)

            untracked = workspace / "notes.md"
            untracked.write_text("See [real](work/tickets/ticket-real.md)\n", encoding="utf-8")
            for ignored_name in (".codex-tmp", ".codex-work", "tmp"):
                nested = workspace / ignored_name / "copy"
                subprocess.run(["git", "init", "-q", str(nested)], check=True)
                (nested / "work" / "maps").mkdir(parents=True)
                (nested / "work" / "tickets").mkdir(parents=True)
                (nested / "work" / "maps" / "nested.md").write_text(
                    "See [nested](work/tickets/nested.md)\n",
                    encoding="utf-8",
                )
                (nested / "work" / "tickets" / "nested.md").write_text("# Nested\n", encoding="utf-8")

            result = run_script("scripts/check_stale_paths.py", "--workspace", str(workspace))
            self.assertIn("No stale work paths found.", result.stdout)

            untracked.write_text("See [missing](work/tickets/missing.md)\n", encoding="utf-8")
            result = run_script("scripts/check_stale_paths.py", "--workspace", str(workspace), check=False)
            self.assertEqual(result.returncode, 1)
            self.assertIn("notes.md:1", result.stdout)
            self.assertNotIn("nested.md", result.stdout)

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

    def test_new_artifact_creates_deep_research_spike_and_indexes_it(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)

            run_script(
                "scripts/new_artifact.py",
                "deep-research",
                "Host Contract",
                "--workspace",
                str(workspace),
                "--shed",
                str(ROOT),
            )

            artifact = workspace / "work" / "spikes" / "spike-host-contract.md"
            text = artifact.read_text(encoding="utf-8")
            self.assertIn("# Deep-Research Spike: Host Contract", text)
            self.assertIn("Type: spike", text)
            self.assertIn("Research Depth: deep", text)
            self.assertNotIn("{{ title }}", text)
            self.assertNotIn("{{ date }}", text)
            payload = json.loads((workspace / "work" / "index.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["artifacts"][0]["path"], "work/spikes/spike-host-contract.md")
            self.assertEqual(payload["artifacts"][0]["type"], "spike")

    def test_new_artifact_ordinary_spike_remains_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)

            run_script(
                "scripts/new_artifact.py",
                "spike",
                "Quick Check",
                "--workspace",
                str(workspace),
                "--shed",
                str(ROOT),
            )

            text = (workspace / "work" / "spikes" / "spike-quick-check.md").read_text(encoding="utf-8")
            self.assertIn("# Spike: Quick Check", text)
            self.assertNotIn("Research Depth:", text)

    def test_completed_deep_research_uses_normal_spike_disposition_rules(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            spike = workspace / "work" / "spikes" / "spike-contract.md"
            spike.parent.mkdir(parents=True)
            spike.write_text(
                """# Deep-Research Spike: Contract

Status: complete
Type: spike
Research Depth: deep
Updated: 2026-08-01
Next Action: create implementation ticket
Parent: work/maps/map-demo.md
Disposition: planned
Produces:
""",
                encoding="utf-8",
            )

            result = run_script(
                "scripts/review_work_state.py", "--workspace", str(workspace), "--strict", check=False
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("MISSING_SPIKE_OUTPUT", result.stdout)

    def test_install_work_readme_mentions_completion_helper(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)

            run_script("scripts/install_into_workspace.py", str(workspace))

            readme = (workspace / "work" / "README.md").read_text(encoding="utf-8")
            self.assertIn("complete_workpackage.py", readme)
            self.assertTrue((workspace / "work" / "evidence").is_dir())
            self.assertTrue((workspace / "work" / "evidence" / "generated").is_dir())
            self.assertTrue((workspace / "work" / "q&a" / "ask.txt").is_file())

    def test_installer_preserves_gitignore_and_adds_generated_evidence_convention(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp) / "workspace with spaces"
            workspace.mkdir()
            original = "# owner rules\n/build output/\n"
            self.init_repository(workspace, original)

            first = run_script("scripts/install_into_workspace.py", str(workspace))
            second = run_script("scripts/install_into_workspace.py", str(workspace))

            gitignore = (workspace / ".gitignore").read_text(encoding="utf-8")
            self.assertTrue(gitignore.startswith(original))
            self.assertEqual(gitignore.count("/tool_shed/"), 1)
            self.assertEqual(gitignore.count("/tool_shed.backup-*.tar"), 1)
            self.assertEqual(gitignore.splitlines().count("/work/q&a/ask.txt"), 1)
            self.assertEqual(gitignore.splitlines().count("/q&a/ask.txt"), 1)
            self.assertEqual(gitignore.count("/work/evidence/generated/"), 1)
            self.assertIn("Workspace preflight", first.stdout)
            self.assertEqual(second.returncode, 0)
            guidance = (workspace / "AGENTS.md").read_text(encoding="utf-8")
            self.assertEqual(guidance.count("BEGIN TOOL SHED GENERATED EVIDENCE GUIDANCE"), 1)
            self.assertEqual(guidance.count("BEGIN TOOL SHED EVIDENCE RESPONSE GUIDANCE"), 1)
            self.assertEqual(guidance.count("BEGIN TOOL SHED CAMPAIGN GUIDANCE"), 1)
            self.assertEqual(guidance.count("BEGIN TOOL SHED Q&A GUIDANCE"), 1)
            self.assertIn("Campaign status: COMPLETE", guidance)
            self.assertIn("A progress summary, artifact update, phase boundary", guidance)
            self.assertIn("command success alone is not outcome success", guidance)
            self.assertIn("at most three credible ways the plan could fail", guidance)

    def test_installer_preserves_existing_ask_inbox(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            ask_path = workspace / "work" / "q&a" / "ask.txt"
            ask_path.parent.mkdir(parents=True)
            ask_path.write_text("Keep this question intact.\n", encoding="utf-8")

            result = run_script("scripts/install_into_workspace.py", str(workspace))
            second = run_script("scripts/install_into_workspace.py", str(workspace))

            self.assertEqual(ask_path.read_text(encoding="utf-8"), "Keep this question intact.\n")
            self.assertIn("Preserved existing Tool Shed Q&A inbox", result.stdout)
            self.assertIn("Preserved existing Tool Shed Q&A inbox", second.stdout)

    def test_installer_replaces_stale_evidence_response_guidance_idempotently(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            self.init_repository(workspace)
            agents = workspace / "AGENTS.md"
            agents.write_text(
                """# Owner guidance

<!-- BEGIN TOOL SHED EVIDENCE RESPONSE GUIDANCE -->
stale loop guidance
<!-- END TOOL SHED EVIDENCE RESPONSE GUIDANCE -->

# Owner footer
""",
                encoding="utf-8",
            )

            first = run_script("scripts/install_into_workspace.py", str(workspace))
            after_first = agents.read_text(encoding="utf-8")
            second = run_script("scripts/install_into_workspace.py", str(workspace))
            after_second = agents.read_text(encoding="utf-8")

            self.assertIn("Codex guidance: updated", first.stdout)
            self.assertNotIn("stale loop guidance", after_first)
            self.assertIn("command success alone is not outcome success", after_first)
            self.assertIn("# Owner guidance", after_first)
            self.assertIn("# Owner footer", after_first)
            self.assertEqual(after_first.count("BEGIN TOOL SHED EVIDENCE RESPONSE GUIDANCE"), 1)
            self.assertEqual(after_first.count("END TOOL SHED EVIDENCE RESPONSE GUIDANCE"), 1)
            self.assertEqual(after_second, after_first)
            self.assertNotIn("Codex guidance: updated", second.stdout)

    def test_installer_warns_for_fallback_inbox_and_preserves_both_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            canonical = workspace / "work" / "q&a" / "ask.txt"
            fallback = workspace / "q&a" / "ask.txt"
            fallback.parent.mkdir(parents=True)
            fallback_text = "Keep fallback content.\n"
            fallback.write_text(fallback_text, encoding="utf-8")

            result = run_script("scripts/install_into_workspace.py", str(workspace))

            self.assertIn("Q&A inbox warning:", result.stdout)
            self.assertIn(str(fallback.resolve()), result.stdout)
            self.assertIn(str(canonical.resolve()), result.stdout)
            self.assertIn("canonical inbox", result.stdout)
            self.assertTrue(canonical.is_file())
            self.assertFalse(any(
                line.strip() and not line.lstrip().startswith("#")
                for line in canonical.read_text(encoding="utf-8").splitlines()
            ))
            self.assertEqual(fallback.read_text(encoding="utf-8"), fallback_text)

    def test_snapshot_updater_is_cross_platform_and_preserves_work(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            release = self.create_test_release(root)
            workspace = self.create_update_workspace(root)
            git_config = root / "global.gitconfig"
            git_config.write_text("[core]\n\tautocrlf = true\n", encoding="utf-8")
            environment = dict(os.environ)
            environment["GIT_CONFIG_GLOBAL"] = str(git_config)

            result = run_script(
                str(ROOT / "scripts" / "update_snapshot.py"),
                "--workspace",
                str(workspace),
                "--repository",
                str(release),
                "--json",
                cwd=workspace,
                env=environment,
            )
            payload = json.loads(result.stdout)

            self.assertEqual(payload["state"], "installed")
            self.assertEqual(payload["selected_tag"], "v9.8.7")
            self.assertEqual(payload["installed_version"], "9.8.7")
            self.assertTrue(payload["work_preserved"])
            self.assertEqual(
                (workspace / "work" / "operator-data.txt").read_text(encoding="utf-8"),
                "preserve exactly\n",
            )
            self.assertFalse((workspace / "tool_shed" / ".git").exists())
            self.assertFalse((workspace / "tool_shed" / "work").exists())
            backups = list(workspace.glob("tool_shed.backup-*.tar"))
            self.assertEqual(len(backups), 1)
            with tarfile.open(backups[0], "r") as archive:
                names = {member.name.replace("\\", "/") for member in archive.getmembers()}
            self.assertIn("tool_shed/old-marker.txt", names)
            self.assertNotIn("work/operator-data.txt", names)

    def test_snapshot_updater_ignores_stale_links_in_ignored_scratch_copy(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            release = self.create_test_release(root, include_stale_checker=True)
            workspace = self.create_update_workspace(root)
            with (workspace / ".gitignore").open("a", encoding="utf-8") as handle:
                handle.write("/.codex-tmp/\n")
            nested = workspace / ".codex-tmp" / "copy"
            subprocess.run(["git", "init", "-q", str(nested)], check=True)
            (nested / "work" / "maps").mkdir(parents=True)
            (nested / "work" / "maps" / "ignored.md").write_text(
                "See [nested](work/tickets/nested.md)\n",
                encoding="utf-8",
            )

            result = run_script(
                str(ROOT / "scripts" / "update_snapshot.py"),
                "--workspace",
                str(workspace),
                "--repository",
                str(release),
                "--json",
                cwd=workspace,
            )
            payload = json.loads(result.stdout)

            self.assertEqual(payload["state"], "installed")
            self.assertNotIn("rollback", payload)
            self.assertIn("No stale work paths found.", payload["post_install"]["check_stale_paths.py"])

    def test_snapshot_updater_rolls_back_from_verified_archive(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            release = self.create_test_release(root)
            workspace = self.create_update_workspace(root)

            result = run_script(
                str(ROOT / "scripts" / "update_snapshot.py"),
                "--workspace",
                str(workspace),
                "--repository",
                str(release),
                "--inject-post-install-failure",
                "--json",
                cwd=workspace,
                check=False,
            )
            payload = json.loads(result.stdout)

            self.assertNotEqual(result.returncode, 0)
            self.assertTrue(payload["rollback"])
            self.assertTrue(payload["work_preserved"])
            self.assertEqual(
                (workspace / "tool_shed" / "old-marker.txt").read_text(encoding="utf-8"),
                "old snapshot\n",
            )
            self.assertEqual(len(list(workspace.glob("tool_shed.backup-*.tar"))), 1)

    def test_snapshot_updater_installs_into_new_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            release = self.create_test_release(root)
            workspace = root / "new workspace with spaces"
            workspace.mkdir()
            self.init_repository(workspace, "/tool_shed/\n/tool_shed.backup-*.tar\n")
            (workspace / "README.md").write_text("project\n", encoding="utf-8")
            subprocess.run(["git", "config", "user.name", "Tool Shed Tests"], cwd=workspace, check=True)
            subprocess.run(["git", "config", "user.email", "tests@example.invalid"], cwd=workspace, check=True)
            subprocess.run(["git", "add", "."], cwd=workspace, check=True)
            subprocess.run(["git", "commit", "-q", "-m", "Workspace"], cwd=workspace, check=True)

            result = run_script(
                str(ROOT / "scripts" / "update_snapshot.py"),
                "--workspace",
                str(workspace),
                "--repository",
                str(release),
                "--json",
                cwd=workspace,
            )
            payload = json.loads(result.stdout)

            self.assertEqual(payload["mode"], "new-installation")
            self.assertEqual(payload["installed_version"], "9.8.7")
            self.assertFalse(list(workspace.glob("tool_shed.backup-*.tar")))
            self.assertFalse((workspace / "tool_shed" / ".git").exists())
            self.assertFalse((workspace / "tool_shed" / "work").exists())

    def test_snapshot_updater_rejects_invalid_release_before_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            release = self.create_test_release(root)
            workspace = self.create_update_workspace(root)
            original = (workspace / "tool_shed" / "old-marker.txt").read_bytes()
            subprocess.run(
                ["git", "tag", "-a", "v9.8.8", "-m", "Invalid higher release"],
                cwd=release,
                check=True,
            )

            result = run_script(
                str(ROOT / "scripts" / "update_snapshot.py"),
                "--workspace",
                str(workspace),
                "--repository",
                str(release),
                "--json",
                cwd=workspace,
                check=False,
            )
            payload = json.loads(result.stdout)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("shed_version does not match", payload["error"])
            self.assertEqual((workspace / "tool_shed" / "old-marker.txt").read_bytes(), original)
            self.assertFalse(list(workspace.glob("tool_shed.backup-*.tar")))

    def test_snapshot_updater_rejects_release_validation_failure_before_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            release = self.create_test_release(root, validation_exit=1)
            workspace = self.create_update_workspace(root)

            result = run_script(
                str(ROOT / "scripts" / "update_snapshot.py"),
                "--workspace",
                str(workspace),
                "--repository",
                str(release),
                "--json",
                cwd=workspace,
                check=False,
            )
            payload = json.loads(result.stdout)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("validate_tool_shed.py", payload["error"])
            self.assertTrue((workspace / "tool_shed" / "old-marker.txt").is_file())
            self.assertFalse(list(workspace.glob("tool_shed.backup-*.tar")))

    def test_installer_preserves_actionable_content_in_both_inboxes_without_fallback_only_warning(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            canonical = workspace / "work" / "q&a" / "ask.txt"
            fallback = workspace / "q&a" / "ask.txt"
            canonical.parent.mkdir(parents=True)
            fallback.parent.mkdir(parents=True)
            canonical_text = "Keep canonical content.\n"
            fallback_text = "Keep legacy content.\n"
            canonical.write_text(canonical_text, encoding="utf-8")
            fallback.write_text(fallback_text, encoding="utf-8")

            result = run_script("scripts/install_into_workspace.py", str(workspace))

            self.assertNotIn("Q&A inbox warning:", result.stdout)
            self.assertEqual(canonical.read_text(encoding="utf-8"), canonical_text)
            self.assertEqual(fallback.read_text(encoding="utf-8"), fallback_text)

    def test_installer_replaces_stale_q_and_a_guidance_idempotently(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            self.init_repository(workspace)
            agents = workspace / "AGENTS.md"
            agents.write_text(
                """# Owner guidance

<!-- BEGIN TOOL SHED Q&A GUIDANCE -->
stale canonical-only guidance
<!-- END TOOL SHED Q&A GUIDANCE -->

# Owner footer
""",
                encoding="utf-8",
            )

            first = run_script("scripts/install_into_workspace.py", str(workspace))
            after_first = agents.read_text(encoding="utf-8")
            second = run_script("scripts/install_into_workspace.py", str(workspace))
            after_second = agents.read_text(encoding="utf-8")

            self.assertIn("Codex guidance: updated", first.stdout)
            self.assertNotIn("stale canonical-only guidance", after_first)
            self.assertIn("work/q&a/ask.txt", after_first)
            self.assertIn("`q&a/ask.txt` as a legacy or misplaced fallback", after_first)
            self.assertIn("# Owner guidance", after_first)
            self.assertIn("# Owner footer", after_first)
            self.assertEqual(after_first.count("BEGIN TOOL SHED Q&A GUIDANCE"), 1)
            self.assertEqual(after_first.count("END TOOL SHED Q&A GUIDANCE"), 1)
            self.assertEqual(after_second, after_first)
            self.assertNotIn("Codex guidance: updated", second.stdout)

    def test_installer_warns_before_existing_generated_outputs_become_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            self.init_repository(workspace)
            generated = workspace / "work" / "evidence" / "generated"
            generated.mkdir(parents=True)
            evidence = generated / "existing capture.bin"
            evidence.write_bytes(b"preserve-me")

            result = run_script("scripts/install_into_workspace.py", str(workspace))

            self.assertIn("Adoption warning:", result.stdout)
            self.assertIn("1 existing file(s)", result.stdout)
            self.assertEqual(evidence.read_bytes(), b"preserve-me")

    def test_preflight_ignores_raw_evidence_and_keeps_summaries_visible(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp) / "Windows Path With Spaces"
            workspace.mkdir()
            self.init_repository(workspace)
            run_script("scripts/install_into_workspace.py", str(workspace))
            generated = workspace / "work" / "evidence" / "generated"
            for number in range(60):
                (generated / f"device C drive capture {number}.bin").write_bytes(b"\0" * 128)
            summary = workspace / "work" / "evidence" / "campaign summary.md"
            summary.write_text("# Passed\n", encoding="utf-8")
            manifest = workspace / "work" / "evidence" / "campaign manifest.json"
            manifest.write_text('{"outcome":"passed"}\n', encoding="utf-8")

            result = run_script(
                "scripts/workspace_preflight.py",
                "--workspace",
                str(workspace),
                "--json",
                "--strict",
            )
            payload = json.loads(result.stdout)

            self.assertEqual(result.returncode, 0)
            self.assertEqual(payload["findings"], [])
            self.assertLess(payload["metrics"]["untracked_count"], 50)
            status = subprocess.run(
                ["git", "status", "--short", "--untracked-files=all"],
                cwd=workspace,
                check=True,
                text=True,
                stdout=subprocess.PIPE,
            ).stdout
            self.assertIn("campaign summary.md", status)
            self.assertIn("campaign manifest.json", status)
            self.assertNotIn("device C drive capture", status)

    def test_preflight_warns_for_versioned_binary_large_diff_and_visible_backup(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            self.init_repository(workspace)
            (workspace / "work" / "evidence").mkdir(parents=True)
            binary = workspace / "work" / "evidence" / "legacy capture.bin"
            binary.write_bytes(b"\0binary")
            tracked = workspace / "source.txt"
            tracked.write_text("base\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=workspace, check=True)
            subprocess.run(
                ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "base"],
                cwd=workspace,
                check=True,
            )
            tracked.write_text("x" * 256, encoding="utf-8")
            (workspace / "tool_shed.backup-2026-07-25.tar").write_bytes(b"backup")

            result = run_script(
                "scripts/workspace_preflight.py",
                "--workspace",
                str(workspace),
                "--diff-bytes",
                "64",
                "--json",
                "--strict",
                check=False,
            )
            codes = {finding["code"] for finding in json.loads(result.stdout)["findings"]}

            self.assertEqual(result.returncode, 1)
            self.assertIn("BINARY_IN_VERSIONED_WORK", codes)
            self.assertIn("DIFF_BYTES", codes)
            self.assertIn("VISIBLE_TOOL_SHED_BACKUP", codes)

    def test_preflight_profiles_workspace_and_explains_adaptive_policy(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            self.init_repository(workspace)
            (workspace / "work" / "evidence").mkdir(parents=True)
            (workspace / "work" / "evidence" / "summary.md").write_text("# durable\n", encoding="utf-8")
            (workspace / ".tool-shed-policy.json").write_text(
                json.dumps({
                    "schema_version": 1,
                    "evidence_policy": {
                        "reason": "Data workspace produces many small result shards.",
                        "generated_path": "artifacts/generated",
                        "evidence_paths": ["artifacts/results"],
                        "thresholds": {"untracked_count": 3},
                    },
                }),
                encoding="utf-8",
            )
            subprocess.run(["git", "add", "."], cwd=workspace, check=True)
            subprocess.run(
                ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com",
                 "commit", "-qm", "base"],
                cwd=workspace,
                check=True,
            )
            for number in range(4):
                (workspace / f"result-{number}.json").write_text("{}\n", encoding="utf-8")

            result = run_script(
                "scripts/workspace_preflight.py",
                "--workspace",
                str(workspace),
                "--json",
                "--strict",
                check=False,
            )
            payload = json.loads(result.stdout)
            count_finding = next(
                finding for finding in payload["findings"]
                if finding["code"] == "UNTRACKED_COUNT"
            )

            self.assertEqual(result.returncode, 1)
            self.assertEqual(payload["schema_version"], 2)
            self.assertEqual(payload["profile"]["generated_path"], "artifacts/generated")
            self.assertIn("artifacts/results", payload["profile"]["evidence_paths"])
            self.assertEqual(
                payload["profile"]["risk_budget"]["untracked_count"]["source"],
                "workspace-policy",
            )
            self.assertEqual(count_finding["source"], "workspace-policy")
            self.assertEqual(count_finding["mitigation"], "prepare")

    def test_preflight_rejects_unreasoned_or_unsafe_evidence_policy(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            self.init_repository(workspace)
            (workspace / ".tool-shed-policy.json").write_text(
                json.dumps({
                    "schema_version": 1,
                    "evidence_policy": {
                        "generated_path": "../outside",
                        "thresholds": {"untracked_count": 999999},
                    },
                }),
                encoding="utf-8",
            )

            result = run_script(
                "scripts/workspace_preflight.py",
                "--workspace",
                str(workspace),
                "--json",
                "--strict",
                check=False,
            )
            payload = json.loads(result.stdout)
            messages = "\n".join(finding["message"] for finding in payload["findings"])

            self.assertEqual(result.returncode, 1)
            self.assertIn("requires a non-empty reason", messages)
            self.assertIn("repository-relative path", messages)
            self.assertLessEqual(
                payload["profile"]["risk_budget"]["untracked_count"]["value"],
                payload["profile"]["risk_budget"]["untracked_count"]["hard_limit"],
            )

    def test_generated_evidence_migration_requires_explicit_approval_and_preserves_dirty_work(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace with spaces"
            workspace.mkdir()
            self.init_repository(workspace, "/work/evidence/generated/\n")
            evidence = workspace / "work" / "evidence"
            evidence.mkdir(parents=True)
            raw = evidence / "Device Capture.SLG"
            raw.write_bytes(b"\0raw-device-capture")
            summary = evidence / "summary.md"
            summary.write_text("# keep\n", encoding="utf-8")
            source = workspace / "firmware.c"
            source.write_text("stable\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=workspace, check=True)
            subprocess.run(
                ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com",
                 "commit", "-qm", "base"],
                cwd=workspace,
                check=True,
            )
            source.write_text("dirty owner work\n", encoding="utf-8")
            output = root / "migration-output"

            prepared = run_script(
                "scripts/migrate_generated_evidence.py",
                "prepare",
                "--workspace",
                str(workspace),
                "--output",
                str(output),
            )
            manifest_path = Path(prepared.stdout.strip())
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            repeat_output = root / "migration-output-repeat"
            repeated = run_script(
                "scripts/migrate_generated_evidence.py",
                "prepare",
                "--workspace",
                str(workspace),
                "--output",
                str(repeat_output),
            )
            repeated_payload = json.loads(Path(repeated.stdout.strip()).read_text(encoding="utf-8"))
            raw_item = next(item for item in payload["candidates"] if item["path"].endswith(".SLG"))
            summary_item = next(item for item in payload["candidates"] if item["path"].endswith(".md"))

            self.assertEqual(raw_item["classification"], "migrate")
            self.assertEqual(summary_item["classification"], "keep")
            self.assertTrue((output / "evidence-backup.tar").is_file())
            self.assertEqual(payload["candidates"], repeated_payload["candidates"])
            self.assertEqual(payload["archive"]["sha256"], repeated_payload["archive"]["sha256"])
            refused = run_script(
                "scripts/migrate_generated_evidence.py",
                "apply",
                "--workspace",
                str(workspace),
                "--manifest",
                str(manifest_path),
                check=False,
            )
            self.assertNotEqual(refused.returncode, 0)
            self.assertIn("approved must be true", refused.stderr)

            payload["approved"] = True
            raw_item["approved"] = True
            manifest_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            applied = run_script(
                "scripts/migrate_generated_evidence.py",
                "apply",
                "--workspace",
                str(workspace),
                "--manifest",
                str(manifest_path),
            )

            self.assertIn("Moved 1 approved file", applied.stdout)
            self.assertFalse(raw.exists())
            self.assertTrue((evidence / "generated" / "Device Capture.SLG").exists())
            self.assertEqual(summary.read_text(encoding="utf-8"), "# keep\n")
            self.assertEqual(source.read_text(encoding="utf-8"), "dirty owner work\n")
            with tarfile.open(output / "evidence-backup.tar", "r") as archive:
                restored = archive.extractfile("work/evidence/Device Capture.SLG")
                self.assertIsNotNone(restored)
                self.assertEqual(restored.read(), b"\0raw-device-capture")

    def test_profile_matrix_handles_non_firmware_workspace_shapes(self) -> None:
        profiles = {
            "application": ("test-results/session.trace", b"request trace\n"),
            "data": ("artifacts/results/model.bin", b"\0model"),
            "media": ("validation/captures/walkthrough.mp4", b"\0video"),
            "documentation": ("work/evidence/review.md", b"# reviewed\n"),
        }
        for name, (relative, content) in profiles.items():
            with self.subTest(profile=name), tempfile.TemporaryDirectory() as temp:
                workspace = Path(temp)
                self.init_repository(workspace)
                evidence_root = str(Path(relative).parent)
                policy = {
                    "schema_version": 1,
                    "evidence_policy": {
                        "reason": f"{name} workspace evidence convention",
                        "evidence_paths": [evidence_root],
                        "generated_path": f"{evidence_root}/generated",
                    },
                }
                (workspace / ".tool-shed-policy.json").write_text(
                    json.dumps(policy),
                    encoding="utf-8",
                )
                path = workspace / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
                subprocess.run(["git", "add", "."], cwd=workspace, check=True)
                subprocess.run(
                    ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com",
                     "commit", "-qm", "base"],
                    cwd=workspace,
                    check=True,
                )

                result = run_script(
                    "scripts/workspace_preflight.py",
                    "--workspace",
                    str(workspace),
                    "--json",
                )
                payload = json.loads(result.stdout)

                self.assertEqual(payload["profile"]["evidence"]["tracked_count"], 1)
                self.assertIn(
                    evidence_root.replace("\\", "/"),
                    payload["profile"]["evidence_paths"],
                )
                codes = {finding["code"] for finding in payload["findings"]}
                if name == "documentation":
                    self.assertNotIn("BINARY_IN_VERSIONED_WORK", codes)
                elif relative.startswith("work/"):
                    self.assertIn("BINARY_IN_VERSIONED_WORK", codes)

    def test_firmware_incident_path_counts_remain_a_compact_regression_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            self.init_repository(workspace)
            evidence = workspace / "work" / "evidence"
            evidence.mkdir(parents=True)
            for number in range(2065):
                suffix = ".SLG" if number < 1488 else ".bin"
                (evidence / f"tracked-{number:04d}{suffix}").write_bytes(b"\0")
            subprocess.run(["git", "add", "."], cwd=workspace, check=True)
            subprocess.run(
                ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com",
                 "commit", "-qm", "incident fixture"],
                cwd=workspace,
                check=True,
            )
            for number in range(124):
                (evidence / f"campaign-{number:03d}.log").write_text("raw\n", encoding="utf-8")

            result = run_script(
                "scripts/workspace_preflight.py",
                "--workspace",
                str(workspace),
                "--json",
                "--strict",
                check=False,
            )
            payload = json.loads(result.stdout)
            codes = {finding["code"] for finding in payload["findings"]}

            self.assertEqual(result.returncode, 1)
            self.assertEqual(payload["metrics"]["tracked_evidence_count"], 2065)
            self.assertEqual(payload["metrics"]["untracked_evidence_count"], 124)
            self.assertIn("UNTRACKED_COUNT", codes)
            self.assertIn("BINARY_IN_VERSIONED_WORK", codes)

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

    def test_reasoning_catalog_refresh_uses_codex_model_list_and_preserves_new_labels(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fake_codex = self.create_fake_codex_catalog(root)
            cache = root / "catalog.json"

            self.assertEqual(fake_codex.suffix, ".cmd" if os.name == "nt" else ".py")

            result = run_script(
                "scripts/reasoning_catalog.py",
                "refresh",
                "--codex",
                str(fake_codex),
                "--cache",
                str(cache),
            )

            status = json.loads(result.stdout)
            payload = json.loads(cache.read_text(encoding="utf-8"))
            self.assertTrue(status["fresh"])
            self.assertEqual(status["source"], "codex-app-server:model/list")
            self.assertEqual(status["model_count"], 1)
            efforts = payload["models"][0]["supported_reasoning_efforts"]
            self.assertEqual([item["id"] for item in efforts], ["low", "medium", "future-depth"])

    def test_reasoning_catalog_status_is_local_and_reports_stale(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            cache = Path(temp) / "catalog.json"
            cache.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "source": "fixture",
                        "source_user_agent": "fixture/1",
                        "retrieved_at": "2026-01-01T00:00:00Z",
                        "expires_at": "2026-01-02T00:00:00Z",
                        "models": [],
                    }
                ),
                encoding="utf-8",
            )

            result = run_script("scripts/reasoning_catalog.py", "status", "--cache", str(cache))
            status = json.loads(result.stdout)
            self.assertFalse(status["fresh"])
            self.assertEqual(status["source"], "fixture")

    def test_reasoning_catalog_failed_refresh_preserves_verified_cache(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            cache = Path(temp) / "catalog.json"
            original = b'{"schema_version":1,"models":[],"expires_at":"2099-01-01T00:00:00Z"}\n'
            cache.write_bytes(original)

            result = run_script(
                "scripts/reasoning_catalog.py",
                "refresh",
                "--codex",
                str(Path(temp) / "missing-codex"),
                "--cache",
                str(cache),
                check=False,
            )

            self.assertEqual(result.returncode, 1)
            self.assertEqual(cache.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
