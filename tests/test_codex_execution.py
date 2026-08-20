from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from scripts.codex_app_server import AuthenticationError
from scripts.codex_execution import CodexExecutionAdapter, ModelPolicy, ModelPolicyError
from scripts.reasoning_catalog import query_codex_catalog


ROOT = Path(__file__).resolve().parents[1]


FAKE_CODEX = r'''#!/usr/bin/env python3
import json
import os
import sys

account_type = os.environ.get("FAKE_CODEX_ACCOUNT", "chatgpt")
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
        thread_id = message.get("params", {}).get("threadId", "thr_fake")
        print(json.dumps({"id": request_id, "result": {"thread": {"id": thread_id, "status": {"type": "idle"}}}}), flush=True)
    elif method == "thread/read":
        thread_id = message["params"]["threadId"]
        print(json.dumps({"id": request_id, "result": {"thread": {"id": thread_id, "status": {"type": "idle"}}}}), flush=True)
    elif method == "turn/start":
        params = message["params"]
        turn_id = "turn_fake"
        print(json.dumps({"id": request_id, "result": {"turn": {"id": turn_id, "status": "inProgress", "items": []}}}), flush=True)
        print(json.dumps({"method": "item/agentMessage/delta", "params": {"threadId": params["threadId"], "turnId": turn_id, "delta": "FAKE_OK"}}), flush=True)
        usage = {"inputTokens": 10, "cachedInputTokens": 2, "outputTokens": 3, "reasoningOutputTokens": 1, "totalTokens": 13}
        print(json.dumps({"method": "thread/tokenUsage/updated", "params": {"threadId": params["threadId"], "turnId": turn_id, "tokenUsage": {"last": usage, "total": usage, "modelContextWindow": 1000}}}), flush=True)
        print(json.dumps({"method": "turn/completed", "params": {"threadId": params["threadId"], "turn": {"id": turn_id, "status": "completed", "items": []}}}), flush=True)
    elif method == "turn/interrupt":
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
        self.assertEqual((planning.model, planning.reasoning), ("gpt-5.6-sol", "high"))
        self.assertEqual((verification.model, verification.reasoning), ("gpt-5.6-terra", "low"))
        self.assertNotIn("luna", json.dumps(self.policy.payload).lower())

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
            )
        self.assertEqual(result.text, "FAKE_OK")
        self.assertEqual(result.requested_model, "gpt-5.6-terra")
        self.assertEqual(result.reasoning, "medium")
        record = json.loads(telemetry.read_text(encoding="utf-8"))
        self.assertEqual(record["program"], "program-a")
        self.assertEqual(record["camp"], "camp-b")
        self.assertEqual(record["actual_model"], "gpt-5.6-terra")
        self.assertEqual(record["token_usage"]["last"]["totalTokens"], 13)
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


if __name__ == "__main__":
    unittest.main()
