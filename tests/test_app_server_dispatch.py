from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from scripts import campaign_queue
from scripts.app_server_dispatch import (
    DispatchError,
    _automatic_preparation_context,
    _automatic_preparation_prompt,
    _parse_automatic_preparation,
    dispatch_next,
    parse_execution_capsule,
)
from scripts.project_identity import ensure_project_identity


def capsule(campaign_id: str, *, shell: bool = False) -> str:
    command = '["bash", "-lc", "true"]' if shell else '["python3", "-c", "assert True"]'
    return f"""## Request

Create only `proof.txt`.

## App Server Execution Capsule

```json
{{
  "schema_version": 1,
  "campaign_id": "{campaign_id}",
  "camp": "create-proof",
  "prompt": "Create proof.txt with the exact text PASS and a trailing newline.",
  "expected_paths": ["proof.txt"],
  "context_files": [],
  "verification_commands": [{command}]
}}
```

## Completion Check

The proof is verified.
"""


class AppServerDispatchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temporary.name).resolve()
        subprocess.run(
            ["git", "init", "-q", "-b", "main", str(self.workspace)],
            check=True,
        )
        ensure_project_identity(self.workspace, project_name="dispatch-test")
        campaign_queue.ensure_tree(self.workspace)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def add_campaign(
        self,
        campaign_id: str,
        *,
        shell: bool = False,
        with_capsule: bool = True,
    ) -> Path:
        path = (
            self.workspace
            / "work"
            / "00-campaigns"
            / "active"
            / f"001-{campaign_id}.md"
        )
        text = campaign_queue._campaign_text(
            campaign_id,
            "Dispatch proof",
            "Prove deterministic dispatch.",
            "The proof is verified.",
            [],
            "none",
            "none",
            "none",
            campaign_number="001",
        )
        if with_capsule:
            text = text[: text.index("## Request")] + capsule(campaign_id, shell=shell)
        path.write_text(text, encoding="utf-8")
        campaigns = campaign_queue.load_all(self.workspace)
        (self.workspace / "work" / "00-campaigns" / "active-queue.md").write_text(
            campaign_queue.render_active_queue([campaign_id], campaigns, None),
            encoding="utf-8",
        )
        return path

    @staticmethod
    def execution_result() -> dict[str, object]:
        return {
            "result": {
                "token_usage": {
                    "total": {
                        "inputTokens": 20000,
                        "cachedInputTokens": 18000,
                        "outputTokens": 200,
                        "reasoningOutputTokens": 50,
                        "totalTokens": 20200,
                    }
                },
                "model_turns": 2,
                "tool_calls": 1,
                "tool_call_types": ["fileChange"],
                "duration_seconds": 4.5,
            },
            "mutation_journal": {
                "safe": True,
                "final_state": "verified",
                "expected_paths": ["proof.txt"],
                "files_created": ["proof.txt"],
                "files_modified": [],
                "files_deleted": [],
                "unexpected_paths": [],
                "deterministic_verification": {"commands_run": 1, "passed": True},
            },
            "camp_duration_seconds": 5.0,
            "next_action": "advance_to_next_camp_step",
        }

    def test_capsule_rejects_shell_verification(self) -> None:
        path = self.add_campaign("dispatch-proof", shell=True)
        campaign = campaign_queue.parse_campaign(path)
        with self.assertRaisesRegex(DispatchError, "cannot invoke a shell"):
            parse_execution_capsule(self.workspace, campaign)

    def test_dispatch_uses_ordinary_next_starts_once_and_returns_compact_usage(self) -> None:
        self.add_campaign("dispatch-proof")
        selection = SimpleNamespace(
            allowed=True,
            reason="explicit_app_server",
            codex_executable="/qualified/codex",
            installed_codex="0.149.0",
            qualification_state="exact-qualified",
            role="CAMP execution",
            model="gpt-5.6-terra",
            reasoning="medium",
            api_fallback=False,
        )
        execution = self.execution_result()
        with (
            patch("scripts.app_server_dispatch.select_command", return_value=selection),
            patch("scripts.app_server_dispatch._app_server_host_preflight", return_value={
                "codex_state": "writable",
                "authentication": "chatgpt",
                "network": "model-list-ok",
                "selected_model": "available",
            }),
            patch(
                "scripts.app_server_dispatch.execute_camp_if_enabled",
                return_value=execution,
            ) as execute,
        ):
            result = dispatch_next(self.workspace, app_server_requested=True)

        self.assertEqual("dispatch-proof", result["campaign"]["campaign_id"])
        self.assertTrue(result["campaign"]["started_by_dispatcher"])
        self.assertEqual(0, result["usage"]["dispatcher"]["model_tokens"])
        self.assertFalse(result["usage"]["dispatcher"]["nested_codex_exec"])
        self.assertEqual(20000, result["usage"]["app_server"]["tokens"]["input"])
        self.assertEqual(1, result["journal"]["verification_commands_run"])
        self.assertEqual("working", campaign_queue.load_all(self.workspace)["dispatch-proof"].status)
        execute.assert_called_once()
        self.assertEqual("/qualified/codex", execute.call_args.kwargs["codex"])

    def test_missing_capsule_is_prepared_persisted_and_executed_once(self) -> None:
        path = self.add_campaign("dispatch-proof", with_capsule=False)
        planning = SimpleNamespace(
            allowed=True,
            reason="explicit_qualified_opt_in",
            codex_executable="/qualified/codex",
            installed_codex="0.149.0",
            qualification_state="exact-qualified",
            role="planning",
            model="gpt-5.6-sol",
            reasoning="high",
            api_fallback=False,
        )
        camp = SimpleNamespace(
            **{
                **planning.__dict__,
                "role": "CAMP execution",
                "model": "gpt-5.6-terra",
                "reasoning": "medium",
            }
        )
        prepared = {
            "status": "prepared",
            "reason": "one bounded proof",
            "schema_version": 1,
            "campaign_id": "dispatch-proof",
            "camp": "create-proof",
            "prompt": "Create proof.txt and return camp_ready_for_verification.",
            "expected_paths": ["proof.txt"],
            "context_files": [],
            "verification_commands": [["python3", "-c", "assert True"]],
        }
        preparation_result = SimpleNamespace(
            status="completed",
            text=json.dumps(prepared),
            context_warning=None,
            mutation_events=(),
            actual_model="gpt-5.6-sol",
            reasoning="high",
            token_usage={"total": {"inputTokens": 1000, "totalTokens": 1100}},
            model_turns=1,
            duration_seconds=2.0,
        )
        with (
            patch(
                "scripts.app_server_dispatch.select_command",
                side_effect=[camp, planning],
            ),
            patch(
                "scripts.app_server_dispatch._app_server_host_preflight",
                return_value={},
            ) as preflight,
            patch(
                "scripts.app_server_dispatch.execute_preparation_if_enabled",
                return_value=(SimpleNamespace(use_app_server=True), preparation_result),
            ) as prepare,
            patch(
                "scripts.app_server_dispatch.execute_camp_if_enabled",
                return_value=self.execution_result(),
            ) as execute,
        ):
            result = dispatch_next(self.workspace, app_server_requested=True)

        persisted = path.read_text(encoding="utf-8")
        self.assertEqual(1, persisted.count("## App Server Execution Capsule"))
        self.assertEqual("automatic", result["preparation"]["mode"])
        self.assertTrue(result["preparation"]["persisted"])
        self.assertEqual(0, result["preparation"]["context_files"])
        self.assertEqual(0, result["preparation"]["context_bytes"])
        self.assertEqual(64_000, result["preparation"]["context_limit_bytes"])
        self.assertEqual(2, preflight.call_count)
        prepare.assert_called_once()
        execute.assert_called_once()
        self.assertEqual("working", campaign_queue.load_all(self.workspace)["dispatch-proof"].status)

    def test_unprepared_campaign_checks_camp_before_spending_planning_tokens(self) -> None:
        path = self.add_campaign("dispatch-proof", with_capsule=False)
        denied = SimpleNamespace(
            allowed=False,
            reason="workspace_write_qualification_missing",
        )
        before = path.read_bytes()
        with (
            patch("scripts.app_server_dispatch.select_command", return_value=denied),
            patch("scripts.app_server_dispatch._app_server_host_preflight") as preflight,
            patch("scripts.app_server_dispatch.execute_preparation_if_enabled") as prepare,
            patch("scripts.app_server_dispatch.execute_camp_if_enabled") as execute,
        ):
            with self.assertRaises(DispatchError) as raised:
                dispatch_next(self.workspace, app_server_requested=True)

        self.assertEqual("workspace_write_qualification_missing", raised.exception.category)
        self.assertEqual(before, path.read_bytes())
        self.assertEqual("queued", campaign_queue.load_all(self.workspace)["dispatch-proof"].status)
        preflight.assert_not_called()
        prepare.assert_not_called()
        execute.assert_not_called()

    def test_automatic_preparation_advertises_actual_sizes_and_context_budget(self) -> None:
        path = self.add_campaign("dispatch-proof", with_capsule=False)
        campaign = campaign_queue.parse_campaign(path)
        source = self.workspace / "src" / "proof.py"
        source.parent.mkdir()
        source.write_text("proof = 1\n", encoding="utf-8")

        prompt = _automatic_preparation_prompt(campaign, max_context_bytes=1234)
        context = _automatic_preparation_context(
            self.workspace,
            campaign,
            max_context_bytes=1234,
        )

        self.assertIn("no greater than 1234 bytes", prompt)
        self.assertIn("Automatic capsule context budget: 1234 bytes total", context)
        self.assertIn("src/proof.py (10 bytes;", context)

    def test_automatic_preparation_rejects_oversized_inline_context(self) -> None:
        path = self.add_campaign("dispatch-proof", with_capsule=False)
        campaign = campaign_queue.parse_campaign(path)
        source = self.workspace / "large.txt"
        source.write_text("x" * 65, encoding="utf-8")
        prepared = {
            "status": "prepared",
            "reason": "bounded proof",
            "schema_version": 1,
            "campaign_id": "dispatch-proof",
            "camp": "create-proof",
            "prompt": "Create proof.txt and return camp_ready_for_verification.",
            "expected_paths": ["proof.txt"],
            "context_files": ["large.txt"],
            "verification_commands": [["python3", "-c", "assert True"]],
        }
        result = SimpleNamespace(
            status="completed",
            text=json.dumps(prepared),
            context_warning=None,
            mutation_events=(),
        )

        with self.assertRaises(DispatchError) as raised:
            _parse_automatic_preparation(
                self.workspace,
                campaign,
                result,
                max_context_bytes=64,
            )

        self.assertEqual("automatic_preparation_context_limit", raised.exception.category)
        self.assertIn("selected 65 context bytes; limit is 64", str(raised.exception))

    def test_blocked_automatic_preparation_does_not_mutate_or_execute(self) -> None:
        path = self.add_campaign("dispatch-proof", with_capsule=False)
        selection = SimpleNamespace(
            allowed=True,
            reason="explicit_qualified_opt_in",
            codex_executable="/qualified/codex",
            installed_codex="0.149.0",
            qualification_state="exact-qualified",
            role="planning",
            model="gpt-5.6-sol",
            reasoning="high",
            api_fallback=False,
        )
        blocked = {
            "status": "blocked",
            "reason": "exact mutation paths require an owner decision",
            "schema_version": 1,
            "campaign_id": "dispatch-proof",
            "camp": "",
            "prompt": "",
            "expected_paths": [],
            "context_files": [],
            "verification_commands": [],
        }
        preparation_result = SimpleNamespace(
            status="completed",
            text=json.dumps(blocked),
            context_warning=None,
            mutation_events=(),
        )
        before = path.read_bytes()
        with (
            patch("scripts.app_server_dispatch.select_command", return_value=selection),
            patch("scripts.app_server_dispatch._app_server_host_preflight", return_value={}),
            patch(
                "scripts.app_server_dispatch.execute_preparation_if_enabled",
                return_value=(SimpleNamespace(use_app_server=True), preparation_result),
            ),
            patch("scripts.app_server_dispatch.execute_camp_if_enabled") as execute,
        ):
            with self.assertRaises(DispatchError) as raised:
                dispatch_next(self.workspace, app_server_requested=True)

        self.assertEqual("automatic_preparation_blocked", raised.exception.category)
        self.assertEqual(before, path.read_bytes())
        self.assertEqual("queued", campaign_queue.load_all(self.workspace)["dispatch-proof"].status)
        execute.assert_not_called()

    def test_automatic_preparation_rejects_campaign_lifecycle_mutation(self) -> None:
        path = self.add_campaign("dispatch-proof", with_capsule=False)
        campaign = campaign_queue.parse_campaign(path)
        prepared = {
            "status": "prepared",
            "reason": "unsafe lifecycle mutation",
            "schema_version": 1,
            "campaign_id": "dispatch-proof",
            "camp": "edit-campaign",
            "prompt": "Edit the campaign request.",
            "expected_paths": ["work/00-campaigns/active/001-dispatch-proof.md"],
            "context_files": [],
            "verification_commands": [["python3", "-c", "assert True"]],
        }
        result = SimpleNamespace(
            status="completed",
            text=json.dumps(prepared),
            context_warning=None,
            mutation_events=(),
        )

        with self.assertRaises(DispatchError) as raised:
            _parse_automatic_preparation(self.workspace, campaign, result)

        self.assertEqual("automatic_preparation_unsafe", raised.exception.category)

    def test_dispatch_passes_selected_config_and_policy_to_execution(self) -> None:
        self.add_campaign("dispatch-proof")
        selection = SimpleNamespace(
            allowed=True,
            reason="explicit_app_server",
            codex_executable="/qualified/codex",
            installed_codex="0.149.0",
            qualification_state="exact-qualified",
            role="CAMP execution",
            model="gpt-5.6-terra",
            reasoning="medium",
            api_fallback=False,
        )
        execution = {
            "result": {},
            "mutation_journal": {
                "safe": True,
                "final_state": "verified",
                "deterministic_verification": {"commands_run": 1, "passed": True},
            },
        }
        config = ROOT / "adapters" / "codex-app-server-config.json"
        policy = ROOT / "adapters" / "codex-model-policy.json"
        with (
            patch("scripts.app_server_dispatch.select_command", return_value=selection),
            patch(
                "scripts.app_server_dispatch._app_server_host_preflight",
                return_value={},
            ),
            patch(
                "scripts.app_server_dispatch.execute_camp_if_enabled",
                return_value=execution,
            ) as execute,
        ):
            dispatch_next(
                self.workspace,
                app_server_requested=True,
                config_path=config,
                policy_path=policy,
            )

        self.assertEqual(config.resolve(), execute.call_args.kwargs["config"].source)
        self.assertEqual(policy.resolve(), execute.call_args.kwargs["policy"].source)

    def test_invalid_capsule_fails_before_lifecycle_mutation(self) -> None:
        path = self.add_campaign("dispatch-proof")
        text = path.read_text(encoding="utf-8").replace(
            '"expected_paths": ["proof.txt"]', '"expected_paths": ["../proof.txt"]'
        )
        path.write_text(text, encoding="utf-8")
        with self.assertRaises(DispatchError) as raised:
            dispatch_next(self.workspace, app_server_requested=True)
        self.assertEqual("execution_capsule_invalid", raised.exception.category)
        self.assertEqual("queued", campaign_queue.load_all(self.workspace)["dispatch-proof"].status)


if __name__ == "__main__":
    unittest.main()
