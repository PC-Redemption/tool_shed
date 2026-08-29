#!/usr/bin/env python3
"""Dispatch ordinary Tool Shed `next` selection to the existing App Server CAMP runner."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
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
        execute_preparation_if_enabled,
    )
    from scripts.codex_execution import DEFAULT_POLICY
    from scripts.codex_app_server_compatibility import DEFAULT_QUALIFICATIONS
    from scripts.project_identity import binding_token, require_project_binding
    from scripts.app_server_user_state import (
        AppServerPreferenceStore,
        record_app_server_event_best_effort,
    )
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
        execute_preparation_if_enabled,
    )
    from codex_app_server_compatibility import (  # type: ignore[no-redef]
        DEFAULT_QUALIFICATIONS,
    )
    from project_identity import (  # type: ignore[no-redef]
        binding_token,
        require_project_binding,
    )
    from app_server_user_state import (  # type: ignore[no-redef]
        AppServerPreferenceStore,
        record_app_server_event_best_effort,
    )


CAPSULE_HEADING = "## App Server Execution Capsule"
PREPARATION_CONTRACT_HEADING = "## App Server Preparation Contract"
CAPSULE_REQUIRED_KEYS = {
    "schema_version",
    "campaign_id",
    "camp",
    "prompt",
    "expected_paths",
    "context_files",
    "verification_commands",
}
CAPSULE_OPTIONAL_KEYS = {
    "source_state_token",
    "execution_shape",
    "estimated_model_turns",
    "estimated_max_tool_result_bytes",
}
CAPSULE_KEYS = CAPSULE_REQUIRED_KEYS | CAPSULE_OPTIONAL_KEYS
AUTO_PREPARATION_KEYS = {
    "status",
    "reason",
    *CAPSULE_REQUIRED_KEYS,
    "execution_shape",
    "estimated_model_turns",
    "estimated_max_tool_result_bytes",
}
AUTO_PREPARATION_MAX_CONTEXT_BYTES = 64_000
AUTO_PREPARATION_MAX_SNAPSHOT_BYTES = 48_000
AUTO_PREPARATION_MAX_INVENTORY_BYTES = 12_000
AUTO_PREPARATION_MAX_EXCERPT_FILES = 8
AUTO_PREPARATION_MAX_EXPECTED_PATHS = 8
AUTO_PREPARATION_MAX_VERIFICATION_COMMANDS = 4
AUTO_PREPARATION_MAX_ESTIMATED_TURNS = 3
AUTO_PREPARATION_MAX_ESTIMATED_TOOL_RESULT_BYTES = 12_288
AUTO_PREPARATION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "status": {"type": "string", "enum": ["prepared", "blocked"]},
        "reason": {"type": "string"},
        "schema_version": {"type": "integer"},
        "campaign_id": {"type": "string"},
        "camp": {"type": "string"},
        "prompt": {"type": "string"},
        "expected_paths": {
            "type": "array",
            "items": {"type": "string"},
        },
        "context_files": {
            "type": "array",
            "items": {"type": "string"},
        },
        "verification_commands": {
            "type": "array",
            "items": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
        "execution_shape": {
            "type": "string",
            "enum": ["atomic", "bounded-slice", "blocked"],
        },
        "estimated_model_turns": {"type": "integer", "minimum": 0, "maximum": 3},
        "estimated_max_tool_result_bytes": {
            "type": "integer",
            "minimum": 0,
            "maximum": 12288,
        },
    },
    "required": sorted(AUTO_PREPARATION_KEYS),
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
PREPARATION_TEXT_SUFFIXES = {
    ".c",
    ".cc",
    ".cpp",
    ".css",
    ".h",
    ".hpp",
    ".html",
    ".ini",
    ".js",
    ".json",
    ".md",
    ".py",
    ".sh",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".yaml",
    ".yml",
}
PREPARATION_STOPWORDS = {
    "active",
    "campaign",
    "change",
    "complete",
    "completion",
    "current",
    "existing",
    "from",
    "into",
    "must",
    "none",
    "only",
    "preserve",
    "request",
    "should",
    "status",
    "that",
    "their",
    "this",
    "through",
    "while",
    "with",
    "without",
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
    source_state_token: str | None = None
    execution_shape: str | None = None
    estimated_model_turns: int | None = None
    estimated_max_tool_result_bytes: int | None = None


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
    missing = sorted(CAPSULE_REQUIRED_KEYS - set(payload))
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
    return _execution_capsule_from_payload(workspace, campaign, payload)


def _preparation_contract(campaign: campaign_queue.Campaign) -> dict[str, Any]:
    """Read stable semantic intent, with a compatible default for legacy campaigns."""

    lines = campaign.body.splitlines()
    headings = [
        index for index, line in enumerate(lines)
        if line.strip() == PREPARATION_CONTRACT_HEADING
    ]
    if not headings:
        return {
            "schema_version": 1,
            "campaign_id": campaign.campaign_id,
            "objective": campaign.outcome,
            "completion_evidence": campaign.fields.get("Completion Gate", ""),
            "execution_shape": "single-bounded-camp",
            "exact_resolution": "dispatch-time",
            "source_freshness": "required",
            "inline_assets": "metadata-only",
            "verification": "orchestrator-exactly-once",
            "origin": "legacy-derived",
        }
    if len(headings) != 1:
        raise DispatchError(
            "preparation_contract_invalid",
            "campaign must contain at most one App Server Preparation Contract",
            recovery_action="repair the campaign preparation contract before retrying",
        )
    index = headings[0] + 1
    while index < len(lines) and not lines[index].strip():
        index += 1
    if index >= len(lines) or lines[index].strip() != "```json":
        raise DispatchError(
            "preparation_contract_invalid",
            "App Server Preparation Contract must begin with an exact ```json fence",
            recovery_action="repair the campaign preparation contract before retrying",
        )
    end = next(
        (cursor for cursor in range(index + 1, len(lines)) if lines[cursor].strip() == "```"),
        None,
    )
    if end is None:
        raise DispatchError(
            "preparation_contract_invalid",
            "App Server Preparation Contract JSON fence is not closed",
            recovery_action="repair the campaign preparation contract before retrying",
        )
    try:
        payload = json.loads("\n".join(lines[index + 1 : end]))
    except json.JSONDecodeError as error:
        raise DispatchError(
            "preparation_contract_invalid",
            "App Server Preparation Contract is malformed JSON",
            recovery_action="repair the campaign preparation contract before retrying",
        ) from error
    required = {
        "schema_version",
        "campaign_id",
        "objective",
        "completion_evidence",
        "execution_shape",
        "exact_resolution",
        "source_freshness",
        "inline_assets",
        "verification",
    }
    if not isinstance(payload, dict) or set(payload) != required:
        raise DispatchError(
            "preparation_contract_invalid",
            "App Server Preparation Contract fields do not match schema version 1",
            recovery_action="regenerate the campaign preparation contract before retrying",
        )
    expected = {
        "schema_version": 1,
        "campaign_id": campaign.campaign_id,
        "execution_shape": "single-bounded-camp",
        "exact_resolution": "dispatch-time",
        "source_freshness": "required",
        "inline_assets": "metadata-only",
        "verification": "orchestrator-exactly-once",
    }
    if any(payload.get(key) != value for key, value in expected.items()):
        raise DispatchError(
            "preparation_contract_invalid",
            "App Server Preparation Contract does not match the selected campaign or policy",
            recovery_action="regenerate the campaign preparation contract before retrying",
        )
    if not all(
        isinstance(payload.get(key), str) and payload[key].strip()
        for key in ("objective", "completion_evidence")
    ):
        raise DispatchError(
            "preparation_contract_invalid",
            "App Server Preparation Contract requires objective and completion evidence",
            recovery_action="repair the campaign preparation contract before retrying",
        )
    return payload


def _request_text(campaign: campaign_queue.Campaign) -> str:
    match = re.search(r"(?ms)^## Request\s*$\n(.*?)(?=^## |\Z)", campaign.body)
    return match.group(1).strip() if match else ""


def _capsule_source_state_token(
    workspace: Path,
    campaign: campaign_queue.Campaign,
    capsule: ExecutionCapsule,
) -> str:
    """Bind automatic collateral to its semantic request and exact file boundary."""

    try:
        head = subprocess.run(
            ["git", "-C", str(workspace), "rev-parse", "HEAD"],
            text=True,
            encoding="utf-8",
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
        ).stdout.strip()
    except OSError:
        head = ""
    files: list[dict[str, object]] = []
    for relative in sorted(
        set((*capsule.expected_paths, *capsule.context_files)),
        key=lambda path: path.as_posix(),
    ):
        path = workspace / relative
        record: dict[str, object] = {"path": relative.as_posix()}
        if path.is_file() and not path.is_symlink():
            raw = path.read_bytes()
            record.update({"state": "file", "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
        elif path.exists():
            record["state"] = "non-file"
        else:
            record["state"] = "missing"
        files.append(record)
    payload = {
        "campaign_id": campaign.campaign_id,
        "outcome": campaign.outcome,
        "completion_gate": campaign.fields.get("Completion Gate", ""),
        "request": _request_text(campaign),
        "contract": _preparation_contract(campaign),
        "head": head,
        "capsule": {
            "camp": capsule.camp,
            "prompt": capsule.prompt,
            "expected_paths": [path.as_posix() for path in capsule.expected_paths],
            "context_files": [path.as_posix() for path in capsule.context_files],
            "verification_commands": [list(command) for command in capsule.verification_commands],
            "execution_shape": capsule.execution_shape,
            "estimated_model_turns": capsule.estimated_model_turns,
            "estimated_max_tool_result_bytes": capsule.estimated_max_tool_result_bytes,
        },
        "files": files,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


def _source_bound_capsule(
    workspace: Path,
    campaign: campaign_queue.Campaign,
    capsule: ExecutionCapsule,
) -> ExecutionCapsule:
    token = _capsule_source_state_token(workspace, campaign, capsule)
    return ExecutionCapsule(
        campaign_id=capsule.campaign_id,
        camp=capsule.camp,
        prompt=capsule.prompt,
        expected_paths=capsule.expected_paths,
        context_files=capsule.context_files,
        verification_commands=capsule.verification_commands,
        source_state_token=token,
        execution_shape=capsule.execution_shape,
        estimated_model_turns=capsule.estimated_model_turns,
        estimated_max_tool_result_bytes=capsule.estimated_max_tool_result_bytes,
    )


def _capsule_source_is_stale(
    workspace: Path,
    campaign: campaign_queue.Campaign,
    capsule: ExecutionCapsule,
) -> bool:
    return (
        capsule.source_state_token is not None
        and capsule.source_state_token != _capsule_source_state_token(workspace, campaign, capsule)
    )


def _execution_capsule_from_payload(
    workspace: Path,
    campaign: campaign_queue.Campaign,
    payload: dict[str, Any],
) -> ExecutionCapsule:
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
    source_state_token = payload.get("source_state_token")
    execution_shape = payload.get("execution_shape")
    estimated_model_turns = payload.get("estimated_model_turns")
    estimated_max_tool_result_bytes = payload.get("estimated_max_tool_result_bytes")
    if source_state_token is not None and (
        not isinstance(source_state_token, str)
        or re.fullmatch(r"[0-9a-f]{16}", source_state_token) is None
    ):
        raise DispatchError(
            "execution_capsule_invalid",
            "execution capsule source_state_token must be 16 lowercase hexadecimal characters",
            recovery_action="regenerate the selected campaign execution capsule",
        )
    if execution_shape is not None and execution_shape not in {"atomic", "bounded-slice"}:
        raise DispatchError(
            "execution_capsule_invalid",
            "execution capsule execution_shape must be atomic or bounded-slice",
            recovery_action="regenerate the selected campaign execution capsule",
        )
    if estimated_model_turns is not None and (
        isinstance(estimated_model_turns, bool)
        or not isinstance(estimated_model_turns, int)
        or not 1 <= estimated_model_turns <= AUTO_PREPARATION_MAX_ESTIMATED_TURNS
    ):
        raise DispatchError(
            "execution_capsule_invalid",
            "execution capsule estimated_model_turns is outside the prelaunch budget",
            recovery_action="reduce the selected campaign to one bounded CAMP",
        )
    if estimated_max_tool_result_bytes is not None and (
        isinstance(estimated_max_tool_result_bytes, bool)
        or not isinstance(estimated_max_tool_result_bytes, int)
        or not 1 <= estimated_max_tool_result_bytes <= AUTO_PREPARATION_MAX_ESTIMATED_TOOL_RESULT_BYTES
    ):
        raise DispatchError(
            "execution_capsule_invalid",
            "execution capsule estimated tool-result size is outside the prelaunch budget",
            recovery_action="scope commands and context before worker launch",
        )
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
        source_state_token=source_state_token,
        execution_shape=execution_shape,
        estimated_model_turns=estimated_model_turns,
        estimated_max_tool_result_bytes=estimated_max_tool_result_bytes,
    )


def _automatic_context_budget(config: AppServerFeatureConfig) -> int:
    """Keep automatically selected inline context small even when clients allow more."""
    return min(config.max_inline_bytes, AUTO_PREPARATION_MAX_CONTEXT_BYTES)


def _automatic_preparation_prompt(
    campaign: campaign_queue.Campaign,
    *,
    max_context_bytes: int,
) -> str:
    return f"""Prepare exactly one bounded implementation CAMP for campaign {campaign.campaign_id!r}.

