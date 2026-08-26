#!/usr/bin/env python3
"""Dispatch ordinary Tool Shed `next` selection to the existing App Server CAMP runner."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
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
        execute_preparation_if_enabled,
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
        execute_preparation_if_enabled,
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
AUTO_PREPARATION_KEYS = {"status", "reason", *CAPSULE_KEYS}
AUTO_PREPARATION_MAX_CONTEXT_BYTES = 64_000
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
    return _execution_capsule_from_payload(workspace, campaign, payload)


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
- write a complete worker prompt that permits only the declared mutations, forbids lifecycle,
  deployment, network, and protected-environment work, reserves verification for the orchestrator,
  and requires camp_ready_for_verification after implementation;
- declare every worker-owned mutation in expected_paths as unique repository-relative POSIX paths;
- declare only existing regular UTF-8 context files needed by the worker, with their combined
  actual file sizes no greater than {max_context_bytes} bytes;
- prefer no context_files, or only small immutable instructions and contracts; the CAMP worker has
  bounded workspace tools and should inspect exact symbols itself instead of receiving whole large
  implementation or test files inline;
- provide one to eight deterministic shell-free verification commands as direct argv arrays;
- use platform-local executable paths that do not depend on shell activation;
- exclude work/00-campaigns, Tool Shed snapshot machinery, Git metadata, deployment, production,
  credentials, generated outputs not owned by the worker, and unrelated cleanup.

If exact mutation paths or safe deterministic verification cannot be established without an owner
decision, protected action, or broader planning, set status to blocked, explain the limiting
condition in reason, and return schema_version 1, the exact campaign_id, and empty camp, prompt,
expected_paths, context_files, and verification_commands. Do not guess or broaden authority.
"""


def _preparation_keywords(campaign: campaign_queue.Campaign) -> tuple[str, ...]:
    text = "\n".join((campaign.title, campaign.outcome, campaign.body)).lower()
    words = {
        word
        for word in re.findall(r"[a-z][a-z0-9_-]{3,}", text)
        if word not in PREPARATION_STOPWORDS and not word.isdigit()
    }
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
            or pure.parts[0] in {".git", "tool_shed"}
            or pure.parts[:3] == ("work", "evidence", "generated")
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
    sections = [
        "# Automatic CAMP Preparation Context",
        "",
        f"Platform: {sys.platform}",
        f"Workspace: {workspace}",
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
    inventory_bytes = 0
    for score, relative in candidates[:500]:
        file_bytes = (workspace / relative).stat().st_size
        line = f"- {relative.as_posix()} ({file_bytes} bytes; relevance {score})"
        size = len((line + "\n").encode("utf-8"))
        if inventory_bytes + size > 24_000:
            break
        sections.append(line)
        inventory_bytes += size
    sections.extend(["", "## Bounded relevant file excerpts", ""])
    excerpt_targets: list[Path] = []
    for relative in [*sorted(referenced), *sorted(preferred), *(path for score, path in candidates if score > 0)]:
        if relative not in excerpt_targets:
            excerpt_targets.append(relative)
        if len(excerpt_targets) >= 14:
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
        if total + size > 90_000:
            break
        sections.append(block)
        total += size
    return "\n".join(sections).rstrip() + "\n"


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
        raise DispatchError(
            "automatic_preparation_blocked",
            reason or "automatic CAMP preparation could not establish a safe bounded execution",
            recovery_action="resolve the reported campaign preparation condition, then rerun once",
        )
    capsule_payload = {key: payload[key] for key in CAPSULE_KEYS}
    capsule = _execution_capsule_from_payload(workspace, campaign, capsule_payload)
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
    return {
        "schema_version": 1,
        "campaign_id": capsule.campaign_id,
        "camp": capsule.camp,
        "prompt": capsule.prompt,
        "expected_paths": [path.as_posix() for path in capsule.expected_paths],
        "context_files": [path.as_posix() for path in capsule.context_files],
        "verification_commands": [list(command) for command in capsule.verification_commands],
    }


def _persist_automatic_capsule(
    workspace: Path,
    campaign: campaign_queue.Campaign,
    capsule: ExecutionCapsule,
) -> campaign_queue.Campaign:
    payload = _capsule_payload_from_execution(capsule)
    section = (
        CAPSULE_HEADING
        + "\n\n```json\n"
        + json.dumps(payload, indent=2, sort_keys=True)
        + "\n```"
    )
    campaign_queue.attach_app_server_capsule(
        workspace,
        campaign.campaign_id,
        section,
        expect=campaign_queue.state_token(workspace),
        project_binding=binding_token(workspace, operation="campaign-queue"),
    )
    persisted = campaign_queue.load_all(workspace)[campaign.campaign_id]
    parse_execution_capsule(workspace, persisted)
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
    execution_config = AppServerFeatureConfig.load(config_path)
    execution_policy = ModelPolicy.load(policy_path)
    automatic_context_bytes = _automatic_context_budget(execution_config)
    capsule_headings = sum(
        line.strip() == CAPSULE_HEADING for line in campaign.body.splitlines()
    )
    if capsule_headings != 0:
        capsule = parse_execution_capsule(root, campaign)
    preparation: dict[str, Any] = {
        "mode": "embedded",
        "persisted": True,
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
    if capsule_headings == 0:
        planning_selection = select_command(
            "plan",
            app_server_requested=app_server_requested,
            codex=codex,
            config_path=config_path,
            policy_path=policy_path,
            qualifications_path=qualifications_path,
            qualification_cache_path=qualification_cache_path,
        )
        if not planning_selection.allowed or not app_server_requested:
            raise DispatchError(
                planning_selection.reason,
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
        preparation = {
            "mode": "automatic",
            "persisted": False,
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
        }
    if planning_preflight is not None:
        preflight["automatic_preparation"] = planning_preflight
        campaign = _persist_automatic_capsule(root, campaign, capsule)
        capsule = parse_execution_capsule(root, campaign)
        preparation["persisted"] = True
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
