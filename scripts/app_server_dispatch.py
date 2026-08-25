#!/usr/bin/env python3
"""Dispatch ordinary Tool Shed `next` selection to the existing App Server CAMP runner."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from types import SimpleNamespace
from typing import Any

# Keep execution of an installed managed snapshot from dirtying that snapshot.
sys.dont_write_bytecode = True

try:
    from scripts import campaign_queue
    from scripts.app_server_control import select_command
    from scripts.codex_app_server import (
        AppServerError,
        AuthenticationError,
        CodexAppServerClient,
    )
    from scripts.codex_execution import ModelPolicy, flatten_token_usage
    from scripts.codex_orchestration import (
        DEFAULT_CONFIG,
        AppServerFeatureConfig,
        execute_camp_if_enabled,
    )
    from scripts.codex_execution import DEFAULT_POLICY
    from scripts.codex_app_server_compatibility import DEFAULT_QUALIFICATIONS
    from scripts.project_identity import binding_token, require_project_binding
except ModuleNotFoundError:  # Direct execution: python scripts/app_server_dispatch.py
    import campaign_queue  # type: ignore[no-redef]
    from app_server_control import select_command  # type: ignore[no-redef]
    from codex_app_server import (  # type: ignore[no-redef]
        AppServerError,
        AuthenticationError,
        CodexAppServerClient,
    )
    from codex_execution import (  # type: ignore[no-redef]
        DEFAULT_POLICY,
        ModelPolicy,
        flatten_token_usage,
    )
    from codex_orchestration import (  # type: ignore[no-redef]
        DEFAULT_CONFIG,
        AppServerFeatureConfig,
        execute_camp_if_enabled,
    )
    from codex_app_server_compatibility import (  # type: ignore[no-redef]
        DEFAULT_QUALIFICATIONS,
    )
    from project_identity import (  # type: ignore[no-redef]
        binding_token,
        require_project_binding,
    )


CAPSULE_HEADING = "## App Server Execution Capsule"
CAPSULE_KEYS = {
    "schema_version",
    "campaign_id",
    "camp",
    "prompt",
    "expected_paths",
    "context_files",
    "verification_commands",
}
ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SHELL_EXECUTABLES = {
    "bash",
    "cmd",
    "cmd.exe",
    "fish",
    "powershell",
    "powershell.exe",
    "pwsh",
    "pwsh.exe",
    "sh",
    "zsh",
}


class DispatchError(ValueError):
    def __init__(
        self,
        category: str,
        message: str,
        *,
        recovery_action: str,
        mutation_state: str = "none",
    ) -> None:
        super().__init__(message)
        self.category = category
        self.recovery_action = recovery_action
        self.mutation_state = mutation_state


@dataclass(frozen=True)
class ExecutionCapsule:
    campaign_id: str
    camp: str
    prompt: str
    expected_paths: tuple[Path, ...]
    context_files: tuple[Path, ...]
    verification_commands: tuple[tuple[str, ...], ...]


def _capsule_payload(text: str) -> dict[str, Any]:
    lines = text.splitlines()
    headings = [index for index, line in enumerate(lines) if line.strip() == CAPSULE_HEADING]
    if len(headings) != 1:
        raise DispatchError(
            "execution_capsule_missing",
            "selected campaign must contain exactly one App Server Execution Capsule section",
            recovery_action="add or repair the selected campaign execution capsule",
        )
    index = headings[0] + 1
    while index < len(lines) and not lines[index].strip():
        index += 1
    if index >= len(lines) or lines[index].strip() != "```json":
        raise DispatchError(
            "execution_capsule_invalid",
            "execution capsule must begin with an exact ```json fence",
            recovery_action="repair the selected campaign execution capsule",
        )
    end = next(
        (cursor for cursor in range(index + 1, len(lines)) if lines[cursor].strip() == "```"),
        None,
    )
    if end is None:
        raise DispatchError(
            "execution_capsule_invalid",
            "execution capsule JSON fence is not closed",
            recovery_action="repair the selected campaign execution capsule",
        )
    try:
        payload = json.loads("\n".join(lines[index + 1 : end]))
    except json.JSONDecodeError as error:
        raise DispatchError(
            "execution_capsule_invalid",
            f"execution capsule is malformed JSON: {error}",
            recovery_action="repair the selected campaign execution capsule",
        ) from error
    if not isinstance(payload, dict):
        raise DispatchError(
            "execution_capsule_invalid",
            "execution capsule must be a JSON object",
            recovery_action="repair the selected campaign execution capsule",
        )
    unknown = sorted(set(payload) - CAPSULE_KEYS)
    missing = sorted(CAPSULE_KEYS - set(payload))
    if unknown or missing:
        details = []
        if missing:
            details.append("missing " + ", ".join(missing))
        if unknown:
            details.append("unsupported " + ", ".join(unknown))
        raise DispatchError(
            "execution_capsule_invalid",
            "execution capsule fields are invalid: " + "; ".join(details),
            recovery_action="repair the selected campaign execution capsule",
        )
    return payload


def _relative_path(workspace: Path, raw: object, *, must_exist: bool) -> Path:
    if not isinstance(raw, str) or not raw.strip() or "\\" in raw:
        raise DispatchError(
            "execution_capsule_invalid",
            "capsule paths must be non-empty repository-relative POSIX paths",
            recovery_action="repair the selected campaign execution capsule",
        )
    pure = PurePosixPath(raw)
    if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
        raise DispatchError(
            "execution_capsule_invalid",
            f"capsule path is not safely repository-relative: {raw}",
            recovery_action="repair the selected campaign execution capsule",
        )
    path = workspace.joinpath(*pure.parts)
    try:
        path.resolve(strict=False).relative_to(workspace)
    except ValueError as error:
        raise DispatchError(
            "execution_capsule_invalid",
            f"capsule path escapes the workspace: {raw}",
            recovery_action="repair the selected campaign execution capsule",
        ) from error
    cursor = workspace
    for part in pure.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise DispatchError(
                "execution_capsule_invalid",
                f"capsule path traverses a symlink: {raw}",
                recovery_action="repair the selected campaign execution capsule",
            )
    if must_exist and (not path.is_file() or path.is_symlink()):
        raise DispatchError(
            "execution_capsule_invalid",
            f"capsule context file is missing or unsafe: {raw}",
            recovery_action="repair the selected campaign execution capsule",
        )
    return Path(*pure.parts)


def parse_execution_capsule(
    workspace: Path,
    campaign: campaign_queue.Campaign,
) -> ExecutionCapsule:
    payload = _capsule_payload(campaign.body)
    if payload["schema_version"] != 1:
        raise DispatchError(
            "execution_capsule_invalid",
            "unsupported execution capsule schema",
            recovery_action="repair the selected campaign execution capsule",
        )
    campaign_id = payload["campaign_id"]
    camp = payload["camp"]
    prompt = payload["prompt"]
    if campaign_id != campaign.campaign_id:
        raise DispatchError(
            "execution_capsule_stale",
            "execution capsule campaign_id does not match the selected campaign",
            recovery_action="regenerate the selected campaign execution capsule",
        )
    if not isinstance(camp, str) or not ID_RE.fullmatch(camp):
        raise DispatchError(
            "execution_capsule_invalid",
            "execution capsule camp must be a lowercase kebab-case ID",
            recovery_action="repair the selected campaign execution capsule",
        )
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt.encode("utf-8")) > 16_384:
        raise DispatchError(
            "execution_capsule_invalid",
            "execution capsule prompt must contain 1 to 16384 UTF-8 bytes",
            recovery_action="repair the selected campaign execution capsule",
        )
    expected_raw = payload["expected_paths"]
    context_raw = payload["context_files"]
    commands_raw = payload["verification_commands"]
    if not isinstance(expected_raw, list) or not 1 <= len(expected_raw) <= 32:
        raise DispatchError(
            "execution_capsule_invalid",
            "execution capsule requires 1 to 32 expected_paths",
            recovery_action="repair the selected campaign execution capsule",
        )
    if not isinstance(context_raw, list) or len(context_raw) > 32:
        raise DispatchError(
            "execution_capsule_invalid",
            "execution capsule permits at most 32 context_files",
            recovery_action="repair the selected campaign execution capsule",
        )
    if not isinstance(commands_raw, list) or not 1 <= len(commands_raw) <= 8:
        raise DispatchError(
            "execution_capsule_invalid",
            "execution capsule requires 1 to 8 verification_commands",
            recovery_action="repair the selected campaign execution capsule",
        )
    expected = tuple(_relative_path(workspace, item, must_exist=False) for item in expected_raw)
    context = tuple(_relative_path(workspace, item, must_exist=True) for item in context_raw)
    if len(expected) != len(set(expected)) or len(context) != len(set(context)):
        raise DispatchError(
            "execution_capsule_invalid",
            "execution capsule paths must be unique",
            recovery_action="repair the selected campaign execution capsule",
        )
    commands: list[tuple[str, ...]] = []
    for raw in commands_raw:
        if (
            not isinstance(raw, list)
            or not raw
            or any(not isinstance(argument, str) or not argument for argument in raw)
        ):
            raise DispatchError(
                "execution_capsule_invalid",
                "each verification command must be a non-empty JSON argv string array",
                recovery_action="repair the selected campaign execution capsule",
            )
        executable = Path(raw[0]).name.lower()
        if executable in SHELL_EXECUTABLES:
            raise DispatchError(
                "execution_capsule_invalid",
                f"verification command cannot invoke a shell: {raw[0]}",
                recovery_action="replace shell verification with a direct argv command",
            )
        commands.append(tuple(raw))
    return ExecutionCapsule(
        campaign_id=campaign_id,
        camp=camp,
        prompt=prompt.strip(),
        expected_paths=expected,
        context_files=context,
        verification_commands=tuple(commands),
    )


def _app_server_host_preflight(selection: Any, *, timeout: float) -> dict[str, Any]:
    configured = os.environ.get("CODEX_HOME")
    state = Path(configured).expanduser() if configured else Path.home() / ".codex"
    probe = state if state.exists() else state.parent
    writable = probe.is_dir() and os.access(probe, os.W_OK | os.X_OK)
    if not writable:
        raise DispatchError(
            "codex_state_unwritable",
            "Codex state is not writable from the current execution environment",
            recovery_action="allow the current GUI execution to write its Codex state directory, then rerun once",
        )
    try:
        with CodexAppServerClient(
            codex=selection.codex_executable,
            timeout=min(timeout, 30.0),
        ) as client:
            client.require_chatgpt_auth()
            models = client.list_models()
    except AuthenticationError as error:
        raise DispatchError(
            "app_server_authentication_unavailable",
            "App Server preflight could not validate managed ChatGPT authentication",
            recovery_action="sign in to Codex with ChatGPT in the current GUI environment, then rerun once",
        ) from error
    except AppServerError as error:
        raise DispatchError(
            error.kind or "app_server_preflight_failed",
            "App Server startup or network preflight failed before mutation",
            recovery_action="restore Codex state and network access for the current GUI execution, then rerun once",
        ) from error
    available_models = {
        str(item.get("model") or item.get("id"))
        for item in models
        if isinstance(item, dict)
    }
    if selection.model not in available_models:
        raise DispatchError(
            "app_server_model_unavailable",
            "selected CAMP model is absent from the App Server model catalog",
            recovery_action="refresh Codex access or qualification before retrying",
        )
    return {
        "codex_state": "writable",
        "authentication": "chatgpt",
        "network": "model-list-ok",
        "selected_model": "available",
    }


def _start_selected_campaign(workspace: Path, campaign_id: str) -> None:
    expected = campaign_queue.state_token(workspace)
    project_binding = binding_token(workspace, operation="campaign-queue")
    require_project_binding(workspace, project_binding, operation="campaign-queue")
    args = SimpleNamespace(
        command="start",
        campaign_id=campaign_id,
        expect=expected,
        project_binding=project_binding,
    )
    campaign_queue.mutate_campaign(args, workspace)


def _compact_success(
    *,
    selected: dict[str, object],
    selection: Any,
    execution: dict[str, Any],
    dispatch_elapsed: float,
    campaign_started: bool,
    preflight: dict[str, Any],
) -> dict[str, Any]:
    result = execution.get("result") if isinstance(execution.get("result"), dict) else {}
    journal = (
        execution.get("mutation_journal")
        if isinstance(execution.get("mutation_journal"), dict)
        else {}
    )
    deterministic = (
        journal.get("deterministic_verification")
        if isinstance(journal.get("deterministic_verification"), dict)
        else {}
    )
    return {
        "schema_version": 1,
        "status": "completed" if journal.get("final_state") == "verified" else "stopped",
        "execution": "App Server",
        "dispatch": "ordinary-next",
        "campaign": {
            "campaign_id": selected.get("campaign_id"),
            "campaign_number": selected.get("campaign_number"),
            "started_by_dispatcher": campaign_started,
        },
        "preflight": {
            **preflight,
            "codex_executable": selection.codex_executable,
            "codex_version": selection.installed_codex,
            "qualification_state": selection.qualification_state,
        },
        "route": {
            "role": selection.role,
            "model": selection.model,
            "reasoning": selection.reasoning,
            "api_fallback": selection.api_fallback,
        },
        "usage": {
            "dispatcher": {
                "model_tokens": 0,
                "nested_codex_exec": False,
                "elapsed_seconds": round(dispatch_elapsed, 6),
                "outer_gui_tokens": "not exposed",
            },
            "app_server": {
                "tokens": flatten_token_usage(result.get("token_usage")),
                "model_turns": result.get("model_turns"),
                "tool_calls": result.get("tool_calls"),
                "tool_call_types": result.get("tool_call_types") or [],
                "model_duration_seconds": result.get("duration_seconds"),
                "camp_duration_seconds": execution.get("camp_duration_seconds"),
            },
        },
        "journal": {
            "safe": journal.get("safe"),
            "final_state": journal.get("final_state"),
            "expected_paths": journal.get("expected_paths") or [],
            "files_created": journal.get("files_created") or [],
            "files_modified": journal.get("files_modified") or [],
            "files_deleted": journal.get("files_deleted") or [],
            "unexpected_paths": journal.get("unexpected_paths") or [],
            "verification_commands_run": deterministic.get("commands_run"),
            "verification_passed": deterministic.get("passed"),
        },
        "next_action": execution.get("next_action"),
        "recovery_action": "none" if journal.get("final_state") == "verified" else "inspect the compact journal and do not replay after mutation",
    }


def dispatch_next(
    workspace: Path,
    *,
    app_server_requested: bool,
    codex: str | None = None,
    config_path: Path = DEFAULT_CONFIG,
    policy_path: Path = DEFAULT_POLICY,
    qualifications_path: Path = DEFAULT_QUALIFICATIONS,
    qualification_cache_path: Path | None = None,
    timeout: float = 300.0,
    telemetry_path: Path | None = None,
) -> dict[str, Any]:
    started_at = time.monotonic()
    root = workspace.expanduser().resolve()
    campaign_queue.require_valid(root)
    selected = campaign_queue.next_campaign_payload(root)
    campaign_id = selected.get("campaign_id")
    if not isinstance(campaign_id, str):
        raise DispatchError(
            "no_executable_campaign",
            "ordinary next selection did not resolve an executable campaign",
            recovery_action=str(selected.get("cycle_state", {}).get("next_transition", {}).get("command", "run ts: next without --app-server")),
        )
    campaigns = campaign_queue.load_all(root)
    campaign = campaigns[campaign_id]
    capsule = parse_execution_capsule(root, campaign)
    selection = select_command(
        "camp-run",
        app_server_requested=app_server_requested,
        codex=codex,
        config_path=config_path,
        policy_path=policy_path,
        qualifications_path=qualifications_path,
        qualification_cache_path=qualification_cache_path,
    )
    if not selection.allowed or not app_server_requested:
        raise DispatchError(
            selection.reason,
            "App Server CAMP selection was not allowed",
            recovery_action="rerun the same Tool Shed command without --app-server",
        )
    preflight = _app_server_host_preflight(selection, timeout=timeout)
    execution_config = AppServerFeatureConfig.load(config_path)
    execution_policy = ModelPolicy.load(policy_path)
    campaign_started = False
    if campaign.status == "queued":
        _start_selected_campaign(root, campaign_id)
        campaign_started = True
    elif campaign.status != "working":
        raise DispatchError(
            "campaign_not_executable",
            f"selected campaign is {campaign.status}, not queued or working",
            recovery_action="resolve the campaign lifecycle state before retrying",
        )
    try:
        execution = execute_camp_if_enabled(
            capsule.prompt,
            cwd=root,
            campaign=campaign_id,
            camp=capsule.camp,
            expected_paths=capsule.expected_paths,
            explicit_files=capsule.context_files,
            verification_commands=capsule.verification_commands,
            enable_override=True,
            config=execution_config,
            policy=execution_policy,
            codex=selection.codex_executable,
            timeout=timeout,
            telemetry_path=telemetry_path,
        )
    except Exception as error:
        raise DispatchError(
            "app_server_execution_failed",
            f"App Server execution failed: {type(error).__name__}",
            recovery_action="inspect the latest compact mutation journal; do not replay if mutation may have occurred",
            mutation_state="unknown",
        ) from error
    return _compact_success(
        selected=selected,
        selection=selection,
        execution=execution,
        dispatch_elapsed=time.monotonic() - started_at,
        campaign_started=campaign_started,
        preflight=preflight,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--codex", default=None)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--qualifications", type=Path, default=DEFAULT_QUALIFICATIONS)
    parser.add_argument("--qualification-cache", type=Path, default=None)
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument("--telemetry", type=Path, default=None)
    commands = parser.add_subparsers(dest="command", required=True)
    next_command = commands.add_parser("next")
    next_command.add_argument("--app-server", action="store_true")
    next_command.add_argument("--json", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        payload = dispatch_next(
            args.workspace,
            app_server_requested=args.app_server,
            codex=args.codex,
            config_path=args.config,
            policy_path=args.policy,
            qualifications_path=args.qualifications,
            qualification_cache_path=args.qualification_cache,
            timeout=args.timeout,
            telemetry_path=args.telemetry,
        )
    except (DispatchError, campaign_queue.CampaignError, OSError) as error:
        if isinstance(error, DispatchError):
            payload = {
                "schema_version": 1,
                "status": "blocked",
                "category": error.category,
                "mutation_state": error.mutation_state,
                "recovery_action": error.recovery_action,
                "error": str(error),
            }
        else:
            payload = {
                "schema_version": 1,
                "status": "blocked",
                "category": "dispatch_preflight_failed",
                "mutation_state": "none",
                "recovery_action": "repair the reported workspace state before retrying",
                "error": str(error),
            }
        print(json.dumps(payload, indent=2, sort_keys=True), file=sys.stderr)
        return 2
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["status"] == "completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