Use only the supplied deterministic campaign, instruction, Git-status, relevant-file inventory,
and bounded source excerpts to identify a coherent first implementation boundary. Do not call
tools or read any other files. Return the strict structured object requested by the output schema.

If a safe bounded CAMP can be prepared, set status to prepared and:
- use schema_version 1 and the exact campaign_id {campaign.campaign_id!r};
- choose one lowercase kebab-case camp ID;
- honor the campaign's App Server Preparation Contract as stable semantic intent while resolving
  exact execution details against the supplied current source snapshot;
- set execution_shape to atomic when the whole request fits, or bounded-slice when the prompt is
  one coherent independently verifiable slice of a broader campaign;
- estimate one to {AUTO_PREPARATION_MAX_ESTIMATED_TURNS} model turns and a largest serialized tool
  result no greater than {AUTO_PREPARATION_MAX_ESTIMATED_TOOL_RESULT_BYTES} bytes; reduce the slice
  before returning it when either estimate would exceed that prelaunch budget;
- write a complete worker prompt that permits only the declared mutations, forbids lifecycle,
  deployment, network, and protected-environment work, reserves verification for the orchestrator,
  and requires camp_ready_for_verification after implementation;
- make the worker prompt and selected inline context complete enough for the first file-change;
  the worker is forbidden to use commandExecution at any point, Tool Shed treats the first
  completed file change as the verification handoff, and the worker must return unknown without
  mutation when the supplied boundary is insufficient;
