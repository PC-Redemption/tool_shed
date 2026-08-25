from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from scripts.codex_app_server import AppServerError, AuthenticationError, CodexAppServerClient
from scripts.codex_cli_resolver import CodexCliResolution, CodexReadiness, CodexSource
from scripts.app_server_control import (
    control_status,
    format_control_status,
    format_selection,
    select_command,
    select_role,
    session_control,
)
from scripts.codex_app_server_compatibility import (
    codex_version_at_least,
    codex_version_core,
    dirty_read_qualification_report,
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
    detect_codex_version,
    sandbox_policy,
    weighted_codex_usage,
)
from scripts.codex_camp_execution import (
    CampExecutionError,
    GitMutationJournal,
    camp_next_action,
    compact_command_evidence,
    focused_context_finding,
    parse_camp_outcome,
)
from scripts.codex_orchestration import (
    AppServerFeatureConfig,
    FeatureConfigError,
    benchmark_comparison,
    benchmark_regressions,
    execute_bounded,
    execute_camp_if_enabled,
    execute_deterministic_verification,
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
    print("codex-cli " + os.environ.get("FAKE_CODEX_VERSION", "0.149.0"))
    raise SystemExit(0)

if "app-server" in sys.argv and "--help" in sys.argv:
    print("Run the Codex App Server over stdio.")
    raise SystemExit(0)

account_type = os.environ.get("FAKE_CODEX_ACCOUNT", "chatgpt")
turn_count = 0
thread_count = 0
read_count = 0
interrupted = False
active_turn_id = None
active_thread_id = None
for raw in sys.stdin:
    message = json.loads(raw)
    method = message.get("method")
    request_id = message.get("id")
    if method == "initialize":
        capabilities = message.get("params", {}).get("capabilities", {})
        if capabilities.get("experimentalApi") is not True:
            print(json.dumps({"id": request_id, "error": {"code": -32600, "message": "experimentalApi capability required"}}), flush=True)
            continue
        print(json.dumps({"id": request_id, "result": {"userAgent": "fake-codex/0.149.0"}}), flush=True)
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
    elif method == "permissionProfile/list":
        if os.environ.get("FAKE_CODEX_NO_PERMISSION_PROFILES") == "1":
            print(json.dumps({"id": request_id, "error": {"code": -32601, "message": "method not found"}}), flush=True)
        else:
            allowed = os.environ.get("FAKE_CODEX_DISALLOW_READ_ONLY") != "1"
            data = [
                {"id": ":read-only", "description": None, "allowed": allowed},
                {"id": ":workspace", "description": None, "allowed": True},
            ]
            print(json.dumps({"id": request_id, "result": {"data": data, "nextCursor": None}}), flush=True)
    elif method in ("thread/start", "thread/resume", "thread/fork"):
        params = message.get("params", {})
        if "permissions" in params and "sandbox" in params:
            print(json.dumps({"id": request_id, "error": {"code": -32602, "message": "permissions cannot be combined with sandbox"}}), flush=True)
            continue
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
        if "permissions" in params and "sandboxPolicy" in params:
            print(json.dumps({"id": request_id, "error": {"code": -32602, "message": "permissions cannot be combined with sandboxPolicy"}}), flush=True)
            continue
        turn_id = "turn_fake"
        print(json.dumps({"id": request_id, "result": {"turn": {"id": turn_id, "status": "inProgress", "items": []}}}), flush=True)
        prompt = " ".join(
            str(item.get("text", ""))
            for item in params.get("input", [])
            if isinstance(item, dict)
        )
        if "ACTIVE_CANCELLATION_PROBE" in prompt:
            active_turn_id = turn_id
            active_thread_id = params["threadId"]
            continue
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
        camp_target = os.environ.get("FAKE_CODEX_CAMP_TARGET")
        if camp_target:
            with open(camp_target, "w", encoding="utf-8") as stream:
                stream.write("after\n")
            item = {"id": "item_change", "type": "fileChange", "status": "completed", "changes": [{"path": camp_target, "kind": "update"}]}
            print(json.dumps({"method": "item/completed", "params": {"threadId": params["threadId"], "turnId": turn_id, "item": item}}), flush=True)
            outcome = os.environ.get(
                "FAKE_CODEX_CAMP_OUTCOME", "step_ready_for_verification"
            )
            reply = json.dumps({"outcome": outcome, "details": "Focused edit complete.", "evidence": [camp_target]})
        else:
            reply = "FAKE_OK"
        print(json.dumps({"method": "item/agentMessage/delta", "params": {"threadId": params["threadId"], "turnId": turn_id, "delta": reply}}), flush=True)
        usage = {"inputTokens": 10, "cachedInputTokens": 2, "outputTokens": 3, "reasoningOutputTokens": 1, "totalTokens": 13}
        print(json.dumps({"method": "thread/tokenUsage/updated", "params": {"threadId": params["threadId"], "turnId": turn_id, "tokenUsage": {"last": usage, "total": usage, "modelContextWindow": 1000}}}), flush=True)
        if os.environ.get("FAKE_CODEX_TOOL") == "1":
            item = {"id": "item_tool", "type": "commandExecution", "status": "completed", "command": "true"}
            print(json.dumps({"method": "item/completed", "params": {"threadId": params["threadId"], "turnId": turn_id, "item": item}}), flush=True)
            second = {"inputTokens": 12, "cachedInputTokens": 3, "outputTokens": 4, "reasoningOutputTokens": 1, "totalTokens": 16}
            total = {"inputTokens": 22, "cachedInputTokens": 5, "outputTokens": 7, "reasoningOutputTokens": 2, "totalTokens": 29}
            print(json.dumps({"method": "thread/tokenUsage/updated", "params": {"threadId": params["threadId"], "turnId": turn_id, "tokenUsage": {"last": second, "total": total, "modelContextWindow": 1000}}}), flush=True)
        print(json.dumps({"method": "turn/completed", "params": {"threadId": params["threadId"], "turn": {"id": turn_id, "status": "completed", "items": []}}}), flush=True)
    elif method == "command/exec":
        exit_code = int(os.environ.get("FAKE_CODEX_COMMAND_EXIT", "0"))
        print(json.dumps({"id": request_id, "result": {"exitCode": exit_code, "stdout": "Ran 1 test in 0.001s\n", "stderr": ""}}), flush=True)
    elif method == "turn/interrupt":
        if os.environ.get("FAKE_CODEX_INTERRUPT_ERROR") == "1":
            print(json.dumps({"id": request_id, "error": {"code": -32000, "message": "interrupt unavailable"}}), flush=True)
        elif os.environ.get("FAKE_CODEX_NO_ACTIVE_INTERRUPT") == "1":
            print(json.dumps({"id": request_id, "error": {"code": -32602, "message": "no active turn to interrupt"}}), flush=True)
        else:
            interrupted = True
            print(json.dumps({"id": request_id, "result": {}}), flush=True)
            if active_turn_id is not None:
                print(json.dumps({"method": "turn/completed", "params": {"threadId": active_thread_id, "turn": {"id": active_turn_id, "status": "interrupted", "items": []}}}), flush=True)
                active_turn_id = None
                active_thread_id = None
'''


class CodexExecutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        script = self.root / "fake-codex.py"
        script.write_text(FAKE_CODEX, encoding="utf-8", newline="\n")
        if os.name == "nt":
            self.fake = self.root / "fake-codex.cmd"
            self.fake.write_text(
                f'@echo off\r\n"{sys.executable}" "{script}" %*\r\n',
                encoding="utf-8",
                newline="",
            )
        else:
            script.chmod(0o755)
            self.fake = script
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
                    "outcome": "step_ready_for_verification",
                    "details": "Focused test passed.",
                    "evidence": ["tests/test_sample.py"],
                }
            )
        )
        self.assertEqual(outcome.outcome, "step_ready_for_verification")
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
        step_complete = parse_camp_outcome(
            json.dumps(
                {"outcome": "step_complete", "details": "edited", "evidence": []}
            )
        )
        self.assertEqual(
            camp_next_action(
                step_complete,
                attempt=1,
                journal=mutated,
                verification_passed=False,
            ),
            "reconcile_workspace_before_retry",
        )
        step_ready = parse_camp_outcome(
            json.dumps(
                {
                    "outcome": "step_ready_for_verification",
                    "details": "implementation ready",
                    "evidence": [],
                }
            )
        )
        self.assertEqual(
            camp_next_action(
                step_ready,
                attempt=1,
                journal=mutated,
                verification_required=True,
            ),
            "needs_user_intervention",
        )
        self.assertEqual(
            camp_next_action(
                step_ready,
                attempt=1,
                journal=mutated,
                verification_passed=True,
                verification_required=True,
                context_budget_exceeded=True,
            ),
            "needs_user_intervention",
        )

    def test_weighted_usage_and_compact_command_evidence_are_versioned(self) -> None:
        usage = {
            "turn": {
                "inputTokens": 10,
                "cachedInputTokens": 2,
                "outputTokens": 3,
                "reasoningOutputTokens": 1,
                "totalTokens": 13,
            }
        }
        weighted = weighted_codex_usage("gpt-5.6-terra", usage)
        self.assertEqual(weighted["weights_version"], "openai-relative-token-rates-2026-08-20-v1")
        self.assertEqual(weighted["units"], 26.2)
        self.assertFalse(weighted["reasoning_output_counted_separately"])
        evidence = compact_command_evidence(
            ("python3", "-m", "unittest"),
            {"exitCode": 0, "stdout": "Ran 7 tests in 0.01s\n", "stderr": ""},
        )
        self.assertTrue(evidence["passed"])
        self.assertEqual(evidence["test_count"], 7)
        self.assertFalse(evidence["output_retained"])
        self.assertNotIn("stdout", evidence)
        failed = compact_command_evidence(
            ("python3", "-c", "raise SystemExit(7)"),
            {"exitCode": 7, "stdout": "detail", "stderr": "failure"},
        )
        self.assertFalse(failed["passed"])
        self.assertEqual((failed["stdout_bytes"], failed["stderr_bytes"]), (6, 7))
        self.assertNotIn("detail", json.dumps(failed))

    def test_focused_context_finding_is_bounded_and_enforceable(self) -> None:
        finding = focused_context_finding(
            context_warning={
                "kind": "input_tokens_above_threshold",
                "input_tokens": 446_957,
                "threshold": 50_000,
            },
            mutation_events=(
                {"type": "commandExecution", "result_bytes": 207_003},
                {"type": "fileChange", "result_bytes": 400},
            ),
            max_tool_result_bytes=100_000,
        )
        self.assertFalse(finding["within_budget"])
        self.assertEqual(finding["total_tool_result_bytes"], 207_403)
        self.assertEqual(
            finding["oversized_tool_results"],
            [
                {
                    "sequence": 1,
                    "type": "commandExecution",
                    "result_bytes": 207_003,
                }
            ],
        )
        self.assertEqual(
            finding["enforcement"],
            "needs_user_intervention_before_lifecycle_advance",
        )
        self.assertNotIn("output", json.dumps(finding))

    def test_camp_execution_uses_focused_capsule_and_deterministic_verification(self) -> None:
        repository = self.root / "camp-repo"
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
        target.write_text("before\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(repository), "add", "target.txt"], check=True)
        subprocess.run(
            ["git", "-C", str(repository), "commit", "-qm", "baseline"], check=True
        )
        os.environ["FAKE_CODEX_CAMP_TARGET"] = str(target)
        try:
            payload = execute_camp_if_enabled(
                "Change the supplied target from before to after.",
                cwd=repository,
                campaign="campaign-040",
                camp="representative-edit",
                expected_paths=(Path("target.txt"),),
                explicit_files=(Path("target.txt"),),
                verification_commands=(
                    ("python3", "-c", "raise SystemExit(0)"),
                    ("python3", "-c", "raise SystemExit(0)"),
                ),
                enable_override=True,
                config=AppServerFeatureConfig.load(
                    ROOT / "adapters" / "codex-app-server-config.json"
                ),
                policy=self.policy,
                codex=str(self.fake),
                telemetry_path=self.root / "camp-telemetry.jsonl",
            )
        finally:
            os.environ.pop("FAKE_CODEX_CAMP_TARGET", None)
        self.assertEqual(target.read_text(encoding="utf-8"), "after\n")
        self.assertGreater(payload["camp_duration_seconds"], 0)
        self.assertEqual(payload["next_action"], "advance_to_next_camp_step")
        self.assertEqual(
            payload["structured_outcome"]["outcome"],
            "step_ready_for_verification",
        )
        self.assertEqual(payload["mutation_journal"]["final_state"], "verified")
        self.assertTrue(payload["verification"][0]["passed"])
        self.assertEqual(payload["verification"][0]["test_count"], 1)
        self.assertEqual(len(payload["verification"]), 2)
        self.assertEqual(payload["mutation_journal"]["files_modified"], ["target.txt"])
        self.assertEqual(
            payload["mutation_journal"]["deterministic_verification"],
            {"required": True, "passed": True, "commands_run": 2},
        )
        self.assertEqual(
            payload["mutation_journal"]["commands_executed"],
            [
                ["python3", "-c", "raise SystemExit(0)"],
                ["python3", "-c", "raise SystemExit(0)"],
            ],
        )
        context = payload["result"]["context_scope"]
        self.assertEqual(context["mode"], "focused_camp_capsule")
        self.assertEqual(context["sandbox_root"], str(repository.resolve()))

    def test_windows_verification_uses_local_read_only_codex_sandbox(self) -> None:
        client = SimpleNamespace(command_exec=Mock())
        adapter = SimpleNamespace(client=client)
        completed = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="verified\n", stderr=""
        )
        with (
            patch("scripts.codex_orchestration.sys.platform", "win32"),
            patch(
                "scripts.codex_orchestration.subprocess.run",
                return_value=completed,
            ) as run,
        ):
            response = execute_deterministic_verification(
                adapter,
                ("python", "verify.py"),
                cwd=self.root,
                codex="C:/gui/codex.exe",
                timeout=30,
            )

        self.assertEqual(0, response["exitCode"])
        self.assertEqual("verified\n", response["stdout"])
        client.command_exec.assert_not_called()
        self.assertEqual(
            [
                "C:/gui/codex.exe",
                "sandbox",
                "--permission-profile",
                ":read-only",
                "-C",
                str(self.root.resolve()),
                "python",
                "verify.py",
            ],
            run.call_args.args[0],
        )
        self.assertEqual("1", run.call_args.kwargs["env"]["PYTHONDONTWRITEBYTECODE"])

    def test_failed_deterministic_verification_requires_reconciliation(self) -> None:
        repository = self.root / "failed-camp-repo"
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
        target.write_text("before\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(repository), "add", "target.txt"], check=True)
        subprocess.run(
            ["git", "-C", str(repository), "commit", "-qm", "baseline"], check=True
        )
        os.environ["FAKE_CODEX_CAMP_TARGET"] = str(target)
        os.environ["FAKE_CODEX_COMMAND_EXIT"] = "7"
        os.environ["FAKE_CODEX_CAMP_OUTCOME"] = "step_complete"
        try:
            payload = execute_camp_if_enabled(
                "Change before to after.",
                cwd=repository,
                campaign="campaign-040",
                camp="diagnostic",
                expected_paths=(Path("target.txt"),),
                explicit_files=(Path("target.txt"),),
                verification_commands=(
                    ("python3", "-c", "raise SystemExit(7)"),
                    ("python3", "-c", "raise SystemExit(7)"),
                ),
                enable_override=True,
                config=AppServerFeatureConfig.load(
                    ROOT / "adapters" / "codex-app-server-config.json"
                ),
                policy=self.policy,
                codex=str(self.fake),
                telemetry_path=self.root / "failed-camp-telemetry.jsonl",
            )
        finally:
            os.environ.pop("FAKE_CODEX_CAMP_TARGET", None)
            os.environ.pop("FAKE_CODEX_COMMAND_EXIT", None)
            os.environ.pop("FAKE_CODEX_CAMP_OUTCOME", None)
        self.assertEqual(payload["next_action"], "reconcile_workspace_before_retry")
        self.assertEqual(payload["mutation_journal"]["final_state"], "verification_failed")
        self.assertEqual(
            payload["mutation_journal"]["deterministic_verification"]["passed"], False
        )
        self.assertEqual(
            payload["mutation_journal"]["deterministic_verification"]["commands_run"], 2
        )

    def test_safe_unknown_after_mutation_stays_unverified_without_retry_or_checks(self) -> None:
        repository = self.root / "unknown-camp-repo"
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
        target.write_text("before\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(repository), "add", "target.txt"], check=True)
        subprocess.run(
            ["git", "-C", str(repository), "commit", "-qm", "baseline"], check=True
        )
        os.environ["FAKE_CODEX_CAMP_TARGET"] = str(target)
        os.environ["FAKE_CODEX_CAMP_OUTCOME"] = "unknown"
        try:
            payload = execute_camp_if_enabled(
                "Make the bounded edit, but reproduce an unknown terminal assessment.",
                cwd=repository,
                campaign="campaign-013",
                camp="observed-safe-unknown",
                expected_paths=(Path("target.txt"),),
                explicit_files=(Path("target.txt"),),
                verification_commands=(("python3", "-c", "raise SystemExit(0)"),),
                enable_override=True,
                config=AppServerFeatureConfig.load(
                    ROOT / "adapters" / "codex-app-server-config.json"
                ),
                policy=self.policy,
                codex=str(self.fake),
                telemetry_path=self.root / "unknown-camp-telemetry.jsonl",
            )
        finally:
            os.environ.pop("FAKE_CODEX_CAMP_TARGET", None)
            os.environ.pop("FAKE_CODEX_CAMP_OUTCOME", None)
        self.assertEqual(target.read_text(encoding="utf-8"), "after\n")
        self.assertEqual(payload["structured_outcome"]["outcome"], "unknown")
        self.assertEqual(payload["verification"], [])
        self.assertEqual(
            payload["mutation_journal"]["deterministic_verification"],
            {"required": True, "passed": None, "commands_run": 0},
        )
        self.assertEqual(payload["mutation_journal"]["final_state"], "safe_unverified")
        self.assertEqual(payload["next_action"], "needs_user_intervention")

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
        self.assertEqual(record["final_state"], "safe_unverified")
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
        self.assertEqual(record["model_turn_events"][0]["tokens"]["uncached_input"], 8)
        self.assertEqual(record["weighted_usage"]["units"], 26.2)
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
        self.assertEqual(user_agent, "fake-codex/0.149.0")
        self.assertEqual({item["id"] for item in models}, {"gpt-5.6-sol", "gpt-5.6-terra"})

    def test_feature_flags_preserve_gui_fallback_and_discussion(self) -> None:
        config = AppServerFeatureConfig.load(ROOT / "adapters" / "codex-app-server-config.json")
        self.assertEqual(config.context_delivery, "inline_relevant_files")
        self.assertEqual(config.max_tool_result_bytes, 100_000)
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
        self.assertEqual(
            config.qualified_codex_versions,
            ("0.149.0", "0.149.0-alpha.4.3"),
        )
        self.assertEqual(config.qualified_write_codex_versions, ("0.149.0",))
        self.assertEqual(config.minimum_dirty_read_codex_version, "0.146.0")
        self.assertIsNone(config.compatibility_warning(str(self.fake)))
        os.environ["FAKE_CODEX_VERSION"] = "0.200.0"
        try:
            warning = config.compatibility_warning(str(self.fake))
        finally:
            os.environ.pop("FAKE_CODEX_VERSION", None)
        self.assertIn(
            "Qualified versions: 0.149.0, 0.149.0-alpha.4.3",
            warning or "",
        )
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

    def test_user_command_control_preserves_gui_and_routes_qualified_roles(self) -> None:
        normal = select_command(
            "plan",
            app_server_requested=False,
            codex=str(self.fake),
        )
        self.assertTrue(normal.allowed)
        self.assertEqual((normal.execution, normal.reason), ("GUI", "default_gui"))
        self.assertEqual(format_selection(normal), "Execution: GUI")

        expected = {
            "plan": ("planning", "gpt-5.6-sol", "high", "run"),
            "verify": ("verification", "gpt-5.6-terra", "low", "run"),
            "camp-run": (
                "CAMP execution",
                "gpt-5.6-terra",
                "medium",
                "camp-run",
            ),
        }
        for command, route in expected.items():
            with self.subTest(command=command):
                selected = select_command(
                    command,
                    app_server_requested=True,
                    codex=str(self.fake),
                )
                self.assertTrue(selected.allowed)
                self.assertEqual(selected.execution, "App Server")
                self.assertEqual(
                    (
                        selected.role,
                        selected.model,
                        selected.reasoning,
                        selected.orchestrator_subcommand,
                    ),
                    route,
                )
                self.assertEqual(selected.opt_in, "explicit")
                self.assertEqual(selected.global_default, "OFF")
                self.assertFalse(selected.api_fallback)
                self.assertIn("Execution: App Server", format_selection(selected))
                self.assertIn("API fallback: disabled", format_selection(selected))

    def test_user_command_control_rejects_discussion_and_unqualified_roles(self) -> None:
        discussion = select_command(
            "discuss",
            app_server_requested=True,
            codex=str(self.fake),
        )
        self.assertFalse(discussion.allowed)
        self.assertEqual(discussion.execution, "GUI")
        self.assertEqual(discussion.reason, "discussion_is_gui_native")
        self.assertIn("App Server request: BLOCKED", format_selection(discussion))

        deployment = select_role(
            "deployment",
            command="deployment",
            display_role="deployment",
            sandbox="workspace-write",
            orchestrator_subcommand="none",
            app_server_requested=True,
            codex=str(self.fake),
        )
        self.assertFalse(deployment.allowed)
        self.assertEqual(deployment.reason, "role_feature_disabled")
        self.assertEqual(deployment.execution, "GUI")

    def test_user_command_control_blocks_codex_below_dirty_read_minimum(self) -> None:
        os.environ["FAKE_CODEX_VERSION"] = "0.145.9"
        try:
            selected = select_command(
                "verify",
                app_server_requested=True,
                codex=str(self.fake),
            )
        finally:
            os.environ.pop("FAKE_CODEX_VERSION", None)
        self.assertFalse(selected.allowed)
        self.assertEqual(selected.reason, "codex_below_minimum_dirty_read_version")
        self.assertEqual(selected.execution, "GUI")
        self.assertTrue(selected.fallback_available)
        self.assertEqual(selected.installed_codex, "0.145.9")
        self.assertEqual(selected.compatibility, "unqualified_version")
        self.assertEqual(selected.qualification_mode, "below_minimum")
        self.assertEqual(selected.qualification_state, "below-minimum")
        self.assertEqual(selected.codex_executable, str(self.fake))
        self.assertIsNone(selected.dirty_qualification)
        blocked_banner = format_selection(selected)
        self.assertIn("Installed Codex: 0.145.9", blocked_banner)
        self.assertIn(f"Executable: {self.fake}", blocked_banner)
        self.assertIn("Qualification state: below-minimum", blocked_banner)
        self.assertIn("Qualified Codex: 0.149.0", blocked_banner)

    def test_unseen_newer_codex_dirty_qualifies_and_continues_read_request(self) -> None:
        os.environ["FAKE_CODEX_VERSION"] = "0.200.0-alpha.7"
        telemetry = self.root / "dirty-select.jsonl"
        try:
            with patch(
                "scripts.codex_app_server_compatibility.default_telemetry_path",
                return_value=telemetry,
            ):
                selected = select_command(
                    "verify",
                    app_server_requested=True,
                    codex=str(self.fake),
                    qualification_cache_path=self.root / "dirty-cache.json",
                )
            decision, result = execute_if_enabled(
                "continue the original explicit verification request",
                role="verification",
                cwd=ROOT,
                enable_override=True,
                config=AppServerFeatureConfig.load(
                    ROOT / "adapters" / "codex-app-server-config.json"
                ),
                policy=self.policy,
                codex=str(self.fake),
                telemetry_path=self.root / "continued.jsonl",
            )
        finally:
            os.environ.pop("FAKE_CODEX_VERSION", None)
        self.assertTrue(selected.allowed)
        self.assertEqual(selected.reason, "explicit_dirty_qualified_opt_in")
        self.assertEqual(selected.qualification_mode, "dirty_read")
        self.assertEqual(selected.qualification_state, "dirty-qualified")
        self.assertEqual(selected.compatibility, "qualified")
        self.assertEqual(selected.dirty_qualification["fatal_failures"], [])
        self.assertIn("Reason: explicit_dirty_qualified_opt_in", format_selection(selected))
        self.assertIn(f"Executable: {self.fake}", format_selection(selected))
        self.assertTrue(decision.use_app_server)
        self.assertEqual(result.status, "completed")

    def test_dirty_read_version_floor_accepts_prereleases_without_upper_cutoff(self) -> None:
        self.assertEqual(codex_version_core("0.149.0-alpha.4.3"), (0, 149, 0))
        for version in ("0.146.0-alpha.1", "0.149.0", "0.150.0", "1.0.0-beta.2"):
            with self.subTest(version=version):
                self.assertTrue(codex_version_at_least(version, "0.146.0"))
        for version in ("0.145.99", "bad", None):
            with self.subTest(version=version):
                self.assertFalse(codex_version_at_least(version, "0.146.0"))

    def test_dirty_read_qualification_negotiates_profile_and_legacy_fallback(self) -> None:
        os.environ["FAKE_CODEX_VERSION"] = "0.200.0"
        try:
            profile = dirty_read_qualification_report(
                codex=str(self.fake),
                cwd=ROOT,
                telemetry_path=self.root / "profile.jsonl",
                timeout=2,
            )
            os.environ["FAKE_CODEX_NO_PERMISSION_PROFILES"] = "1"
            legacy = dirty_read_qualification_report(
                codex=str(self.fake),
                cwd=ROOT,
                telemetry_path=self.root / "legacy.jsonl",
                timeout=2,
            )
        finally:
            os.environ.pop("FAKE_CODEX_NO_PERMISSION_PROFILES", None)
            os.environ.pop("FAKE_CODEX_VERSION", None)
        self.assertEqual(profile["outcome"], "qualified")
        self.assertEqual(
            profile["permission_negotiation"]["permission_profile"], ":read-only"
        )
        self.assertEqual(legacy["outcome"], "qualified")
        self.assertEqual(
            legacy["permission_negotiation"]["mode"], "legacy_sandbox_policy"
        )
        for report in (profile, legacy):
            by_name = {item["name"]: item for item in report["checks"]}
            self.assertEqual(by_name["read_only_workspace_unchanged"]["status"], "pass")
            self.assertEqual(by_name["read_only_no_mutation_events"]["status"], "pass")
            self.assertEqual(by_name["cancellation_reconciliation"]["status"], "pass")

    def test_dirty_read_qualification_classifies_transient_and_unsafe_failures(self) -> None:
        os.environ["FAKE_CODEX_VERSION"] = "0.200.0"
        os.environ["FAKE_CODEX_ACCOUNT"] = "apiKey"
        try:
            transient = dirty_read_qualification_report(
                codex=str(self.fake),
                cwd=ROOT,
                telemetry_path=self.root / "fatal.jsonl",
                timeout=2,
            )
        finally:
            os.environ.pop("FAKE_CODEX_ACCOUNT", None)
        os.environ["FAKE_CODEX_DISALLOW_READ_ONLY"] = "1"
        try:
            unsafe = dirty_read_qualification_report(
                codex=str(self.fake),
                cwd=ROOT,
                telemetry_path=self.root / "unknown.jsonl",
                timeout=2,
            )
        finally:
            os.environ.pop("FAKE_CODEX_DISALLOW_READ_ONLY", None)
            os.environ.pop("FAKE_CODEX_VERSION", None)
        self.assertEqual(transient["outcome"], "unqualified_transient")
        self.assertIn("app_server_runtime", transient["transient_failures"])
        self.assertFalse(transient["cacheable_unsafe"])
        self.assertEqual(unsafe["outcome"], "unqualified_fatal")
        self.assertIn("app_server_runtime", unsafe["fatal_failures"])
        self.assertTrue(unsafe["cacheable_unsafe"])

    def test_dirty_read_qualification_keeps_safe_blockers_distinct(self) -> None:
        os.environ.update(
            {
                "FAKE_CODEX_VERSION": "0.200.0",
                "FAKE_CODEX_NO_ACTIVE_INTERRUPT": "1",
                "FAKE_CODEX_READ_TURN_STATUS": "interrupted",
            }
        )
        try:
            report = dirty_read_qualification_report(
                codex=str(self.fake),
                cwd=ROOT,
                telemetry_path=self.root / "safe-blocker.jsonl",
                timeout=2,
            )
        finally:
            for name in (
                "FAKE_CODEX_VERSION",
                "FAKE_CODEX_NO_ACTIVE_INTERRUPT",
                "FAKE_CODEX_READ_TURN_STATUS",
            ):
                os.environ.pop(name, None)
        self.assertEqual(report["outcome"], "qualified_with_blockers")
        self.assertEqual(report["safe_blockers"], ["cancellation_acknowledgement"])
        self.assertEqual(report["fatal_failures"], [])
        self.assertEqual(report["unknown_failures"], [])

    def test_unseen_version_never_inherits_workspace_write_qualification(self) -> None:
        os.environ["FAKE_CODEX_VERSION"] = "0.200.0"
        try:
            with patch(
                "scripts.app_server_control.dirty_read_qualification_report"
            ) as dirty_qualify:
                selected = select_command(
                    "camp-run",
                    app_server_requested=True,
                    codex=str(self.fake),
                )
        finally:
            os.environ.pop("FAKE_CODEX_VERSION", None)
        dirty_qualify.assert_not_called()
        self.assertFalse(selected.allowed)
        self.assertEqual(selected.reason, "codex_version_not_qualified")
        self.assertEqual(selected.qualification_mode, "none")
        self.assertEqual(selected.qualification_state, "write-not-qualified")

    def test_dirty_selection_distinguishes_transient_fallback_and_unsafe_block(self) -> None:
        os.environ["FAKE_CODEX_VERSION"] = "0.200.0"
        try:
            for outcome, expected_state, expected_reason in (
                ("unqualified_unknown", "transient-fallback", "dirty_qualification_unknown"),
                ("unqualified_fatal", "unsafe-blocked", "dirty_qualification_failed"),
            ):
                with self.subTest(outcome=outcome), patch(
                    "scripts.app_server_control.dirty_read_qualification_report",
                    return_value={"outcome": outcome},
                ):
                    selected = select_command(
                        "verify",
                        app_server_requested=True,
                        codex=str(self.fake),
                        qualification_cache_path=self.root / f"{outcome}.json",
                    )
                    self.assertFalse(selected.allowed)
                    self.assertEqual(selected.qualification_state, expected_state)
                    self.assertEqual(selected.reason, expected_reason)
                    self.assertIn(f"Executable: {self.fake}", format_selection(selected))
        finally:
            os.environ.pop("FAKE_CODEX_VERSION", None)

    def test_dirty_qualification_cache_reuses_safe_results_and_retries_transient_failures(self) -> None:
        os.environ["FAKE_CODEX_VERSION"] = "0.200.0"
        safe_cache = self.root / "safe-cache.json"
        transient_cache = self.root / "transient-cache.json"
        try:
            with patch(
                "scripts.app_server_control.dirty_read_qualification_report",
                return_value={
                    "outcome": "qualified_with_blockers",
                    "safe_blockers": ["cancellation_acknowledgement"],
                    "fatal_failures": [],
                    "transient_failures": [],
                    "unknown_failures": [],
                    "cacheable_unsafe": False,
                },
            ) as qualify:
                first = select_command(
                    "verify",
                    app_server_requested=True,
                    codex=str(self.fake),
                    qualification_cache_path=safe_cache,
                )
                second = select_command(
                    "verify",
                    app_server_requested=True,
                    codex=str(self.fake),
                    qualification_cache_path=safe_cache,
                )
            self.assertEqual(qualify.call_count, 1)
            self.assertTrue(first.allowed)
            self.assertTrue(second.allowed)
            self.assertEqual(second.qualification_cache["decision_source"], "cache")
            self.assertEqual(second.qualification_cache["record"]["state"], "qualified")

            status = status_report(
                codex=str(self.fake), qualification_cache_path=safe_cache
            )
            self.assertEqual(status["qualification_state"], "dirty-qualified")
            self.assertEqual(status["compatibility"], "dirty_qualified")
            self.assertIn("planning", status["enabled_roles"])
            self.assertIn("verification", status["enabled_roles"])
            self.assertNotIn("camp_execution", status["enabled_roles"])
            self.assertIsNone(status["version_warning"])
            self.assertIn("workspace-write is not qualified", status["known_blockers"])

            with patch(
                "scripts.app_server_control.dirty_read_qualification_report",
                return_value={
                    "outcome": "unqualified_transient",
                    "safe_blockers": [],
                    "fatal_failures": [],
                    "transient_failures": ["app_server_runtime"],
                    "unknown_failures": [],
                    "cacheable_unsafe": False,
                },
            ) as qualify:
                for _ in range(2):
                    selected = select_command(
                        "verify",
                        app_server_requested=True,
                        codex=str(self.fake),
                        qualification_cache_path=transient_cache,
                    )
                    self.assertFalse(selected.allowed)
                    self.assertEqual(selected.qualification_state, "transient-fallback")
            self.assertEqual(qualify.call_count, 2)
            self.assertFalse(transient_cache.exists())
        finally:
            os.environ.pop("FAKE_CODEX_VERSION", None)

    def test_cached_unsafe_denial_requires_explicit_requalification(self) -> None:
        os.environ["FAKE_CODEX_VERSION"] = "0.200.0"
        cache_path = self.root / "unsafe-cache.json"
        try:
            with patch(
                "scripts.app_server_control.dirty_read_qualification_report",
                return_value={
                    "outcome": "unqualified_fatal",
                    "safe_blockers": [],
                    "fatal_failures": ["read_only_permission_profile"],
                    "transient_failures": [],
                    "unknown_failures": [],
                    "cacheable_unsafe": True,
                },
            ) as qualify:
                first = select_command(
                    "verify",
                    app_server_requested=True,
                    codex=str(self.fake),
                    qualification_cache_path=cache_path,
                )
                second = select_command(
                    "verify",
                    app_server_requested=True,
                    codex=str(self.fake),
                    qualification_cache_path=cache_path,
                )
            self.assertEqual(qualify.call_count, 1)
            self.assertFalse(first.allowed)
            self.assertFalse(second.allowed)
            self.assertEqual(second.qualification_cache["decision_source"], "cache")
            self.assertEqual(
                second.qualification_cache["record"]["state"], "unsafe_denied"
            )

            with patch(
                "scripts.app_server_control.dirty_read_qualification_report",
                return_value={
                    "outcome": "qualified",
                    "safe_blockers": [],
                    "fatal_failures": [],
                    "transient_failures": [],
                    "unknown_failures": [],
                    "cacheable_unsafe": False,
                },
            ) as qualify:
                requalified = select_command(
                    "verify",
                    app_server_requested=True,
                    codex=str(self.fake),
                    qualification_cache_path=cache_path,
                    force_requalification=True,
                )
            qualify.assert_called_once()
            self.assertTrue(requalified.allowed)
            self.assertEqual(
                requalified.qualification_cache["decision_source"],
                "live-requalification",
            )
        finally:
            os.environ.pop("FAKE_CODEX_VERSION", None)

    def test_user_command_control_allows_alpha_reads_but_blocks_alpha_camp(self) -> None:
        os.environ["FAKE_CODEX_VERSION"] = "0.149.0-alpha.4.3"
        try:
            planning = select_command(
                "plan",
                app_server_requested=True,
                codex=str(self.fake),
            )
            camp = select_command(
                "camp-run",
                app_server_requested=True,
                codex=str(self.fake),
            )
            status = status_report(codex=str(self.fake))
        finally:
            os.environ.pop("FAKE_CODEX_VERSION", None)
        self.assertTrue(planning.allowed)
        self.assertEqual(planning.reason, "explicit_qualified_opt_in")
        self.assertFalse(camp.allowed)
        self.assertEqual(camp.reason, "role_not_qualified")
        self.assertEqual(camp.qualification_state, "write-not-qualified")
        self.assertEqual(status["compatibility"], "qualified_with_blockers")
        self.assertNotIn("camp_execution", status["enabled_roles"])
        self.assertIn("CAMP execution", status["disabled"])

    def test_project_write_qualification_rejects_executable_hash_mismatch(self) -> None:
        config_payload = json.loads(
            (ROOT / "adapters" / "codex-app-server-config.json").read_text(encoding="utf-8")
        )
        config_payload["qualification"]["validated_codex_cli_version"] = "0.149.0-alpha.4.3"
        config_payload["qualification"]["validated_codex_cli_versions"] = [
            "0.149.0-alpha.4.3"
        ]
        config_payload["write_execution"]["qualified_codex_cli_version"] = (
            "0.149.0-alpha.4.3"
        )
        config_payload["write_execution"].pop("qualified_codex_cli_versions", None)
        config_path = self.root / "project-config.json"
        config_path.write_text(json.dumps(config_payload), encoding="utf-8")
        qualifications_path = self.root / "project-qualifications.json"
        qualifications_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "records": [
                        {
                            "codex_version": "0.149.0-alpha.4.3",
                            "status": "qualified_with_blockers",
                            "routing": {
                                "camp_execution": {
                                    "model": "gpt-5.6-terra",
                                    "reasoning": "medium",
                                    "qualified": True,
                                }
                            },
                            "workspace_writing": True,
                            "workspace_write_qualification": {
                                "executable_sha256": "0" * 64,
                            },
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        os.environ["FAKE_CODEX_VERSION"] = "0.149.0-alpha.4.3"
        try:
            selected = select_command(
                "camp-run",
                app_server_requested=True,
                codex=str(self.fake),
                config_path=config_path,
                qualifications_path=qualifications_path,
            )
        finally:
            os.environ.pop("FAKE_CODEX_VERSION", None)
        self.assertFalse(selected.allowed)
        self.assertEqual("codex_executable_hash_mismatch", selected.reason)
        self.assertEqual("write-not-qualified", selected.qualification_state)

        qualification_payload = json.loads(
            qualifications_path.read_text(encoding="utf-8")
        )
        qualification_payload["records"][0]["workspace_write_qualification"][
            "executable_sha256"
        ] = hashlib.sha256(self.fake.read_bytes()).hexdigest()
        qualifications_path.write_text(
            json.dumps(qualification_payload), encoding="utf-8"
        )
        os.environ["FAKE_CODEX_VERSION"] = "0.149.0-alpha.4.3"
        try:
            matching = select_command(
                "camp-run",
                app_server_requested=True,
                codex=str(self.fake),
                config_path=config_path,
                qualifications_path=qualifications_path,
            )
        finally:
            os.environ.pop("FAKE_CODEX_VERSION", None)
        self.assertTrue(matching.allowed)
        self.assertEqual("explicit_qualified_opt_in", matching.reason)

    def test_user_command_status_and_session_control_are_explicit_only(self) -> None:
        report = control_status(codex=str(self.fake))
        self.assertEqual(report["global_default"], "OFF")
        self.assertEqual(report["session_opt_in"], "OFF")
        self.assertFalse(report["session_control_supported"])
        self.assertEqual(report["current_execution_default"], "GUI")
        self.assertEqual(report["discussion_execution"], "GUI-native")
        self.assertFalse(report["api_fallback"])
        self.assertEqual(report["minimum_dirty_read_codex"], "0.146.0")
        self.assertEqual(
            (
                report["enabled_roles"]["planning"]["model"],
                report["enabled_roles"]["planning"]["reasoning"],
            ),
            ("gpt-5.6-sol", "high"),
        )
        self.assertIn("App Server global default: OFF", format_control_status(report))
        for action in ("on", "off"):
            with self.subTest(action=action):
                session = session_control(action)
                self.assertFalse(session["accepted"])
                self.assertEqual(session["session_opt_in"], "OFF")
                self.assertFalse(session["session_control_supported"])
                self.assertFalse(session["persistent_changes"])
                self.assertIn("--app-server", session["next_action"])

    def test_user_command_control_cli_reports_banners_and_fail_closed_exits(self) -> None:
        base = [
            sys.executable,
            str(ROOT / "scripts" / "app_server_control.py"),
            "--codex",
            str(self.fake),
        ]
        selected = subprocess.run(
            [*base, "select", "camp-run", "--app-server"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(selected.returncode, 0)
        self.assertIn("Execution: App Server", selected.stdout)
        self.assertIn("Role: CAMP execution", selected.stdout)
        self.assertIn("Model: gpt-5.6-terra", selected.stdout)
        self.assertIn("Reasoning: medium", selected.stdout)

        discussion = subprocess.run(
            [*base, "select", "discuss", "--app-server"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(discussion.returncode, 2)
        self.assertIn("discussion_is_gui_native", discussion.stdout)

        session = subprocess.run(
            [*base, "session", "on", "--json"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(session.returncode, 2)
        self.assertFalse(json.loads(session.stdout)["persistent_changes"])

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
        self.assertEqual(len(result.model_turn_events), 2)
        self.assertEqual(result.model_turn_events[1]["preceding_tool"], "commandExecution")
        self.assertGreater(result.model_turn_events[1]["preceding_tool_result_bytes"], 0)
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
        self.assertEqual(report["summary"]["weighted_codex_usage_units"], 26.2)
        self.assertEqual(report["operations"][0]["program"], "P")
        self.assertNotIn("secret prompt", json.dumps(report))
        qualification = qualification_report(
            telemetry,
            qualification_id="Q",
            baseline_input_tokens=8,
            expected_codex_version="0.149.0",
            codex=str(self.fake),
        )
        self.assertEqual(qualification["operations"], 1)
        self.assertEqual(qualification["verification_terra"]["avoidable_input_tokens"], 2)
        self.assertEqual(qualification["codex_cli_version"], "0.149.0")
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

    def test_resolved_bundled_executable_is_shared_by_version_detection_and_startup(self) -> None:
        # The resolver's source records that this represents a trusted VS Code
        # bundle; the executable remains platform-native for this test run.
        bundled = self.fake
        resolution = CodexCliResolution(
            CodexSource.VSCODE_EXTENSION,
            bundled,
            "0.144.6",
            CodexReadiness.AVAILABLE_UNQUALIFIED,
        )

        class BundledResolver:
            def resolve(self, **_kwargs: object) -> CodexCliResolution:
                return resolution

        with patch("scripts.codex_execution.CodexCliResolver", return_value=BundledResolver()), patch(
            "scripts.codex_app_server.CodexCliResolver", return_value=BundledResolver()
        ):
            self.assertEqual(detect_codex_version(), "0.144.6")
            with CodexAppServerClient(timeout=2) as client:
                self.assertEqual(client.codex, str(bundled))

    def test_orchestration_resolves_once_before_passing_to_adapter(self) -> None:
        discovered = str(self.fake)
        config = AppServerFeatureConfig.load(ROOT / "adapters" / "codex-app-server-config.json")
        with patch("scripts.codex_orchestration.resolve_codex_executable", return_value=discovered) as resolve:
            decision, result = execute_if_enabled(
                "use the discovered executable",
                role="planning",
                cwd=ROOT,
                enable_override=True,
                config=config,
                policy=self.policy,
                codex=None,
                telemetry_path=self.root / "resolved.jsonl",
            )
        self.assertTrue(decision.use_app_server)
        self.assertIsNotNone(result)
        resolve.assert_called_once_with(None)

    def test_compatibility_status_and_smoke_are_version_aware(self) -> None:
        qualifications = load_qualifications(
            ROOT / "adapters" / "codex-app-server-qualifications.json"
        )
        self.assertEqual(qualifications[-1]["codex_version"], "0.149.0")
        status = status_report(codex=str(self.fake))
        self.assertEqual(status["status"], "OPT-IN")
        self.assertEqual(status["global_default"], "disabled")
        self.assertEqual(status["compatibility"], "qualified_with_blockers")
        self.assertIsNone(status["qualified_savings"])
        self.assertEqual(
            status["qualification_record"]["tiny_smoke_input_tokens"]["minimum"],
            18983,
        )
        self.assertEqual(
            status["enabled_roles"]["camp_execution"],
            {
                "model": "gpt-5.6-terra",
                "reasoning": "medium",
                "sandbox": "workspace-write",
                "scope": "explicit paths with Git mutation journal",
                "qualification": "exact-qualified",
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
        self.assertEqual(by_name["cancellation_reconciliation"]["status"], "pass")
        self.assertEqual(smoke["cancellation"]["outcome"], "cancelled")
        self.assertEqual(by_name["restricted_read_behavior"]["status"], "blocked")
        self.assertFalse(smoke["qualification_record_updated"])
        self.assertNotIn("APP_SERVER_PLANNING_SMOKE_OK", telemetry.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
