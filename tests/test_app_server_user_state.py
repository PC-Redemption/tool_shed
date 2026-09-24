from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from scripts.app_server_user_state import (
    AppServerDispatchLifecycle,
    AppServerEventStore,
    AppServerOwnerProfileStore,
    AppServerPreferenceStore,
    AppServerUserStateError,
    default_app_server_event_path,
    default_app_server_preference_path,
    default_app_server_profile_path,
    record_app_server_event_best_effort,
    PREFERENCE_SCHEMA_VERSION,
)


class AppServerUserStateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.path = self.root / "codex" / "tool-shed" / "app-server-preference.json"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_default_path_uses_codex_home(self) -> None:
        self.assertEqual(
            self.path,
            default_app_server_preference_path({"CODEX_HOME": str(self.root / "codex")}),
        )

    def test_default_paths_use_validation_state_root_without_codex_home_pollution(self) -> None:
        environment = {
            "CODEX_HOME": str(self.root / "real-codex"),
            "TOOL_SHED_STATE_ROOT": str(self.root / "isolated"),
        }
        isolated = self.root / "isolated"
        self.assertEqual(
            isolated / "tool-shed" / "app-server-preference.json",
            default_app_server_preference_path(environment),
        )
        self.assertEqual(
            isolated / "tool-shed" / "app-server-events.jsonl",
            default_app_server_event_path(environment),
        )
        self.assertEqual(
            isolated / "tool-shed-profile" / "app-server-owner-profile.json",
            default_app_server_profile_path(environment),
        )

    def test_missing_and_malformed_state_fail_safely_to_off(self) -> None:
        store = AppServerPreferenceStore(self.path)
        self.assertEqual(("OFF", "not-found"), (store.status().mode, store.status().warning))
        self.path.parent.mkdir(parents=True)
        self.path.write_text("not json\n", encoding="utf-8")
        self.assertEqual(
            ("OFF", "malformed-preference"),
            (store.status().mode, store.status().warning),
        )
        self.path.write_text(
            json.dumps({"schema_version": 99, "mode": "on", "updated_at": "now"}),
            encoding="utf-8",
        )
        self.assertEqual("unsupported-preference-schema", store.status().warning)

    def test_set_is_durable_and_leaves_no_lock_or_temporary_file(self) -> None:
        store = AppServerPreferenceStore(self.path, now=lambda: 10.0)
        enabled = store.set(True)
        self.assertTrue(enabled.enabled)
        self.assertEqual(PREFERENCE_SCHEMA_VERSION, enabled.schema_version)
        self.assertTrue(enabled.operator_trust)
        self.assertEqual("operator-runtime", enabled.trust_policy)
        self.assertEqual(enabled.updated_at, enabled.consented_at)
        self.assertEqual("ON", AppServerPreferenceStore(self.path).status().mode)
        self.assertFalse(self.path.with_suffix(self.path.suffix + ".lock").exists())
        self.assertEqual([], list(self.path.parent.glob("*.tmp")))
        self.assertEqual("OFF", store.set(False).mode)

    def test_legacy_on_remains_enabled_without_operator_runtime_trust(self) -> None:
        self.path.parent.mkdir(parents=True)
        self.path.write_text(
            json.dumps(
                {"schema_version": 1, "mode": "on", "updated_at": "legacy"}
            ),
            encoding="utf-8",
        )
        state = AppServerPreferenceStore(self.path).status()
        self.assertTrue(state.enabled)
        self.assertFalse(state.operator_trust)
        self.assertEqual("legacy-read-only", state.trust_policy)
        self.assertEqual("legacy-on-camp-trust-not-confirmed", state.warning)

    def test_schema_two_rejects_on_without_explicit_trust_consent(self) -> None:
        self.path.parent.mkdir(parents=True)
        self.path.write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "mode": "on",
                    "updated_at": "now",
                }
            ),
            encoding="utf-8",
        )
        state = AppServerPreferenceStore(self.path).status()
        self.assertFalse(state.enabled)
        self.assertEqual("malformed-preference", state.warning)

    def test_repository_local_preference_is_rejected(self) -> None:
        repository_path = Path(__file__).resolve().parents[1] / "app-server-preference.json"
        with self.assertRaisesRegex(AppServerUserStateError, "outside Tool Shed"):
            AppServerPreferenceStore(repository_path)

    def test_any_repository_local_preference_is_rejected(self) -> None:
        repository = self.root / "project"
        (repository / ".git").mkdir(parents=True)
        (repository / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
        with self.assertRaisesRegex(AppServerUserStateError, "repository"):
            AppServerPreferenceStore(repository / "preference.json")

    def test_event_log_contains_only_the_sanitized_operational_schema(self) -> None:
        events = self.root / "codex" / "tool-shed" / "app-server-events.jsonl"
        event = AppServerEventStore(events, now=lambda: 20.0).record(
            command="next",
            outcome="gui_fallback",
            category="network_failure",
            mutation_state="none",
            backend="gui",
            preference_mode="ON",
            strict_request=False,
            source="passive",
            event_type="fallback",
            role="camp_execution",
            correlation_id="abc123",
        )
        self.assertEqual(event, json.loads(events.read_text(encoding="utf-8")))
        self.assertEqual(
            {
                "schema_version",
                "recorded_at",
                "command",
                "outcome",
                "category",
                "mutation_state",
                "backend",
                "preference_mode",
                "strict_request",
                "source",
                "event_type",
                "role",
                "correlation_id",
            },
            set(event),
        )
        self.assertNotIn("prompt", event)
        self.assertNotIn("output", event)
        if os.name == "posix":
            self.assertEqual(0o600, events.stat().st_mode & 0o777)

    def test_owner_profile_is_recovery_only_and_restore_is_explicit(self) -> None:
        profile_path = self.root / "profile" / "app-server-owner-profile.json"
        preference = AppServerPreferenceStore(self.path, now=lambda: 30.0)
        profile = AppServerOwnerProfileStore(profile_path)
        saved = profile.save(preference.set(True))
        self.assertEqual("ON", saved.mode)
        self.assertFalse(saved.operator_trust)
        self.assertEqual("explicit-restore-required", saved.warning)
        self.path.unlink()
        self.assertEqual("OFF", preference.status().mode)
        restored = profile.restore(preference)
        self.assertEqual("ON", restored.mode)
        self.assertTrue(restored.operator_trust)

    def test_report_excludes_schema_one_and_counts_schema_two_funnel(self) -> None:
        events = self.root / "codex" / "tool-shed" / "app-server-events.jsonl"
        store = AppServerEventStore(events, now=lambda: 100.0)
        store.record(
            command="plan", outcome="selected", category="eligible", mutation_state="none",
            backend="app_server", preference_mode="ON", strict_request=False,
            source="passive", event_type="opportunity", role="planning", correlation_id="one",
        )
        store.record(
            command="next", outcome="completed", category="completed", mutation_state="verified",
            backend="app_server", preference_mode="ON", strict_request=False,
            source="passive", event_type="execution", role="camp_execution", correlation_id="one",
        )
        with events.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"schema_version": 1, "recorded_at": "legacy"}) + "\n")
        report = store.report(hours=1)
        self.assertEqual(2, report["included_runtime_events"])
        self.assertEqual(1, report["excluded_legacy_events"])
        self.assertEqual(1, report["opportunities"])
        self.assertEqual(1, report["app_server_selections"])
        self.assertEqual(1, report["completions"])
        self.assertIsNone(report["usage"]["input_tokens"])

    def test_event_failure_is_best_effort(self) -> None:
        self.assertFalse(
            record_app_server_event_best_effort(
                path=Path(__file__).resolve().parents[1] / "forbidden-events.jsonl",
                command="next",
                outcome="gui_fallback",
                category="network_failure",
                mutation_state="none",
                backend="gui",
                preference_mode="ON",
                strict_request=False,
            )
        )

    def test_dispatch_lifecycle_resumes_one_selection_and_refuses_replay(self) -> None:
        events = self.root / "codex" / "tool-shed" / "app-server-events.jsonl"
        selected = AppServerDispatchLifecycle(
            command="plan",
            role="planning",
            preference_mode="ON",
            strict_request=False,
            source="passive",
            path=events,
            correlation_id="one",
        )
        selected.selected("eligible")

        resumed = AppServerDispatchLifecycle.resume("one", path=events)
        resumed.attempted()
        resumed.terminal(
            "completed",
            category="completed",
            mutation_state="none",
            backend="app_server",
        )

        records = AppServerEventStore(events).correlation_events("one")
        self.assertEqual(
            ["selected", "attempted", "completed"],
            [event["outcome"] for event in records],
        )
        with self.assertRaisesRegex(AppServerUserStateError, "already consumed"):
            AppServerDispatchLifecycle.resume("one", path=events)

    def test_dispatch_lifecycle_rejects_an_expired_selection(self) -> None:
        events = self.root / "codex" / "tool-shed" / "app-server-events.jsonl"
        AppServerEventStore(events, now=lambda: 0.0).record(
            command="verify",
            outcome="selected",
            category="eligible",
            mutation_state="none",
            backend="app_server",
            preference_mode="ON",
            strict_request=False,
            source="passive",
            event_type="opportunity",
            role="verification",
            correlation_id="expired",
        )
        with self.assertRaisesRegex(AppServerUserStateError, "lease expired"):
            AppServerDispatchLifecycle.resume("expired", path=events)

    def test_report_classifies_pending_expired_and_invalid_dispatch_debt(self) -> None:
        events = self.root / "codex" / "tool-shed" / "app-server-events.jsonl"

        def record(now: float, correlation: str, outcome: str, event_type: str, **overrides):
            fields = {
                "command": "plan",
                "outcome": outcome,
                "category": "dispatch",
                "mutation_state": "none",
                "backend": "app_server",
                "preference_mode": "ON",
                "strict_request": False,
                "source": "passive",
                "event_type": event_type,
                "role": "planning",
                "correlation_id": correlation,
            }
            fields.update(overrides)
            AppServerEventStore(events, now=lambda: now).record(**fields)

        record(1000.0, "complete", "selected", "opportunity")
        record(1000.0, "complete", "attempted", "execution")
        record(1000.0, "complete", "completed", "terminal")
        record(1000.0, "pending", "selected", "opportunity")
        record(0.0, "expired", "selected", "opportunity")
        record(1000.0, "invalid", "selected", "opportunity")
        record(1000.0, "invalid", "attempted", "execution")
        record(
            1000.0,
            "invalid",
            "gui_fallback",
            "terminal",
            strict_request=True,
            backend="gui",
        )

        report = AppServerEventStore(events, now=lambda: 1000.0).report(hours=1)
        dispatch = report["dispatch_lifecycles"]
        self.assertEqual(1, dispatch["complete_count"])
        self.assertEqual(1, dispatch["pending_count"])
        self.assertEqual(1, dispatch["expired_count"])
        self.assertEqual(1, dispatch["invalid_count"])
        self.assertEqual(3, report["dispatch_debt"])
        by_id = {item["correlation_id"]: item for item in dispatch["findings"]}
        self.assertIn("lease_expired", by_id["expired"]["codes"])
        self.assertIn("metadata_mismatch", by_id["invalid"]["codes"])

    def test_report_excludes_pre_contract_schema_two_lifecycles(self) -> None:
        events = self.root / "codex" / "tool-shed" / "app-server-events.jsonl"
        event = AppServerEventStore(events, now=lambda: 100.0).record(
            command="plan",
            outcome="selected",
            category="eligible",
            mutation_state="none",
            backend="app_server",
            preference_mode="ON",
            strict_request=False,
            source="passive",
            event_type="opportunity",
            role="planning",
            correlation_id="legacy",
        )
        event["schema_version"] = 2
        events.write_text(json.dumps(event) + "\n", encoding="utf-8")
        report = AppServerEventStore(events, now=lambda: 100.0).report(hours=1)
        self.assertEqual(1, report["excluded_legacy_events"])
        self.assertEqual(0, report["dispatch_debt"])

    def test_interrupted_dispatch_recovery_is_terminal_and_idempotent(self) -> None:
        events = self.root / "codex" / "tool-shed" / "app-server-events.jsonl"
        lifecycle = AppServerDispatchLifecycle(
            command="camp-run",
            role="camp_execution",
            preference_mode="ON",
            strict_request=False,
            source="passive",
            path=events,
            correlation_id="interrupted",
        )
        lifecycle.selected("eligible")
        lifecycle.attempted()

        first = AppServerDispatchLifecycle.recover(
            "interrupted", disposition="mutation-uncertain", path=events
        )
        second = AppServerDispatchLifecycle.recover(
            "interrupted", disposition="mutation-uncertain", path=events
        )
        self.assertTrue(first["writes_performed"])
        self.assertFalse(first["idempotent"])
        self.assertTrue(second["idempotent"])
        self.assertEqual("reconciliation_required", second["outcome"])
        report = AppServerEventStore(events).report(hours=1)
        self.assertEqual(0, report["dispatch_debt"])
        records = AppServerEventStore(events).correlation_events("interrupted")
        self.assertEqual(3, len(records))

    def test_pre_mutation_recovery_closes_dispatch_debt_without_an_attempt(self) -> None:
        events = self.root / "codex" / "tool-shed" / "app-server-events.jsonl"
        lifecycle = AppServerDispatchLifecycle(
            command="next",
            role="camp_execution",
            preference_mode="ON",
            strict_request=False,
            source="passive",
            path=events,
            correlation_id="pre-mutation-loss",
        )
        lifecycle.selected("eligible")

        recovered = AppServerDispatchLifecycle.recover(
            "pre-mutation-loss", disposition="pre-mutation", path=events
        )

        self.assertEqual("gui_fallback", recovered["outcome"])
        self.assertEqual(0, AppServerEventStore(events).report(hours=1)["dispatch_debt"])
        records = AppServerEventStore(events).correlation_events("pre-mutation-loss")
        self.assertEqual(["selected", "gui_fallback"], [item["outcome"] for item in records])

    def test_unknown_role_repair_preserves_chain_and_requires_exact_evidence(self) -> None:
        events = self.root / "codex" / "tool-shed" / "app-server-events.jsonl"
        lifecycle = AppServerDispatchLifecycle(
            command="camp-run", role="camp_execution", preference_mode="ON",
            strict_request=False, source="passive", path=events,
            correlation_id="role-mismatch",
        )
        lifecycle.selected("eligible")
        lifecycle.attempted()
        lifecycle.terminal(
            "reconciliation_required", category="process_loss_mutation_uncertain",
            mutation_state="possible", backend="gui",
        )
        # Simulate the historical metadata fault in a disposable fixture only.
        lines = [json.loads(line) for line in events.read_text(encoding="utf-8").splitlines()]
        for line in lines:
            line["role"] = "unknown"
        original = "".join(json.dumps(line, sort_keys=True, separators=(",", ":")) + "\n"
                           for line in lines)
        events.write_text(original, encoding="utf-8")
        store = AppServerEventStore(events)
        self.assertEqual(1, store.report(hours=1)["dispatch_debt"])
        plan = store.role_repair_plan("role-mismatch")
        self.assertTrue(plan["eligible"])
        self.assertEqual("camp_execution", plan["expected_role"])

        evidence = self.root / "verified-reconciliation.md"
        evidence.write_text("GUI repair and exact worktree verification\n", encoding="utf-8")
        with self.assertRaisesRegex(AppServerUserStateError, "chain changed"):
            store.reconcile_unknown_role(
                "role-mismatch", expected_chain_sha256="0" * 64,
                evidence_file=evidence,
            )
        result = store.reconcile_unknown_role(
            "role-mismatch", expected_chain_sha256=plan["chain_sha256"],
            evidence_file=evidence,
        )
        self.assertTrue(result["writes_performed"])
        self.assertEqual(0, store.report(hours=1)["dispatch_debt"])
        self.assertTrue(events.read_text(encoding="utf-8").startswith(original))
        again = store.reconcile_unknown_role(
            "role-mismatch", expected_chain_sha256=plan["chain_sha256"],
            evidence_file=evidence,
        )
        self.assertTrue(again["idempotent"])
        self.assertFalse(again["writes_performed"])
        evidence.write_text("different evidence\n", encoding="utf-8")
        with self.assertRaisesRegex(AppServerUserStateError, "conflicting"):
            store.reconcile_unknown_role(
                "role-mismatch", expected_chain_sha256=plan["chain_sha256"],
                evidence_file=evidence,
            )

        corrected = events.read_text(encoding="utf-8")
        corrected_lines = corrected.splitlines(keepends=True)
        events.write_text(
            corrected_lines[-1] + "".join(corrected_lines[:-1]), encoding="utf-8"
        )
        self.assertIn(
            "correction_contract_invalid",
            store.report(hours=1)["dispatch_lifecycles"]["findings"][0]["codes"],
        )
        events.write_text(corrected, encoding="utf-8")
        correction_line = corrected.splitlines()[-1]
        with events.open("a", encoding="utf-8") as stream:
            stream.write(correction_line + "\n")
        duplicate_report = store.report(hours=1)
        self.assertEqual(1, duplicate_report["dispatch_debt"])
        self.assertIn(
            "correction_contract_invalid",
            duplicate_report["dispatch_lifecycles"]["findings"][0]["codes"],
        )
        events.write_text(corrected, encoding="utf-8")

        tampered = [json.loads(line) for line in events.read_text(encoding="utf-8").splitlines()]
        tampered[0]["category"] = "altered"
        events.write_text("".join(json.dumps(line) + "\n" for line in tampered), encoding="utf-8")
        self.assertEqual(1, store.report(hours=1)["dispatch_debt"])
        self.assertIn("correction_contract_invalid", store.report(hours=1)["dispatch_lifecycles"]["findings"][0]["codes"])

    def test_selection_refuses_role_mismatch_before_writing(self) -> None:
        events = self.root / "codex" / "tool-shed" / "app-server-events.jsonl"
        with self.assertRaisesRegex(AppServerUserStateError, "before selection"):
            AppServerDispatchLifecycle(
                command="camp-run", role="unknown", preference_mode="ON",
                strict_request=False, source="passive", path=events,
            ).selected("eligible")
        self.assertFalse(events.exists())

    def test_role_repair_carries_original_chain_into_short_report_window(self) -> None:
        events = self.root / "codex" / "tool-shed" / "app-server-events.jsonl"
        lifecycle = AppServerDispatchLifecycle(
            command="camp-run", role="camp_execution", preference_mode="ON",
            strict_request=False, source="passive", path=events,
            correlation_id="older-chain",
        )
        lifecycle.selected("eligible")
        lifecycle.attempted()
        lifecycle.terminal(
            "reconciliation_required", category="process_loss_mutation_uncertain",
            mutation_state="possible", backend="gui",
        )
        original = [json.loads(line) for line in events.read_text(encoding="utf-8").splitlines()]
        for event in original:
            event["role"] = "unknown"
            event["recorded_at"] = "1970-01-01T00:00:00+00:00"
        events.write_text("".join(json.dumps(event) + "\n" for event in original), encoding="utf-8")
        store = AppServerEventStore(events, now=lambda: 7200.0)
        plan = store.role_repair_plan("older-chain")
        self.assertTrue(plan["eligible"])
        evidence = self.root / "reconciled.md"
        evidence.write_text("verified\n", encoding="utf-8")
        store.reconcile_unknown_role(
            "older-chain", expected_chain_sha256=plan["chain_sha256"],
            evidence_file=evidence,
        )
        report = store.report(hours=1)
        self.assertEqual(3, report["carried_repair_chain_events"])
        self.assertEqual(0, report["dispatch_debt"])

    def test_report_groups_failures_without_exposing_raw_categories(self) -> None:
        events = self.root / "codex" / "tool-shed" / "app-server-events.jsonl"
        store = AppServerEventStore(events, now=lambda: 100.0)
        store.record(
            command="next", outcome="failed", category="transport_timeout", mutation_state="none",
            backend="app_server", preference_mode="ON", strict_request=True,
            source="operator", event_type="execution", role="camp_execution", correlation_id="one",
        )
        report = store.report(hours=1)
        self.assertEqual(report["failure_groups"][0]["category"], "transport")
        self.assertEqual(report["failure_groups"][0]["count"], 1)
        self.assertNotIn("transport_timeout", json.dumps(report["failure_groups"]))
        self.assertEqual(report["last_failure"], report["failure_groups"][0]["last_seen"])


if __name__ == "__main__":
    unittest.main()
