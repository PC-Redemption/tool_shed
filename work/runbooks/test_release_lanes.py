from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
RUNBOOKS = ROOT / "work" / "runbooks"
for path in (SCRIPTS, RUNBOOKS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import release_lanes  # noqa: E402
from project_identity import binding_token  # noqa: E402


class ReleaseLaneTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temporary.name)
        subprocess.run(["git", "init", "--quiet"], cwd=self.workspace, check=True)
        subprocess.run(["git", "config", "user.name", "Tool Shed Tests"], cwd=self.workspace, check=True)
        subprocess.run(
            ["git", "config", "user.email", "tests@example.invalid"],
            cwd=self.workspace,
            check=True,
        )
        identity = {
            "schema_version": 1,
            "project_id": str(uuid.uuid4()),
            "project_name": "release-lane-fixture",
        }
        for relative, content in {
            "work/tool-shed-project.json": json.dumps(identity, indent=2, sort_keys=True) + "\n",
            "product.txt": "candidate\n",
        }.items():
            path = self.workspace / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=self.workspace, check=True)
        subprocess.run(["git", "commit", "--quiet", "-m", "candidate"], cwd=self.workspace, check=True)
        self.candidate = release_lanes.resolve_commit(self.workspace, "HEAD")
        self.binding = binding_token(self.workspace, operation=release_lanes.OPERATION)
        self.path, self.manifest = release_lanes.initialize(
            self.workspace,
            release_id="cohort-1",
            supplied_path=None,
            project_binding=self.binding,
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _bind(self) -> None:
        self.manifest = release_lanes.bind_candidate(
            self.workspace,
            self.manifest,
            commitish=self.candidate,
            expected=release_lanes.digest(self.manifest),
            project_binding=self.binding,
            path=self.path,
        )

    def _record(self, lane: str, stage: str, *, status: str = "verified", commit: str | None = None) -> None:
        self.manifest = release_lanes.record_lane(
            self.workspace,
            self.manifest,
            lane=lane,
            stage=stage,
            status=status,
            source_commitish=commit or self.candidate,
            artifact=f"{lane}-{stage}-artifact",
            evidence=[f"test:{lane}-{stage}"],
            actor="test-suite",
            authorization_ref="owner:test" if status == "manual-closed" else None,
            reason="accepted exception" if status == "manual-closed" else None,
            expected=release_lanes.digest(self.manifest),
            project_binding=self.binding,
            path=self.path,
        )

    def test_open_child_lane_keeps_work3_open(self) -> None:
        self._bind()
        self._record("web", "development")
        self._record("windows", "development")
        status = release_lanes.report(self.workspace, self.manifest, phase="work3")
        self.assertFalse(status["ready"])
        self.assertEqual(status["blockers"], ["linux.development is open"])

    def test_generic_status_keeps_release_open_until_production_children_close(self) -> None:
        self._bind()
        for lane in release_lanes.LANES:
            self._record(lane, "development")
        status = release_lanes.report(self.workspace, self.manifest)
        self.assertFalse(status["ready"])
        self.assertEqual(
            status["blockers"],
            [
                "web.production is open",
                "windows.production is open",
                "linux.production is open",
            ],
        )

    def test_verified_and_manual_children_allow_work3(self) -> None:
        self._bind()
        self._record("web", "development")
        self._record("windows", "development", status="manual-closed")
        self._record("linux", "development")
        status = release_lanes.report(self.workspace, self.manifest, phase="work3")
        self.assertTrue(status["ready"])
        self.assertEqual(status["blockers"], [])

    def test_work5_requires_every_production_lane_at_the_release_commit(self) -> None:
        self._bind()
        for lane in release_lanes.LANES:
            self._record(lane, "development")
        (self.workspace / "release.txt").write_text("release\n", encoding="utf-8")
        subprocess.run(["git", "add", "release.txt"], cwd=self.workspace, check=True)
        subprocess.run(["git", "commit", "--quiet", "-m", "release"], cwd=self.workspace, check=True)
        release = release_lanes.resolve_commit(self.workspace, "HEAD")
        for lane in ("web", "windows"):
            self._record(lane, "production", commit=release)
        blocked = release_lanes.report(
            self.workspace, self.manifest, phase="work5-complete", release_commit=release
        )
        self.assertFalse(blocked["ready"])
        self.assertIn("linux.production is open", blocked["blockers"])
        self._record("linux", "production", commit=release)
        ready = release_lanes.report(
            self.workspace, self.manifest, phase="work5-complete", release_commit=release
        )
        self.assertTrue(ready["ready"])

    def test_stale_write_and_cross_workspace_binding_fail(self) -> None:
        self._bind()
        stale = release_lanes.digest(self.manifest)
        self._record("web", "development")
        with self.assertRaisesRegex(release_lanes.ReleaseLaneError, "STALE_WRITE"):
            release_lanes.record_lane(
                self.workspace,
                self.manifest,
                lane="windows",
                stage="development",
                status="verified",
                source_commitish=self.candidate,
                artifact="windows-dev",
                evidence=["test:windows"],
                actor="test-suite",
                authorization_ref=None,
                reason=None,
                expected=stale,
                project_binding=self.binding,
                path=self.path,
            )
        with self.assertRaisesRegex(ValueError, "WORKSPACE_MISMATCH"):
            release_lanes.record_lane(
                self.workspace,
                self.manifest,
                lane="windows",
                stage="development",
                status="verified",
                source_commitish=self.candidate,
                artifact="windows-dev",
                evidence=["test:windows"],
                actor="test-suite",
                authorization_ref=None,
                reason=None,
                expected=release_lanes.digest(self.manifest),
                project_binding="wrong-binding",
                path=self.path,
            )

    def test_candidate_rebinding_and_path_escape_fail_closed(self) -> None:
        self._bind()
        (self.workspace / "other.txt").write_text("other\n", encoding="utf-8")
        subprocess.run(["git", "add", "other.txt"], cwd=self.workspace, check=True)
        subprocess.run(["git", "commit", "--quiet", "-m", "other"], cwd=self.workspace, check=True)
        with self.assertRaisesRegex(release_lanes.ReleaseLaneError, "different candidate"):
            release_lanes.bind_candidate(
                self.workspace,
                self.manifest,
                commitish="HEAD",
                expected=release_lanes.digest(self.manifest),
                project_binding=self.binding,
                path=self.path,
            )
        with self.assertRaisesRegex(release_lanes.ReleaseLaneError, "must remain under"):
            release_lanes.manifest_path(self.workspace, "cohort-1", "outside.json")

    def test_existing_write_lock_fails_closed(self) -> None:
        lock = self.path.with_name(f".{self.path.name}.lock")
        lock.write_text("held by fixture\n", encoding="utf-8")
        with self.assertRaisesRegex(release_lanes.ReleaseLaneError, "CONCURRENT_WRITE"):
            release_lanes.bind_candidate(
                self.workspace,
                self.manifest,
                commitish=self.candidate,
                expected=release_lanes.digest(self.manifest),
                project_binding=self.binding,
                path=self.path,
            )
        self.assertTrue(lock.is_file())


if __name__ == "__main__":
    unittest.main()
