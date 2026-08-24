from __future__ import annotations

import json
import multiprocessing
import os
import stat
import tempfile
import unittest
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

from scripts.codex_qualification_cache import (
    QualificationCache,
    QualificationCacheError,
    QualificationIdentity,
    build_qualification_identity,
    default_qualification_cache_path,
)


def _identity(**changes: str) -> QualificationIdentity:
    values = {
        "executable": "/opt/codex/bin/codex",
        "executable_sha256": "exe-a",
        "codex_version": "0.200.0-alpha.1",
        "protocol_source": "generated-schema",
        "protocol_sha256": "protocol-a",
        "qualification_policy_sha256": "qualification-a",
        "model_policy_sha256": "model-a",
        "platform": "linux-x86_64",
    }
    values.update(changes)
    return QualificationIdentity(**values)


def _concurrent_store(cache_path: str, index: int) -> None:
    cache = QualificationCache(Path(cache_path))
    cache.store(
        _identity(
            executable=f"/opt/codex/bin/codex-{index}",
            executable_sha256=f"exe-{index}",
        ),
        state="qualified",
        outcome="qualified",
    )


class QualificationCacheTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.cache_path = self.root / "codex-state" / "qualifications.json"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_default_cache_is_user_local_and_tool_shed_paths_are_rejected(self) -> None:
        expected = self.root / "codex-home" / "tool-shed" / "dirty-read-qualifications.json"
        self.assertEqual(
            default_qualification_cache_path({"CODEX_HOME": str(self.root / "codex-home")}),
            expected,
        )
        with self.assertRaisesRegex(QualificationCacheError, "outside Tool Shed"):
            QualificationCache(
                Path(__file__).resolve().parents[1] / "qualification-cache.json"
            )
        with self.assertRaisesRegex(QualificationCacheError, "installed Tool Shed"):
            QualificationCache(self.root / "snapshot" / "tool_shed" / "cache.json")

    def test_store_is_sanitized_and_permission_restricted(self) -> None:
        cache = QualificationCache(self.cache_path)
        cache.store(
            _identity(),
            state="qualified",
            outcome="qualified_with_blockers",
            safe_blockers=["cancellation_acknowledgement"],
        )
        raw = self.cache_path.read_text(encoding="utf-8")
        for prohibited in (
            "sentinel-secret",
            "prompt text",
            "response text",
            "credential",
        ):
            self.assertNotIn(prohibited, raw)
        payload = json.loads(raw)
        record = next(iter(payload["records"].values()))
        self.assertEqual(
            set(record),
            {
                "identity",
                "state",
                "outcome",
                "safe_blockers",
                "recorded_at",
                "recorded_epoch",
            },
        )
        if os.name == "posix":
            self.assertEqual(stat.S_IMODE(self.cache_path.stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(self.cache_path.parent.stat().st_mode), 0o700)

    def test_malformed_partial_and_stale_success_entries_are_ignored(self) -> None:
        self.cache_path.parent.mkdir(parents=True)
        self.cache_path.write_text("{partial", encoding="utf-8")
        cache = QualificationCache(self.cache_path, now=lambda: 200.0)
        self.assertEqual(cache.lookup(_identity()).invalidation_reason, "malformed-cache")

        self.cache_path.write_text(
            json.dumps({"schema_version": 1, "records": {_identity().key: {"state": "qualified"}}}),
            encoding="utf-8",
        )
        self.assertEqual(cache.lookup(_identity()).invalidation_reason, "malformed-entry")

        old = QualificationCache(self.cache_path, max_age_seconds=10, now=lambda: 100.0)
        old.store(_identity(), state="qualified", outcome="qualified")
        stale = QualificationCache(self.cache_path, max_age_seconds=10, now=lambda: 111.0)
        self.assertEqual(stale.lookup(_identity()).invalidation_reason, "stale")

    def test_reviewed_unsafe_entry_does_not_expire_but_can_be_requalified(self) -> None:
        old = QualificationCache(self.cache_path, max_age_seconds=10, now=lambda: 100.0)
        old.store(_identity(), state="unsafe_denied", outcome="unqualified_fatal")
        current = QualificationCache(self.cache_path, max_age_seconds=10, now=lambda: 999.0)
        self.assertEqual(current.lookup(_identity()).record["state"], "unsafe_denied")
        current.store(_identity(), state="qualified", outcome="qualified")
        self.assertEqual(current.lookup(_identity()).record["state"], "qualified")

    def test_each_relevant_fingerprint_change_invalidates_the_entry(self) -> None:
        base = _identity()
        QualificationCache(self.cache_path).store(
            base, state="qualified", outcome="qualified"
        )
        cases = {
            "foreign-platform": {"platform": "windows-amd64"},
            "codex-version-changed": {"codex_version": "0.201.0"},
            "executable-changed": {"executable_sha256": "exe-b"},
            "protocol-changed": {"protocol_sha256": "protocol-b"},
            "qualification-policy-changed": {
                "qualification_policy_sha256": "qualification-b"
            },
            "model-policy-changed": {"model_policy_sha256": "model-b"},
        }
        for reason, changes in cases.items():
            with self.subTest(reason=reason):
                lookup = QualificationCache(self.cache_path).lookup(_identity(**changes))
                self.assertEqual(lookup.status, "miss")
                self.assertEqual(lookup.invalidation_reason, reason)

    def test_identity_uses_generated_schema_or_sanitized_runtime_probe(self) -> None:
        config = self.root / "config.json"
        policy = self.root / "policy.json"
        config.write_text(json.dumps({"qualification": {"minimum": "0.146.0"}}))
        policy.write_text(json.dumps({"roles": {"planning": "model"}}))
        generated = self.root / "generated-codex"
        generated.write_text("generated fixture", encoding="utf-8")

        def generate_schema(command: list[str], **_: object) -> CompletedProcess[str]:
            out = Path(command[command.index("--out") + 1])
            (out / "schema.json").write_text(
                json.dumps({"protocol": 2}), encoding="utf-8"
            )
            return CompletedProcess(command, 0, "", "")

        with patch(
            "scripts.codex_qualification_cache.subprocess.run",
            side_effect=generate_schema,
        ):
            generated_identity = build_qualification_identity(
                executable=generated,
                codex_version="0.200.0",
                config_path=config,
                model_policy_path=policy,
            )
        self.assertEqual(generated_identity.protocol_source, "generated-schema")

        fallback = self.root / "fallback-codex"
        fallback.write_text("fallback fixture", encoding="utf-8")
        with patch(
            "scripts.codex_qualification_cache.subprocess.run",
            side_effect=[
                CompletedProcess([], 1, "", "schema unavailable"),
                CompletedProcess([], 0, "app-server protocol help\n", ""),
            ],
        ):
            fallback_identity = build_qualification_identity(
                executable=fallback,
                codex_version="0.200.0",
                config_path=config,
                model_policy_path=policy,
            )
        self.assertEqual(fallback_identity.protocol_source, "runtime-probe")
        self.assertNotIn("app-server protocol help", fallback_identity.protocol_sha256)

    def test_concurrent_processes_preserve_every_record(self) -> None:
        context = multiprocessing.get_context("spawn")
        processes = [
            context.Process(target=_concurrent_store, args=(str(self.cache_path), index))
            for index in range(4)
        ]
        for process in processes:
            process.start()
        for process in processes:
            process.join(15)
            self.assertEqual(process.exitcode, 0)
        payload = json.loads(self.cache_path.read_text(encoding="utf-8"))
        self.assertEqual(len(payload["records"]), 4)


if __name__ == "__main__":
    unittest.main()
