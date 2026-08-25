from __future__ import annotations

import tempfile
import unittest
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from scripts import campaign_queue
from scripts.app_server_dispatch import DispatchError, dispatch_next, parse_execution_capsule
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
        ensure_project_identity(self.workspace, project_name="dispatch-test")
        campaign_queue.ensure_tree(self.workspace)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def add_campaign(self, campaign_id: str, *, shell: bool = False) -> Path:
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
        text = text[: text.index("## Request")] + capsule(campaign_id, shell=shell)
        path.write_text(text, encoding="utf-8")
        campaigns = campaign_queue.load_all(self.workspace)
        (self.workspace / "work" / "00-campaigns" / "active-queue.md").write_text(
            campaign_queue.render_active_queue([campaign_id], campaigns, None),
            encoding="utf-8",
        )
        return path

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
        execution = {
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
