from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]


def skill_tree_digest(files: dict[str, bytes]) -> str:
    fingerprint = {
        relative: hashlib.sha256(content).hexdigest()
        for relative, content in files.items()
    }
    digest = hashlib.sha256()
    for relative, file_digest in sorted(fingerprint.items()):
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(file_digest.encode("ascii"))
        digest.update(b"\0")
    return digest.hexdigest()


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
    def create_symlink_or_skip(
        self,
        link: Path,
        target: Path,
        *,
        target_is_directory: bool = False,
    ) -> None:
        if not hasattr(os, "symlink"):
            self.skipTest("symlinks are unavailable")
        try:
            link.symlink_to(target, target_is_directory=target_is_directory)
        except OSError as error:
            if getattr(error, "winerror", None) == 1314:
                self.skipTest(f"Windows symlink privilege is unavailable: {error}")
            raise

    def init_repository(self, root: Path, gitignore: str = "") -> None:
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        (root / ".gitignore").write_text(gitignore, encoding="utf-8")

    def create_test_release(
        self,
        root: Path,
        version: str = "9.8.7",
        *,
        validation_exit: int = 0,
        validation_delay: float = 0,
        include_stale_checker: bool = False,
        include_provider_adapter: bool = False,
        minimum_updater_protocol: int = 2,
        known_skill_releases: dict[str, dict[str, bytes]] | None = None,
        updater_mutation_paths: list[dict[str, str]] | None = None,
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
        if include_provider_adapter:
            for name in (
                "codex_skill_sync.py",
                "campaign_queue.py",
                "check_stale_paths.py",
                "check_work_tree.py",
                "install_into_workspace.py",
                "provider_adapters.py",
                "reconcile_campaign_queue.py",
                "repository_policy.py",
                "review_work_state.py",
                "update_work_index.py",
                "work_tree.py",
                "workspace_preflight.py",
            ):
                shutil.copyfile(ROOT / "scripts" / name, repository / "scripts" / name)
            shutil.copytree(ROOT / "adapters", repository / "adapters")
            shutil.copytree(ROOT / "skills", repository / "skills")
            (repository / "adapters" / "codex-skill-releases.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "releases": {
                            version: skill_tree_digest(files)
                            for version, files in (known_skill_releases or {}).items()
                        },
                    },
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
                newline="\n",
            )
        (repository / "scripts" / "validate_tool_shed.py").write_text(
            f"import time\ntime.sleep({validation_delay!r})\nraise SystemExit({validation_exit})\n",
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
        if include_provider_adapter:
            hashed_paths.extend(
                path.relative_to(repository).as_posix()
                for directory in (repository / "adapters", repository / "skills")
                for path in directory.rglob("*")
                if path.is_file()
            )
            hashed_paths.extend(
                f"scripts/{name}"
                for name in (
                    "codex_skill_sync.py",
                    "campaign_queue.py",
                    "check_stale_paths.py",
                    "check_work_tree.py",
                    "install_into_workspace.py",
                    "provider_adapters.py",
                    "reconcile_campaign_queue.py",
                    "repository_policy.py",
                    "review_work_state.py",
                    "update_work_index.py",
                    "work_tree.py",
                    "workspace_preflight.py",
                )
            )
        content_hashes = {
            relative: hashlib.sha256((repository / relative).read_bytes()).hexdigest()
            for relative in hashed_paths
        }
        (repository / "SHED_VERSION.json").write_text(
            json.dumps(
                {
                    "shed_version": version,
                    "manifest_schema_version": 2,
                    "minimum_updater_protocol": minimum_updater_protocol,
                    "artifact_model_version": "test",
                    "content_hashes": content_hashes,
                    "release_tag": f"v{version}",
                    "release_commit": None,
                    "released_at": None,
                    "updater_mutation_paths": updater_mutation_paths,
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

    def add_historical_skill_release(
        self,
        repository: Path,
        version: str,
        files: dict[str, bytes],
    ) -> None:
        current_branch = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=repository,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
        ).stdout.strip()
        subprocess.run(
            ["git", "switch", "-q", "-c", f"historical-{version}"],
            cwd=repository,
            check=True,
        )
        skill = repository / "skills" / "tool-shed"
        shutil.rmtree(skill)
        skill.mkdir(parents=True)
        for relative, content in files.items():
            path = skill / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        manifest_path = repository / "SHED_VERSION.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        hashes = {
            path: digest
            for path, digest in manifest["content_hashes"].items()
            if not path.startswith("skills/tool-shed/")
        }
        hashes.update(
            {
                f"skills/tool-shed/{relative}": hashlib.sha256(content).hexdigest()
                for relative, content in files.items()
            }
        )
        manifest.update(
            {
                "shed_version": version,
                "release_tag": f"v{version}",
                "content_hashes": hashes,
            }
        )
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=repository, check=True)
        subprocess.run(
            ["git", "commit", "-q", "-m", f"Historical skill {version}"],
            cwd=repository,
            check=True,
        )
        subprocess.run(
            ["git", "tag", "-a", f"v{version}", "-m", f"Historical {version}"],
            cwd=repository,
            check=True,
        )
        subprocess.run(["git", "switch", "-q", current_branch], cwd=repository, check=True)

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

    def test_manifest_writer_rejects_mismatched_tag_without_mutation(self) -> None:
        manifest_path = ROOT / "SHED_VERSION.json"
        catalog_path = ROOT / "adapters" / "codex-skill-releases.json"
        manifest_before = manifest_path.read_bytes()
        catalog_before = catalog_path.read_bytes()
        current_version = json.loads(manifest_before)["shed_version"]
        major, minor, patch = (int(part) for part in current_version.split("."))

        result = run_script(
            "scripts/update_shed_manifest.py",
            "--write",
            "--version",
            f"{major}.{minor}.{patch + 1}",
            "--release-tag",
            "v9.9.9",
            check=False,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--release-tag must equal v<version>", result.stderr)
        self.assertEqual(manifest_path.read_bytes(), manifest_before)
        self.assertEqual(catalog_path.read_bytes(), catalog_before)

    def test_manifest_writer_cleans_first_temp_when_second_stage_fails(self) -> None:
        spec = importlib.util.spec_from_file_location(
            "update_shed_manifest_failure_test",
            ROOT / "scripts" / "update_shed_manifest.py",
        )
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            catalog_path = root / "adapters" / "codex-skill-releases.json"
            catalog_path.parent.mkdir()
            manifest_path = root / "SHED_VERSION.json"
            catalog_before = b"original catalog\n"
            manifest_before = b"original manifest\n"
            catalog_path.write_bytes(catalog_before)
            manifest_path.write_bytes(manifest_before)
            module.CODEX_SKILL_CATALOG = catalog_path
            module.MANIFEST = manifest_path
            real_stage_bytes = module.stage_bytes
            stage_calls = 0

            def fail_second_stage(path: Path, payload: bytes) -> Path:
                nonlocal stage_calls
                stage_calls += 1
                if stage_calls == 2:
                    raise OSError("injected second-stage failure")
                return real_stage_bytes(path, payload)

            module.stage_bytes = fail_second_stage

            with self.assertRaisesRegex(OSError, "injected second-stage failure"):
                module.write_release_metadata(
                    catalog=b"replacement catalog\n",
                    manifest=b"replacement manifest\n",
                )

            self.assertEqual(catalog_path.read_bytes(), catalog_before)
            self.assertEqual(manifest_path.read_bytes(), manifest_before)
            self.assertEqual(list(root.rglob("*.tmp")), [])

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
        skill_catalog = json.loads(
            (ROOT / "adapters" / "codex-skill-releases.json").read_text(encoding="utf-8")
        )

        self.assertEqual(manifest["manifest_schema_version"], 2)
        self.assertEqual(manifest["minimum_updater_protocol"], 3)
        self.assertEqual(manifest["release_tag"], f"v{manifest['shed_version']}")
        self.assertIn("release_commit", manifest)
        self.assertIn("released_at", manifest)
        self.assertEqual(skill_catalog["schema_version"], 1)
        self.assertIn("v0.10.3", skill_catalog["releases"])
        self.assertNotIn(manifest["release_tag"], skill_catalog["releases"])

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

    def test_strict_snapshot_check_rejects_forbidden_work_and_git(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            shed = root / "tool_shed"
            shed.mkdir()
            manifest = {
                "shed_version": "1.0.0",
                "manifest_schema_version": 2,
                "minimum_updater_protocol": 2,
                "artifact_model_version": "test",
                "content_hashes": {},
                "release_tag": "v1.0.0",
                "release_commit": None,
                "released_at": None,
            }
            (shed / "SHED_VERSION.json").write_text(json.dumps(manifest), encoding="utf-8")
            (shed / "work").mkdir()
            (shed / ".git").write_text("embedded metadata\n", encoding="utf-8")

            result = run_script(
                "scripts/check_shed_version.py",
                "--shed",
                str(shed),
                "--local-only",
                "--strict",
                "--verification-only",
                "--snapshot",
                "--json",
                check=False,
            )
            payload = json.loads(result.stdout)

            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(payload["state"], "modified")
            self.assertEqual(payload["forbidden"], [".git", "work"])

    def test_strict_snapshot_check_rejects_python_bytecode(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            shed = Path(temp) / "tool_shed"
            cache = shed / "scripts" / "__pycache__"
            cache.mkdir(parents=True)
            bytecode = cache / "helper.cpython-311.pyc"
            optimized = shed / "scripts" / "legacy.pyo"
            bytecode.write_bytes(b"bytecode")
            optimized.write_bytes(b"optimized")
            manifest = {
                "shed_version": "1.0.0",
                "manifest_schema_version": 2,
                "minimum_updater_protocol": 2,
                "artifact_model_version": "test",
                "content_hashes": {},
                "release_tag": "v1.0.0",
                "release_commit": None,
                "released_at": None,
            }
            (shed / "SHED_VERSION.json").write_text(json.dumps(manifest), encoding="utf-8")

            result = run_script(
                "scripts/check_shed_version.py",
                "--shed",
                str(shed),
                "--local-only",
                "--strict",
                "--verification-only",
                "--snapshot",
                "--json",
                check=False,
            )
            payload = json.loads(result.stdout)

            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(payload["state"], "modified")
            self.assertEqual(
                payload["forbidden"],
                [
                    "scripts/__pycache__",
                    "scripts/__pycache__/helper.cpython-311.pyc",
                    "scripts/legacy.pyo",
                ],
            )

    def test_disconnected_snapshot_validator_is_nonmutating(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            snapshot = root / "tool_shed"

            def ignore(directory: str, names: list[str]) -> set[str]:
                ignored = {name for name in names if name in {".git", "work", "tests", "__pycache__"}}
                ignored.update(name for name in names if name.endswith((".pyc", ".pyo")))
                return ignored

            shutil.copytree(ROOT, snapshot, ignore=ignore)
            (snapshot / "tests").mkdir()
            (snapshot / "tests" / "test_snapshot_smoke.py").write_text(
                "import unittest\n\nclass SnapshotSmoke(unittest.TestCase):\n"
                "    def test_snapshot_loads(self):\n        self.assertTrue(True)\n",
                encoding="utf-8",
            )
            before = {
                path.relative_to(snapshot).as_posix(): path.read_bytes()
                for path in snapshot.rglob("*")
                if path.is_file()
            }

            result = run_script(
                str(snapshot / "scripts" / "validate_tool_shed.py"),
                cwd=snapshot,
                check=False,
            )
            after = {
                path.relative_to(snapshot).as_posix(): path.read_bytes()
                for path in snapshot.rglob("*")
                if path.is_file()
            }

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("Skipped for disconnected snapshot", result.stdout)
            self.assertEqual(after, before)
            self.assertFalse((snapshot / "work").exists())

    def test_real_v0_10_3_updater_refuses_protocol_two_release_before_mutation(self) -> None:
        legacy = subprocess.run(
            ["git", "show", "v0.10.3:scripts/update_snapshot.py"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        legacy_manifest = subprocess.run(
            ["git", "show", "v0.10.3:SHED_VERSION.json"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if legacy.returncode or legacy_manifest.returncode:
            self.skipTest("canonical v0.10.3 Git fixture is unavailable")
        expected_hash = json.loads(legacy_manifest.stdout)["content_hashes"][
            "scripts/update_snapshot.py"
        ]
        self.assertEqual(hashlib.sha256(legacy.stdout.encode("utf-8")).hexdigest(), expected_hash)

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            updater = root / "update_snapshot_v0_10_3.py"
            updater.write_text(legacy.stdout, encoding="utf-8", newline="\n")
            release = self.create_test_release(root, version="9.9.0")
            workspace = self.create_update_workspace(root, version="9.8.0")

            result = run_script(
                str(updater),
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
            self.assertEqual(payload["state"], "failed")
            self.assertIn("requires updater protocol 2", payload["error"])
            self.assertIn("current released Tool Shed checkout", payload["error"])
            self.assertTrue((workspace / "tool_shed" / "old-marker.txt").is_file())
            self.assertFalse(list(workspace.glob("tool_shed.backup-*.tar")))

    def test_current_updater_refuses_future_protocol_before_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            release = self.create_test_release(
                root,
                version="9.9.0",
                minimum_updater_protocol=4,
            )
            workspace = self.create_update_workspace(root, version="9.8.0")

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
            self.assertIn("requires updater protocol 4", payload["error"])
            self.assertIn("supports protocol 3", payload["error"])
            self.assertTrue((workspace / "tool_shed" / "old-marker.txt").is_file())
            self.assertFalse(list(workspace.glob("tool_shed.backup-*.tar")))

    def test_operator_help_is_packaged_and_routed(self) -> None:
        guide = (ROOT / "docs" / "operator-guide.md").read_text(encoding="utf-8")
        commands = (ROOT / "docs" / "commands.md").read_text(encoding="utf-8")
        skill = (ROOT / "skills" / "tool-shed" / "SKILL.md").read_text(encoding="utf-8")
        skill_bundle = skill + "\n" + "\n".join(
            path.read_text(encoding="utf-8")
            for path in sorted((ROOT / "skills" / "tool-shed" / "references").glob("*.md"))
        )
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("ts: help", guide)
        self.assertIn("ts: commands", guide)
        self.assertIn("ts: help all", guide)
        self.assertIn("ts:ask", guide)
        self.assertIn("## Common Use Cases", guide)
        self.assertIn("docs/operator-guide.md", skill_bundle)
        self.assertIn("docs/commands.md", skill_bundle)
        self.assertIn("ts: commands", commands)
        self.assertIn("ts: build focus areas", commands)
        self.assertIn("ts:work1", commands)
        self.assertIn("ts:work5", commands)
        self.assertIn("ts: status", commands)
        self.assertIn("ts: unblock", commands)
        self.assertIn("ts: unblock", guide)
        self.assertIn("ts: unblock", skill_bundle)
        self.assertIn("ts: reconcile campaigns", commands)
        self.assertIn("ts: reconcile campaigns", guide)
        self.assertIn("reconcile_campaign_queue.py", skill_bundle)
        self.assertIn("`camp`", commands)
        self.assertIn("`que N`", commands)
        self.assertIn("`que N`", guide)
        self.assertIn("`que N`", skill_bundle)
        self.assertIn("ts: version", commands)
        self.assertIn("ts: fulltsupgrade", commands)
        self.assertIn("ts: fulltsupgrade", guide)
        self.assertIn("ts: fulltsupgrade", skill_bundle)
        self.assertIn("ts: fulltsupgrade", readme)
        self.assertIn("ts:ask", commands)
        self.assertIn("01-q&a/ask.txt", skill_bundle)
        self.assertIn("scripts/read_ask_inbox.py", skill_bundle)
        self.assertTrue((ROOT / "scripts" / "read_ask_inbox.py").is_file())
        self.assertIn("artifacts for a help-only request.", skill_bundle)
        self.assertIn("[Tool Shed operator guide](docs/operator-guide.md)", readme)
        self.assertIn("[AI command reference](docs/commands.md)", readme)
        self.assertIn("ts: version", skill_bundle)
        self.assertIn("ts: check for updates", guide)
        self.assertIn("## Reasoning Preflight", skill)
        self.assertIn("Do not run a command", skill)
        self.assertIn("ts: refresh reasoning catalog", skill_bundle)
        self.assertIn("ts: reasoning status", guide)
        self.assertIn("### **Reasoning: <model> / <effort>**", skill)
        self.assertIn("ts: recommend reasoning <task>", skill_bundle)
        self.assertIn("Do not ask for repeated confirmation for reversible, in-scope steps", skill_bundle)
        self.assertIn("One request may authorize multiple named operations", guide)
        self.assertIn("ts:work1", skill_bundle)
        self.assertIn("ts:work5", skill_bundle)
        self.assertIn("work/tool-shed.yaml", guide)
        self.assertIn("work_model: combined", readme)
        self.assertIn("In `split` mode", guide)
        self.assertIn("`ts:check", skill_bundle)
        self.assertIn("Treat `ts: build focus areas` as a two-stage", skill_bundle)
        self.assertIn("<spot|focused|full|release>", skill_bundle)
        self.assertNotIn("abstract/currently advertised tier", skill)
        self.assertIn("### **Reasoning: <model> / <effort>**", guide)
        self.assertNotIn("GPT-5.6 Terra", guide)
        self.assertTrue((ROOT / "scripts" / "reasoning_catalog.py").is_file())

    def test_fulltsupgrade_is_end_to_end_scoped_and_installed(self) -> None:
        skill = (ROOT / "skills" / "tool-shed" / "SKILL.md").read_text(encoding="utf-8")
        maintenance = (
            ROOT / "skills" / "tool-shed" / "references" / "maintenance-routes.md"
        ).read_text(encoding="utf-8")
        commands = (ROOT / "docs" / "commands.md").read_text(encoding="utf-8")
        guide = (ROOT / "docs" / "operator-guide.md").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        for surface in (skill, maintenance, commands, guide, readme):
            self.assertIn("ts: fulltsupgrade", surface)
        normalized_maintenance = " ".join(maintenance.split())
        self.assertIn("latest verified published stable release", normalized_maintenance)
        self.assertIn("synchronize the separately installed Codex skill", normalized_maintenance)
        self.assertIn("even when the workspace snapshot was already current", normalized_maintenance)
        self.assertIn(
            "does not authorize publishing a new Tool Shed release", normalized_maintenance
        )
        self.assertIn("updating any other workspace or fleet target", normalized_maintenance)

        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            self.init_repository(workspace)
            run_script("scripts/install_into_workspace.py", str(workspace), "--provider", "all")
            guidance_paths = (
                workspace / "AGENTS.md",
                workspace / "CLAUDE.md",
                workspace / "GEMINI.md",
                workspace / ".github" / "copilot-instructions.md",
                workspace / ".cursor" / "rules" / "tool-shed.mdc",
            )
            for path in guidance_paths:
                with self.subTest(path=path):
                    guidance = path.read_text(encoding="utf-8")
                    self.assertIn("`ts: fulltsupgrade`", guidance)
                    self.assertIn("latest verified published GitHub release", guidance)
                    self.assertIn("installed Codex skill synchronization", guidance)

    def test_direct_routing_scenarios_match_portable_and_installed_contract(self) -> None:
        scenarios = json.loads(
            (ROOT / "tests" / "fixtures" / "direct-routing-scenarios.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            {scenario["name"] for scenario in scenarios},
            {
                "ordinary bounded web bug",
                "bounded web bug through ask inbox",
                "ship-adjacent documentation edit",
                "explicit end-to-end ship request",
            },
        )

        for scenario in scenarios:
            prompt = scenario["prompt"].lstrip().lower()
            explicit_ship = prompt.startswith("ts:ship ") or prompt.startswith("ts: ship ")
            expected_coordination = (
                "direct" if scenario["bounded_single_repository"] and not explicit_ship else "coordinated"
            )
            with self.subTest(scenario=scenario["name"]):
                self.assertEqual(explicit_ship, scenario["explicit_ship"])
                self.assertEqual(expected_coordination, scenario["expected_coordination"])
                self.assertEqual(scenario["create_artifact"], expected_coordination != "direct")
                self.assertEqual(scenario["broad_validation"], explicit_ship)

        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            self.init_repository(workspace)
            owner_guidance = "# Owner guidance\n"
            (workspace / "AGENTS.md").write_text(owner_guidance, encoding="utf-8")
            run_script("scripts/install_into_workspace.py", str(workspace), "--provider", "all")

            guidance_paths = (
                "AGENTS.md",
                "CLAUDE.md",
                "GEMINI.md",
                ".github/copilot-instructions.md",
                ".cursor/rules/tool-shed.mdc",
            )
            for relative in guidance_paths:
                guidance = (workspace / relative).read_text(encoding="utf-8")
                with self.subTest(provider_guidance=relative):
                    self.assertIn("single-repository bug fix or enhancement to Direct", guidance)
                    self.assertIn("orient to the named target once", guidance)
                    self.assertIn("campaign continuity does not upgrade Direct", guidance)
                    self.assertIn("ts:ask` does not turn a bounded Direct request", guidance)
                    self.assertIn("merely mentions or discusses `ts:ship`", guidance)
            self.assertTrue((workspace / "AGENTS.md").read_text(encoding="utf-8").startswith(owner_guidance))

            direct_ask = next(
                scenario for scenario in scenarios if scenario["transport"] == "ts:ask"
            )
            ask_path = workspace / "work" / "01-q&a" / "ask.txt"
            ask_path.write_text(direct_ask["prompt"] + "\n", encoding="utf-8")
            work_before = sorted(path.relative_to(workspace).as_posix() for path in (workspace / "work").rglob("*"))
            result = run_script(
                "scripts/read_ask_inbox.py", "--workspace", str(workspace), "--json"
            )
            payload = json.loads(result.stdout)
            work_after = sorted(path.relative_to(workspace).as_posix() for path in (workspace / "work").rglob("*"))
            self.assertEqual(payload["status"], "canonical")
            self.assertEqual(payload["content"], direct_ask["prompt"])
            self.assertEqual(work_after, work_before)

    def test_numbered_work_levels_match_models_and_installed_contract(self) -> None:
        scenarios = json.loads(
            (ROOT / "tests" / "fixtures" / "work-level-routing-scenarios.json").read_text(
                encoding="utf-8"
            )
        )
        aliases = {"ts:work ": 2, "ts:freeze ": 3, "ts:push ": 4, "ts:ship ": 5}

        for scenario in scenarios:
            level = scenario["level"]
            is_check = scenario["route"].startswith("ts:check ")
            with self.subTest(route=scenario["route"], model=scenario["model"]):
                self.assertEqual(scenario["implement"], not is_check)
                self.assertEqual(
                    scenario["documentation_crud"], not is_check and level >= 3
                )
                self.assertEqual(scenario["focused_remote_check"], not is_check and level >= 2)
                self.assertEqual(scenario["full_validation"], level >= 3)
                self.assertEqual(scenario["push"], not is_check and level >= 4)
                expected_promotion = not is_check and (
                    level >= 5 or (scenario["model"] == "combined" and level in {2, 3})
                )
                self.assertEqual(scenario["production_promotion"], expected_promotion)

        self.assertEqual(aliases, {"ts:work ": 2, "ts:freeze ": 3, "ts:push ": 4, "ts:ship ": 5})

        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            self.init_repository(workspace)
            owner_guidance = "# Owner guidance\n"
            (workspace / "AGENTS.md").write_text(owner_guidance, encoding="utf-8")
            run_script("scripts/install_into_workspace.py", str(workspace), "--provider", "all")
            first = {
                relative: (workspace / relative).read_bytes()
                for relative in (
                    "AGENTS.md",
                    "CLAUDE.md",
                    "GEMINI.md",
                    ".github/copilot-instructions.md",
                    ".cursor/rules/tool-shed.mdc",
                )
            }
            run_script("scripts/install_into_workspace.py", str(workspace), "--provider", "all")

            for relative, initial in first.items():
                guidance = (workspace / relative).read_text(encoding="utf-8")
                with self.subTest(provider_guidance=relative):
                    self.assertEqual((workspace / relative).read_bytes(), initial)
                    self.assertIn("ts:work1` through `ts:work5", guidance)
                    self.assertIn("`ts:work` = `work2`", guidance)
                    self.assertIn("work/tool-shed.yaml", guidance)
                    self.assertIn("work_model: combined", guidance)
                    self.assertIn("work_model: split", guidance)
                    self.assertIn("automatically deploys production", guidance)
            self.assertTrue((workspace / "AGENTS.md").read_text(encoding="utf-8").startswith(owner_guidance))

        documentation_contract = "create, read, update, or delete project documentation"
        for relative in (
            "README.md",
            "docs/commands.md",
            "docs/operator-guide.md",
            "skills/tool-shed/references/campaign-routes.md",
            "scripts/install_into_workspace.py",
        ):
            with self.subTest(work3_contract=relative):
                content = " ".join((ROOT / relative).read_text(encoding="utf-8").split())
                self.assertIn(
                    documentation_contract,
                    content,
                )

    def test_ask_resolver_uses_canonical_content_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            canonical = workspace / "work" / "01-q&a" / "ask.txt"
            fallback = workspace / "work" / "q&a" / "ask.txt"
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
            self.assertEqual(payload["selected_path"], "work/01-q&a/ask.txt")
            self.assertEqual(payload["content"], "Run the canonical request.")
            self.assertEqual(payload["canonical"]["path"], "work/01-q&a/ask.txt")
            self.assertEqual(payload["fallback"]["path"], "work/q&a/ask.txt")
            self.assertIn("Using canonical inbox work/01-q&a/ask.txt", text_result.stdout)
            self.assertNotIn("Warning:", text_result.stdout)

    def test_ask_resolver_uses_fallback_content_only_and_reports_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            canonical = workspace / "work" / "01-q&a" / "ask.txt"
            fallback = workspace / "work" / "q&a" / "ask.txt"
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
            self.assertEqual(payload["selected_path"], "work/q&a/ask.txt")
            self.assertEqual(payload["content"], "Run the fallback request.")
            self.assertIn("noncanonical legacy location work/q&a/ask.txt", text_result.stdout)
            self.assertIn("canonical inbox is work/01-q&a/ask.txt", text_result.stdout)

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
            canonical = workspace / "work" / "01-q&a" / "ask.txt"
            fallback = workspace / "work" / "q&a" / "ask.txt"
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
            canonical = workspace / "work" / "01-q&a" / "ask.txt"
            fallback = workspace / "work" / "q&a" / "ask.txt"
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
            self.assertIn("both work/01-q&a/ask.txt and work/q&a/ask.txt", text_result.stdout)
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

    def test_work_index_includes_campaign_requests_but_skips_queue_projections(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            run_script("scripts/campaign_queue.py", "--workspace", str(workspace), "init")
            status = run_script(
                "scripts/campaign_queue.py", "--workspace", str(workspace), "status", "--json"
            )
            token = json.loads(status.stdout)["state_token"]
            run_script(
                "scripts/campaign_queue.py",
                "--workspace",
                str(workspace),
                "add",
                "demo-campaign",
                "Demo campaign",
                "--outcome",
                "prove campaign indexing",
                "--completion-gate",
                "focused checks pass",
                "--expect",
                token,
            )

            run_script("scripts/update_work_index.py", "--workspace", str(workspace))
            payload = json.loads((workspace / "work" / "index.json").read_text(encoding="utf-8"))
            paths = {item["path"] for item in payload["artifacts"]}
            self.assertIn("work/00-campaigns/active/demo-campaign.md", paths)
            self.assertNotIn("work/00-campaigns/active-queue.md", paths)
            self.assertNotIn("work/00-campaigns/completed-queue.md", paths)

    def test_campaign_lifecycle_rejects_stale_writes_and_promotes_next_ready(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            run_script("scripts/campaign_queue.py", "--workspace", str(workspace), "init")

            initial = json.loads(
                run_script(
                    "scripts/campaign_queue.py", "--workspace", str(workspace), "status", "--json"
                ).stdout
            )
            run_script(
                "scripts/campaign_queue.py", "--workspace", str(workspace), "add", "first",
                "First", "--outcome", "finish first", "--completion-gate", "first is verified",
                "--expect", initial["state_token"],
            )
            stale = run_script(
                "scripts/campaign_queue.py", "--workspace", str(workspace), "add", "stale",
                "Stale", "--outcome", "must not write", "--completion-gate", "never",
                "--expect", initial["state_token"], check=False,
            )
            self.assertEqual(stale.returncode, 2)
            self.assertIn("stale campaign state", stale.stderr)
            self.assertFalse((workspace / "work" / "00-campaigns" / "active" / "stale.md").exists())

            token = json.loads(
                run_script(
                    "scripts/campaign_queue.py", "--workspace", str(workspace), "status", "--json"
                ).stdout
            )["state_token"]
            run_script(
                "scripts/campaign_queue.py", "--workspace", str(workspace), "add", "second",
                "Second", "--outcome", "finish second", "--completion-gate", "second is verified",
                "--depends-on", "first", "--detour-for", "first", "--return-to", "first",
                "--expect", token,
            )
            token = json.loads(
                run_script(
                    "scripts/campaign_queue.py", "--workspace", str(workspace), "status", "--json"
                ).stdout
            )["state_token"]
            run_script(
                "scripts/campaign_queue.py", "--workspace", str(workspace), "start", "first",
                "--expect", token,
            )
            token = json.loads(
                run_script(
                    "scripts/campaign_queue.py", "--workspace", str(workspace), "status", "--json"
                ).stdout
            )["state_token"]
            run_script(
                "scripts/campaign_queue.py", "--workspace", str(workspace), "complete", "first",
                "--evidence", "tests:first", "--gate-passed", "--expect", token,
            )

            final = json.loads(
                run_script(
                    "scripts/campaign_queue.py", "--workspace", str(workspace), "status", "--json"
                ).stdout
            )
            self.assertEqual(final["working"], ["second"])
            self.assertEqual(final["completed"], ["first"])
            self.assertEqual(final["last_completed"], "first")
            self.assertEqual(final["detours"], ["second"])
            self.assertEqual(final["findings"], [])
            self.assertTrue((workspace / "work" / "00-campaigns" / "completed" / "first.md").is_file())
            active_queue = (workspace / "work" / "00-campaigns" / "active-queue.md").read_text(encoding="utf-8")
            self.assertIn("Detour and return point: second", active_queue)

    def test_campaign_readiness_is_dependency_aware_across_surfaces(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            run_script("scripts/campaign_queue.py", "--workspace", str(workspace), "init")

            def status() -> dict[str, object]:
                return json.loads(
                    run_script(
                        "scripts/campaign_queue.py", "--workspace", str(workspace),
                        "status", "--json",
                    ).stdout
                )

            def add(campaign_id: str, depends_on: str | None = None) -> None:
                arguments = [
                    "scripts/campaign_queue.py", "--workspace", str(workspace), "add",
                    campaign_id, campaign_id.title(), "--outcome", f"deliver {campaign_id}",
                    "--completion-gate", f"{campaign_id} verified",
                    "--expect", str(status()["state_token"]),
                ]
                if depends_on:
                    arguments.extend(["--depends-on", depends_on])
                run_script(*arguments)

            add("blocked")
            run_script(
                "scripts/campaign_queue.py", "--workspace", str(workspace), "start", "blocked",
                "--expect", str(status()["state_token"]),
            )
            run_script(
                "scripts/campaign_queue.py", "--workspace", str(workspace), "block", "blocked",
                "--reason", "external dependency", "--expect", str(status()["state_token"]),
            )
            add("dependent", "blocked")

            queue_path = workspace / "work" / "00-campaigns" / "active-queue.md"
            queue = queue_path.read_text(encoding="utf-8")
            self.assertIn("- Next: none", queue)
            self.assertIsNone(status()["next"])
            self.assertIsNone(json.loads(
                run_script(
                    "scripts/campaign_queue.py", "--workspace", str(workspace), "next", "--json",
                ).stdout
            ))

            add("independent")
            queue = queue_path.read_text(encoding="utf-8")
            self.assertIn("- Next: independent — Independent", queue)
            self.assertEqual(status()["next"], "independent")
            self.assertEqual(
                json.loads(
                    run_script(
                        "scripts/campaign_queue.py", "--workspace", str(workspace),
                        "next", "--json",
                    ).stdout
                )["campaign_id"],
                "independent",
            )

            queue_path.write_text(
                queue.replace(
                    "- Next: independent — Independent",
                    "- Next: dependent — Dependent",
                ),
                encoding="utf-8",
            )
            validation = json.loads(
                run_script(
                    "scripts/campaign_queue.py", "--workspace", str(workspace),
                    "validate", "--json",
                ).stdout
            )
            self.assertFalse(validation["valid"])
            self.assertIn(
                "active-queue.md is stale or manually inconsistent",
                validation["findings"],
            )

    def test_focus_area_catalog_validation_and_readiness_cards(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            run_script("scripts/campaign_queue.py", "--workspace", str(workspace), "init")
            (workspace / "work" / "focus-areas.md").write_text(
                """# Demo Focus Areas

Status: approved
Type: focus-area-catalog
Updated: 2026-08-15
Next Action: none

Focus Area ID: firmware
Name: Firmware
Purpose: Embedded behavior
Includes: controller logic
Excludes: release orchestration
Evidence: src/firmware and firmware tests
Uncertainty: none

Focus Area ID: qualification
Name: Qualification and Release
Purpose: Product qualification and release
Includes: qualification gates
Excludes: embedded implementation
Evidence: qualification tests and release runbooks
Uncertainty: none
""",
                encoding="utf-8",
            )

            def status() -> dict[str, object]:
                return json.loads(
                    run_script(
                        "scripts/campaign_queue.py", "--workspace", str(workspace),
                        "status", "--json",
                    ).stdout
                )

            def add(
                campaign_id: str,
                *,
                primary: str = "firmware",
                supporting: str | None = None,
                depends_on: str | None = None,
                decision: str | None = None,
            ) -> None:
                arguments = [
                    "scripts/campaign_queue.py", "--workspace", str(workspace), "add",
                    campaign_id, campaign_id.title(), "--outcome", f"deliver {campaign_id}",
                    "--completion-gate", f"{campaign_id} verified",
                    "--primary-focus-area", primary,
                    "--expect", str(status()["state_token"]),
                ]
                if supporting:
                    arguments.extend(["--supporting-focus-area", supporting])
                if depends_on:
                    arguments.extend(["--depends-on", depends_on])
                if decision:
                    arguments.extend(["--decision", decision])
                run_script(*arguments)

            add("foundation")
            run_script(
                "scripts/campaign_queue.py", "--workspace", str(workspace), "start", "foundation",
                "--expect", str(status()["state_token"]),
            )
            run_script(
                "scripts/campaign_queue.py", "--workspace", str(workspace), "complete", "foundation",
                "--gate-passed", "--evidence", "verified",
                "--expect", str(status()["state_token"]),
            )
            add("working", supporting="qualification")
            run_script(
                "scripts/campaign_queue.py", "--workspace", str(workspace), "start", "working",
                "--expect", str(status()["state_token"]),
            )
            add("ready", primary="qualification")
            add("waiting", primary="qualification", depends_on="working")
            add("blocked", decision="owner approval")

            payload = status()
            self.assertEqual(
                payload["readiness"],
                {
                    "working": "working",
                    "ready": "ready",
                    "waiting": "waiting",
                    "blocked": "blocked",
                },
            )
            self.assertEqual(payload["next"], "ready")
            selected = json.loads(
                run_script(
                    "scripts/campaign_queue.py", "--workspace", str(workspace), "next", "--json",
                ).stdout
            )
            self.assertEqual(selected["campaign_id"], "working")

            queue = (
                workspace / "work" / "00-campaigns" / "active-queue.md"
            ).read_text(encoding="utf-8")
            for display in (
                "🔵 **WORKING**", "🟢 **READY**", "🟡 **WAITING**", "🔴 **BLOCKED**"
            ):
                self.assertIn(display, queue)
            self.assertIn("**PRIMARY FOCUS AREAS:** Firmware", queue)
            self.assertIn("**SUPPORTING FOCUS AREAS:** Qualification and Release", queue)
            self.assertIn("**DEPENDS ON:** `working` — 🔵 **WORKING**", queue)
            self.assertIn("**DECISION NEEDED:** owner approval", queue)
            self.assertNotIn("<style", queue.lower())
            self.assertNotIn("<div", queue.lower())

            ready_path = workspace / "work" / "00-campaigns" / "active" / "ready.md"
            original = ready_path.read_text(encoding="utf-8")
            ready_path.write_text(
                original.replace(
                    "Primary Focus Areas: qualification",
                    "Primary Focus Areas: unknown-area",
                ),
                encoding="utf-8",
            )
            unknown = json.loads(
                run_script(
                    "scripts/campaign_queue.py", "--workspace", str(workspace),
                    "validate", "--json",
                ).stdout
            )
            self.assertTrue(any("unknown IDs: unknown-area" in item for item in unknown["findings"]))
            ready_path.write_text(
                original.replace("Primary Focus Areas: qualification", "Primary Focus Areas: none"),
                encoding="utf-8",
            )
            unmapped = json.loads(
                run_script(
                    "scripts/campaign_queue.py", "--workspace", str(workspace),
                    "validate", "--json",
                ).stdout
            )
            self.assertTrue(any("has no Primary Focus Areas" in item for item in unmapped["findings"]))

    def test_focus_area_migration_is_previewed_and_manifest_applied(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            run_script("scripts/campaign_queue.py", "--workspace", str(workspace), "init")
            (workspace / "work" / "focus-areas.md").write_text(
                """# Demo Focus Areas

Status: approved
Type: focus-area-catalog
Updated: 2026-08-15
Next Action: none

Focus Area ID: firmware
Name: Firmware
Purpose: Embedded behavior
Includes: controller logic
Excludes: release orchestration
Evidence: src/firmware and firmware tests
Uncertainty: none

Focus Area ID: qualification
Name: Qualification
Purpose: Product qualification
Includes: qualification gates
Excludes: embedded implementation
Evidence: qualification tests
Uncertainty: none
""",
                encoding="utf-8",
            )
            status = json.loads(
                run_script(
                    "scripts/campaign_queue.py", "--workspace", str(workspace),
                    "status", "--json",
                ).stdout
            )
            run_script(
                "scripts/campaign_queue.py", "--workspace", str(workspace), "add", "legacy",
                "Legacy", "--outcome", "deliver legacy — Focus areas: Firmware, Qualification",
                "--completion-gate", "legacy verified", "--primary-focus-area", "firmware",
                "--expect", str(status["state_token"]),
            )

            preview = json.loads(
                run_script(
                    "scripts/campaign_queue.py", "--workspace", str(workspace),
                    "migrate-preview", "--json",
                ).stdout
            )
            migration = preview["focus_area_migration"]
            self.assertFalse(migration["writes_performed"])
            self.assertTrue(migration["requires_owner_review"])
            self.assertEqual(migration["candidates"][0]["matched_ids"], ["firmware", "qualification"])
            self.assertEqual(migration["candidates"][0]["outcome_after"], "deliver legacy")

            manifest = workspace / "focus-area-migration.json"
            manifest.write_text(
                json.dumps(migration["suggested_manifest"]), encoding="utf-8"
            )
            applied = json.loads(
                run_script(
                    "scripts/reconcile_campaign_queue.py", "--workspace", str(workspace),
                    "--apply", "--expect", migration["suggested_manifest"]["state_token"],
                    "--manifest", str(manifest), "--json",
                ).stdout
            )
            self.assertTrue(applied["writes_performed"])
            campaign = (
                workspace / "work" / "00-campaigns" / "active" / "legacy.md"
            ).read_text(encoding="utf-8")
            self.assertIn("Outcome: deliver legacy", campaign)
            self.assertIn("Primary Focus Areas: firmware, qualification", campaign)
            self.assertNotIn("Focus areas:", campaign)
            self.assertEqual(applied["validation_findings"], [])

    def test_campaign_same_day_completions_preserve_completion_order(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            run_script("scripts/campaign_queue.py", "--workspace", str(workspace), "init")

            def token() -> str:
                return json.loads(
                    run_script(
                        "scripts/campaign_queue.py", "--workspace", str(workspace), "status", "--json"
                    ).stdout
                )["state_token"]

            for campaign_id in ("alpha", "zulu"):
                run_script(
                    "scripts/campaign_queue.py", "--workspace", str(workspace), "add", campaign_id,
                    campaign_id.title(), "--outcome", f"finish {campaign_id}",
                    "--completion-gate", f"{campaign_id} verified", "--expect", token(),
                )
                run_script(
                    "scripts/campaign_queue.py", "--workspace", str(workspace), "start", campaign_id,
                    "--expect", token(),
                )
                run_script(
                    "scripts/campaign_queue.py", "--workspace", str(workspace), "complete", campaign_id,
                    "--evidence", f"tests:{campaign_id}", "--gate-passed", "--expect", token(),
                )

            status = json.loads(
                run_script(
                    "scripts/campaign_queue.py", "--workspace", str(workspace), "status", "--json"
                ).stdout
            )
            self.assertEqual(status["completed"], ["zulu", "alpha"])
            self.assertEqual(status["last_completed"], "zulu")
            self.assertEqual(status["findings"], [])
            completed_root = workspace / "work" / "00-campaigns" / "completed"
            self.assertIn("Completion Order: 1", (completed_root / "alpha.md").read_text(encoding="utf-8"))
            self.assertIn("Completion Order: 2", (completed_root / "zulu.md").read_text(encoding="utf-8"))

    def test_campaign_terminal_transitions_and_migration_are_preserving(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            inbox = workspace / "work" / "q&a" / "ask.txt"
            inbox.parent.mkdir(parents=True)
            inbox.write_text("# inbox\nBuild the requested feature\n", encoding="utf-8")
            legacy = inbox.parent / "legacy-request.md"
            legacy.write_text("# Legacy request\n", encoding="utf-8")
            run_script("scripts/campaign_queue.py", "--workspace", str(workspace), "init")

            preview = json.loads(
                run_script(
                    "scripts/campaign_queue.py", "--workspace", str(workspace), "migrate-preview", "--json"
                ).stdout
            )
            self.assertEqual(preview["mode"], "preview-only")
            self.assertFalse(preview["writes_performed"])
            self.assertEqual(inbox.read_text(encoding="utf-8"), "# inbox\nBuild the requested feature\n")
            self.assertTrue(legacy.is_file())

            token = json.loads(
                run_script(
                    "scripts/campaign_queue.py", "--workspace", str(workspace), "status", "--json"
                ).stdout
            )["state_token"]
            run_script(
                "scripts/campaign_queue.py", "--workspace", str(workspace), "add", "defer-me",
                "Defer me", "--outcome", "exercise deferral", "--completion-gate", "not now",
                "--expect", token,
            )
            token = json.loads(
                run_script(
                    "scripts/campaign_queue.py", "--workspace", str(workspace), "status", "--json"
                ).stdout
            )["state_token"]
            run_script(
                "scripts/campaign_queue.py", "--workspace", str(workspace), "defer", "defer-me",
                "--reason", "lower priority", "--reactivate-when", "capacity opens", "--expect", token,
            )
            token = json.loads(
                run_script(
                    "scripts/campaign_queue.py", "--workspace", str(workspace), "status", "--json"
                ).stdout
            )["state_token"]
            run_script(
                "scripts/campaign_queue.py", "--workspace", str(workspace), "abandon", "defer-me",
                "--reason", "superseded", "--replacement", "future-campaign", "--expect", token,
            )
            result = json.loads(
                run_script(
                    "scripts/campaign_queue.py", "--workspace", str(workspace), "validate", "--json"
                ).stdout
            )
            self.assertTrue(result["valid"])
            abandoned = workspace / "work" / "00-campaigns" / "abandoned" / "defer-me.md"
            self.assertIn("replacement: future-campaign", abandoned.read_text(encoding="utf-8"))

    def test_campaign_reorder_overlap_block_and_failed_completion(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            run_script("scripts/campaign_queue.py", "--workspace", str(workspace), "init")

            def token() -> str:
                result = run_script(
                    "scripts/campaign_queue.py", "--workspace", str(workspace), "status", "--json"
                )
                return json.loads(result.stdout)["state_token"]

            run_script(
                "scripts/campaign_queue.py", "--workspace", str(workspace), "add", "alpha",
                "Alpha", "--outcome", "deliver alpha", "--completion-gate", "alpha verified",
                "--expect", token(),
            )
            duplicate = run_script(
                "scripts/campaign_queue.py", "--workspace", str(workspace), "add", "alpha-copy",
                "Alpha", "--outcome", "deliver alpha", "--completion-gate", "copy verified",
                "--expect", token(), check=False,
            )
            self.assertEqual(duplicate.returncode, 2)
            self.assertIn("overlaps existing alpha", duplicate.stderr)

            run_script(
                "scripts/campaign_queue.py", "--workspace", str(workspace), "add", "beta",
                "Beta", "--outcome", "deliver beta", "--completion-gate", "beta verified",
                "--expect", token(),
            )
            run_script(
                "scripts/campaign_queue.py", "--workspace", str(workspace), "reorder", "beta",
                "--position", "1", "--expect", token(),
            )
            self.assertEqual(
                json.loads(
                    run_script(
                        "scripts/campaign_queue.py", "--workspace", str(workspace), "status", "--json"
                    ).stdout
                )["active_order"],
                ["beta", "alpha"],
            )
            run_script(
                "scripts/campaign_queue.py", "--workspace", str(workspace), "start", "beta",
                "--expect", token(),
            )
            run_script(
                "scripts/campaign_queue.py", "--workspace", str(workspace), "block", "beta",
                "--reason", "owner decision needed", "--expect", token(),
            )
            before_failure = token()
            failed = run_script(
                "scripts/campaign_queue.py", "--workspace", str(workspace), "complete", "beta",
                "--evidence", "none", "--expect", before_failure, check=False,
            )
            self.assertEqual(failed.returncode, 2)
            self.assertIn("completion requires --gate-passed", failed.stderr)
            self.assertEqual(token(), before_failure)
            queue = (workspace / "work" / "00-campaigns" / "active-queue.md").read_text(encoding="utf-8")
            self.assertIn("Blocker or decision needed: beta", queue)

    def test_campaign_unblock_returns_work_to_queued_without_starting(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            run_script("scripts/campaign_queue.py", "--workspace", str(workspace), "init")

            def status() -> dict[str, object]:
                result = run_script(
                    "scripts/campaign_queue.py", "--workspace", str(workspace), "status", "--json"
                )
                return json.loads(result.stdout)

            run_script(
                "scripts/campaign_queue.py", "--workspace", str(workspace), "add", "resume-me",
                "Resume me", "--outcome", "resume safely", "--completion-gate", "resume verified",
                "--expect", str(status()["state_token"]),
            )
            run_script(
                "scripts/campaign_queue.py", "--workspace", str(workspace), "start", "resume-me",
                "--expect", str(status()["state_token"]),
            )
            run_script(
                "scripts/campaign_queue.py", "--workspace", str(workspace), "block", "resume-me",
                "--reason", "dependency unavailable", "--expect", str(status()["state_token"]),
            )
            blocked = status()
            rejected_start = run_script(
                "scripts/campaign_queue.py", "--workspace", str(workspace), "start", "resume-me",
                "--expect", str(blocked["state_token"]), check=False,
            )
            self.assertEqual(rejected_start.returncode, 2)
            self.assertIn("only a queued campaign can start", rejected_start.stderr)

            run_script(
                "scripts/campaign_queue.py", "--workspace", str(workspace), "unblock", "resume-me",
                "--expect", str(blocked["state_token"]),
            )
            unblocked = status()
            self.assertEqual(unblocked["working"], [])
            self.assertEqual(unblocked["next"], "resume-me")
            self.assertEqual(unblocked["blocked"], [])
            self.assertEqual(unblocked["decisions_needed"], [])
            campaign = workspace / "work" / "00-campaigns" / "active" / "resume-me.md"
            text = campaign.read_text(encoding="utf-8")
            self.assertIn("Status: queued", text)
            self.assertIn("Decision: none", text)
            self.assertIn("Next Action: execute when selected", text)
            queue = (workspace / "work" / "00-campaigns" / "active-queue.md").read_text(encoding="utf-8")
            self.assertIn("Blocker or decision needed: none", queue)

            before_invalid = str(unblocked["state_token"])
            invalid = run_script(
                "scripts/campaign_queue.py", "--workspace", str(workspace), "unblock", "resume-me",
                "--expect", before_invalid, check=False,
            )
            self.assertEqual(invalid.returncode, 2)
            self.assertIn("only a blocked campaign can be unblocked", invalid.stderr)
            self.assertEqual(status()["state_token"], before_invalid)

            run_script(
                "scripts/campaign_queue.py", "--workspace", str(workspace), "start", "resume-me",
                "--expect", before_invalid,
            )
            self.assertEqual(status()["working"], ["resume-me"])

    def test_campaign_reconciliation_reports_and_repairs_only_projection_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            run_script("scripts/campaign_queue.py", "--workspace", str(workspace), "init")

            def status() -> dict[str, object]:
                return json.loads(
                    run_script(
                        "scripts/campaign_queue.py", "--workspace", str(workspace), "status", "--json"
                    ).stdout
                )

            for campaign_id in ("alpha", "beta", "gamma"):
                run_script(
                    "scripts/campaign_queue.py", "--workspace", str(workspace), "add", campaign_id,
                    campaign_id.title(), "--outcome", f"deliver {campaign_id}",
                    "--completion-gate", f"{campaign_id} verified",
                    "--expect", str(status()["state_token"]),
                )
            run_script(
                "scripts/campaign_queue.py", "--workspace", str(workspace), "start", "beta",
                "--expect", str(status()["state_token"]),
            )
            run_script(
                "scripts/campaign_queue.py", "--workspace", str(workspace), "block", "gamma",
                "--reason", "owner decision", "--expect", str(status()["state_token"]),
            )
            alpha = workspace / "work" / "00-campaigns" / "active" / "alpha.md"
            alpha.write_text(
                alpha.read_text(encoding="utf-8").replace(
                    f"Updated: {date.today().isoformat()}", "Updated: 2000-01-01"
                ),
                encoding="utf-8",
            )
            queue = workspace / "work" / "00-campaigns" / "active-queue.md"
            lines = queue.read_text(encoding="utf-8").splitlines()
            alpha_line = next(line for line in lines if "active/alpha.md" in line)
            lines = [line for line in lines if "active/beta.md" not in line]
            lines.extend(
                [
                    alpha_line,
                    "99. [Ghost](active/ghost.md) — state: queued — outcome: missing",
                ]
            )
            queue.write_text("\n".join(lines) + "\n", encoding="utf-8")
            before = queue.read_bytes()

            dry = run_script(
                "scripts/reconcile_campaign_queue.py", "--workspace", str(workspace),
                "--dry-run", "--json",
            )
            report = json.loads(dry.stdout)
            self.assertEqual(queue.read_bytes(), before)
            self.assertEqual(report["orphaned_active"], ["beta"])
            self.assertEqual(report["missing_active_files"], ["ghost"])
            self.assertEqual(report["duplicate_queue_ids"], ["alpha"])
            self.assertEqual(report["working"], ["beta"])
            self.assertEqual(report["blocked"], ["gamma"])
            self.assertEqual([item["campaign_id"] for item in report["stalled"]], ["alpha"])
            self.assertEqual(report["repair_order"], ["alpha", "gamma", "beta"])
            self.assertEqual(
                report["proposed_execution_order"], ["beta", "alpha", "gamma"]
            )
            self.assertTrue(report["owner_action_required"])
            self.assertFalse(report["writes_performed"])

            missing_manifest = run_script(
                "scripts/reconcile_campaign_queue.py", "--workspace", str(workspace),
                "--apply", "--expect", report["state_token"], "--json", check=False,
            )
            self.assertEqual(missing_manifest.returncode, 2)
            self.assertIn("--apply requires --manifest PATH", missing_manifest.stderr)

            gamma = workspace / "work" / "00-campaigns" / "active" / "gamma.md"
            manifest = workspace / "reconcile-manifest.json"
            manifest.write_text(
                json.dumps(report["reconciliation_manifest"]), encoding="utf-8"
            )
            gamma.write_text(
                gamma.read_text(encoding="utf-8").replace(
                    "## Request", "## Request\n\nPreserve owner context."
                ),
                encoding="utf-8",
            )
            stale = run_script(
                "scripts/reconcile_campaign_queue.py", "--workspace", str(workspace),
                "--apply", "--expect", report["state_token"], "--manifest", str(manifest),
                "--json", check=False,
            )
            self.assertEqual(stale.returncode, 2)
            self.assertIn("stale whole-work state", stale.stderr)

            refreshed = json.loads(
                run_script(
                    "scripts/reconcile_campaign_queue.py", "--workspace", str(workspace),
                    "--dry-run", "--json",
                ).stdout
            )
            manifest.write_text(
                json.dumps(refreshed["reconciliation_manifest"]), encoding="utf-8"
            )
            applied = json.loads(
                run_script(
                    "scripts/reconcile_campaign_queue.py", "--workspace", str(workspace),
                    "--apply", "--expect", refreshed["state_token"],
                    "--manifest", str(manifest), "--json",
                ).stdout
            )
            self.assertTrue(applied["writes_performed"])
            self.assertFalse(applied["changes_required"])
            self.assertEqual(
                status()["active_order"], ["alpha", "gamma", "beta"]
            )
            self.assertEqual(applied["proposed_execution_order"], ["beta", "alpha", "gamma"])
            self.assertEqual(applied["validation_findings"], [])
            self.assertIn("update_work_index.py", applied["post_apply_checks"])

    def test_campaign_reconciliation_reports_whole_work_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            run_script("scripts/campaign_queue.py", "--workspace", str(workspace), "init")

            def status() -> dict[str, object]:
                return json.loads(
                    run_script(
                        "scripts/campaign_queue.py", "--workspace", str(workspace),
                        "status", "--json",
                    ).stdout
                )

            for campaign_id in ("alpha", "beta", "finished", "later"):
                run_script(
                    "scripts/campaign_queue.py", "--workspace", str(workspace), "add",
                    campaign_id, campaign_id.title(), "--outcome", f"deliver {campaign_id}",
                    "--completion-gate", f"{campaign_id} verified",
                    "--expect", str(status()["state_token"]),
                )
            run_script(
                "scripts/campaign_queue.py", "--workspace", str(workspace), "complete", "finished",
                "--gate-passed", "--evidence", "verified", "--expect", str(status()["state_token"]),
            )
            run_script(
                "scripts/campaign_queue.py", "--workspace", str(workspace), "defer", "later",
                "--reason", "later scope", "--reactivate-when", "owner selects it",
                "--expect", str(status()["state_token"]),
            )

            tickets = workspace / "work" / "tickets"
            tickets.mkdir(parents=True)

            def artifact(name: str, headers: str, body: str = "") -> None:
                (tickets / f"{name}.md").write_text(
                    f"# {name.title()}\n\n{headers}\n\n{body}\n", encoding="utf-8"
                )

            common = f"Status: active\nType: ticket\nUpdated: {date.today().isoformat()}\nNext Action: implement"
            artifact("uncovered", common)
            artifact("linked", common + "\nCampaign: alpha")
            artifact("standalone", common + "\nCampaign: standalone\nCampaign Reason: intentionally local")
            artifact("excluded", common + "\nCampaign: excluded\nCampaign Reason: external ownership")
            artifact("deferred", common.replace("Status: active", "Status: deferred") + "\nCampaign: later")
            artifact("ghost", common + "\nCampaign: missing-id")
            artifact("done-but-active", common + "\nCampaign: finished")
            artifact("parent", common + "\nCampaign: alpha")
            artifact(
                "child",
                common + "\nParent: work/tickets/parent.md\nCampaign: beta",
            )
            artifact(
                "terminal-parent",
                common.replace("Status: active", "Status: complete").replace(
                    "Next Action: implement", "Next Action: none"
                ),
            )
            artifact(
                "active-descendant",
                common + "\nParent: work/tickets/terminal-parent.md\nCampaign: alpha",
            )
            artifact("bad-standalone", common + "\nCampaign: standalone")
            (tickets / "rough-notes.md").write_text(
                "# Rough notes\n\n- [ ] unresolved item\n", encoding="utf-8"
            )

            before = {
                path.relative_to(workspace).as_posix(): path.read_bytes()
                for path in workspace.rglob("*.md")
            }
            report = json.loads(
                run_script(
                    "scripts/reconcile_campaign_queue.py", "--workspace", str(workspace),
                    "--dry-run", "--json",
                ).stdout
            )
            after = {
                path.relative_to(workspace).as_posix(): path.read_bytes()
                for path in workspace.rglob("*.md")
            }
            self.assertEqual(before, after)
            whole = report["whole_work"]
            self.assertGreaterEqual(whole["coverage"]["artifacts_scanned"], 11)
            self.assertEqual(whole["coverage"]["standalone"], 2)
            self.assertEqual(whole["coverage"]["explicitly_excluded"], 1)
            self.assertTrue(any(
                any(path.endswith("uncovered.md") for path in item["paths"])
                for item in whole["missing_campaign"]
            ))
            self.assertTrue(any(item.get("campaign") == "missing-id" for item in whole["unlinked_artifact"]))
            self.assertTrue(whole["duplicate_coverage"])
            self.assertTrue(whole["lifecycle_mismatch"])
            self.assertTrue(any(
                "terminal artifact" in item["message"] for item in whole["lifecycle_mismatch"]
            ))
            self.assertTrue(whole["stale_completion"])
            self.assertTrue(whole["scope_conflict"])
            self.assertTrue(any(
                any(path.endswith("rough-notes.md") for path in item["paths"])
                for item in whole["unstructured_candidate"]
            ))
            linked = next(item for item in whole["artifacts"] if item["path"].endswith("linked.md"))
            deferred = next(item for item in whole["artifacts"] if item["path"].endswith("deferred.md"))
            self.assertEqual(linked["campaign"], "alpha")
            self.assertEqual(deferred["campaign"], "later")
            self.assertTrue(report["owner_action_required"])

    def test_dangler_resolution_is_automatically_created_refreshed_and_visible(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            run_script("scripts/campaign_queue.py", "--workspace", str(workspace), "init")
            ticket = workspace / "work" / "tickets" / "dangling.md"
            ticket.parent.mkdir(parents=True)
            ticket.write_text(
                "# Dangling\n\nStatus: active\nType: ticket\nUpdated: 2026-08-14\n"
                "Next Action: classify this work\n\n- [ ] resolve\n",
                encoding="utf-8",
            )

            report = json.loads(
                run_script(
                    "scripts/reconcile_campaign_queue.py", "--workspace", str(workspace),
                    "--dry-run", "--json",
                ).stdout
            )
            proposal = report["dangler_resolution"]
            self.assertEqual(proposal["campaign_id"], "resolve-unclassified-work")
            self.assertEqual(proposal["status"], "proposed")
            self.assertFalse(proposal["requires_manifest_approval"])
            self.assertTrue(proposal["automatic_update_required"])
            self.assertEqual(proposal["unresolved_paths"], ["work/tickets/dangling.md"])
            self.assertEqual(
                report["reconciliation_manifest"]["operations"][-1]["op"],
                "create_campaign",
            )
            self.assertFalse(
                (
                    workspace
                    / "work"
                    / "00-campaigns"
                    / "active"
                    / "resolve-unclassified-work.md"
                ).exists()
            )

            status = json.loads(
                run_script(
                    "scripts/campaign_queue.py", "--workspace", str(workspace), "status", "--json"
                ).stdout
            )
            self.assertEqual(status["next"], "resolve-unclassified-work")
            self.assertEqual(status["next_source"], "campaign-reconciliation")
            self.assertEqual(status["dangler_resolution"]["status"], "proposed")

            next_item = json.loads(
                run_script(
                    "scripts/campaign_queue.py", "--workspace", str(workspace), "next", "--json"
                ).stdout
            )
            self.assertEqual(next_item["campaign_id"], "resolve-unclassified-work")
            self.assertEqual(next_item["status"], "proposed")
            self.assertFalse(next_item["requires_manifest_approval"])

            applied = json.loads(
                run_script(
                    "scripts/reconcile_campaign_queue.py", "--workspace", str(workspace), "--json"
                ).stdout
            )
            self.assertEqual(
                applied["automatic_dangler_resolution"]["operation"], "create_campaign"
            )
            self.assertTrue(applied["writes_performed"])
            applied_status = json.loads(
                run_script(
                    "scripts/campaign_queue.py", "--workspace", str(workspace), "status", "--json"
                ).stdout
            )
            self.assertEqual(applied_status["active_order"], ["resolve-unclassified-work"])
            self.assertEqual(applied_status["next"], "resolve-unclassified-work")
            self.assertEqual(applied_status["next_source"], "campaign-queue")
            self.assertEqual(applied_status["dangler_resolution"]["status"], "queued")

            second = workspace / "work" / "tickets" / "second-dangling.md"
            second.write_text(
                "# Second Dangling\n\nStatus: active\nType: ticket\nUpdated: 2026-08-14\n"
                "Next Action: classify this work\n\n- [ ] resolve\n",
                encoding="utf-8",
            )
            refreshed = json.loads(
                run_script(
                    "scripts/reconcile_campaign_queue.py", "--workspace", str(workspace), "--json"
                ).stdout
            )
            self.assertEqual(
                refreshed["automatic_dangler_resolution"]["operation"],
                "refresh_dangler_campaign",
            )
            refreshed_status = json.loads(
                run_script(
                    "scripts/campaign_queue.py", "--workspace", str(workspace), "status", "--json"
                ).stdout
            )
            self.assertEqual(refreshed_status["active_order"], ["resolve-unclassified-work"])
            campaign = (
                workspace
                / "work"
                / "00-campaigns"
                / "active"
                / "resolve-unclassified-work.md"
            )
            campaign_text = campaign.read_text(encoding="utf-8")
            self.assertIn("work/tickets/dangling.md", campaign_text)
            self.assertIn("work/tickets/second-dangling.md", campaign_text)

            unchanged = json.loads(
                run_script(
                    "scripts/reconcile_campaign_queue.py", "--workspace", str(workspace), "--json"
                ).stdout
            )
            self.assertNotIn("automatic_dangler_resolution", unchanged)
            self.assertFalse(unchanged["writes_performed"])

    def test_auto_dangler_is_first_queued_after_working_campaign(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            run_script("scripts/campaign_queue.py", "--workspace", str(workspace), "init")

            def status() -> dict[str, object]:
                return json.loads(
                    run_script(
                        "scripts/campaign_queue.py", "--workspace", str(workspace),
                        "status", "--json",
                    ).stdout
                )

            run_script(
                "scripts/campaign_queue.py", "--workspace", str(workspace), "add",
                "already-working", "Already working", "--outcome", "finish current work",
                "--completion-gate", "current work verified",
                "--expect", str(status()["state_token"]),
            )
            run_script(
                "scripts/campaign_queue.py", "--workspace", str(workspace), "start",
                "already-working", "--expect", str(status()["state_token"]),
            )
            ticket = workspace / "work" / "tickets" / "dangling.md"
            ticket.parent.mkdir(parents=True)
            ticket.write_text(
                "# Dangling\n\nStatus: active\nType: ticket\nUpdated: 2026-08-14\n"
                "Next Action: classify\n",
                encoding="utf-8",
            )

            run_script(
                "scripts/reconcile_campaign_queue.py", "--workspace", str(workspace), "--json"
            )
            final = status()
            self.assertEqual(
                final["active_order"],
                ["already-working", "resolve-unclassified-work"],
            )
            self.assertEqual(final["working"], ["already-working"])
            self.assertEqual(final["next"], "resolve-unclassified-work")

    def test_campaign_reconciliation_manifest_applies_create_update_and_history_preserving_delete(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            run_script("scripts/campaign_queue.py", "--workspace", str(workspace), "init")
            tickets = workspace / "work" / "tickets"
            tickets.mkdir(parents=True)
            ticket = tickets / "candidate.md"
            ticket.write_text(
                "# Candidate\n\nStatus: active\nType: ticket\nUpdated: 2026-08-14\n"
                "Next Action: implement\n\n- [ ] deliver\n",
                encoding="utf-8",
            )
            report = json.loads(
                run_script(
                    "scripts/reconcile_campaign_queue.py", "--workspace", str(workspace),
                    "--dry-run", "--json",
                ).stdout
            )
            manifest = {
                "schema_version": 1,
                "kind": "tool-shed-campaign-reconciliation",
                "state_token": report["state_token"],
                "operations": [
                    {
                        "op": "create_campaign",
                        "campaign_id": "candidate-campaign",
                        "title": "Candidate campaign",
                        "outcome": "deliver candidate",
                        "completion_gate": "candidate verified",
                        "request": "Implement work/tickets/candidate.md.",
                        "position": 1,
                    },
                    {
                        "op": "set_association",
                        "path": "work/tickets/candidate.md",
                        "campaign": "candidate-campaign",
                    },
                ],
            }
            path = workspace / "manifest.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            applied = json.loads(
                run_script(
                    "scripts/reconcile_campaign_queue.py", "--workspace", str(workspace),
                    "--apply", "--expect", report["state_token"], "--manifest", str(path), "--json",
                ).stdout
            )
            self.assertTrue(applied["writes_performed"])
            self.assertIn("Campaign: candidate-campaign", ticket.read_text(encoding="utf-8"))
            self.assertTrue((workspace / "work" / "00-campaigns" / "active" / "candidate-campaign.md").is_file())

            refreshed = json.loads(
                run_script(
                    "scripts/reconcile_campaign_queue.py", "--workspace", str(workspace),
                    "--dry-run", "--json",
                ).stdout
            )
            transition = {
                "schema_version": 1,
                "kind": "tool-shed-campaign-reconciliation",
                "state_token": refreshed["state_token"],
                "operations": [
                    {
                        "op": "transition_campaign",
                        "campaign_id": "candidate-campaign",
                        "action": "abandon",
                        "reason": "superseded by owner decision",
                    }
                ],
            }
            path.write_text(json.dumps(transition), encoding="utf-8")
            run_script(
                "scripts/reconcile_campaign_queue.py", "--workspace", str(workspace),
                "--apply", "--expect", refreshed["state_token"], "--manifest", str(path), "--json",
            )
            preserved = workspace / "work" / "00-campaigns" / "abandoned" / "candidate-campaign.md"
            self.assertTrue(preserved.is_file())
            self.assertIn("Status: abandoned", preserved.read_text(encoding="utf-8"))
            self.assertFalse((workspace / "work" / "00-campaigns" / "active" / "candidate-campaign.md").exists())

    def test_campaign_validation_detects_dependency_cycle(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            run_script("scripts/campaign_queue.py", "--workspace", str(workspace), "init")

            def add(campaign_id: str, depends_on: str | None = None) -> None:
                status = json.loads(
                    run_script(
                        "scripts/campaign_queue.py", "--workspace", str(workspace), "status", "--json"
                    ).stdout
                )
                arguments = [
                    "scripts/campaign_queue.py", "--workspace", str(workspace), "add", campaign_id,
                    campaign_id.title(), "--outcome", f"deliver {campaign_id}",
                    "--completion-gate", f"{campaign_id} verified", "--expect", status["state_token"],
                ]
                if depends_on:
                    arguments.extend(["--depends-on", depends_on])
                run_script(*arguments)

            add("alpha")
            add("beta", "alpha")
            alpha = workspace / "work" / "00-campaigns" / "active" / "alpha.md"
            alpha.write_text(
                alpha.read_text(encoding="utf-8").replace("Depends On: none", "Depends On: beta"),
                encoding="utf-8",
            )
            result = json.loads(
                run_script(
                    "scripts/campaign_queue.py", "--workspace", str(workspace), "validate", "--json"
                ).stdout
            )
            self.assertFalse(result["valid"])
            self.assertTrue(any("dependency cycle" in finding for finding in result["findings"]))

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
            self.assertTrue((workspace / "work" / "01-q&a" / "ask.txt").is_file())
            self.assertTrue((workspace / "work" / "00-campaigns" / "active-queue.md").is_file())
            self.assertTrue((workspace / "work" / "00-campaigns" / "completed-queue.md").is_file())
            self.assertIn("work/00-campaigns", readme)

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
            self.assertEqual(gitignore.splitlines().count("/work/01-q&a/ask.txt"), 1)
            self.assertEqual(gitignore.splitlines().count("/work/01-q&a/*.legacy-*"), 1)
            self.assertEqual(gitignore.splitlines().count("/work/q&a/ask.txt"), 1)
            self.assertNotIn("/q&a/ask.txt", gitignore.splitlines())
            self.assertEqual(gitignore.count("/work/evidence/generated/"), 1)
            self.assertIn("Workspace preflight", first.stdout)
            self.assertEqual(second.returncode, 0)
            guidance = (workspace / "AGENTS.md").read_text(encoding="utf-8")
            self.assertEqual(guidance.count("BEGIN TOOL SHED GENERATED EVIDENCE GUIDANCE"), 1)
            self.assertEqual(guidance.count("BEGIN TOOL SHED ROUTING GUIDANCE"), 1)
            self.assertEqual(guidance.count("BEGIN TOOL SHED DISCUSSION GUIDANCE"), 1)
            self.assertEqual(guidance.count("BEGIN TOOL SHED COORDINATION GUIDANCE"), 1)
            self.assertEqual(guidance.count("BEGIN TOOL SHED EVIDENCE RESPONSE GUIDANCE"), 1)
            self.assertEqual(guidance.count("BEGIN TOOL SHED CAMPAIGN GUIDANCE"), 1)
            self.assertEqual(guidance.count("BEGIN TOOL SHED Q&A GUIDANCE"), 1)
            self.assertEqual(guidance.count("BEGIN TOOL SHED OWNER CAMPAIGN GUIDANCE"), 1)
            self.assertIn("Campaign status: COMPLETE", guidance)
            self.assertIn("A progress summary, artifact update, phase boundary", guidance)
            self.assertIn("command success alone is not outcome success", guidance)
            self.assertIn("at most three credible ways the plan could fail", guidance)
            self.assertIn("ts: discuss <topic>", guidance)
            self.assertIn("Direct, Guided, Coordinated, or Deep", guidance)
            self.assertIn("orient to the named target once", guidance)
            self.assertIn("campaign continuity does not upgrade Direct", guidance)
            self.assertIn("ts:ask` does not turn a bounded Direct request", guidance)
            self.assertIn("merely mentions or discusses `ts:ship`", guidance)
            self.assertIn("interpret `camp` as `campaign`", guidance)
            self.assertIn("Interpret `que N`", guidance)
            self.assertIn("`ts: unblock` returns blocked work to queued state", guidance)
            self.assertIn(
                "`ts: reconcile campaigns` as authorization", guidance
            )
            self.assertIn("Dangler Resolution campaign as the first queued work", guidance)
            self.assertIn("optional project-specific catalog", guidance)
            self.assertIn("shared dependency/decision readiness states", guidance)
            self.assertIn("`ts: build focus areas` as a two-stage route", guidance)
            self.assertIn("A build or refresh request is not approval", guidance)

    def test_build_focus_areas_route_is_portable_and_approval_gated(self) -> None:
        skill = (ROOT / "skills" / "tool-shed" / "SKILL.md").read_text(encoding="utf-8")
        route = (
            ROOT / "skills" / "tool-shed" / "references" / "campaign-routes.md"
        ).read_text(encoding="utf-8")
        commands = (ROOT / "docs" / "commands.md").read_text(encoding="utf-8")
        guide = (ROOT / "docs" / "operator-guide.md").read_text(encoding="utf-8")

        for content in (skill, route, commands, guide):
            self.assertIn("ts: build focus areas", content)
        self.assertIn("A request to discover, build, or refresh areas is not by", route)
        self.assertIn("Present an exact proposed catalog", route)
        self.assertIn("proposed primary", route)
        self.assertIn("After explicit approval", route)
        self.assertIn("Preserve stable IDs", route)
        self.assertIn("leave active campaigns unmapped", route)

        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            self.init_repository(workspace)
            run_script("scripts/install_into_workspace.py", str(workspace), "--provider", "all")
            for relative in (
                "AGENTS.md",
                "CLAUDE.md",
                "GEMINI.md",
                ".github/copilot-instructions.md",
                ".cursor/rules/tool-shed.mdc",
            ):
                guidance = (workspace / relative).read_text(encoding="utf-8")
                with self.subTest(provider_guidance=relative):
                    self.assertIn("`ts: build focus areas` as a two-stage route", guidance)
                    self.assertIn("A build or refresh request is not approval", guidance)
                    self.assertIn("apply all active-campaign assignments", guidance)
                    self.assertIn("Preserve stable IDs", guidance)

    def test_installer_supports_all_provider_adapters_idempotently(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            self.init_repository(workspace)
            owner_files = {
                "AGENTS.md": "# Codex owner guidance\n",
                "CLAUDE.md": "# Claude owner guidance\n",
                "GEMINI.md": "# Gemini owner guidance\n",
                ".github/copilot-instructions.md": "# Copilot owner guidance\n",
            }
            for relative, content in owner_files.items():
                path = workspace / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")

            first = run_script(
                "scripts/install_into_workspace.py", str(workspace), "--provider", "all"
            )
            second = run_script(
                "scripts/install_into_workspace.py", str(workspace), "--provider", "all"
            )

            expected = {
                "codex": "AGENTS.md",
                "claude-code": "CLAUDE.md",
                "gemini-cli": "GEMINI.md",
                "github-copilot": ".github/copilot-instructions.md",
                "cursor": ".cursor/rules/tool-shed.mdc",
            }
            for provider_id, relative in expected.items():
                path = workspace / relative
                self.assertTrue(path.is_file(), provider_id)
                text = path.read_text(encoding="utf-8")
                self.assertEqual(text.count("BEGIN TOOL SHED ROUTING GUIDANCE"), 1)
                self.assertEqual(text.count("BEGIN TOOL SHED DISCUSSION GUIDANCE"), 1)
                self.assertEqual(text.count("BEGIN TOOL SHED COORDINATION GUIDANCE"), 1)
                self.assertIn("skills/tool-shed/SKILL.md", text)
                self.assertIn(f"Provider guidance ({provider_id}): updated", first.stdout)
                self.assertNotIn(f"Provider guidance ({provider_id}): updated", second.stdout)
            for relative, content in owner_files.items():
                self.assertTrue((workspace / relative).read_text(encoding="utf-8").startswith(content))
            cursor = (workspace / ".cursor/rules/tool-shed.mdc").read_text(encoding="utf-8")
            self.assertTrue(cursor.startswith("---\n"))
            self.assertIn("alwaysApply: true", cursor)

    def test_installer_guidance_only_does_not_touch_work_inbox_index_or_gitignore(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            self.init_repository(workspace, "# owner ignore\n")
            work = workspace / "work"
            work.mkdir()
            evidence = work / "owner-plan.md"
            evidence.write_text("preserve exactly\n", encoding="utf-8")
            before_work = {
                path.relative_to(work).as_posix(): path.read_bytes()
                for path in work.rglob("*")
                if path.is_file()
            }
            before_ignore = (workspace / ".gitignore").read_bytes()

            result = run_script(
                "scripts/install_into_workspace.py",
                str(workspace),
                "--guidance-only",
                "--provider",
                "codex",
            )

            after_work = {
                path.relative_to(work).as_posix(): path.read_bytes()
                for path in work.rglob("*")
                if path.is_file()
            }
            self.assertEqual(after_work, before_work)
            self.assertEqual((workspace / ".gitignore").read_bytes(), before_ignore)
            self.assertFalse((work / "01-q&a" / "ask.txt").exists())
            self.assertFalse((work / "q&a" / "ask.txt").exists())
            self.assertFalse((work / "index.md").exists())
            self.assertIn("Provider guidance (codex): updated", result.stdout)
            self.assertIn("BEGIN TOOL SHED ROUTING GUIDANCE", (workspace / "AGENTS.md").read_text())

    def test_installer_guidance_only_rejects_symlinked_instruction_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            self.init_repository(workspace)
            external = root / "outside.md"
            original = b"outside owner content\n"
            external.write_bytes(original)
            self.create_symlink_or_skip(workspace / "AGENTS.md", external)

            result = run_script(
                "scripts/install_into_workspace.py",
                str(workspace),
                "--guidance-only",
                "--provider",
                "codex",
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("must not traverse a symlink", result.stderr)
            self.assertEqual(external.read_bytes(), original)

    def test_symlink_fixture_skips_windows_privilege_error_only(self) -> None:
        privilege_error = OSError("A required privilege is not held by the client")
        privilege_error.winerror = 1314
        with mock.patch.object(Path, "symlink_to", side_effect=privilege_error):
            with self.assertRaisesRegex(unittest.SkipTest, "Windows symlink privilege"):
                self.create_symlink_or_skip(Path("link"), Path("target"))

        unrelated_error = OSError("unexpected symlink failure")
        unrelated_error.winerror = 5
        with mock.patch.object(Path, "symlink_to", side_effect=unrelated_error):
            with self.assertRaisesRegex(OSError, "unexpected symlink failure"):
                self.create_symlink_or_skip(Path("link"), Path("target"))

    def test_provider_adapter_conformance_script(self) -> None:
        result = run_script("scripts/check_provider_adapters.py", "--json")
        payload = json.loads(result.stdout)
        providers = {item["provider"]: item for item in payload["providers"]}
        self.assertEqual(
            set(providers),
            {"codex", "claude-code", "gemini-cli", "github-copilot", "cursor"},
        )
        self.assertEqual(providers["codex"]["qualified_level"], 5)
        for provider_id in {"claude-code", "gemini-cli", "github-copilot", "cursor"}:
            self.assertEqual(providers[provider_id]["qualified_level"], 2)
            self.assertTrue(providers[provider_id]["owner_content_preserved"])

    def test_installer_migrates_existing_ask_inbox(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            ask_path = workspace / "work" / "q&a" / "ask.txt"
            ask_path.parent.mkdir(parents=True)
            ask_path.write_text("Keep this question intact.\n", encoding="utf-8")

            result = run_script("scripts/install_into_workspace.py", str(workspace))
            second = run_script("scripts/install_into_workspace.py", str(workspace))

            canonical = workspace / "work" / "01-q&a" / "ask.txt"
            self.assertFalse(ask_path.parent.exists())
            self.assertEqual(canonical.read_text(encoding="utf-8"), "Keep this question intact.\n")
            self.assertIn("Migrated 1 legacy Q&A file(s)", result.stdout)
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

            self.assertIn("Provider guidance (codex): updated", first.stdout)
            self.assertNotIn("stale loop guidance", after_first)
            self.assertIn("command success alone is not outcome success", after_first)
            self.assertIn("# Owner guidance", after_first)
            self.assertIn("# Owner footer", after_first)
            self.assertEqual(after_first.count("BEGIN TOOL SHED EVIDENCE RESPONSE GUIDANCE"), 1)
            self.assertEqual(after_first.count("END TOOL SHED EVIDENCE RESPONSE GUIDANCE"), 1)
            self.assertEqual(after_second, after_first)
            self.assertNotIn("Provider guidance (codex): updated", second.stdout)

    def test_installer_migrates_root_legacy_inbox_and_removes_old_folder(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            canonical = workspace / "work" / "01-q&a" / "ask.txt"
            fallback = workspace / "q&a" / "ask.txt"
            fallback.parent.mkdir(parents=True)
            fallback_text = "Keep fallback content.\n"
            fallback.write_text(fallback_text, encoding="utf-8")

            result = run_script("scripts/install_into_workspace.py", str(workspace))

            self.assertIn("Migrated 1 legacy Q&A file(s)", result.stdout)
            self.assertEqual(canonical.read_text(encoding="utf-8"), fallback_text)
            self.assertFalse(fallback.parent.exists())

    def test_installer_reports_missing_user_codex_skill_and_sync_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            self.init_repository(workspace)
            codex_home = root / "empty codex home"
            environment = {**os.environ, "CODEX_HOME": str(codex_home)}

            result = run_script(
                "scripts/install_into_workspace.py",
                str(workspace),
                "--guidance-only",
                env=environment,
            )

            self.assertIn("Codex skill: missing", result.stdout)
            self.assertIn("--sync-codex-skill", result.stdout)
            self.assertIn("fresh Codex session", result.stdout)
            self.assertFalse((codex_home / "skills" / "tool-shed").exists())

    def test_installer_refuses_modified_or_unmanaged_codex_skill(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            self.init_repository(workspace)
            codex_home = root / "codex home"
            installed = codex_home / "skills" / "tool-shed"
            installed.mkdir(parents=True)
            (installed / "SKILL.md").write_text("locally managed content\n", encoding="utf-8")
            environment = {**os.environ, "CODEX_HOME": str(codex_home)}

            result = run_script(
                "scripts/install_into_workspace.py",
                str(workspace),
                "--guidance-only",
                env=environment,
            )

            self.assertIn("Codex skill: modified-or-unmanaged", result.stdout)
            self.assertIn("synchronization refused", result.stdout)
            self.assertNotIn("Safe Codex skill synchronization:", result.stdout)

    def test_codex_skill_sync_refuses_change_after_safe_inspection(self) -> None:
        from scripts.codex_skill_sync import (
            CodexSkillError,
            fingerprint_skill,
            inspect_codex_skill,
            synchronize_codex_skill,
        )

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            source.mkdir()
            (source / "SKILL.md").write_text("new\n", encoding="utf-8")
            codex_home = root / "codex"
            installed = codex_home / "skills" / "tool-shed"
            installed.mkdir(parents=True)
            (installed / "SKILL.md").write_text("old\n", encoding="utf-8")
            known = [("v1.0.0", fingerprint_skill(installed))]

            with mock.patch.dict(os.environ, {"CODEX_HOME": str(codex_home)}):
                inspection = inspect_codex_skill(source, known)
                (installed / "SKILL.md").write_text("locally changed\n", encoding="utf-8")
                with self.assertRaisesRegex(CodexSkillError, "changed after inspection"):
                    synchronize_codex_skill(source, inspection, "20260809T000000Z")

            self.assertEqual(
                (installed / "SKILL.md").read_text(encoding="utf-8"),
                "locally changed\n",
            )
            self.assertFalse((codex_home / "tool-shed-backups").exists())

    def test_codex_skill_backup_retention_uses_verified_sidecars(self) -> None:
        from scripts.codex_skill_sync import (
            fingerprint_skill,
            inspect_codex_skill,
            synchronize_codex_skill,
        )
        scripts_path = str(ROOT / "scripts")
        sys.path.insert(0, scripts_path)
        try:
            import update_snapshot
        finally:
            sys.path.remove(scripts_path)

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            codex_home = root / "codex"
            installed = codex_home / "skills" / "tool-shed"
            installed.mkdir(parents=True)
            (installed / "SKILL.md").write_text("version 1\n", encoding="utf-8")

            current_backup = None
            with mock.patch.dict(os.environ, {"CODEX_HOME": str(codex_home)}):
                for index in range(2, 5):
                    source = root / f"source-{index}"
                    source.mkdir()
                    (source / "SKILL.md").write_text(
                        f"version {index}\n", encoding="utf-8"
                    )
                    inspection = inspect_codex_skill(
                        source,
                        [(f"v1.0.{index - 1}", fingerprint_skill(installed))],
                    )
                    result = synchronize_codex_skill(
                        source,
                        inspection,
                        f"20260815T00000{index}Z",
                        transaction_id=f"transaction-{index}",
                        target_version=f"1.0.{index}",
                    )
                    current_backup = Path(str(result["backup_path"]))

                unknown = codex_home / "tool-shed-backups" / "owner-copy"
                unknown.mkdir()
                (unknown / "SKILL.md").write_text("owner\n", encoding="utf-8")
                report = update_snapshot.inventory_skill_backups(
                    retention=2,
                    current=current_backup,
                    prune=True,
                    preview=False,
                )

            self.assertEqual(len(report["retained"]), 2)
            self.assertEqual(len(report["pruned"]), 1)
            self.assertEqual(report["protected"], [str(current_backup)])
            self.assertEqual(len(report["unknown"]), 1)
            self.assertTrue(unknown.is_dir())
            self.assertTrue(current_backup.is_dir())

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
            self.assertIn(".tool-shed-backup-manifest.json", names)
            self.assertIn(".gitignore", names)
            self.assertEqual(
                payload["backup_scope"]["excluded"][0]["path"],
                "work/evidence/generated",
            )

    def test_snapshot_backup_scope_excludes_generated_evidence_and_preserves_hard_links(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            release = self.create_test_release(root)
            workspace = self.create_update_workspace(root)
            generated = workspace / "work" / "evidence" / "generated"
            generated.mkdir(parents=True)
            source = generated / "capture.bin"
            source.write_bytes(b"large generated evidence" * 4096)
            linked = generated / "capture-linked.bin"
            try:
                os.link(source, linked)
            except OSError:
                linked.write_bytes(source.read_bytes())
            before = {
                path.relative_to(generated).as_posix(): path.read_bytes()
                for path in generated.rglob("*")
                if path.is_file()
            }

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
            exclusion = next(
                item
                for item in payload["backup_scope"]["excluded"]
                if item["path"] == "work/evidence/generated"
            )
            self.assertEqual(exclusion["file_count"], 2)
            self.assertGreater(exclusion["size_bytes"], 100_000)
            with tarfile.open(payload["backup_path"], "r") as archive:
                names = {member.name.replace("\\", "/") for member in archive.getmembers()}
            self.assertFalse(any(name.startswith("work/evidence/generated/") for name in names))
            self.assertEqual(
                {
                    path.relative_to(generated).as_posix(): path.read_bytes()
                    for path in generated.rglob("*")
                    if path.is_file()
                },
                before,
            )

    def test_release_declared_mutation_expands_generated_backup_scope_with_reason(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            release = self.create_test_release(
                root,
                updater_mutation_paths=[
                    {
                        "path": "work/evidence/generated",
                        "mode": "tree",
                        "reason": "fixture migration rewrites generated evidence metadata",
                    }
                ],
            )
            workspace = self.create_update_workspace(root)
            generated = workspace / "work" / "evidence" / "generated"
            generated.mkdir(parents=True)
            (generated / "capture.bin").write_bytes(b"migration target")

            payload = json.loads(
                run_script(
                    str(ROOT / "scripts" / "update_snapshot.py"),
                    "--workspace",
                    str(workspace),
                    "--repository",
                    str(release),
                    "--json",
                    cwd=workspace,
                ).stdout
            )

            included = next(
                item
                for item in payload["backup_scope"]["included"]
                if item["path"] == "work/evidence/generated"
            )
            self.assertEqual(included["mode"], "tree")
            self.assertIn("release-declared expansion", included["reason"])
            self.assertFalse(
                any(
                    item["path"] == "work/evidence/generated"
                    for item in payload["backup_scope"]["excluded"]
                )
            )
            with tarfile.open(payload["backup_path"], "r") as archive:
                names = {member.name.replace("\\", "/") for member in archive.getmembers()}
            self.assertIn("work/evidence/generated/capture.bin", names)

    def test_snapshot_backup_retention_preview_pruning_unknowns_and_noop(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            releases = []
            for index, version in enumerate(("9.8.7", "9.8.8", "9.8.9"), start=1):
                release_root = root / f"release-{index}"
                release_root.mkdir()
                releases.append(self.create_test_release(release_root, version=version))
            workspace = self.create_update_workspace(root)

            for release in releases[:2]:
                payload = json.loads(
                    run_script(
                        str(ROOT / "scripts" / "update_snapshot.py"),
                        "--workspace",
                        str(workspace),
                        "--repository",
                        str(release),
                        "--no-prune-backups",
                        "--json",
                        cwd=workspace,
                    ).stdout
                )
                self.assertEqual(payload["state"], "installed")
            malformed = workspace / "tool_shed.backup-20260815T010101Z.tar"
            malformed.write_bytes(b"not an updater archive")
            manual = workspace / "tool_shed.backup-manual.tar"
            manual.write_bytes(b"owner backup")
            before_preview = {
                path.name: path.read_bytes()
                for path in workspace.glob("tool_shed.backup-*.tar")
            }

            preview = json.loads(
                run_script(
                    str(ROOT / "scripts" / "update_snapshot.py"),
                    "--workspace",
                    str(workspace),
                    "--backup-retention",
                    "1",
                    "--prune-preview",
                    "--json",
                    cwd=workspace,
                ).stdout
            )
            report = preview["backup_retention"]["workspace"]
            self.assertEqual(preview["state"], "prune-preview")
            self.assertEqual(len(report["retained"]), 1)
            self.assertEqual(len(report["removable"]), 1)
            self.assertEqual(len(report["unknown"]), 2)
            self.assertEqual(report["pruned"], [])
            self.assertEqual(
                {
                    path.name: path.read_bytes()
                    for path in workspace.glob("tool_shed.backup-*.tar")
                },
                before_preview,
            )

            third = json.loads(
                run_script(
                    str(ROOT / "scripts" / "update_snapshot.py"),
                    "--workspace",
                    str(workspace),
                    "--repository",
                    str(releases[2]),
                    "--json",
                    cwd=workspace,
                ).stdout
            )
            retention = third["backup_retention"]["workspace"]
            self.assertEqual(third["state"], "installed")
            self.assertEqual(len(retention["protected"]), 1)
            self.assertEqual(len(retention["retained"]), 2)
            self.assertEqual(len(retention["pruned"]), 1)
            self.assertGreater(retention["reclaimed_bytes"], 0)
            self.assertTrue(malformed.is_file())
            self.assertTrue(manual.is_file())

            verified_before_noop = {
                item["path"] for item in retention["retained"]
            }
            noop = json.loads(
                run_script(
                    str(ROOT / "scripts" / "update_snapshot.py"),
                    "--workspace",
                    str(workspace),
                    "--repository",
                    str(releases[2]),
                    "--json",
                    cwd=workspace,
                ).stdout
            )
            self.assertEqual(noop["state"], "current")
            self.assertEqual(
                {item["path"] for item in noop["backup_retention"]["workspace"]["retained"]},
                verified_before_noop,
            )

    def test_snapshot_failure_after_replacement_restores_scope_and_prunes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            release = self.create_test_release(root)
            workspace = self.create_update_workspace(root)
            generated = workspace / "work" / "evidence" / "generated"
            generated.mkdir(parents=True)
            evidence = generated / "capture.bin"
            evidence.write_bytes(b"preserve excluded bytes")
            before = evidence.read_bytes()

            result = run_script(
                str(ROOT / "scripts" / "update_snapshot.py"),
                "--workspace",
                str(workspace),
                "--repository",
                str(release),
                "--inject-after-replacement-failure",
                "--json",
                cwd=workspace,
                check=False,
            )
            payload = json.loads(result.stdout)

            self.assertNotEqual(result.returncode, 0)
            self.assertTrue(payload["rollback"])
            self.assertNotIn("backup_retention", payload)
            self.assertEqual(evidence.read_bytes(), before)
            self.assertTrue((workspace / "tool_shed" / "old-marker.txt").is_file())
            self.assertEqual(len(list(workspace.glob("tool_shed.backup-*.tar"))), 1)

    def test_backup_retention_policy_and_symlinked_preview_candidate_are_safe(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = self.create_update_workspace(root)
            (workspace / ".tool-shed-policy.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "backup_policy": {"retention": 4},
                    }
                ),
                encoding="utf-8",
            )
            outside = root / "outside.tar"
            outside.write_bytes(b"owner recovery material")
            candidate = workspace / "tool_shed.backup-20260815T020202Z.tar"
            self.create_symlink_or_skip(candidate, outside)
            unsafe = workspace / "tool_shed.backup-20260815T030303Z.tar"
            unsafe_manifest = root / "unsafe-manifest.json"
            unsafe_manifest.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "kind": "tool-shed-workspace-backup",
                        "backup_name": unsafe.name,
                        "created_at": "2026-08-15T03:03:03+00:00",
                        "workspace_sha256": hashlib.sha256(
                            str(workspace.resolve()).encode("utf-8")
                        ).hexdigest(),
                        "included": [
                            {
                                "path": "tool_shed",
                                "mode": "tree",
                                "pre_update_type": "directory",
                            }
                        ],
                        "entries": {"../escape.txt": hashlib.sha256(b"escape").hexdigest()},
                    }
                ),
                encoding="utf-8",
            )
            escape = root / "escape.txt"
            escape.write_bytes(b"escape")
            with tarfile.open(unsafe, "w") as archive:
                archive.add(
                    unsafe_manifest,
                    arcname=".tool-shed-backup-manifest.json",
                )
                archive.add(escape, arcname="../escape.txt")

            preview = json.loads(
                run_script(
                    str(ROOT / "scripts" / "update_snapshot.py"),
                    "--workspace",
                    str(workspace),
                    "--prune-preview",
                    "--json",
                    cwd=workspace,
                ).stdout
            )

            self.assertEqual(
                preview["backup_retention_policy"],
                {"retention": 4, "source": "workspace-policy"},
            )
            unknown = preview["backup_retention"]["workspace"]["unknown"]
            self.assertEqual(len(unknown), 2)
            reasons = {item["reason"] for item in unknown}
            self.assertTrue(any("regular file" in reason for reason in reasons))
            self.assertTrue(any("unsafe backup scope path" in reason for reason in reasons))
            self.assertTrue(candidate.is_symlink())
            self.assertTrue(unsafe.is_file())
            self.assertEqual(outside.read_bytes(), b"owner recovery material")

    def test_snapshot_upgrade_converges_legacy_work_tree_transactionally(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            release = self.create_test_release(
                root,
                version="9.9.0",
                include_provider_adapter=True,
                minimum_updater_protocol=3,
            )
            workspace = self.create_update_workspace(root, version="0.13.0")
            legacy = workspace / "work" / "q&a"
            legacy.mkdir(parents=True)
            (legacy / "ask.txt").write_text("Preserve and migrate this request.\n", encoding="utf-8")
            (legacy / "legacy-request.md").write_text("# Owner request\n", encoding="utf-8")
            before_operator = (workspace / "work" / "operator-data.txt").read_bytes()

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
            self.assertEqual(payload["previous_version"], "0.13.0")
            self.assertTrue(payload["work_preserved"])
            self.assertTrue(payload["work_changed"])
            self.assertTrue(payload["work_converged"])
            self.assertIn("workspace_convergence", payload["post_install"])
            self.assertEqual(
                (workspace / "work" / "operator-data.txt").read_bytes(), before_operator
            )
            self.assertFalse(legacy.exists())
            self.assertEqual(
                (workspace / "work" / "01-q&a" / "ask.txt").read_text(encoding="utf-8"),
                "Preserve and migrate this request.\n",
            )
            self.assertTrue(
                (workspace / "work" / "01-q&a" / "legacy-request.md").is_file()
            )
            self.assertTrue((workspace / "work" / "00-campaigns" / "active").is_dir())
            self.assertTrue((workspace / "work" / "README.md").is_file())
            self.assertTrue((workspace / "work" / "index.json").is_file())
            convergence = json.loads(payload["post_install"]["check_work_tree.py"])
            self.assertTrue(convergence["converged"])
            backup = Path(payload["backup_path"])
            with tarfile.open(backup, "r") as archive:
                names = {member.name.replace("\\", "/") for member in archive.getmembers()}
            self.assertIn("tool_shed/old-marker.txt", names)
            self.assertNotIn("work/operator-data.txt", names)
            self.assertIn("work/q&a/ask.txt", names)
            self.assertIn(".gitignore", names)

    def test_snapshot_upgrade_rolls_back_legacy_work_migration(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            release = self.create_test_release(
                root,
                version="9.9.0",
                include_provider_adapter=True,
                minimum_updater_protocol=3,
            )
            workspace = self.create_update_workspace(root, version="0.13.0")
            legacy = workspace / "work" / "q&a"
            legacy.mkdir(parents=True)
            (legacy / "ask.txt").write_text("Restore this exact request.\n", encoding="utf-8")
            before_work = {
                path.relative_to(workspace / "work").as_posix(): path.read_bytes()
                for path in (workspace / "work").rglob("*")
                if path.is_file()
            }
            before_gitignore = (workspace / ".gitignore").read_bytes()

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
            after_work = {
                path.relative_to(workspace / "work").as_posix(): path.read_bytes()
                for path in (workspace / "work").rglob("*")
                if path.is_file()
            }
            self.assertEqual(after_work, before_work)
            self.assertEqual((workspace / ".gitignore").read_bytes(), before_gitignore)
            self.assertTrue((workspace / "work" / "q&a" / "ask.txt").is_file())
            self.assertFalse((workspace / "work" / "01-q&a").exists())
            self.assertTrue((workspace / "tool_shed" / "old-marker.txt").is_file())

    def test_snapshot_updater_keeps_consecutive_updates_bytecode_free(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first_root = root / "first"
            second_root = root / "second"
            first_root.mkdir()
            second_root.mkdir()
            first_release = self.create_test_release(
                first_root,
                version="9.8.7",
                include_provider_adapter=True,
            )
            second_release = self.create_test_release(
                second_root,
                version="9.8.8",
                include_provider_adapter=True,
            )
            workspace = self.create_update_workspace(root)
            old_cache = workspace / "tool_shed" / "scripts" / "__pycache__"
            old_cache.mkdir(parents=True)
            (old_cache / "old.cpython-311.pyc").write_bytes(b"old bytecode")
            (workspace / "tool_shed" / "scripts" / "legacy.pyo").write_bytes(b"old optimized")
            environment = dict(os.environ)
            environment["CODEX_HOME"] = str(root / "codex")

            def runtime_artifacts(snapshot: Path) -> list[str]:
                return sorted(
                    path.relative_to(snapshot).as_posix()
                    for path in snapshot.rglob("*")
                    if "__pycache__" in path.relative_to(snapshot).parts
                    or path.name.endswith((".pyc", ".pyo"))
                )

            def assert_cache_free_update(
                repository: Path,
            ) -> dict[str, object]:
                result = run_script(
                    str(ROOT / "scripts" / "update_snapshot.py"),
                    "--workspace",
                    str(workspace),
                    "--repository",
                    str(repository),
                    "--provider",
                    "codex",
                    "--json",
                    cwd=workspace,
                    env=environment,
                )
                payload = json.loads(result.stdout)
                self.assertEqual(payload["state"], "installed")
                self.assertEqual(runtime_artifacts(workspace / "tool_shed"), [])
                difference_paths = [
                    path
                    for group in payload["difference"].values()
                    for path in group["paths"]
                ]
                self.assertFalse(
                    any(
                        "__pycache__" in Path(path).parts
                        or path.endswith((".pyc", ".pyo"))
                        for path in difference_paths
                    )
                )
                backup = Path(payload["backup_path"])
                with tarfile.open(backup, "r") as archive:
                    backup_names = [
                        member.name.replace("\\", "/")
                        for member in archive.getmembers()
                    ]
                self.assertFalse(
                    any(
                        "__pycache__" in Path(name).parts
                        or name.endswith((".pyc", ".pyo"))
                        for name in backup_names
                    )
                )
                return payload

            first_payload = assert_cache_free_update(first_release)
            Path(first_payload["backup_path"]).unlink()
            second_payload = assert_cache_free_update(second_release)

            self.assertEqual(first_payload["installed_version"], "9.8.7")
            self.assertEqual(second_payload["installed_version"], "9.8.8")

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

    def test_snapshot_upgrade_replaces_old_skill_and_refreshes_guidance_transactionally(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            release = self.create_test_release(
                root,
                version="9.9.0",
                include_provider_adapter=True,
            )
            workspace = self.create_update_workspace(root, version="9.8.0")
            old_skill = workspace / "tool_shed" / "skills" / "tool-shed"
            old_skill.mkdir(parents=True)
            (old_skill / "SKILL.md").write_text("old always-loaded skill\n" * 400, encoding="utf-8")
            (old_skill / "stale-reference.md").write_text("must not linger\n", encoding="utf-8")
            owner_guidance = "# Owner guidance\n\n"
            old_guidance = """<!-- BEGIN TOOL SHED GENERATED EVIDENCE GUIDANCE -->
old Tool Shed guidance
<!-- END TOOL SHED GENERATED EVIDENCE GUIDANCE -->
"""
            (workspace / "AGENTS.md").write_text(owner_guidance + old_guidance, encoding="utf-8")
            work_before = (workspace / "work" / "operator-data.txt").read_bytes()

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
            self.assertEqual(payload["providers"], ["codex"])
            self.assertEqual((workspace / "work" / "operator-data.txt").read_bytes(), work_before)
            installed_skill = workspace / "tool_shed" / "skills" / "tool-shed"
            self.assertEqual(
                (installed_skill / "SKILL.md").read_bytes(),
                (release / "skills" / "tool-shed" / "SKILL.md").read_bytes(),
            )
            self.assertTrue((installed_skill / "references" / "campaign-routes.md").is_file())
            self.assertTrue((installed_skill / "references" / "maintenance-routes.md").is_file())
            self.assertFalse((installed_skill / "stale-reference.md").exists())
            agents = (workspace / "AGENTS.md").read_text(encoding="utf-8")
            self.assertTrue(agents.startswith(owner_guidance))
            self.assertNotIn("old Tool Shed guidance", agents)
            self.assertEqual(agents.count("BEGIN TOOL SHED ROUTING GUIDANCE"), 1)
            self.assertIn("ts: discuss <topic>", agents)
            self.assertIn("Direct, Guided, Coordinated, or Deep", agents)
            backup = Path(payload["backup_path"])
            with tarfile.open(backup, "r") as archive:
                names = {member.name.replace("\\", "/") for member in archive.getmembers()}
            self.assertIn("tool_shed/skills/tool-shed/stale-reference.md", names)

    def test_snapshot_upgrade_reports_stale_released_user_codex_skill(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            old_files = {"SKILL.md": b"old released Codex skill\n"}
            release = self.create_test_release(
                root,
                version="9.9.0",
                include_provider_adapter=True,
                known_skill_releases={"v9.8.0": old_files},
            )
            self.add_historical_skill_release(release, "9.8.0", old_files)
            workspace = self.create_update_workspace(root, version="9.8.0")
            codex_home = root / "codex home"
            installed = codex_home / "skills" / "tool-shed"
            installed.mkdir(parents=True)
            for relative, content in old_files.items():
                (installed / relative).write_bytes(content)
            environment = {**os.environ, "CODEX_HOME": str(codex_home)}

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
            self.assertEqual(payload["codex_skill"]["state"], "stale-released")
            self.assertEqual(payload["codex_skill"]["matched_release"], "v9.8.0")
            self.assertTrue(payload["codex_skill"]["sync_safe"])
            self.assertIn("--sync-codex-skill", payload["codex_skill"]["sync_command"])
            self.assertEqual((installed / "SKILL.md").read_bytes(), old_files["SKILL.md"])
            guidance = payload["post_install"]["provider_guidance"]
            self.assertIn("Codex skill: stale-released", guidance)
            self.assertIn("Safe Codex skill synchronization:", guidance)
            self.assertNotIn("modified-or-unmanaged", guidance)

            direct = run_script(
                str(workspace / "tool_shed" / "scripts" / "install_into_workspace.py"),
                str(workspace),
                "--guidance-only",
                cwd=workspace,
                env=environment,
            )
            self.assertIn("Codex skill: stale-released", direct.stdout)
            self.assertNotIn("modified-or-unmanaged", direct.stdout)

    def test_snapshot_upgrade_synchronizes_known_user_codex_skill_with_backup(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            release = self.create_test_release(
                root,
                version="9.9.0",
                include_provider_adapter=True,
            )
            old_files = {"SKILL.md": b"old released Codex skill\n"}
            self.add_historical_skill_release(release, "9.8.0", old_files)
            workspace = self.create_update_workspace(root, version="9.8.0")
            codex_home = root / "codex home"
            installed = codex_home / "skills" / "tool-shed"
            installed.mkdir(parents=True)
            for relative, content in old_files.items():
                (installed / relative).write_bytes(content)
            environment = {**os.environ, "CODEX_HOME": str(codex_home)}

            result = run_script(
                str(ROOT / "scripts" / "update_snapshot.py"),
                "--workspace",
                str(workspace),
                "--repository",
                str(release),
                "--sync-codex-skill",
                "--json",
                cwd=workspace,
                env=environment,
            )
            payload = json.loads(result.stdout)

            self.assertEqual(payload["state"], "installed")
            self.assertEqual(payload["codex_skill"]["state"], "current")
            self.assertEqual(payload["codex_skill"]["previous_state"], "stale-released")
            self.assertTrue(payload["codex_skill"]["changed"])
            self.assertTrue(payload["codex_skill"]["restart_required"])
            release_manifest = json.loads(
                (release / "SHED_VERSION.json").read_text(encoding="utf-8")
            )
            skill_prefix = "skills/tool-shed/"
            self.assertEqual(
                {
                    path.relative_to(installed).as_posix(): hashlib.sha256(
                        path.read_bytes()
                    ).hexdigest()
                    for path in installed.rglob("*")
                    if path.is_file()
                },
                {
                    path.removeprefix(skill_prefix): digest
                    for path, digest in release_manifest["content_hashes"].items()
                    if path.startswith(skill_prefix)
                },
            )
            backup = Path(payload["codex_skill"]["backup_path"])
            self.assertEqual((backup / "SKILL.md").read_bytes(), old_files["SKILL.md"])
            self.assertTrue(backup.parent.samefile(codex_home / "tool-shed-backups"))
            backup_manifest = Path(payload["codex_skill"]["backup_manifest_path"])
            self.assertTrue(backup_manifest.is_file())
            skill_retention = payload["backup_retention"]["codex_skill"]
            self.assertEqual(skill_retention["protected"], [str(backup)])
            self.assertEqual(skill_retention["retained"][0]["path"], str(backup))
            self.assertFalse(list((codex_home / "skills").glob("tool-shed.backup-*")))

    def test_snapshot_upgrade_installs_missing_user_codex_skill_without_backup(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            release = self.create_test_release(
                root,
                version="9.9.0",
                include_provider_adapter=True,
            )
            workspace = self.create_update_workspace(root, version="9.8.0")
            codex_home = root / "codex home"
            environment = {**os.environ, "CODEX_HOME": str(codex_home)}

            result = run_script(
                str(ROOT / "scripts" / "update_snapshot.py"),
                "--workspace",
                str(workspace),
                "--repository",
                str(release),
                "--sync-codex-skill",
                "--json",
                cwd=workspace,
                env=environment,
            )
            payload = json.loads(result.stdout)

            installed = codex_home / "skills" / "tool-shed"
            self.assertEqual(payload["codex_skill"]["previous_state"], "missing")
            self.assertEqual(payload["codex_skill"]["state"], "current")
            self.assertIsNone(payload["codex_skill"]["backup_path"])
            self.assertTrue((installed / "SKILL.md").is_file())
            self.assertFalse((codex_home / "tool-shed-backups").exists())

    def test_snapshot_upgrade_refuses_to_overwrite_modified_user_codex_skill(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            release = self.create_test_release(
                root,
                version="9.9.0",
                include_provider_adapter=True,
            )
            old_files = {"SKILL.md": b"old released Codex skill\n"}
            self.add_historical_skill_release(release, "9.8.0", old_files)
            workspace = self.create_update_workspace(root, version="9.8.0")
            codex_home = root / "codex home"
            installed = codex_home / "skills" / "tool-shed"
            installed.mkdir(parents=True)
            modified = b"locally modified Codex skill\n"
            (installed / "SKILL.md").write_bytes(modified)
            environment = {**os.environ, "CODEX_HOME": str(codex_home)}

            result = run_script(
                str(ROOT / "scripts" / "update_snapshot.py"),
                "--workspace",
                str(workspace),
                "--repository",
                str(release),
                "--sync-codex-skill",
                "--json",
                cwd=workspace,
                env=environment,
                check=False,
            )
            payload = json.loads(result.stdout)

            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(payload["state"], "failed")
            self.assertEqual(payload["codex_skill"]["state"], "modified-or-unmanaged")
            self.assertIn("unsafe", payload["error"])
            self.assertEqual((installed / "SKILL.md").read_bytes(), modified)
            self.assertTrue((workspace / "tool_shed" / "old-marker.txt").is_file())
            self.assertFalse(list(workspace.glob("tool_shed.backup-*.tar")))

    def test_snapshot_upgrade_rolls_back_codex_skill_and_snapshot_on_sync_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            release = self.create_test_release(
                root,
                version="9.9.0",
                include_provider_adapter=True,
            )
            old_files = {"SKILL.md": b"old released Codex skill\n"}
            self.add_historical_skill_release(release, "9.8.0", old_files)
            workspace = self.create_update_workspace(root, version="9.8.0")
            codex_home = root / "codex home"
            installed = codex_home / "skills" / "tool-shed"
            installed.mkdir(parents=True)
            for relative, content in old_files.items():
                (installed / relative).write_bytes(content)
            environment = {**os.environ, "CODEX_HOME": str(codex_home)}

            result = run_script(
                str(ROOT / "scripts" / "update_snapshot.py"),
                "--workspace",
                str(workspace),
                "--repository",
                str(release),
                "--sync-codex-skill",
                "--inject-codex-sync-failure",
                "--json",
                cwd=workspace,
                env=environment,
                check=False,
            )
            payload = json.loads(result.stdout)

            self.assertNotEqual(result.returncode, 0)
            self.assertTrue(payload["rollback"])
            self.assertIn("injected Codex skill verification failure", payload["error"])
            self.assertEqual((installed / "SKILL.md").read_bytes(), old_files["SKILL.md"])
            self.assertTrue((workspace / "tool_shed" / "old-marker.txt").is_file())
            self.assertFalse((codex_home / "tool-shed-backups").exists())

    def test_snapshot_upgrade_rolls_back_provider_guidance_with_old_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            release = self.create_test_release(
                root,
                version="9.9.0",
                include_provider_adapter=True,
            )
            workspace = self.create_update_workspace(root, version="9.8.0")
            snapshot_before = {
                path.relative_to(workspace / "tool_shed").as_posix(): path.read_bytes()
                for path in (workspace / "tool_shed").rglob("*")
                if path.is_file()
            }
            original_agents = b"# Owner\n\n<!-- BEGIN TOOL SHED GENERATED EVIDENCE GUIDANCE -->\nold\n<!-- END TOOL SHED GENERATED EVIDENCE GUIDANCE -->\n"
            (workspace / "AGENTS.md").write_bytes(original_agents)

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
            self.assertEqual((workspace / "AGENTS.md").read_bytes(), original_agents)
            snapshot_after = {
                path.relative_to(workspace / "tool_shed").as_posix(): path.read_bytes()
                for path in (workspace / "tool_shed").rglob("*")
                if path.is_file()
            }
            self.assertEqual(snapshot_after, snapshot_before)
            self.assertTrue((workspace / "tool_shed" / "old-marker.txt").is_file())
            self.assertFalse((workspace / "tool_shed" / "skills").exists())

    def test_snapshot_upgrade_rejects_symlinked_provider_guidance_before_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            release = self.create_test_release(
                root,
                version="9.9.0",
                include_provider_adapter=True,
            )
            workspace = self.create_update_workspace(root, version="9.8.0")
            external = root / "outside-agents.md"
            original = b"<!-- BEGIN TOOL SHED GENERATED EVIDENCE GUIDANCE -->\noutside\n"
            external.write_bytes(original)
            self.create_symlink_or_skip(workspace / "AGENTS.md", external)

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
            self.assertIn("must not traverse a symlink", payload["error"])
            self.assertFalse(payload["rollback"])
            self.assertEqual(external.read_bytes(), original)
            self.assertTrue((workspace / "tool_shed" / "old-marker.txt").is_file())
            self.assertFalse(list(workspace.glob("tool_shed.backup-*.tar")))

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
            phases = (
                "clone/fetch",
                "manifest verification",
                "release validation",
                "staging",
                "post-install validation",
                "completion",
            )
            positions = [result.stderr.index(f"Tool Shed update: {phase}") for phase in phases]
            self.assertEqual(positions, sorted(positions))

    def test_native_launcher_runtime_fallback_installs_and_updates_workspaces(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fallback_bin = root / "fallback runtime"
            fallback_bin.mkdir()
            git_executable = shutil.which("git")
            self.assertIsNotNone(git_executable)
            fallback_path_entries = [str(fallback_bin)]

            if os.name == "nt":
                shell_executable = shutil.which("pwsh") or shutil.which("powershell")
                if shell_executable is None:
                    self.skipTest("PowerShell is unavailable")
                (fallback_bin / "python.cmd").write_text(
                    f'@echo off\r\n"{sys.executable}" %*\r\n',
                    encoding="utf-8",
                    newline="",
                )
                fallback_path_entries.append(str(Path(git_executable).parent))
                launcher = [
                    shell_executable,
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(ROOT / "scripts" / "update-tool-shed.ps1"),
                ]
                self.assertIsNone(shutil.which("py", path=str(fallback_bin)))
            else:
                dirname_executable = shutil.which("dirname")
                self.assertIsNotNone(dirname_executable)
                for name, executable in (
                    ("python", sys.executable),
                    ("git", git_executable),
                    ("dirname", dirname_executable),
                ):
                    (fallback_bin / name).symlink_to(executable)
                launcher = ["/bin/sh", str(ROOT / "scripts" / "update-tool-shed.sh")]
                self.assertIsNone(shutil.which("python3", path=str(fallback_bin)))

            self.assertIsNotNone(shutil.which("python", path=str(fallback_bin)))
            environment = dict(os.environ)
            environment["PATH"] = os.pathsep.join(fallback_path_entries)
            environment["CODEX_HOME"] = str(root / "codex home")

            for expected_mode in ("new-installation", "existing-update"):
                with self.subTest(mode=expected_mode):
                    case_root = root / expected_mode
                    case_root.mkdir()
                    release = self.create_test_release(case_root)
                    if expected_mode == "existing-update":
                        workspace = self.create_update_workspace(case_root)
                    else:
                        workspace = case_root / "new workspace with spaces"
                        workspace.mkdir()
                        self.init_repository(
                            workspace,
                            "/tool_shed/\n/tool_shed.backup-*.tar\n",
                        )
                        (workspace / "README.md").write_text(
                            "project\n", encoding="utf-8"
                        )
                        subprocess.run(
                            ["git", "config", "user.name", "Tool Shed Tests"],
                            cwd=workspace,
                            check=True,
                        )
                        subprocess.run(
                            ["git", "config", "user.email", "tests@example.invalid"],
                            cwd=workspace,
                            check=True,
                        )
                        subprocess.run(["git", "add", "."], cwd=workspace, check=True)
                        subprocess.run(
                            ["git", "commit", "-q", "-m", "Workspace"],
                            cwd=workspace,
                            check=True,
                        )

                    result = subprocess.run(
                        [
                            *launcher,
                            "--workspace",
                            str(workspace),
                            "--repository",
                            str(release),
                            "--json",
                        ],
                        cwd=workspace,
                        text=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        check=False,
                        env=environment,
                    )
                    self.assertEqual(
                        result.returncode,
                        0,
                        f"launcher stdout:\n{result.stdout}\nlauncher stderr:\n{result.stderr}",
                    )
                    payload = json.loads(result.stdout)

                    self.assertEqual(payload["mode"], expected_mode)
                    self.assertEqual(payload["state"], "installed")
                    self.assertEqual(payload["installed_version"], "9.8.7")
                    self.assertTrue((workspace / "tool_shed" / "SHED_VERSION.json").is_file())
                    if expected_mode == "existing-update":
                        self.assertTrue(payload["work_preserved"])
                        self.assertEqual(
                            (workspace / "work" / "operator-data.txt").read_text(
                                encoding="utf-8"
                            ),
                            "preserve exactly\n",
                        )

    def test_snapshot_updater_times_out_release_validation_before_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            release = self.create_test_release(root, validation_delay=1)
            workspace = self.create_update_workspace(root)
            original = (workspace / "tool_shed" / "old-marker.txt").read_bytes()

            result = run_script(
                str(ROOT / "scripts" / "update_snapshot.py"),
                "--workspace",
                str(workspace),
                "--repository",
                str(release),
                "--validation-timeout",
                "0.05",
                "--json",
                cwd=workspace,
                check=False,
            )
            payload = json.loads(result.stdout)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("timed out after 0.05 seconds", payload["error"])
            self.assertIn("increase --validation-timeout", payload["error"])
            self.assertIn("Tool Shed update: release validation", result.stderr)
            self.assertEqual((workspace / "tool_shed" / "old-marker.txt").read_bytes(), original)
            self.assertFalse(list(workspace.glob("tool_shed.backup-*.tar")))

    def test_snapshot_subprocess_timeout_names_recovery_option(self) -> None:
        scripts_path = str(ROOT / "scripts")
        sys.path.insert(0, scripts_path)
        try:
            import update_snapshot
        finally:
            sys.path.remove(scripts_path)

        with mock.patch.object(
            update_snapshot.subprocess,
            "run",
            side_effect=subprocess.TimeoutExpired(["git", "clone"], 0.01),
        ):
            with self.assertRaisesRegex(
                update_snapshot.UpdateError,
                r"increase --network-timeout.*git clone",
            ):
                update_snapshot.run(
                    ["git", "clone"],
                    timeout=0.01,
                    timeout_option="--network-timeout",
                )

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

    def test_installer_migrates_colliding_inboxes_without_overwriting(self) -> None:
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

            target = workspace / "work" / "01-q&a"
            self.assertIn("Migrated 2 legacy Q&A file(s)", result.stdout)
            self.assertEqual((target / "ask.txt").read_text(encoding="utf-8"), canonical_text)
            self.assertEqual(
                (target / "ask.legacy-root-q-and-a.txt").read_text(encoding="utf-8"),
                fallback_text,
            )
            self.assertFalse(canonical.parent.exists())
            self.assertFalse(fallback.parent.exists())

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

            self.assertIn("Provider guidance (codex): updated", first.stdout)
            self.assertNotIn("stale canonical-only guidance", after_first)
            self.assertIn("work/01-q&a/ask.txt", after_first)
            self.assertIn("`work/q&a/ask.txt` only as a pre-migration legacy fallback", after_first)
            self.assertIn("# Owner guidance", after_first)
            self.assertIn("# Owner footer", after_first)
            self.assertEqual(after_first.count("BEGIN TOOL SHED Q&A GUIDANCE"), 1)
            self.assertEqual(after_first.count("END TOOL SHED Q&A GUIDANCE"), 1)
            self.assertEqual(after_second, after_first)
            self.assertNotIn("Provider guidance (codex): updated", second.stdout)

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
            self.assertTrue((workspace / "work" / "focus-areas.md").exists())
            payload = json.loads((workspace / "work" / "index.json").read_text(encoding="utf-8"))
            paths = {item["path"] for item in payload["artifacts"]}
            self.assertIn("work/maps/map-index-test.md", paths)
            self.assertIn("work/inventories/inventory-index-test-surfaces.md", paths)
            self.assertIn("work/focus-areas.md", paths)
            readme = (workspace / "work" / "README.md").read_text(encoding="utf-8")
            self.assertIn("complete_workpackage.py", readme)
            review = run_script(
                "scripts/review_work_state.py",
                "--workspace",
                str(workspace),
                "--strict",
                "--json",
            )
            review_payload = json.loads(review.stdout)
            self.assertFalse(
                any(
                    item["path"] == "work/focus-areas.md"
                    for item in review_payload["findings"]
                )
            )

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
