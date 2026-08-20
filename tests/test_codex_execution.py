from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.codex_app_server import AppServerError, AuthenticationError
from scripts.codex_app_server_compatibility import (
    load_qualifications,
    smoke_report,
    status_report,
)
from scripts.codex_execution import (
    ApprovalBridge,
    CodexExecutionAdapter,
    ModelPolicy,
    ModelPolicyError,
    activity_report,
    classify_recovery,
    qualification_report,
    sandbox_policy,
)
from scripts.codex_camp_execution import (
    CampExecutionError,
    GitMutationJournal,
    camp_next_action,
    parse_camp_outcome,
)
from scripts.codex_orchestration import (
    AppServerFeatureConfig,
    FeatureConfigError,
    benchmark_comparison,
    benchmark_regressions,
    execute_bounded,
    execute_if_enabled,
    inline_context_prompt,
    validate_summary_context,
)
from scripts.reasoning_catalog import query_codex_catalog


ROOT = Path(__file__).resolve().parents[1]


FAKE_CODEX = r'''#!/usr/bin/env python3
import json
import os
import sys
import time

if "--version" in sys.argv:
    print("codex-cli " + os.environ.get("FAKE_CODEX_VERSION", "0.144.6"))
    raise SystemExit(0)

account_type = os.environ.get("FAKE_CODEX_ACCOUNT", "chatgpt")
turn_count = 0
thread_count = 0
read_count = 0
interrupted = False
for raw in sys.stdin:
    message = json.loads(raw)
    method = message.get("method")
    request_id = message.get("id")
    if method == "initialize":
        print(json.dumps({"id": request_id, "result": {"userAgent": "fake-codex/0.144.6"}}), flush=True)
    elif method == "account/read":
        account = {"type": account_type}
        if account_type == "chatgpt":
            account["email"] = "hidden@example.com"
            account["planType"] = "pro"
        print(json.dumps({"id": request_id, "result": {"account": account, "requiresOpenaiAuth": True}}), flush=True)
    elif method == "model/list":
        data = []
        for model, default in (("gpt-5.6-sol", "low"), ("gpt-5.6-terra", "medium")):
            data.append({
                "id": model,
                "model": model,
                "defaultReasoningEffort": default,
                "supportedReasoningEfforts": [
                    {"reasoningEffort": effort, "description": effort}
                    for effort in ("low", "medium", "high", "xhigh", "max", "ultra")
                ],
            })
        print(json.dumps({"id": request_id, "result": {"data": data, "nextCursor": None}}), flush=True)
    elif method in ("thread/start", "thread/resume", "thread/fork"):
        if method == "thread/resume" and os.environ.get("FAKE_CODEX_STALE_THREAD") == "1":
            print(json.dumps({"id": request_id, "error": {"code": -32602, "message": "thread not found: stale thread id"}}), flush=True)
            continue
        if method == "thread/start":
            thread_count += 1
            thread_id = f"thr_fake_{thread_count}"
        else:
            thread_id = message.get("params", {}).get("threadId", "thr_fake")
        print(json.dumps({"id": request_id, "result": {"thread": {"id": thread_id, "status": {"type": "idle"}}, "instructionSources": ["/workspace/AGENTS.md"]}}), flush=True)
    elif method == "thread/read":
        read_count += 1
        thread_id = message["params"]["threadId"]
        thread = {"id": thread_id, "status": {"type": "idle"}}
        sequence = os.environ.get("FAKE_CODEX_READ_TURN_SEQUENCE", "").split(",")
        terminal = sequence[min(read_count - 1, len(sequence) - 1)] if sequence and sequence[0] else None
        terminal = terminal or os.environ.get("FAKE_CODEX_READ_TURN_STATUS")
        terminal = terminal or ("interrupted" if interrupted else None)
        if terminal:
            thread["turns"] = [{"id": "turn_fake", "status": terminal}]
        print(json.dumps({"id": request_id, "result": {"thread": thread}}), flush=True)
    elif method == "turn/start":
        turn_count += 1
        params = message["params"]
        turn_id = "turn_fake"
        print(json.dumps({"id": request_id, "result": {"turn": {"id": turn_id, "status": "inProgress", "items": []}}}), flush=True)
        if os.environ.get("FAKE_CODEX_EXIT_ON_TURN") == "1":
            sys.exit(7)
        if os.environ.get("FAKE_CODEX_DELAY_TURN") == "1":
            time.sleep(0.3)
        if os.environ.get("FAKE_CODEX_INTERRUPT") == "1":
            print(json.dumps({"method": "turn/completed", "params": {"threadId": params["threadId"], "turn": {"id": turn_id, "status": "interrupted", "items": []}}}), flush=True)
            continue
        if os.environ.get("FAKE_CODEX_FAIL_TERRA") == "1" and params.get("model") == "gpt-5.6-terra":
            error = {"message": "recoverable failure", "codexErrorInfo": {"type": "InternalServerError"}}
            print(json.dumps({"method": "turn/completed", "params": {"threadId": params["threadId"], "turn": {"id": turn_id, "status": "failed", "error": error, "items": []}}}), flush=True)
            continue
        print(json.dumps({"method": "item/agentMessage/delta", "params": {"threadId": params["threadId"], "turnId": turn_id, "delta": "FAKE_OK"}}), flush=True)
        usage = {"inputTokens": 10, "cachedInputTokens": 2, "outputTokens": 3, "reasoningOutputTokens": 1, "totalTokens": 13}
        print(json.dumps({"method": "thread/tokenUsage/updated", "params": {"threadId": params["threadId"], "turnId": turn_id, "tokenUsage": {"last": usage, "total": usage, "modelContextWindow": 1000}}}), flush=True)
        if os.environ.get("FAKE_CODEX_TOOL") == "1":
            item = {"id": "item_tool", "type": "commandExecution", "status": "completed", "command": "true"}
            print(json.dumps({"method": "item/completed", "params": {"threadId": params["threadId"], "turnId": turn_id, "item": item}}), flush=True)
            second = {"inputTokens": 12, "cachedInputTokens": 3, "outputTokens": 4, "reasoningOutputTokens": 1, "totalTokens": 16}
            total = {"inputTokens": 22, "cachedInputTokens": 5, "outputTokens": 7, "reasoningOutputTokens": 2, "totalTokens": 29}
            print(json.dumps({"method": "thread/tokenUsage/updated", "params": {"threadId": params["threadId"], "turnId": turn_id, "tokenUsage": {"last": second, "total": total, "modelContextWindow": 1000}}}), flush=True)
        print(json.dumps({"method": "turn/completed", "params": {"threadId": params["threadId"], "turn": {"id": turn_id, "status": "completed", "items": []}}}), flush=True)
    elif method == "turn/interrupt":
        if os.environ.get("FAKE_CODEX_INTERRUPT_ERROR") == "1":
            print(json.dumps({"id": request_id, "error": {"code": -32000, "message": "interrupt unavailable"}}), flush=True)
        elif os.environ.get("FAKE_CODEX_NO_ACTIVE_INTERRUPT") == "1":
            print(json.dumps({"id": request_id, "error": {"code": -32602, "message": "no active turn to interrupt"}}), flush=True)
        else:
            interrupted = True
            print(json.dumps({"id": request_id, "result": {}}), flush=True)
'''


class CodexExecutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.fake = self.root / "fake-codex"
        self.fake.write_text(FAKE_CODEX, encoding="utf-8", newline="\n")
        self.fake.chmod(0o755)
        self.policy = ModelPolicy.load(ROOT / "adapters" / "codex-model-policy.json")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_policy_routes_frontier_and_workhorse_roles(self) -> None:
        planning = self.policy.select("planning")
        verification = self.policy.select("verification")
        architecture = self.policy.select("architecture")
        testing = self.policy.select("testing")
        self.assertEqual((planning.model, planning.reasoning), ("gpt-5.6-sol", "high"))
        self.assertEqual((verification.model, verification.reasoning), ("gpt-5.6-terra", "low"))
        self.assertEqual((architecture.model, architecture.reasoning), ("gpt-5.6-sol", "xhigh"))
        self.assertEqual((testing.model, testing.reasoning), ("gpt-5.6-terra", "low"))
        self.assertNotIn("luna", json.dumps(self.policy.payload).lower())

    def test_workspace_write_policy_excludes_implicit_temp_roots(self) -> None:
        policy = sandbox_policy("workspace-write", self.root)
        self.assertEqual(policy["type"], "workspaceWrite")
        self.assertEqual(policy["writableRoots"], [str(self.root.resolve())])
        self.assertFalse(policy["networkAccess"])
        self.assertTrue(policy["excludeSlashTmp"])
        self.assertTrue(policy["excludeTmpdirEnvVar"])

    def test_camp_outcomes_are_strict_and_machine_readable(self) -> None:
        outcome = parse_camp_outcome(
            json.dumps(
                {
                    "outcome": "step_complete",
                    "details": "Focused test passed.",
                    "evidence": ["tests/test_sample.py"],
                }
            )
        )
        self.assertEqual(outcome.outcome, "step_complete")
        with self.assertRaisesRegex(CampExecutionError, "missing or unexpected"):
            parse_camp_outcome(
                json.dumps(
                    {
                        "outcome": "step_complete",
                        "details": "done",
                        "evidence": [],
                        "free_form": True,
                    }
                )
            )
        clean_journal = {
            "safe": True,
            "files_created": [],
            "files_modified": [],
            "files_deleted": [],
        }
        retry = parse_camp_outcome(
            json.dumps(
                {
                    "outcome": "recoverable_failure",
                    "details": "retry safely",
                    "evidence": [],
                }
            )
        )
        self.assertEqual(
            camp_next_action(retry, attempt=1, journal=clean_journal),
            "retry_terra_once",
        )
        self.assertEqual(
            camp_next_action(retry, attempt=2, journal=clean_journal),
            "escalate_to_sol_read_only",
        )
        mutated = dict(clean_journal, files_modified=["target.txt"])
        self.assertEqual(
            camp_next_action(retry, attempt=1, journal=mutated),
            "reconcile_workspace_before_retry",
        )
        unsafe = dict(clean_journal, safe=False)
        self.assertEqual(
            camp_next_action(retry, attempt=1, journal=unsafe),
            "needs_user_intervention",
        )

    def test_git_mutation_journal_preserves_unrelated_dirty_work(self) -> None:
        repository = self.root / "repo"
        repository.mkdir()
        subprocess.run(["git", "init", "-q", str(repository)], check=True)
        subprocess.run(
            ["git", "-C", str(repository), "config", "user.email", "test@example.com"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(repository), "config", "user.name", "Tool Shed Test"],
            check=True,
        )
        target = repository / "target.txt"
        unrelated = repository / "unrelated.txt"
        target.write_text("before\n", encoding="utf-8")
        unrelated.write_text("clean\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(repository), "add", "."], check=True)
        subprocess.run(
            ["git", "-C", str(repository), "commit", "-qm", "baseline"], check=True
        )
        unrelated.write_text("owner work\n", encoding="utf-8")
        journal = GitMutationJournal.begin(
            campaign="campaign-036",
            camp="camp-write",
            workspace=repository,
            expected_paths=(Path("target.txt"),),
        )
        target.write_text("after\n", encoding="utf-8")
        record = journal.finalize(
            thread_id="thr_1",
            turn_id="turn_1",
            turn_status="completed",
        )
        self.assertTrue(record["safe"])
        self.assertTrue(record["preexisting_dirty_preserved"])
        self.assertEqual(record["files_modified"], ["target.txt"])
        self.assertEqual(record["unexpected_paths"], [])
        with self.assertRaisesRegex(CampExecutionError, "already contain dirty work"):
            GitMutationJournal.begin(
                campaign="campaign-036",
                camp="camp-write",
                workspace=repository,
                expected_paths=(Path("unrelated.txt"),),
            )

    def test_execution_requires_chatgpt_and_records_model_aware_telemetry(self) -> None:
        telemetry = self.root / "telemetry.jsonl"
        with CodexExecutionAdapter(
            policy=self.policy,
            codex=str(self.fake),
            telemetry_path=telemetry,
        ) as adapter:
            result = adapter.execute(
                "test",
                role="camp_execution",
                cwd=ROOT,
                program="program-a",
                camp="camp-b",
                campaign="campaign-b",
                qualification_id="qualification-1",
            )
        self.assertEqual(result.text, "FAKE_OK")
        self.assertEqual(result.requested_model, "gpt-5.6-terra")
        self.assertEqual(result.reasoning, "medium")
        record = json.loads(telemetry.read_text(encoding="utf-8"))
        self.assertEqual(record["program"], "program-a")
        self.assertEqual(record["camp"], "camp-b")
        self.assertEqual(record["campaign"], "campaign-b")
        self.assertEqual(record["qualification_id"], "qualification-1")
        self.assertEqual(record["actual_model"], "gpt-5.6-terra")
        self.assertEqual(record["token_usage"]["last"]["totalTokens"], 13)
        self.assertEqual(record["tokens"]["input"], 10)
        self.assertEqual(record["tokens"]["cached_input"], 2)
        self.assertEqual(record["tokens"]["reasoning_output"], 1)
        self.assertEqual(record["thread_mode"], "new")
        self.assertEqual(record["model_turns"], 1)
        self.assertEqual(record["tool_calls"], 0)
        self.assertEqual(record["mutation_events"], [])
        self.assertFalse(record["fallback_used"])
        self.assertGreaterEqual(record["duration_seconds"], 0)
        self.assertEqual(record["context_scope"]["instruction_sources"], ["/workspace/AGENTS.md"])
        self.assertTrue(record["success"])

    def test_api_key_authentication_fails_closed(self) -> None:
        prior = os.environ.get("FAKE_CODEX_ACCOUNT")
        os.environ["FAKE_CODEX_ACCOUNT"] = "apiKey"
        try:
            adapter = CodexExecutionAdapter(
                policy=self.policy,
                codex=str(self.fake),
                telemetry_path=self.root / "telemetry.jsonl",
            )
            with self.assertRaisesRegex(AuthenticationError, "API-key fallback is disabled"):
                adapter.start()
            adapter.close()
        finally:
            if prior is None:
                os.environ.pop("FAKE_CODEX_ACCOUNT", None)
            else:
                os.environ["FAKE_CODEX_ACCOUNT"] = prior

    def test_escalation_is_bounded_and_explicit(self) -> None:
        adapter = CodexExecutionAdapter(
            policy=self.policy,
            codex=str(self.fake),
            telemetry_path=self.root / "telemetry.jsonl",
        )
        with self.assertRaisesRegex(ModelPolicyError, "requires 2 bounded"):
            adapter.escalate(
                "blocked",
                source_role="implementation",
                workhorse_attempts=1,
                reason="attempt_limit",
                cwd=ROOT,
            )

    def test_reasoning_catalog_uses_shared_app_server_client(self) -> None:
        models, user_agent = query_codex_catalog(str(self.fake), timeout=5)
        self.assertEqual(user_agent, "fake-codex/0.144.6")
        self.assertEqual({item["id"] for item in models}, {"gpt-5.6-sol", "gpt-5.6-terra"})

    def test_feature_flags_preserve_gui_fallback_and_discussion(self) -> None:
        config = AppServerFeatureConfig.load(ROOT / "adapters" / "codex-app-server-config.json")
        self.assertEqual(config.context_delivery, "inline_relevant_files")
        inline = inline_context_prompt(
            config,
            ROOT,
            (Path("adapters/codex-model-policy.json"),),
            "verify",
        )
        self.assertIn("BEGIN adapters/codex-model-policy.json", inline)
        self.assertEqual(config.route("planning").reason, "global_feature_disabled")
        self.assertTrue(config.route("planning", enable_override=True).use_app_server)
        self.assertTrue(config.route("verification", enable_override=True).use_app_server)
        self.assertFalse(config.route("implementation", enable_override=True).use_app_server)
        discussion = config.route(
            "planning", request_text="ts: discuss context", enable_override=True
        )
        self.assertEqual((discussion.backend, discussion.reason), ("existing-gui", "gui_native_discussion"))
        writing = config.route(
            "planning", sandbox="workspace-write", enable_override=True
        )
        self.assertEqual(writing.reason, "role_sandbox_not_enabled")
        camp_write = config.route(
            "camp_execution", sandbox="workspace-write", enable_override=True
        )
        self.assertTrue(camp_write.use_app_server)
        self.assertEqual(camp_write.reason, "workspace_write_role_enabled")
        self.assertFalse(
            config.route("camp_execution", sandbox="read-only", enable_override=True).use_app_server
        )
        self.assertIsNone(config.compatibility_warning(str(self.fake)))
        os.environ["FAKE_CODEX_VERSION"] = "0.200.0"
        try:
            warning = config.compatibility_warning(str(self.fake))
        finally:
            os.environ.pop("FAKE_CODEX_VERSION", None)
        self.assertIn("Qualified version: 0.144.6", warning or "")
        self.assertIn("Installed version: 0.200.0", warning or "")
        self.assertIn(
            "python3 scripts/codex_app_server_compatibility.py smoke --cwd .",
            warning or "",
        )
        self.assertEqual(config.thread_policy("planning"), "new")
        with self.assertRaisesRegex(FeatureConfigError, "defaults to new threads"):
            execute_if_enabled(
                "resume",
                role="planning",
                cwd=ROOT,
                enable_override=True,
                thread_id="thr_existing",
                config=config,
                policy=self.policy,
                codex=str(self.fake),
                telemetry_path=self.root / "unexpected-resume.jsonl",
            )

    def test_thread_resume_restart_and_stale_thread_classification(self) -> None:
        telemetry = self.root / "telemetry.jsonl"
        with CodexExecutionAdapter(
            policy=self.policy,
            codex=str(self.fake),
            telemetry_path=telemetry,
        ) as adapter:
            first = adapter.execute("first", role="planning", cwd=ROOT)
            adapter.client.restart()
            resumed = adapter.execute(
                "second", role="planning", cwd=ROOT, thread_id=first.thread_id
            )
        self.assertTrue(resumed.thread_reused)
        self.assertEqual(resumed.thread_id, first.thread_id)

        prior = os.environ.get("FAKE_CODEX_STALE_THREAD")
        os.environ["FAKE_CODEX_STALE_THREAD"] = "1"
        try:
            adapter = CodexExecutionAdapter(
                policy=self.policy,
                codex=str(self.fake),
                telemetry_path=self.root / "stale.jsonl",
            )
            with self.assertRaises(AppServerError) as captured:
                adapter.execute("stale", role="planning", cwd=ROOT, thread_id="thr_stale")
            adapter.close()
            self.assertEqual(
                classify_recovery("failed", captured.exception.details),
                "requires_new_thread",
            )
        finally:
            if prior is None:
                os.environ.pop("FAKE_CODEX_STALE_THREAD", None)
            else:
                os.environ["FAKE_CODEX_STALE_THREAD"] = prior

    def test_interrupted_and_terminated_streams_are_resume_not_replay(self) -> None:
        scenarios = (
            ("FAKE_CODEX_INTERRUPT", "safe_to_resume"),
            ("FAKE_CODEX_EXIT_ON_TURN", "safe_to_resume"),
        )
        for variable, expected in scenarios:
            with self.subTest(variable=variable):
                os.environ[variable] = "1"
                telemetry = self.root / f"{variable}.jsonl"
                adapter = CodexExecutionAdapter(
                    policy=self.policy,
                    codex=str(self.fake),
                    telemetry_path=telemetry,
                )
                try:
                    with self.assertRaises(AppServerError):
                        adapter.execute("test", role="planning", cwd=ROOT)
                finally:
                    adapter.close()
                    os.environ.pop(variable, None)
                record = json.loads(telemetry.read_text(encoding="utf-8"))
                self.assertEqual(record["recovery_action"], expected)
        os.environ["FAKE_CODEX_DELAY_TURN"] = "1"
        timeout_telemetry = self.root / "timeout.jsonl"
        adapter = CodexExecutionAdapter(
            policy=self.policy,
            codex=str(self.fake),
            timeout=0.1,
            telemetry_path=timeout_telemetry,
        )
        try:
            with self.assertRaises(AppServerError):
                adapter.execute("test", role="planning", cwd=ROOT)
        finally:
            adapter.close()
            os.environ.pop("FAKE_CODEX_DELAY_TURN", None)
        timeout_record = json.loads(timeout_telemetry.read_text(encoding="utf-8"))
        self.assertEqual(timeout_record["recovery_action"], "safe_to_resume")

    def test_bounded_terra_retry_escalates_once_to_sol(self) -> None:
        os.environ["FAKE_CODEX_FAIL_TERRA"] = "1"
        telemetry = self.root / "bounded.jsonl"
        try:
            with CodexExecutionAdapter(
                policy=self.policy,
                codex=str(self.fake),
                telemetry_path=telemetry,
            ) as adapter:
                result = execute_bounded(
                    adapter,
                    "verify",
                    role="verification",
                    cwd=ROOT,
                )
        finally:
            os.environ.pop("FAKE_CODEX_FAIL_TERRA", None)
        records = [json.loads(line) for line in telemetry.read_text(encoding="utf-8").splitlines()]
        self.assertEqual([item["attempt"] for item in records[:2]], [1, 2])
        self.assertEqual(result.actual_model, "gpt-5.6-sol")
        self.assertTrue(result.escalation)
        self.assertEqual(result.escalation_reason, "recoverable_failure_exhausted")
        self.assertEqual(sum(bool(item["escalation"]) for item in records), 1)

    def test_approval_bridge_is_bounded_and_fail_closed(self) -> None:
        command = {
            "threadId": "thr_1",
            "turnId": "turn_1",
            "itemId": "item_1",
            "availableDecisions": ["accept", "decline", "cancel"],
            "command": "true",
        }
        file_change = {
            "threadId": "thr_1",
            "turnId": "turn_1",
            "itemId": "item_2",
        }
        disabled = ApprovalBridge(lambda _: "accept")
        self.assertEqual(
            disabled("item/commandExecution/requestApproval", command),
            {"decision": "cancel"},
        )
        accepting = ApprovalBridge(lambda _: "accept", workspace_write_enabled=True)
        self.assertEqual(
            accepting("item/fileChange/requestApproval", file_change),
            {"decision": "accept"},
        )
        denied = ApprovalBridge(lambda _: "decline", workspace_write_enabled=True)
        self.assertEqual(
            denied("item/commandExecution/requestApproval", command),
            {"decision": "decline"},
        )
        cancelled = ApprovalBridge(lambda _: "cancel", workspace_write_enabled=True)
        self.assertEqual(
            cancelled("item/fileChange/requestApproval", file_change),
            {"decision": "cancel"},
        )
        self.assertEqual(
            accepting("item/commandExecution/requestApproval", command),
            {"decision": "accept"},
        )
        malformed = ApprovalBridge(lambda _: "accept", workspace_write_enabled=True)
        self.assertEqual(
            malformed("item/fileChange/requestApproval", {"threadId": "thr_1"}),
            {"decision": "cancel"},
        )
        timed_out = ApprovalBridge(
            lambda _: __import__("time").sleep(0.05) or "accept",
            workspace_write_enabled=True,
            timeout=0.005,
        )
        self.assertEqual(
            timed_out("item/commandExecution/requestApproval", command),
            {"decision": "cancel"},
        )
        self.assertEqual(timed_out.events[-1]["outcome"], "timed_out")
        self.assertEqual(
            accepting(
                "item/permissions/requestApproval",
                {"threadId": "thr_1", "turnId": "turn_1", "itemId": "item_3"},
            ),
            {"permissions": []},
        )

    def test_cancellation_calls_bounded_turn_interrupt(self) -> None:
        with CodexExecutionAdapter(
            policy=self.policy,
            codex=str(self.fake),
            telemetry_path=self.root / "cancel.jsonl",
        ) as adapter:
            result = adapter.cancel("thr_fake", "turn_fake")
        self.assertEqual(result["outcome"], "cancelled")
        self.assertTrue(result["diagnostics"]["cancel_acknowledged"])
        self.assertEqual(result["diagnostics"]["final_classification"], "cancelled")

    def test_cancellation_race_reconciles_to_explicit_recovery_action(self) -> None:
        os.environ["FAKE_CODEX_NO_ACTIVE_INTERRUPT"] = "1"
        try:
            for sequence, outcome, action in (
                ("inProgress,inProgress", "unknown", "user_intervention"),
                ("inProgress,interrupted", "cancelled", "resume"),
                ("completed", "completed", "none"),
            ):
                with self.subTest(sequence=sequence):
                    os.environ["FAKE_CODEX_READ_TURN_SEQUENCE"] = sequence
                    with CodexExecutionAdapter(
                        policy=self.policy,
                        codex=str(self.fake),
                        telemetry_path=self.root / f"cancel-{sequence}.jsonl",
                    ) as adapter:
                        result = adapter.cancel(
                            "thr_fake", "turn_fake", timeout=0.03, poll_interval=0.005
                        )
                    self.assertEqual(result["outcome"], outcome)
                    self.assertEqual(result["recovery_action"], action)
                    self.assertGreaterEqual(len(result["diagnostics"]["event_sequence"]), 3)
        finally:
            os.environ.pop("FAKE_CODEX_NO_ACTIVE_INTERRUPT", None)
            os.environ.pop("FAKE_CODEX_READ_TURN_SEQUENCE", None)

        os.environ["FAKE_CODEX_INTERRUPT_ERROR"] = "1"
        os.environ["FAKE_CODEX_READ_TURN_STATUS"] = "interrupted"
        try:
            with CodexExecutionAdapter(
                policy=self.policy,
                codex=str(self.fake),
                telemetry_path=self.root / "cancel-error.jsonl",
            ) as adapter:
                result = adapter.cancel("thr_fake", "turn_fake", timeout=0.05)
            self.assertEqual(result["outcome"], "cancelled")
            self.assertFalse(result["diagnostics"]["cancel_acknowledged"])
        finally:
            os.environ.pop("FAKE_CODEX_INTERRUPT_ERROR", None)
            os.environ.pop("FAKE_CODEX_READ_TURN_STATUS", None)

    def test_context_accounting_warns_without_blocking(self) -> None:
        telemetry = self.root / "context.jsonl"
        with CodexExecutionAdapter(
            policy=self.policy,
            codex=str(self.fake),
            telemetry_path=telemetry,
        ) as adapter:
            result = adapter.execute(
                "inspect policy",
                role="verification",
                cwd=ROOT,
                explicit_files=(Path("adapters/codex-model-policy.json"),),
                restricted_read=True,
                warning_input_tokens=5,
            )
        self.assertEqual(result.context_warning["input_tokens"], 10)
        self.assertGreater(result.context_scope["explicit_file_bytes"], 0)
        self.assertTrue(result.context_scope["restricted_read"])

    def test_observed_model_turns_and_tool_calls_are_counted_from_protocol_events(self) -> None:
        os.environ["FAKE_CODEX_TOOL"] = "1"
        try:
            with CodexExecutionAdapter(
                policy=self.policy,
                codex=str(self.fake),
                telemetry_path=self.root / "events.jsonl",
            ) as adapter:
                result = adapter.execute("inspect", role="verification", cwd=ROOT)
        finally:
            os.environ.pop("FAKE_CODEX_TOOL", None)
        self.assertEqual(result.model_turns, 2)
        self.assertEqual(result.model_turns_metric, "distinct_token_usage_last_updates")
        self.assertEqual(result.tool_calls, 1)
        self.assertEqual(result.tool_call_types, ("commandExecution",))

    def test_focused_summary_must_name_all_source_files(self) -> None:
        source = self.root / "source.md"
        source.write_text("source", encoding="utf-8")
        summary = self.root / "summary.md"
        summary.write_text("## Source files\n\n- source.md\n\n## Summary\n\nSummary", encoding="utf-8")
        validate_summary_context(self.root, (summary,), (source,))
        summary.write_text("Summary without provenance", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "identify every source"):
            validate_summary_context(self.root, (summary,), (source,))
        summary.write_text(
            "## Notes\n\nThe text source.md appears here, outside provenance.\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "identify every source"):
            validate_summary_context(self.root, (summary,), (source,))

    def test_activity_report_is_prompt_free_and_summarized(self) -> None:
        telemetry = self.root / "activity.jsonl"
        with CodexExecutionAdapter(
            policy=self.policy,
            codex=str(self.fake),
            telemetry_path=telemetry,
        ) as adapter:
            adapter.execute(
                "secret prompt not retained",
                role="verification",
                cwd=ROOT,
                program="P",
                camp="C",
                qualification_id="Q",
            )
        report = activity_report(telemetry, limit=20)
        self.assertEqual(report["operation_count"], 1)
        self.assertEqual(report["summary"]["input_tokens"], 10)
        self.assertEqual(report["operations"][0]["program"], "P")
        self.assertNotIn("secret prompt", json.dumps(report))
        qualification = qualification_report(
            telemetry,
            qualification_id="Q",
            baseline_input_tokens=8,
            expected_codex_version="0.144.6",
            codex=str(self.fake),
        )
        self.assertEqual(qualification["operations"], 1)
        self.assertEqual(qualification["verification_terra"]["avoidable_input_tokens"], 2)
        self.assertEqual(qualification["codex_cli_version"], "0.144.6")
        self.assertFalse(qualification["observation_gate"]["met"])
        changed = qualification_report(
            telemetry,
            qualification_id="Q",
            baseline_input_tokens=8,
            expected_codex_version="9.9.9",
            codex=str(self.fake),
        )
        self.assertTrue(changed["version_changed"])
        self.assertFalse(changed["observation_gate"]["version_compatible"])
        baseline = self.root / "baseline.json"
        baseline.write_text(
            json.dumps({"results": [{"id": "small", "tokens": {"input": 10}}]}),
            encoding="utf-8",
        )
        findings = benchmark_regressions(
            [{"id": "small", "tokens": {"input": 16}}], baseline, factor=1.5
        )
        self.assertEqual(findings[0]["kind"], "input_token_regression")
        self.assertEqual(findings[0]["absolute_change_tokens"], 6)
        self.assertEqual(findings[0]["relative_change_percent"], 60.0)
        comparison = benchmark_comparison(
            [{"id": "small", "tokens": {"input": 12}}], baseline
        )
        self.assertEqual(comparison["aggregate"]["absolute_change_tokens"], 2)
        self.assertEqual(comparison["aggregate"]["relative_change_percent"], 20.0)

    def test_compatibility_status_and_smoke_are_version_aware(self) -> None:
        qualifications = load_qualifications(
            ROOT / "adapters" / "codex-app-server-qualifications.json"
        )
        self.assertEqual(qualifications[0]["codex_version"], "0.144.6")
        status = status_report(codex=str(self.fake))
        self.assertEqual(status["status"], "OPT-IN")
        self.assertEqual(status["global_default"], "disabled")
        self.assertEqual(status["compatibility"], "qualified_with_blockers")
        self.assertEqual(status["qualified_savings"]["input_reduction_percent"], 82.54)
        self.assertEqual(
            status["enabled_roles"]["camp_execution"],
            {
                "model": "gpt-5.6-terra",
                "reasoning": "medium",
                "sandbox": "workspace-write",
                "scope": "explicit paths with Git mutation journal",
            },
        )
        self.assertNotIn("CAMP execution", status["disabled"])
        self.assertIn("deployment", status["disabled"])

        telemetry = self.root / "smoke.jsonl"
        smoke = smoke_report(
            codex=str(self.fake),
            cwd=ROOT,
            telemetry_path=telemetry,
            timeout=2,
        )
        self.assertEqual(smoke["outcome"], "qualified_with_blockers")
        by_name = {item["name"]: item for item in smoke["checks"]}
        self.assertEqual(by_name["chatgpt_authentication"]["status"], "pass")
        self.assertEqual(by_name["read_only_planning_turn"]["status"], "pass")
        self.assertEqual(by_name["read_only_verification_turn"]["status"], "pass")
        self.assertEqual(by_name["cancellation_reconciliation"]["status"], "blocked")
        self.assertEqual(smoke["cancellation"]["outcome"], "completed")
        self.assertEqual(by_name["restricted_read_behavior"]["status"], "blocked")
        self.assertFalse(smoke["qualification_record_updated"])
        self.assertNotIn("APP_SERVER_PLANNING_SMOKE_OK", telemetry.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