- declare every worker-owned mutation in expected_paths as unique repository-relative POSIX paths;
- declare only existing regular UTF-8 context files needed by the worker, with their combined
  actual file sizes no greater than {max_context_bytes} bytes;
- prefer small immutable instructions and contracts; existing UTF-8 expected source paths are
  injected deterministically when they fit the context budget, so the worker must not reread them
  through command output;
- provide one to eight deterministic shell-free verification commands as direct argv arrays;
- retain at most {AUTO_PREPARATION_MAX_VERIFICATION_COMMANDS} focused verification commands and at
  most {AUTO_PREPARATION_MAX_EXPECTED_PATHS} expected mutation paths for automatic execution;
- keep each verifier quiet or scoped enough to remain below the estimated tool-result size; do not
  select whole-suite discovery, repository-wide output, or commands whose useful result is an
  unbounded listing or diff;
- use platform-local executable paths that do not depend on shell activation;
- use the exact current Python executable advertised in the preparation context for Python checks;
- for prose or documentation checks, use one shared normalizer for both document text and expected
  multiword semantic phrases; it must collapse whitespace and normalize case so Markdown line
  wrapping or sentence capitalization cannot change the verification result;
- do not assert that the whole Git worktree is clean or exclude only expected_paths from a clean
  diff check because the dispatcher persists the capsule and lifecycle state before execution;
- exclude work/00-campaigns, Tool Shed snapshot machinery, Git metadata, deployment, production,
  credentials, generated outputs not owned by the worker, and unrelated cleanup.

