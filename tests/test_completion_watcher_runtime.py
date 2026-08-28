from __future__ import annotations

import contextlib
import io
import os
import json
import sys
import unittest
import tempfile
from unittest import mock
from datetime import timedelta
from pathlib import Path

from scripts import completion_watcher as cw


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "completion-watcher-v1" / "contract-cases.json"


def _load_fixture() -> dict[str, object]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


class CompletionWatcherRuntimeTests(unittest.TestCase):
    def _new_state_root(self) -> Path:
        tmp_root = Path(tempfile.mkdtemp(prefix="cw-runtime-"))
        os.chmod(tmp_root, 0o700)
        self.addCleanup(lambda: self._cleanup_tree(tmp_root))
        state_root = tmp_root / "state"
        state_root.mkdir(mode=0o700)
        return state_root

    def _cleanup_tree(self, root: Path) -> None:
        if not root.exists():
            return
        for path in sorted(root.rglob("*"), reverse=True):
            if path.is_file():
                try:
                    path.unlink()
                except FileNotFoundError:
                    pass
            else:
                try:
                    path.rmdir()
                except FileNotFoundError:
                    pass
                except OSError:
                    pass
        try:
            root.rmdir()
        except FileNotFoundError:
            pass

    def _descriptor(self, watch_id: str | None = None) -> dict[str, object]:
        fixture = _load_fixture()
        descriptor = json.loads(json.dumps(fixture["descriptor"]))
        if watch_id is not None:
            descriptor["watch_id"] = watch_id
        return descriptor

    def _run_main(self, *argv: str) -> tuple[int, str]:
        out = io.StringIO()
        err = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = cw.main(list(argv))
        output = out.getvalue() + err.getvalue()
        return rc, output.strip()

    def test_arm_status_cancel_workflow(self) -> None:
        state_root = self._new_state_root()
        watch_id = "123e4567-e89b-42d3-a456-426614174100"
        state_root.mkdir(parents=True, exist_ok=True)
        descriptor = self._descriptor(watch_id)
        descriptor_path = state_root / "descriptor.json"
        descriptor_path.write_text(json.dumps(descriptor), encoding="utf-8")

        rc, output = self._run_main(
            "--state-root",
            str(state_root),
            "--json",
            "arm",
            str(descriptor_path),
        )
        self.assertEqual(rc, 0)
        data = json.loads(output)
        self.assertEqual(data["watch_id"], watch_id)

        paths = cw.WatcherPaths.from_root(state_root)
        self.assertTrue(paths.pending_path(watch_id).is_file())

        rc, output = self._run_main("--state-root", str(state_root), "--json", "status")
        self.assertEqual(rc, 0)
        status = json.loads(output)
        self.assertIn(watch_id, status["pending"])

        rc, _ = self._run_main("--state-root", str(state_root), "--json", "cancel", watch_id)
        self.assertEqual(rc, 0)
        self.assertTrue(paths.cancel_path(watch_id).is_file())

        rc, _ = self._run_main("--state-root", str(state_root), "--json", "retire", watch_id)
        self.assertEqual(rc, 0)

    def test_terminal_event_is_idempotent(self) -> None:
        state_root = self._new_state_root()
        state_root.mkdir(parents=True, exist_ok=True)
        paths = cw.WatcherPaths.from_root(state_root)
        cw._ensure_state_layout(paths)
        cw._ensure_format(paths)
        descriptor = self._descriptor("123e4567-e89b-42d3-a456-426614174200")
        occurred = cw._utcnow()

        with mock.patch.object(
            cw,
            "_utcnow",
            side_effect=[occurred, occurred + timedelta(seconds=1)],
        ):
            first = cw._upsert_terminal_event(
                paths,
                descriptor,
                terminal_class="SATISFIED",
                reason_code="TARGET_SUCCEEDED",
                occurred_at=occurred,
                detail="done",
            )
            second = cw._upsert_terminal_event(
                paths,
                descriptor,
                terminal_class="SATISFIED",
                reason_code="TARGET_SUCCEEDED",
                occurred_at=occurred,
                detail="done",
            )
        self.assertEqual(first, second)
        event_id = cw.terminal_event_id(descriptor["watch_id"])
        event_path = paths.outbox_pending_dir / f"{event_id}.json"
        payload = json.loads(event_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["event_id"], event_id)
        self.assertEqual(payload["terminal_class"], "SATISFIED")

        with self.assertRaises(ValueError):
            cw._upsert_terminal_event(
                paths,
                descriptor,
                terminal_class="SATISFIED",
                reason_code="TARGET_FAILED",
                occurred_at=cw._utcnow(),
                detail="different",
            )

    def test_windows_directory_fsync_is_skipped(self) -> None:
        state_root = self._new_state_root()
        with mock.patch.object(cw.os, "name", "nt"), mock.patch.object(
            cw.os, "open", side_effect=AssertionError("directory open must be skipped")
        ):
            cw._fsync_fd(state_root)

    def test_ensure_runner_respects_existing_lock(self) -> None:
        state_root = self._new_state_root()
        state_root.mkdir(parents=True, exist_ok=True)
        descriptor = self._descriptor("123e4567-e89b-42d3-a456-426614174300")
        descriptor["created_at"] = cw._fmt_ts(cw._utcnow())
        descriptor["checker"] = {
            "argv": [
                sys.executable,
                "-c",
                (
                    "import json;"
                    "print(json.dumps({"
                    "'schema_version': 1, 'state': 'SATISFIED', 'observed_at': '2026-08-18T23:02:00Z',"
                    " 'target': {'kind': 'qualification-run', 'id': 'build-8472', 'generation': 'attempt-1'},"
                    " 'reason_code': 'TARGET_SUCCEEDED', 'identity_confirmed': True, 'target_exists': True,"
                    " 'authoritative_nonterminal': False})"
                    ")"
                ),
            ],
            "timeout_seconds": 15,
        }
        paths = cw.WatcherPaths.from_root(state_root)
        cw._ensure_state_layout(paths)
        cw._ensure_format(paths)
        record = cw._make_watch_record(descriptor)
        record["due_at"] = cw._fmt_ts(cw._utcnow() - timedelta(seconds=61))
        cw._write_json_atomically(paths.pending_path(descriptor["watch_id"]), record, tmp_dir=paths.tmp_dir)

        with cw.SingletonLock(paths.singleton_lock) as lock:
            self.assertTrue(lock.acquire(non_blocking=True))
            rc, output = self._run_main(
                "--state-root",
                str(state_root),
                "--json",
                "ensure-runner",
            )
            self.assertEqual(rc, 0)
            self.assertIn("already_running", output)