If exact mutation paths or safe deterministic verification cannot be established without an owner
decision, protected action, or broader planning, set status to blocked, explain the limiting
condition in reason, and return schema_version 1, the exact campaign_id, and empty camp, prompt,
expected_paths, context_files, and verification_commands, execution_shape blocked, and zero for
both estimates. Do not guess or broaden authority.
"""


def _preparation_keywords(campaign: campaign_queue.Campaign) -> tuple[str, ...]:
    text = "\n".join((campaign.title, campaign.outcome, campaign.body)).lower()
    base_words = {
        word
        for word in re.findall(r"[a-z][a-z0-9_-]{3,}", text)
        if word not in PREPARATION_STOPWORDS and not word.isdigit()
    }
    words = set(base_words)
    for word in base_words:
        parts = [part for part in re.split(r"[-_]", word) if len(part) >= 4]
        words.update(parts)
        if len(parts) > 1:
            words.add("_".join(parts))
            words.add("-".join(parts))
    return tuple(sorted(words, key=lambda word: (-len(word), word))[:80])


def _referenced_workspace_files(
    workspace: Path,
    campaign: campaign_queue.Campaign,
) -> set[Path]:
    candidates = set(re.findall(r"`([^`\n]+)`", campaign.body))
    candidates.update(
        re.findall(
            r"(?<![A-Za-z0-9_.-])((?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]+)",
            campaign.body,
        )
    )
    result: set[Path] = set()
    for raw in candidates:
        normalized = raw.strip().strip(".,:;()[]{}\"'").replace("\\", "/")
        pure = PurePosixPath(normalized)
        if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
            continue
        path = workspace.joinpath(*pure.parts)
        if path.is_file() and not path.is_symlink():
            result.add(Path(*pure.parts))
    return result


def _bounded_excerpt(path: Path, keywords: tuple[str, ...]) -> str | None:
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    if b"\0" in raw:
        return None
    try:
        lines = raw.decode("utf-8").splitlines()
    except UnicodeDecodeError:
        return None
    if len(lines) <= 80:
        selected = lines
    else:
        matches = [
            index
            for index, line in enumerate(lines)
            if any(keyword in line.lower() for keyword in keywords)
        ]
        indexes: set[int] = set()
        for match in matches[:16]:
            indexes.update(range(max(0, match - 2), min(len(lines), match + 3)))
        if not indexes:
            indexes.update(range(min(40, len(lines))))
        selected = [f"{index + 1}: {lines[index]}" for index in sorted(indexes)[:80]]
    excerpt = "\n".join(selected)
    encoded = excerpt.encode("utf-8")
    if len(encoded) > 12_000:
        excerpt = encoded[:12_000].decode("utf-8", errors="ignore")
    return excerpt


def _automatic_preparation_context(
    workspace: Path,
    campaign: campaign_queue.Campaign,
    *,
    max_context_bytes: int,
) -> str:
    completed = subprocess.run(
        [
            "git",
            "-C",
            str(workspace),
            "ls-files",
            "--cached",
            "--others",
            "--exclude-standard",
        ],
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise DispatchError(
            "automatic_preparation_failed",
            "automatic CAMP preparation could not inventory the Git workspace",
            recovery_action="repair Git workspace access before retrying",
        )
    keywords = _preparation_keywords(campaign)
    referenced = _referenced_workspace_files(workspace, campaign)
    preferred = {Path("AGENTS.md"), Path("README.md"), Path("docs/script_index.md")}
    candidates: list[tuple[int, Path]] = []
    for raw in completed.stdout.splitlines():
        pure = PurePosixPath(raw)
        if (
            pure.is_absolute()
            or any(part in {"", ".", ".."} for part in pure.parts)
            or pure.parts[0] in {".git", "tool_shed", "work"}
        ):
            continue
        relative = Path(*pure.parts)
        absolute = workspace / relative
        if not absolute.is_file() or absolute.is_symlink():
            continue
        lowered = relative.as_posix().lower()
        score = sum(1 for keyword in keywords if keyword in lowered)
        if relative in referenced:
            score += 100
        if relative in preferred:
            score += 50
        candidates.append((score, relative))
    candidates.sort(key=lambda item: (-item[0], item[1].as_posix()))

    status = subprocess.run(
        ["git", "-C", str(workspace), "status", "--short"],
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    ).stdout.strip()
    explicit_reference_score = 2 if referenced else 1
    relevant_candidates = [
        item
        for item in candidates
        if item[0] >= explicit_reference_score
        or item[1] in referenced
        or item[1] in preferred
    ]
    if not relevant_candidates:
        relevant_candidates = candidates[:200]

    sections = [
        "# Automatic CAMP Preparation Context",
        "",
        f"Platform: {sys.platform}",
        f"Workspace: {workspace}",
        f"Current Python executable for verification: {Path(sys.executable).as_posix()}",
        "Dispatcher-owned capsule and lifecycle edits will be pre-existing Git changes during verification.",
        "",
        "## Selected campaign",
        "",
        campaign.path.read_text(encoding="utf-8"),
        "",
        "## Pre-existing Git status",
        "",
        status or "clean",
        "",
        "## Relevant repository file inventory",
        "",
        f"Automatic capsule context budget: {max_context_bytes} bytes total.",
        "File sizes below are actual bytes; context_files must stay within that combined budget.",
        "",
    ]
    total = len("\n".join(sections).encode("utf-8"))
    if total > AUTO_PREPARATION_MAX_SNAPSHOT_BYTES:
        raise DispatchError(
            "automatic_preparation_context_limit",
            "automatic CAMP preparation campaign and workspace state exceed the deterministic snapshot budget",
            recovery_action="reduce the campaign intent before retrying",
        )
    inventory_bytes = 0
    for score, relative in relevant_candidates[:200]:
        file_bytes = (workspace / relative).stat().st_size
        line = f"- {relative.as_posix()} ({file_bytes} bytes; relevance {score})"
        size = len((line + "\n").encode("utf-8"))
        if (
            inventory_bytes + size > AUTO_PREPARATION_MAX_INVENTORY_BYTES
            or total + size > AUTO_PREPARATION_MAX_SNAPSHOT_BYTES
        ):
            break
        sections.append(line)
        inventory_bytes += size
        total += size
    sections.extend(["", "## Bounded relevant file excerpts", ""])
    excerpt_targets: list[Path] = []
    for relative in [
        *sorted(referenced),
        *(
            path
            for score, path in candidates
            if score >= explicit_reference_score and path not in preferred
        ),
        *sorted(preferred),
    ]:
        if relative not in excerpt_targets:
            excerpt_targets.append(relative)
        if len(excerpt_targets) >= AUTO_PREPARATION_MAX_EXCERPT_FILES:
            break
    total = len("\n".join(sections).encode("utf-8"))
    for relative in excerpt_targets:
        if relative.parts[:2] == ("work", "00-campaigns"):
            continue
        excerpt = _bounded_excerpt(workspace / relative, keywords)
        if excerpt is None:
            continue
        block = f"### {relative.as_posix()}\n\n```text\n{excerpt}\n```\n"
        size = len(block.encode("utf-8"))
        if total + size > AUTO_PREPARATION_MAX_SNAPSHOT_BYTES:
            continue
        sections.append(block)
        total += size
    return "\n".join(sections).rstrip() + "\n"


def _normalize_automatic_verification_commands(
    capsule: ExecutionCapsule,
) -> ExecutionCapsule:
    """Make planner-selected verification executable and Git scope deterministic."""

    commands: list[tuple[str, ...]] = []
    python_names = {
        "py",
        "py.exe",
        "python",
        "python.exe",
        "python3",
        "python3.exe",
    }
    for command in capsule.verification_commands:
        argv = list(command)
        executable_name = Path(argv[0]).name.lower()
        if executable_name in python_names:
            if executable_name in {"py", "py.exe"} and len(argv) > 1:
                if re.fullmatch(r"-\d+(?:\.\d+)?", argv[1]):
                    del argv[1]
            argv[0] = Path(sys.executable).as_posix()
        lowered = [argument.lower() for argument in argv]
        if executable_name in {"git", "git.exe"} and "diff" in lowered and (
            "--exit-code" in lowered or "--quiet" in lowered
        ):
            separator = argv.index("--") if "--" in argv else -1
            scopes = argv[separator + 1 :] if separator >= 0 else []
            if not scopes or any(scope == "." or scope.startswith(":(") for scope in scopes):
                continue
            if "--exit-code" in argv and "--quiet" not in argv:
                argv[argv.index("--exit-code")] = "--quiet"
        if _documentation_verifier_is_formatting_fragile(capsule, tuple(argv)):
            raise DispatchError(
                "automatic_preparation_output_risk",
                "automatic documentation verification lacks shared whitespace-and-case normalization",
                recovery_action=(
                    "apply one shared whitespace-and-case normalizer to the document and expected phrases"
                ),
            )
        commands.append(tuple(argv))
    if not commands:
        raise DispatchError(
            "automatic_preparation_invalid",
            "automatic CAMP preparation did not retain a scoped deterministic verification command",
            recovery_action="repair the automatic verification boundary before retrying",
        )
    return ExecutionCapsule(
        campaign_id=capsule.campaign_id,
        camp=capsule.camp,
        prompt=capsule.prompt,
        expected_paths=capsule.expected_paths,
        context_files=capsule.context_files,
        verification_commands=tuple(commands),
        source_state_token=capsule.source_state_token,
        execution_shape=capsule.execution_shape,
        estimated_model_turns=capsule.estimated_model_turns,
        estimated_max_tool_result_bytes=capsule.estimated_max_tool_result_bytes,
    )


def _documentation_verifier_is_formatting_fragile(
    capsule: ExecutionCapsule,
    command: tuple[str, ...],
) -> bool:
    """Recognize Markdown phrase checks lacking shared whitespace-and-case normalization."""

    if not any(path.suffix.lower() == ".md" for path in capsule.expected_paths):
        return False
    executable = Path(command[0]).name.lower()
    if executable not in {
        "python",
        "python.exe",
        "python3",
        "python3.exe",
        Path(sys.executable).name.lower(),
    }:
        return False
    try:
        code = command[command.index("-c") + 1]
    except (ValueError, IndexError):
        return False
    compact = re.sub(r"\s+", " ", code.lower())
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return False
    has_multiword_literal = any(
        isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and len(node.value.split()) > 1
        for node in ast.walk(tree)
    )
    phrase_membership = (
        "required" in compact and " not in " in compact and has_multiword_literal
    )
    shared_normalizers: set[str] = set()

    def normalizes_whitespace_and_case(node: ast.AST) -> bool:
        attributes = {
            child.func.attr.lower()
            for child in ast.walk(node)
            if isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute)
        }
        collapses_whitespace = "split" in attributes and "join" in attributes
        normalizes_case = bool({"casefold", "lower"} & attributes)
        return collapses_whitespace and normalizes_case

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Lambda):
            if normalizes_whitespace_and_case(node.value):
                shared_normalizers.update(
                    target.id for target in node.targets if isinstance(target, ast.Name)
                )
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if normalizes_whitespace_and_case(node):
                shared_normalizers.add(node.name)

    shared_normalization_applied = False
    for name in shared_normalizers:
        arguments = {
            ast.dump(node.args[0], include_attributes=False)
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == name
            and node.args
        }
        if len(arguments) >= 2:
            shared_normalization_applied = True
            break
    return phrase_membership and not shared_normalization_applied


def _include_existing_expected_context(
    workspace: Path,
    capsule: ExecutionCapsule,
    *,
    max_context_bytes: int,
) -> ExecutionCapsule:
    """Supply bounded expected source files so the worker need not print them through tools."""

    context = list(capsule.context_files)
    total = sum((workspace / path).stat().st_size for path in context)
    for relative in capsule.expected_paths:
        if relative in context or relative.suffix.lower() not in PREPARATION_TEXT_SUFFIXES:
            continue
        path = workspace / relative
        if not path.is_file() or path.is_symlink():
            continue
        raw = path.read_bytes()
        if b"\0" in raw:
            continue
        try:
            raw.decode("utf-8")
        except UnicodeDecodeError:
            continue
        if total + len(raw) > max_context_bytes:
            raise DispatchError(
                "automatic_preparation_context_limit",
                f"existing expected source {relative.as_posix()} does not fit the inline context budget",
                recovery_action="reduce the campaign to a smaller source boundary before retrying",
            )
        context.append(relative)
        total += len(raw)
    return ExecutionCapsule(
        campaign_id=capsule.campaign_id,
        camp=capsule.camp,
        prompt=capsule.prompt,
        expected_paths=capsule.expected_paths,
        context_files=tuple(context),
        verification_commands=capsule.verification_commands,
        source_state_token=capsule.source_state_token,
        execution_shape=capsule.execution_shape,
        estimated_model_turns=capsule.estimated_model_turns,
        estimated_max_tool_result_bytes=capsule.estimated_max_tool_result_bytes,
    )


def _verification_output_is_broad(command: tuple[str, ...]) -> bool:
    executable = Path(command[0]).name.lower()
    lowered = [argument.lower() for argument in command[1:]]
    if executable in {"git", "git.exe"} and "diff" in lowered:
        separator = lowered.index("--") if "--" in lowered else -1
        scopes = lowered[separator + 1 :] if separator >= 0 else []
        bounded_mode = any(
            option in lowered
            for option in {"--quiet", "--check", "--name-only", "--name-status", "--stat"}
        )
        if not scopes or any(scope == "." or scope.startswith(":(") for scope in scopes):
            return True
        if not bounded_mode:
            return True
    if executable in {"python", "python.exe", "python3", "python3.exe"}:
        if "unittest" in lowered and "discover" in lowered:
            pattern = None
            for option in ("-p", "--pattern"):
                if option in lowered and lowered.index(option) + 1 < len(lowered):
                    pattern = lowered[lowered.index(option) + 1]
                    break
            if not pattern or any(character in pattern for character in "*?[]"):
                return True
    if executable in {"pytest", "pytest.exe"}:
        positional = [argument for argument in command[1:] if argument and not argument.startswith("-")]
        if not positional:
            return True
    return False


def _validate_prelaunch_capsule(
    workspace: Path,
    capsule: ExecutionCapsule,
    *,
    max_context_bytes: int,
    automatic: bool,
) -> None:
    """Apply deterministic feasibility checks before lifecycle mutation or worker launch."""

    context_bytes = sum((workspace / path).stat().st_size for path in capsule.context_files)
    if context_bytes > max_context_bytes:
        raise DispatchError(
            "automatic_preparation_context_limit" if automatic else "execution_capsule_invalid",
            f"execution capsule selected {context_bytes} context bytes; limit is {max_context_bytes}",
            recovery_action="reduce inline context before retrying",
        )
    for path in capsule.expected_paths:
        if path.parts[0] in {".git", "tool_shed"} or path.parts[:2] == ("work", "00-campaigns"):
            raise DispatchError(
                "automatic_preparation_unsafe" if automatic else "execution_capsule_invalid",
                f"execution capsule selected a protected mutation path: {path.as_posix()}",
                recovery_action="repair the execution boundary before retrying",
            )
    if automatic:
        if capsule.execution_shape not in {"atomic", "bounded-slice"}:
            raise DispatchError(
                "automatic_preparation_non_atomic",
                "automatic CAMP preparation did not declare an atomic or bounded-slice shape",
                recovery_action="reduce the request to one independently verifiable CAMP",
            )
        if capsule.estimated_model_turns is None or capsule.estimated_max_tool_result_bytes is None:
            raise DispatchError(
                "automatic_preparation_invalid",
                "automatic CAMP preparation omitted prelaunch turn or tool-result estimates",
                recovery_action="repair the App Server planning output contract before retrying",
            )
    for command in capsule.verification_commands:
        executable = command[0]
        resolved = (
            Path(executable)
            if Path(executable).is_absolute()
            else Path(shutil.which(executable) or "")
        )
        if not str(resolved) or not resolved.is_file():
            raise DispatchError(
                "automatic_preparation_executable_missing" if automatic else "execution_capsule_invalid",
                f"verification executable is unavailable: {executable}",
                recovery_action="select an available platform-local executable before retrying",
            )
        if automatic and _verification_output_is_broad(command):
            raise DispatchError(
                "automatic_preparation_output_risk",
                "automatic CAMP preparation selected broad verification output",
                recovery_action="replace it with a quiet path-scoped deterministic verifier",
            )


def _parse_automatic_preparation(
    workspace: Path,
    campaign: campaign_queue.Campaign,
    result: Any,
    *,
    max_context_bytes: int = AUTO_PREPARATION_MAX_CONTEXT_BYTES,
) -> tuple[ExecutionCapsule, str]:
    if result is None or result.status != "completed":
        raise DispatchError(
            "automatic_preparation_failed",
            "App Server planning did not complete automatic CAMP preparation",
            recovery_action="inspect the compact preparation result; no campaign or product mutation occurred",
        )
    if result.context_warning is not None:
        raise DispatchError(
            "automatic_preparation_context_limit",
            "automatic CAMP preparation exceeded the focused context warning threshold",
            recovery_action="reduce the campaign preparation scope before retrying",
        )
    if result.mutation_events:
        raise DispatchError(
            "automatic_preparation_unsafe",
            "read-only automatic CAMP preparation reported mutation events",
            recovery_action="inspect the planning environment before retrying",
            mutation_state="unknown",
        )
    if not isinstance(result.text, str) or len(result.text.encode("utf-8")) > 65_536:
        raise DispatchError(
            "automatic_preparation_invalid",
            "automatic CAMP preparation output exceeded the structured result limit",
            recovery_action="reduce the preparation scope before retrying",
        )
    try:
        payload = json.loads(result.text)
    except (TypeError, json.JSONDecodeError) as error:
        raise DispatchError(
            "automatic_preparation_invalid",
            "automatic CAMP preparation did not return valid structured JSON",
            recovery_action="repair the App Server planning output contract before retrying",
        ) from error
    if not isinstance(payload, dict) or set(payload) != AUTO_PREPARATION_KEYS:
        raise DispatchError(
            "automatic_preparation_invalid",
            "automatic CAMP preparation returned unsupported or missing fields",
            recovery_action="repair the App Server planning output contract before retrying",
        )
    reason = str(payload.get("reason") or "").strip()
    if len(reason.encode("utf-8")) > 2_048:
        raise DispatchError(
            "automatic_preparation_invalid",
            "automatic CAMP preparation reason exceeded the compact result limit",
            recovery_action="reduce the preparation scope before retrying",
        )
    if payload.get("status") != "prepared":
        if (
            payload.get("execution_shape") != "blocked"
            or payload.get("estimated_model_turns") != 0
            or payload.get("estimated_max_tool_result_bytes") != 0
        ):
            raise DispatchError(
                "automatic_preparation_invalid",
                "blocked automatic preparation did not return the bounded empty estimate contract",
                recovery_action="repair the App Server planning output contract before retrying",
            )
        raise DispatchError(
            "automatic_preparation_blocked",
            reason or "automatic CAMP preparation could not establish a safe bounded execution",
            recovery_action="resolve the reported campaign preparation condition, then rerun once",
        )
    capsule_payload = {
        key: payload[key]
        for key in (
            *CAPSULE_REQUIRED_KEYS,
            "execution_shape",
            "estimated_model_turns",
            "estimated_max_tool_result_bytes",
        )
    }
    capsule = _execution_capsule_from_payload(workspace, campaign, capsule_payload)
    capsule = _normalize_automatic_verification_commands(capsule)
    capsule = _include_existing_expected_context(
        workspace,
        capsule,
        max_context_bytes=max_context_bytes,
    )
    if len(capsule.expected_paths) > AUTO_PREPARATION_MAX_EXPECTED_PATHS:
        raise DispatchError(
            "automatic_preparation_non_atomic",
            "automatic CAMP preparation selected too many mutation paths for one bounded worker",
            recovery_action="reduce the campaign to one independently verifiable CAMP before retrying",
        )
    if len(capsule.verification_commands) > AUTO_PREPARATION_MAX_VERIFICATION_COMMANDS:
        raise DispatchError(
            "automatic_preparation_output_risk",
            "automatic CAMP preparation selected too many verification commands",
            recovery_action="scope verification to the bounded CAMP before retrying",
        )
    context_bytes = sum((workspace / path).stat().st_size for path in capsule.context_files)
    if context_bytes > max_context_bytes:
        raise DispatchError(
            "automatic_preparation_context_limit",
            (
                "automatic CAMP preparation selected "
                f"{context_bytes} context bytes; limit is {max_context_bytes}"
            ),
            recovery_action="select fewer or smaller context files before retrying",
        )
    forbidden_roots = {".git", "tool_shed"}
    for path in capsule.expected_paths:
        if path.parts[0] in forbidden_roots or path.parts[:2] == ("work", "00-campaigns"):
            raise DispatchError(
                "automatic_preparation_unsafe",
                f"automatic CAMP preparation selected a protected mutation path: {path.as_posix()}",
                recovery_action="repair the automatic preparation boundary before retrying",
            )
    return capsule, reason


def _capsule_payload_from_execution(capsule: ExecutionCapsule) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": 1,
        "campaign_id": capsule.campaign_id,
        "camp": capsule.camp,
        "prompt": capsule.prompt,
        "expected_paths": [path.as_posix() for path in capsule.expected_paths],
        "context_files": [path.as_posix() for path in capsule.context_files],
        "verification_commands": [list(command) for command in capsule.verification_commands],
    }
    for key, value in (
        ("source_state_token", capsule.source_state_token),
        ("execution_shape", capsule.execution_shape),
        ("estimated_model_turns", capsule.estimated_model_turns),
        ("estimated_max_tool_result_bytes", capsule.estimated_max_tool_result_bytes),
    ):
        if value is not None:
            payload[key] = value
    return payload


def _persist_automatic_capsule(
    workspace: Path,
    campaign: campaign_queue.Campaign,
    capsule: ExecutionCapsule,
    *,
    replace_existing: bool = False,
) -> campaign_queue.Campaign:
    capsule = _source_bound_capsule(workspace, campaign, capsule)
    payload = _capsule_payload_from_execution(capsule)
    section = (
        CAPSULE_HEADING
        + "\n\n```json\n"
        + json.dumps(payload, indent=2, sort_keys=True)
        + "\n```"
    )
    writer = (
        campaign_queue.replace_app_server_capsule
        if replace_existing
        else campaign_queue.attach_app_server_capsule
    )
    writer(
        workspace,
        campaign.campaign_id,
        section,
        expect=campaign_queue.state_token(workspace),
        project_binding=binding_token(workspace, operation="campaign-queue"),
    )
    persisted = campaign_queue.load_all(workspace)[campaign.campaign_id]
    reloaded = parse_execution_capsule(workspace, persisted)
    if _capsule_source_is_stale(workspace, persisted, reloaded):
        raise DispatchError(
            "automatic_preparation_stale",
            "persisted automatic capsule did not retain its source-state binding",
            recovery_action="inspect the guarded capsule transaction before retrying",
        )
    return persisted


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
    preparation: dict[str, Any],
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
        "preparation": preparation,
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
                "usage_budget": result.get("usage_budget"),
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
            "cancelled_or_interrupted": journal.get("cancelled_or_interrupted"),
            "usage_budget": journal.get("usage_budget"),
        },
        "next_action": execution.get("next_action"),
        "recovery_action": (
            "none"
            if journal.get("final_state") == "verified"
            else execution.get("next_action")
            or "inspect the compact journal and do not replay after mutation"
        ),
    }


def dispatch_next(
    workspace: Path,
    *,
    app_server_requested: bool,
    gui_requested: bool = False,
    codex: str | None = None,
    config_path: Path = DEFAULT_CONFIG,
    policy_path: Path = DEFAULT_POLICY,
    qualifications_path: Path = DEFAULT_QUALIFICATIONS,
    qualification_cache_path: Path | None = None,
    preference_path: Path | None = None,
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
    execution_config = AppServerFeatureConfig.load(config_path)
    execution_policy = ModelPolicy.load(policy_path)
    automatic_context_bytes = _automatic_context_budget(execution_config)
    _preparation_contract(campaign)
    capsule_headings = sum(
        line.strip() == CAPSULE_HEADING for line in campaign.body.splitlines()
    )
    replace_existing_capsule = False
    requires_preparation = capsule_headings == 0
    if capsule_headings != 0:
        capsule = parse_execution_capsule(root, campaign)
        replace_existing_capsule = _capsule_source_is_stale(root, campaign, capsule)
        if replace_existing_capsule and campaign.status != "queued":
            raise DispatchError(
                "execution_capsule_stale_after_start",
                "a working campaign's source-bound capsule changed after execution may have started",
                recovery_action="reconcile the workspace and mutation journal; do not replay the worker",
                mutation_state="unknown",
            )
        requires_preparation = replace_existing_capsule
    preparation: dict[str, Any] = {
        "mode": "automatic-refresh" if replace_existing_capsule else "embedded",
        "persisted": not replace_existing_capsule,
        "source_state": "stale" if replace_existing_capsule else (
            "bound" if capsule_headings and capsule.source_state_token is not None else "legacy-unbound"
        ),
        "model": None,
        "reasoning": None,
        "tokens": flatten_token_usage(None),
        "model_turns": 0,
        "duration_seconds": 0.0,
    }
    planning_preflight: dict[str, Any] | None = None
    selection = select_command(
        "camp-run",
        app_server_requested=app_server_requested,
        gui_requested=gui_requested,
        codex=codex,
        config_path=config_path,
        policy_path=policy_path,
        qualifications_path=qualifications_path,
        qualification_cache_path=qualification_cache_path,
        preference_path=preference_path,
        workspace=root,
    )
    if not selection.allowed or getattr(selection, "execution", "App Server") != "App Server":
        raise DispatchError(
            getattr(selection, "fallback_reason", None) or selection.reason,
            "App Server CAMP selection was not allowed",
            recovery_action=(
                "rerun the same Tool Shed command with --gui"
                if not getattr(selection, "strict_request", app_server_requested)
                else "rerun the same Tool Shed command without --app-server or with --gui"
            ),
        )
    preflight = _app_server_host_preflight(selection, timeout=timeout)
    if requires_preparation:
        planning_selection = select_command(
            "plan",
            app_server_requested=app_server_requested,
            gui_requested=gui_requested,
            codex=codex,
            config_path=config_path,
            policy_path=policy_path,
            qualifications_path=qualifications_path,
            qualification_cache_path=qualification_cache_path,
            preference_path=preference_path,
            workspace=root,
        )
        if (
            not planning_selection.allowed
            or getattr(planning_selection, "execution", "App Server") != "App Server"
        ):
            raise DispatchError(
                getattr(planning_selection, "fallback_reason", None) or planning_selection.reason,
                "automatic App Server CAMP preparation was not allowed",
                recovery_action="rerun the same Tool Shed command without --app-server",
            )
        planning_preflight = _app_server_host_preflight(
            planning_selection,
            timeout=timeout,
        )
        _, preparation_result = execute_preparation_if_enabled(
            _automatic_preparation_prompt(
                campaign,
                max_context_bytes=automatic_context_bytes,
            ),
            cwd=root,
            campaign=campaign_id,
            preparation_context=_automatic_preparation_context(
                root,
                campaign,
                max_context_bytes=automatic_context_bytes,
            ),
            output_schema=AUTO_PREPARATION_SCHEMA,
            enable_override=True,
            config=execution_config,
            policy=execution_policy,
            codex=planning_selection.codex_executable,
            timeout=timeout,
            telemetry_path=telemetry_path,
        )
        capsule, preparation_reason = _parse_automatic_preparation(
            root,
            campaign,
            preparation_result,
            max_context_bytes=automatic_context_bytes,
        )
        _validate_prelaunch_capsule(
            root,
            capsule,
            max_context_bytes=automatic_context_bytes,
            automatic=True,
        )
        preparation = {
            "mode": "automatic-refresh" if replace_existing_capsule else "automatic",
            "persisted": False,
            "source_state": "stale" if replace_existing_capsule else "new",
            "model": preparation_result.actual_model,
            "reasoning": preparation_result.reasoning,
            "context_files": len(capsule.context_files),
            "context_bytes": sum(
                (root / path).stat().st_size for path in capsule.context_files
            ),
            "context_limit_bytes": automatic_context_bytes,
            "tokens": flatten_token_usage(preparation_result.token_usage),
            "model_turns": preparation_result.model_turns,
            "duration_seconds": preparation_result.duration_seconds,
            "reason": preparation_reason,
            "execution_shape": capsule.execution_shape,
            "estimated_model_turns": capsule.estimated_model_turns,
            "estimated_max_tool_result_bytes": capsule.estimated_max_tool_result_bytes,
        }
    else:
        _validate_prelaunch_capsule(
            root,
            capsule,
            max_context_bytes=automatic_context_bytes,
            automatic=capsule.source_state_token is not None,
        )
    if planning_preflight is not None:
        preflight["automatic_preparation"] = planning_preflight
        campaign = _persist_automatic_capsule(
            root,
            campaign,
            capsule,
            replace_existing=replace_existing_capsule,
        )
        capsule = parse_execution_capsule(root, campaign)
        preparation["persisted"] = True
        preparation["source_state"] = "bound"
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
        preparation=preparation,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--codex", default=None)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--qualifications", type=Path, default=DEFAULT_QUALIFICATIONS)
    parser.add_argument("--qualification-cache", type=Path, default=None)
    parser.add_argument("--preference", type=Path, default=None)
    parser.add_argument("--events", type=Path, default=None)
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument("--telemetry", type=Path, default=None)
    commands = parser.add_subparsers(dest="command", required=True)
    next_command = commands.add_parser("next")
    execution = next_command.add_mutually_exclusive_group()
    execution.add_argument("--app-server", action="store_true")
    execution.add_argument("--gui", action="store_true")
    next_command.add_argument("--json", action="store_true")
    return parser


def _gui_handoff_payload(
    *,
    category: str,
    mutation_state: str,
    prior: dict[str, Any] | None = None,
) -> dict[str, Any]:
    reconciliation = mutation_state != "none"
    payload: dict[str, Any] = {
        "schema_version": 1,
        "status": "gui_reconciliation_required" if reconciliation else "gui_fallback",
        "execution": "GUI",
        "fallback": {
            "automatic": True,
            "category": category,
            "mutation_state": mutation_state,
            "continue_same_action": True,
            "action": (
                "reconcile workspace and mutation journal, then continue in GUI without replay"
                if reconciliation
                else "continue the same action immediately in GUI"
            ),
            "replay_app_server": False,
        },
    }
    if prior:
        journal = prior.get("journal") if isinstance(prior.get("journal"), dict) else {}
        payload["reconciliation"] = {
            "journal_final_state": journal.get("final_state"),
            "journal_safe": journal.get("safe"),
            "changed_path_count": sum(
                len(journal.get(field) or [])
                for field in ("files_created", "files_modified", "files_deleted")
            ),
            "verification_passed": journal.get("verification_passed"),
        }
    return payload


def main() -> int:
    args = build_parser().parse_args()
    correlation_id = uuid.uuid4().hex
    preference = AppServerPreferenceStore(args.preference).status()
    record_app_server_event_best_effort(
        path=args.events,
        command="next",
        outcome="attempted",
        category="dispatch",
        mutation_state="none",
        backend="app_server",
        preference_mode=preference.mode,
        strict_request=args.app_server,
        source="operator" if args.app_server else "passive",
        event_type="execution",
        role="camp_execution",
        correlation_id=correlation_id,
    )
    try:
        payload = dispatch_next(
            args.workspace,
            app_server_requested=args.app_server,
            gui_requested=args.gui,
            codex=args.codex,
            config_path=args.config,
            policy_path=args.policy,
            qualifications_path=args.qualifications,
            qualification_cache_path=args.qualification_cache,
            preference_path=args.preference,
            timeout=args.timeout,
            telemetry_path=args.telemetry,
        )
    except (DispatchError, campaign_queue.CampaignError, OSError) as error:
        if isinstance(error, DispatchError):
            category = error.category
            mutation_state = error.mutation_state
        else:
            category = "dispatch_preflight_failed"
            mutation_state = "none"
        record_app_server_event_best_effort(
            path=args.events,
            command="next",
            outcome="failed" if args.app_server else "gui_fallback",
            category=category,
            mutation_state=mutation_state,
            backend="gui" if not args.app_server else "app_server",
            preference_mode=preference.mode,
            strict_request=args.app_server,
            source="operator" if args.app_server else "passive",
            event_type="fallback",
            role="camp_execution",
            correlation_id=correlation_id,
        )
        if not args.app_server:
            payload = _gui_handoff_payload(
                category=category,
                mutation_state=mutation_state,
            )
            print(json.dumps(payload, indent=2, sort_keys=True))
            return 0
        payload = {
            "schema_version": 1,
            "status": "blocked",
            "category": category,
            "mutation_state": mutation_state,
            "recovery_action": error.recovery_action if isinstance(error, DispatchError) else "repair the reported workspace state before retrying",
            "error": str(error),
        }
        print(json.dumps(payload, indent=2, sort_keys=True), file=sys.stderr)
        return 2
    if payload["status"] != "completed" and not args.app_server:
        final_state = str((payload.get("journal") or {}).get("final_state") or "stopped")
        category = f"app_server_{final_state}"
        record_app_server_event_best_effort(
            path=args.events,
            command="next",
            outcome="gui_reconciliation",
            category=category,
            mutation_state="possible",
            backend="gui",
            preference_mode=preference.mode,
            strict_request=False,
            source="passive",
            event_type="reconciliation",
            role="camp_execution",
            correlation_id=correlation_id,
        )
        payload = _gui_handoff_payload(
            category=category,
            mutation_state="possible",
            prior=payload,
        )
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    record_app_server_event_best_effort(
        path=args.events,
        command="next",
        outcome="completed" if payload["status"] == "completed" else "stopped",
        category=str(payload["status"]),
        mutation_state="verified" if payload["status"] == "completed" else "possible",
        backend="app_server",
        preference_mode=preference.mode,
        strict_request=args.app_server,
        source="operator" if args.app_server else "passive",
        event_type="execution",
        role="camp_execution",
        correlation_id=correlation_id,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["status"] == "completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
