#!/usr/bin/env python3
"""Feature-flagged Tool Shed orchestration for read-only Codex App Server roles."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import tempfile
from contextlib import contextmanager
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Iterator

try:
    from scripts.codex_app_server import AppServerError, AuthenticationError
    from scripts.codex_execution import (
        CodexExecutionAdapter,
        ExecutionResult,
        ModelPolicy,
        ModelPolicyError,
        classify_recovery,
        default_telemetry_path,
        detect_codex_version,
        flatten_token_usage,
        last_token_usage,
        sandbox_policy,
    )
    from scripts.codex_camp_execution import (
        CAMP_OUTCOME_SCHEMA,
        CampExecutionError,
        CampStructuredOutcome,
        GitMutationJournal,
        camp_next_action,
        compact_command_evidence,
        parse_camp_outcome,
        structured_outcome_record,
    )
except ModuleNotFoundError:  # Direct execution: python scripts/codex_orchestration.py
    from codex_app_server import AppServerError, AuthenticationError  # type: ignore[no-redef]
    from codex_execution import (  # type: ignore[no-redef]
        CodexExecutionAdapter,
        ExecutionResult,
        ModelPolicy,
        ModelPolicyError,
        classify_recovery,
        default_telemetry_path,
        detect_codex_version,
        flatten_token_usage,
        last_token_usage,
        sandbox_policy,
    )
    from codex_camp_execution import (  # type: ignore[no-redef]
        CAMP_OUTCOME_SCHEMA,
        CampExecutionError,
        CampStructuredOutcome,
        GitMutationJournal,
        camp_next_action,
        compact_command_evidence,
        parse_camp_outcome,
        structured_outcome_record,
    )


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "adapters" / "codex-app-server-config.json"
DEFAULT_BENCHMARKS = ROOT / "adapters" / "codex-app-server-benchmarks.json"
DEFAULT_BASELINE = ROOT / "docs" / "codex-app-server-benchmark-baseline.json"


class FeatureConfigError(ValueError):
    pass


@dataclass(frozen=True)
class RouteDecision:
    backend: str
    role: str
    reason: str
    app_server_enabled: bool
    role_enabled: bool
    sandbox: str
    compatibility_warning: str | None = None

    @property
    def use_app_server(self) -> bool:
        return self.backend == "app-server"


@dataclass(frozen=True)
class ContextTarget:
    execution_cwd: Path
    explicit_files: tuple[Path, ...]
    source_cwd: Path
    mode: str
    ephemeral: bool


class AppServerFeatureConfig:
    def __init__(self, payload: dict[str, Any], *, source: Path) -> None:
        self.payload = payload
        self.source = source
        self._validate()

    @classmethod
    def load(cls, path: Path = DEFAULT_CONFIG) -> AppServerFeatureConfig:
        resolved = path.expanduser().resolve()
        try:
            payload = json.loads(resolved.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise FeatureConfigError(f"cannot load App Server feature config {resolved}: {error}") from error
        if not isinstance(payload, dict):
            raise FeatureConfigError("App Server feature config must be a JSON object")
        return cls(payload, source=resolved)

    def _validate(self) -> None:
        if self.payload.get("schema_version") != 1:
            raise FeatureConfigError("App Server feature config schema_version must equal 1")
        if not isinstance(self.payload.get("codex_app_server_enabled"), bool):
            raise FeatureConfigError("codex_app_server_enabled must be boolean")
        flags = self.payload.get("role_flags")
        if not isinstance(flags, dict) or not flags:
            raise FeatureConfigError("role_flags must be a non-empty object")
        if any(not isinstance(role, str) or not isinstance(value, bool) for role, value in flags.items()):
            raise FeatureConfigError("every role flag must be boolean")
        for required in ("planning", "verification"):
            if required not in flags:
                raise FeatureConfigError(f"role_flags must include {required!r}")
        routes = self.payload.get("gui_native_routes")
        if not isinstance(routes, list) or "ts: discuss" not in routes:
            raise FeatureConfigError("gui_native_routes must include 'ts: discuss'")
        allowed = self.payload.get("allowed_sandboxes")
        if not isinstance(allowed, list) or not allowed:
            raise FeatureConfigError("allowed_sandboxes must be a non-empty list")
        if any(item not in {"read-only", "workspace-write", "danger-full-access"} for item in allowed):
            raise FeatureConfigError("allowed_sandboxes contains an unknown sandbox")
        role_sandboxes = self.payload.get("role_sandboxes")
        if not isinstance(role_sandboxes, dict):
            raise FeatureConfigError("role_sandboxes must be an object")
        for role, sandboxes in role_sandboxes.items():
            if role not in flags or not isinstance(sandboxes, list) or not sandboxes:
                raise FeatureConfigError(f"invalid role_sandboxes entry for {role!r}")
            if any(sandbox not in allowed for sandbox in sandboxes):
                raise FeatureConfigError(
                    f"role_sandboxes.{role} contains a sandbox that is not globally allowed"
                )
        approvals = self.payload.get("approvals")
        if not isinstance(approvals, dict):
            raise FeatureConfigError("approvals must be an object")
        if approvals.get("workspace_write_enabled") is not False:
            raise FeatureConfigError(
                "this phase requires approvals.workspace_write_enabled to remain false"
            )
        write_execution = self.payload.get("write_execution")
        if "workspace-write" in allowed:
            required_write_policy = {
                "approval_policy": "never",
                "network_access": False,
                "exclude_slash_tmp": True,
                "exclude_tmpdir_env_var": True,
                "require_git": True,
                "require_explicit_path_scope": True,
                "retry_after_mutation": False,
                "deployment_qualified": False,
            }
            if not isinstance(write_execution, dict):
                raise FeatureConfigError("workspace-write requires write_execution policy")
            for key, expected in required_write_policy.items():
                if write_execution.get(key) != expected:
                    raise FeatureConfigError(
                        f"write_execution.{key} must equal {expected!r}"
                    )
            if not flags.get("camp_execution"):
                raise FeatureConfigError("workspace-write requires camp_execution role flag")
            if role_sandboxes.get("camp_execution") != ["workspace-write"]:
                raise FeatureConfigError(
                    "camp_execution must be restricted to workspace-write"
                )
        qualification = self.payload.get("qualification")
        if not isinstance(qualification, dict):
            raise FeatureConfigError("qualification must be an object")
        baseline = qualification.get("estimated_codex_baseline_input_tokens")
        if not isinstance(baseline, int) or baseline < 0:
            raise FeatureConfigError(
                "qualification.estimated_codex_baseline_input_tokens must be non-negative"
            )
        thread_policy = self.payload.get("thread_policy")
        if not isinstance(thread_policy, dict):
            raise FeatureConfigError("thread_policy must be an object")
        for role in ("planning", "verification", "camp_execution"):
            if role not in flags or not flags[role]:
                continue
            if thread_policy.get(role) not in {"new", "resume"}:
                raise FeatureConfigError(
                    f"thread_policy.{role} must be 'new' or 'resume'"
                )

    @property
    def globally_enabled(self) -> bool:
        return bool(self.payload["codex_app_server_enabled"])

    def role_enabled(self, role: str) -> bool:
        return self.payload["role_flags"].get(role) is True

    def thread_policy(self, role: str) -> str:
        return str(self.payload["thread_policy"].get(role) or "new")

    @property
    def qualified_codex_version(self) -> str:
        qualification = self.payload.get("qualification")
        value = qualification.get("validated_codex_cli_version") if isinstance(qualification, dict) else None
        return str(value or "unknown")

    def compatibility_warning(self, codex: str = "codex") -> str | None:
        installed = detect_codex_version(codex)
        qualified = self.qualified_codex_version
        if installed is None:
            return (
                "Codex App Server version could not be detected. "
                "Run `python3 scripts/codex_app_server_compatibility.py smoke --cwd .` "
                "before relying on App Server execution."
            )
        if installed == qualified:
            return None
        return (
            "Codex App Server version changed. "
            f"Qualified version: {qualified}. Installed version: {installed}. "
            "Run `python3 scripts/codex_app_server_compatibility.py smoke --cwd .` "
            "before relying on App Server execution."
        )

    def validate_model_policy(self, policy: ModelPolicy) -> None:
        missing = sorted(set(policy.roles) - set(self.payload["role_flags"]))
        if missing:
            raise FeatureConfigError(
                "role_flags is missing model-policy roles: " + ", ".join(missing)
            )

    def warning_threshold(self, role: str) -> int | None:
        context = self.payload.get("context")
        warnings = context.get("warning_input_tokens") if isinstance(context, dict) else None
        if not isinstance(warnings, dict):
            return None
        value = warnings.get(role, warnings.get("default"))
        return int(value) if isinstance(value, int) and value > 0 else None

    @property
    def restricted_read(self) -> bool:
        context = self.payload.get("context")
        return isinstance(context, dict) and context.get("restricted_read") is True

    @property
    def context_mode(self) -> str:
        context = self.payload.get("context")
        value = context.get("scope") if isinstance(context, dict) else None
        return str(value or "workspace")

    @property
    def context_delivery(self) -> str:
        context = self.payload.get("context")
        value = context.get("delivery") if isinstance(context, dict) else None
        delivery = str(value or "reference")
        if delivery not in {"reference", "inline_relevant_files"}:
            raise FeatureConfigError(f"unsupported context delivery {delivery!r}")
        return delivery

    @property
    def max_snapshot_bytes(self) -> int:
        context = self.payload.get("context")
        value = context.get("max_snapshot_bytes") if isinstance(context, dict) else None
        return int(value) if isinstance(value, int) and value > 0 else 2_000_000

    @property
    def max_inline_bytes(self) -> int:
        context = self.payload.get("context")
        value = context.get("max_inline_bytes") if isinstance(context, dict) else None
        return int(value) if isinstance(value, int) and value > 0 else 100_000

    def route(
        self,
        role: str,
        *,
        request_text: str = "",
        sandbox: str = "read-only",
        enable_override: bool | None = None,
    ) -> RouteDecision:
        normalized = request_text.lstrip().lower()
        gui_native = any(
            normalized.startswith(str(prefix).lower())
            for prefix in self.payload["gui_native_routes"]
        )
        enabled = self.globally_enabled if enable_override is None else enable_override
        role_enabled = self.role_enabled(role)
        if role == "discussion" or gui_native:
            return RouteDecision("existing-gui", role, "gui_native_discussion", enabled, role_enabled, sandbox)
        if not enabled:
            return RouteDecision("existing-gui", role, "global_feature_disabled", enabled, role_enabled, sandbox)
        if not role_enabled:
            return RouteDecision("existing-gui", role, "role_feature_disabled", enabled, role_enabled, sandbox)
        if sandbox not in self.payload["allowed_sandboxes"]:
            return RouteDecision("existing-gui", role, "sandbox_not_enabled", enabled, role_enabled, sandbox)
        role_sandboxes = self.payload.get("role_sandboxes")
        permitted = role_sandboxes.get(role) if isinstance(role_sandboxes, dict) else None
        if not isinstance(permitted, list) or sandbox not in permitted:
            return RouteDecision(
                "existing-gui", role, "role_sandbox_not_enabled", enabled, role_enabled, sandbox
            )
        reason = "workspace_write_role_enabled" if sandbox == "workspace-write" else "read_only_role_enabled"
        return RouteDecision("app-server", role, reason, enabled, role_enabled, sandbox)


@contextmanager
def context_target(
    config: AppServerFeatureConfig,
    cwd: Path,
    explicit_files: tuple[Path, ...],
    *,
    persistent_thread: bool = False,
) -> Iterator[ContextTarget]:
    source_cwd = cwd.resolve()
    if config.context_mode != "focused_snapshot":
        yield ContextTarget(source_cwd, explicit_files, source_cwd, config.context_mode, False)
        return
    with tempfile.TemporaryDirectory(prefix="tool-shed-codex-context-") as temporary_name:
        temporary = Path(temporary_name)
        total = 0
        copied: list[Path] = []
        for supplied in explicit_files:
            candidate = supplied if supplied.is_absolute() else source_cwd / supplied
            if candidate.is_symlink():
                raise FeatureConfigError(f"focused context refuses symlinked file: {candidate}")
            source = candidate.resolve()
            try:
                relative = source.relative_to(source_cwd)
            except ValueError as error:
                raise FeatureConfigError(
                    f"focused context file escapes source workspace: {source}"
                ) from error
            if not source.is_file():
                raise FeatureConfigError(f"focused context requires a regular file: {source}")
            total += source.stat().st_size
            if total > config.max_snapshot_bytes:
                raise FeatureConfigError(
                    f"focused context exceeds {config.max_snapshot_bytes} bytes"
                )
            if config.context_delivery == "reference":
                destination = temporary / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, destination)
                destination.chmod(0o400)
            copied.append(relative)
        instructions = temporary / "AGENTS.md"
        instructions.write_text(
            "# Focused Tool Shed read-only worker\n\n"
            "Use only the context supplied in the request. Do not modify files, run network "
            "operations, or infer authority beyond the request. Return only the requested analysis.\n",
            encoding="utf-8",
            newline="\n",
        )
        instructions.chmod(0o400)
        yield ContextTarget(
            temporary,
            tuple(copied),
            source_cwd,
            "focused_snapshot",
            not persistent_thread,
        )


@contextmanager
def camp_context_target(
    cwd: Path,
    explicit_files: tuple[Path, ...],
    *,
    max_snapshot_bytes: int,
) -> Iterator[ContextTarget]:
    """Create a minimal CAMP worker cwd while the real repository remains writable."""

    source_cwd = cwd.resolve()
    total = 0
    normalized: list[Path] = []
    for supplied in explicit_files:
        candidate = supplied if supplied.is_absolute() else source_cwd / supplied
        if candidate.is_symlink():
            raise FeatureConfigError(f"focused CAMP context refuses symlinked file: {candidate}")
        source = candidate.resolve()
        try:
            relative = source.relative_to(source_cwd)
        except ValueError as error:
            raise FeatureConfigError(
                f"focused CAMP context file escapes source workspace: {source}"
            ) from error
        if not source.is_file():
            raise FeatureConfigError(f"focused CAMP context requires a regular file: {source}")
        total += source.stat().st_size
        if total > max_snapshot_bytes:
            raise FeatureConfigError(
                f"focused CAMP context exceeds {max_snapshot_bytes} bytes"
            )
        normalized.append(relative)
    with tempfile.TemporaryDirectory(prefix="tool-shed-camp-context-") as temporary_name:
        temporary = Path(temporary_name)
        instructions = temporary / "AGENTS.md"
        instructions.write_text(
            "# Focused bounded workspace worker\n\n"
            "The request is the complete execution capsule. Do not inspect parent or project "
            "instruction files, rediscover Tool Shed state, or broaden scope. Modify only the "
            "authorized absolute repository paths. Do not change lifecycle files, use the "
            "network, or run verification commands reserved for Tool Shed. Return only the "
            "required structured outcome. The enclosing orchestrator owns state transitions.\n",
            encoding="utf-8",
            newline="\n",
        )
        instructions.chmod(0o400)
        yield ContextTarget(
            temporary,
            tuple(normalized),
            source_cwd,
            "focused_camp_capsule",
            True,
        )


def validate_summary_context(
    cwd: Path,
    summary_files: tuple[Path, ...],
    summary_source_files: tuple[Path, ...],
) -> None:
    if not summary_files and not summary_source_files:
        return
    if not summary_files or not summary_source_files:
        raise FeatureConfigError(
            "focused summaries require both --summary-file and --summary-source-file"
        )
    root = cwd.resolve()
    source_labels: list[str] = []
    for supplied in summary_source_files:
        candidate = supplied if supplied.is_absolute() else root / supplied
        source = candidate.resolve()
        try:
            label = str(source.relative_to(root))
        except ValueError as error:
            raise FeatureConfigError(f"summary source escapes workspace: {source}") from error
        if not source.is_file():
            raise FeatureConfigError(f"summary source is not a regular file: {source}")
        source_labels.append(label)
    declared_sources: set[str] = set()
    for supplied in summary_files:
        candidate = supplied if supplied.is_absolute() else root / supplied
        summary = candidate.resolve()
        try:
            summary.relative_to(root)
        except ValueError as error:
            raise FeatureConfigError(f"summary file escapes workspace: {summary}") from error
        try:
            content = summary.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as error:
            raise FeatureConfigError(f"cannot read UTF-8 summary file {summary}: {error}") from error
        in_sources = False
        for line in content.splitlines():
            if line.strip() == "## Source files":
                in_sources = True
                continue
            if in_sources and line.startswith("## "):
                in_sources = False
            if in_sources and line.startswith("- "):
                declared_sources.add(line[2:].strip().strip("`"))
    missing = [label for label in source_labels if label not in declared_sources]
    if missing:
        raise FeatureConfigError(
            "focused summary must identify every source file: " + ", ".join(missing)
        )


def inline_context_prompt(
    config: AppServerFeatureConfig,
    cwd: Path,
    explicit_files: tuple[Path, ...],
    prompt: str,
    *,
    read_only: bool = True,
) -> str:
    if config.context_delivery != "inline_relevant_files":
        return prompt
    source_cwd = cwd.resolve()
    blocks: list[str] = []
    total = 0
    for supplied in explicit_files:
        candidate = supplied if supplied.is_absolute() else source_cwd / supplied
        if candidate.is_symlink():
            raise FeatureConfigError(f"inline context refuses symlinked file: {candidate}")
        source = candidate.resolve()
        try:
            relative = source.relative_to(source_cwd)
        except ValueError as error:
            raise FeatureConfigError(f"inline context file escapes source workspace: {source}") from error
        try:
            raw = source.read_bytes()
        except OSError as error:
            raise FeatureConfigError(f"cannot read inline context file {source}: {error}") from error
        total += len(raw)
        if total > config.max_inline_bytes:
            raise FeatureConfigError(
                f"inline context exceeds {config.max_inline_bytes} bytes; supply a smaller summary"
            )
        try:
            content = raw.decode("utf-8")
        except UnicodeDecodeError as error:
            raise FeatureConfigError(f"inline context must be UTF-8 text: {source}") from error
        blocks.append(f"--- BEGIN {relative} ---\n{content}\n--- END {relative} ---")
    if not blocks:
        return prompt
    context_label = "complete, read-only context" if read_only else "complete focused context"
    return (
        f"Use the following {context_label}. Do not reread unchanged supplied context with tools.\n\n"
        + "\n\n".join(blocks)
        + "\n\nREQUEST\n"
        + prompt
    )


def execute_if_enabled(
    prompt: str,
    *,
    role: str,
    cwd: Path,
    request_text: str = "",
    sandbox: str = "read-only",
    enable_override: bool | None = None,
    thread_id: str | None = None,
    program: str | None = None,
    camp: str | None = None,
    campaign: str | None = None,
    qualification_id: str | None = None,
    explicit_files: tuple[Path, ...] = (),
    summary_files: tuple[Path, ...] = (),
    summary_source_files: tuple[Path, ...] = (),
    additional_context_requested: bool | None = None,
    retain_thread: bool = False,
    config: AppServerFeatureConfig | None = None,
    policy: ModelPolicy | None = None,
    codex: str = "codex",
    timeout: float = 300.0,
    telemetry_path: Path | None = None,
) -> tuple[RouteDecision, ExecutionResult | None]:
    if sandbox == "workspace-write":
        raise FeatureConfigError(
            "generic run does not execute workspace writes; use camp-run with explicit expected paths"
        )
    features = config or AppServerFeatureConfig.load()
    decision = features.route(
        role,
        request_text=request_text,
        sandbox=sandbox,
        enable_override=enable_override,
    )
    if not decision.use_app_server:
        return decision, None
    warning = features.compatibility_warning(codex)
    if warning:
        decision = replace(decision, compatibility_warning=warning)
        print(f"WARNING: {warning}", file=os.sys.stderr)
    selected_policy = policy or ModelPolicy.load()
    features.validate_model_policy(selected_policy)
    validate_summary_context(cwd, summary_files, summary_source_files)
    all_inline_files = tuple(dict.fromkeys((*explicit_files, *summary_files)))
    effective_prompt = inline_context_prompt(features, cwd, all_inline_files, prompt)
    configured_thread_policy = features.thread_policy(role)
    if thread_id is not None and configured_thread_policy == "new" and not retain_thread:
        raise FeatureConfigError(
            f"{role} defaults to new threads; pass --retain-thread with --thread-id for a controlled resume"
        )
    persistent_thread = retain_thread or configured_thread_policy == "resume"
    with context_target(
        features,
        cwd,
        all_inline_files,
        persistent_thread=persistent_thread,
    ) as target:
        if target.ephemeral and thread_id is not None:
            raise FeatureConfigError("focused_snapshot threads are short-lived and cannot resume")
        with CodexExecutionAdapter(
            policy=selected_policy,
            codex=codex,
            timeout=timeout,
            telemetry_path=telemetry_path,
        ) as adapter:
            result = execute_bounded(
                adapter,
                effective_prompt,
                role=role,
                cwd=target.execution_cwd,
                thread_id=thread_id,
                sandbox=sandbox,
                program=program,
                camp=camp,
                campaign=campaign,
                qualification_id=qualification_id,
                explicit_files=target.explicit_files,
                context_mode=target.mode,
                context_delivery=features.context_delivery,
                warning_input_tokens=features.warning_threshold(role),
                restricted_read=features.restricted_read,
                ephemeral=target.ephemeral,
                source_cwd=target.source_cwd,
                summary_files=summary_files,
                summary_source_files=summary_source_files,
                additional_context_requested=additional_context_requested,
            )
    return decision, result


def execute_camp_if_enabled(
    prompt: str,
    *,
    cwd: Path,
    campaign: str,
    camp: str,
    expected_paths: tuple[Path, ...],
    explicit_files: tuple[Path, ...] = (),
    verification_commands: tuple[tuple[str, ...], ...] = (),
    attempt: int = 1,
    enable_override: bool | None = None,
    config: AppServerFeatureConfig | None = None,
    policy: ModelPolicy | None = None,
    codex: str = "codex",
    timeout: float = 300.0,
    telemetry_path: Path | None = None,
) -> dict[str, Any]:
    """Run one fail-closed Terra CAMP step; lifecycle transitions remain deterministic."""

    features = config or AppServerFeatureConfig.load()
    decision = features.route(
        "camp_execution",
        request_text="",
        sandbox="workspace-write",
        enable_override=enable_override,
    )
    if not decision.use_app_server:
        return {
            "route": asdict(decision),
            "fallback": "continue in the existing Tool Shed/Codex GUI path",
        }
    warning = features.compatibility_warning(codex)
    if warning:
        decision = replace(decision, compatibility_warning=warning)
        print(f"WARNING: {warning}", file=os.sys.stderr)
    selected_policy = policy or ModelPolicy.load()
    features.validate_model_policy(selected_policy)
    journal = GitMutationJournal.begin(
        campaign=campaign,
        camp=camp,
        workspace=cwd,
        expected_paths=expected_paths,
    )
    effective_prompt = inline_context_prompt(
        features,
        cwd,
        explicit_files,
        (
            "The enclosing orchestrator has completed repository orientation and the Git "
            "preflight. Do not "
            "repeat either operation or reread supplied files. Execute exactly one bounded "
            "implementation step. The repository root is "
            + str(journal.repository_root)
            + ". The authorized mutation scope is: "
            + ", ".join(journal.expected_paths)
            + ". The starting state identifier is "
            + journal.start_state_identifier
            + ". Deterministic verification reserved for the enclosing orchestrator: "
            + json.dumps([list(command) for command in verification_commands], separators=(",", ":"))
            + ". Do not alter lifecycle files or claim a state transition. The orchestrator will "
            "run the declared deterministic verification commands, verify the Git journal, "
            "and choose the next action. Do not run tests or other verification commands "
            "yourself. Prefer one focused file-change operation, then return the required "
            "structured outcome.\n\n"
            + prompt
        ),
        read_only=False,
    )
    with camp_context_target(
        cwd,
        explicit_files,
        max_snapshot_bytes=features.max_snapshot_bytes,
    ) as target, CodexExecutionAdapter(
        policy=selected_policy,
        codex=codex,
        timeout=timeout,
        telemetry_path=telemetry_path,
    ) as adapter:
        try:
            result = adapter.execute(
                effective_prompt,
                role="camp_execution",
                cwd=target.execution_cwd,
                approval_policy="never",
                sandbox="workspace-write",
                program=None,
                camp=camp,
                campaign=campaign,
                operation="camp_execute",
                explicit_files=target.explicit_files,
                context_mode=target.mode,
                context_delivery=features.context_delivery,
                warning_input_tokens=features.warning_threshold("camp_execution"),
                restricted_read=False,
                attempt=attempt,
                ephemeral=target.ephemeral,
                source_cwd=target.source_cwd,
                sandbox_root=cwd.resolve(),
                output_schema=CAMP_OUTCOME_SCHEMA,
            )
        except Exception:
            failed_journal = journal.finalize(
                thread_id=None,
                turn_id=None,
                turn_status="failed",
                cancelled_or_interrupted=True,
                recovery_action="needs_user_intervention",
            )
            adapter.record_control_event(
                operation="camp_mutation_journal",
                qualification_id=None,
                campaign=campaign,
                recovery_action="needs_user_intervention",
                status="failed",
                details=failed_journal,
            )
            raise
        try:
            outcome = parse_camp_outcome(result.text)
        except CampExecutionError as error:
            outcome = CampStructuredOutcome(
                "unknown",
                f"App Server returned an invalid structured outcome: {error}",
                (),
            )
        verification: list[dict[str, Any]] = []
        command_events: list[dict[str, Any]] = []
        if outcome.outcome in {"step_complete", "camp_complete"}:
            for sequence, command in enumerate(verification_commands, start=1):
                if not command or any(not str(argument) for argument in command):
                    raise FeatureConfigError("verification commands must contain non-empty arguments")
                try:
                    response = adapter.client.command_exec(
                        list(command),
                        cwd=cwd.resolve(),
                        sandbox_policy=sandbox_policy("workspace-write", cwd.resolve()),
                        timeout_ms=max(1_000, int(timeout * 1_000)),
                    )
                    evidence = compact_command_evidence(command, response)
                except AppServerError as error:
                    evidence = {
                        "schema_version": 1,
                        "command": list(command),
                        "exit_code": None,
                        "passed": False,
                        "stdout_bytes": 0,
                        "stderr_bytes": 0,
                        "stdout_sha256": None,
                        "stderr_sha256": None,
                        "test_count": None,
                        "output_retained": False,
                        "transport_error_kind": error.kind or "app_server_error",
                    }
                evidence["sequence"] = sequence
                verification.append(evidence)
                command_events.append(
                    {
                        "type": "commandExecution",
                        "status": "completed" if evidence["passed"] else "failed",
                        "command": list(command),
                        "cwd": str(cwd.resolve()),
                        "exit_code": evidence["exit_code"],
                        "result_bytes": evidence["stdout_bytes"] + evidence["stderr_bytes"],
                        "source": "tool_shed_deterministic_verification",
                    }
                )
                if not evidence["passed"]:
                    break
        verification_passed = (
            all(item["passed"] for item in verification)
            if verification_commands and verification
            else None
        )
        journal_record = journal.finalize(
            thread_id=result.thread_id,
            turn_id=result.turn_id,
            turn_status=result.status,
            mutation_events=(*result.mutation_events, *command_events),
            recovery_action="none",
        )
        next_action = camp_next_action(
            outcome,
            attempt=attempt,
            journal=journal_record,
            verification_passed=verification_passed,
        )
        adapter.record_control_event(
            operation="camp_mutation_journal",
            qualification_id=None,
            campaign=campaign,
            recovery_action=next_action,
            status=("completed" if journal_record["safe"] else "needs_user_intervention"),
            thread_id=result.thread_id,
            turn_id=result.turn_id,
            details={
                "camp": camp,
                "outcome": structured_outcome_record(outcome),
                "verification": verification,
                "journal": journal_record,
            },
        )
    return {
        "route": asdict(decision),
        "result": asdict(result),
        "structured_outcome": structured_outcome_record(outcome),
        "verification": verification,
        "mutation_journal": journal_record,
        "next_action": next_action,
    }


def execute_bounded(
    adapter: CodexExecutionAdapter,
    prompt: str,
    *,
    role: str,
    cwd: Path,
    thread_id: str | None = None,
    sandbox: str = "read-only",
    program: str | None = None,
    camp: str | None = None,
    campaign: str | None = None,
    qualification_id: str | None = None,
    explicit_files: tuple[Path, ...] = (),
    context_mode: str = "workspace",
    context_delivery: str = "reference",
    warning_input_tokens: int | None = None,
    restricted_read: bool = False,
    ephemeral: bool = False,
    source_cwd: Path | None = None,
    summary_files: tuple[Path, ...] = (),
    summary_source_files: tuple[Path, ...] = (),
    additional_context_requested: bool | None = None,
) -> ExecutionResult:
    """Run at most two workhorse attempts, then one explicit Sol escalation."""

    selection = adapter.policy.select(role)
    escalation = adapter.policy.payload["escalation"]
    maximum = int(escalation["max_workhorse_attempts"])
    attempts = maximum if selection.model_class == "workhorse" else 1
    last_error: AppServerError | None = None
    for attempt in range(1, attempts + 1):
        try:
            return adapter.execute(
                prompt,
                role=role,
                cwd=cwd,
                thread_id=thread_id if attempt == 1 else None,
                sandbox=sandbox,
                program=program,
                camp=camp,
                campaign=campaign,
                qualification_id=qualification_id,
                operation="execute" if attempt == 1 else "bounded_retry",
                explicit_files=explicit_files,
                context_mode=context_mode,
                context_delivery=context_delivery,
                warning_input_tokens=warning_input_tokens,
                restricted_read=restricted_read,
                attempt=attempt,
                ephemeral=ephemeral,
                source_cwd=source_cwd,
                summary_files=summary_files,
                summary_source_files=summary_source_files,
                additional_context_requested=additional_context_requested,
            )
        except AppServerError as error:
            last_error = error
            action = classify_recovery(
                "failed",
                error.details if isinstance(error.details, dict) else None,
                transport_kind=error.kind,
            )
            if action != "safe_to_retry":
                raise
    assert last_error is not None
    if selection.model_class != "workhorse":
        raise last_error
    return adapter.escalate(
        prompt,
        source_role=role,
        workhorse_attempts=attempts,
        reason="recoverable_failure_exhausted",
        cwd=cwd,
        program=program,
        camp=camp,
        campaign=campaign,
        qualification_id=qualification_id,
        explicit_files=explicit_files,
        context_mode=context_mode,
        context_delivery=context_delivery,
        warning_input_tokens=warning_input_tokens,
        restricted_read=restricted_read,
        ephemeral=ephemeral,
        source_cwd=source_cwd,
        summary_files=summary_files,
        summary_source_files=summary_source_files,
        additional_context_requested=additional_context_requested,
    )


def load_benchmarks(path: Path) -> list[dict[str, Any]]:
    resolved = path.expanduser().resolve()
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise FeatureConfigError(f"cannot load benchmark tasks {resolved}: {error}") from error
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise FeatureConfigError("benchmark task schema_version must equal 1")
    tasks = payload.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        raise FeatureConfigError("benchmark tasks must be a non-empty list")
    required = {("planning", "small"), ("planning", "medium"), ("verification", "small"), ("verification", "medium")}
    observed: set[tuple[str, str]] = set()
    normalized: list[dict[str, Any]] = []
    for task in tasks:
        if not isinstance(task, dict):
            raise FeatureConfigError("each benchmark task must be an object")
        role, size = task.get("role"), task.get("size")
        if not all(isinstance(task.get(key), str) and task[key] for key in ("id", "prompt")):
            raise FeatureConfigError("each benchmark requires non-empty id and prompt")
        if not isinstance(role, str) or not isinstance(size, str):
            raise FeatureConfigError("each benchmark requires role and size")
        files = task.get("files") or []
        if not isinstance(files, list) or any(not isinstance(item, str) for item in files):
            raise FeatureConfigError("benchmark files must be strings")
        observed.add((role, size))
        normalized.append(dict(task))
    if not required.issubset(observed):
        raise FeatureConfigError("benchmarks must cover small/medium planning and verification")
    return normalized


def benchmark_record(task: dict[str, Any], result: ExecutionResult) -> dict[str, Any]:
    return {
        "id": task["id"],
        "role": task["role"],
        "size": task["size"],
        "model": result.actual_model,
        "reasoning": result.reasoning,
        "status": result.status,
        "thread_mode": "resumed" if result.thread_reused else "new",
        "tokens": flatten_token_usage(result.token_usage),
        "last_request_tokens": last_token_usage(result.token_usage),
        "context_scope": {
            "mode": result.context_scope.get("mode"),
            "restricted_read": result.context_scope.get("restricted_read"),
            "instruction_source_count": len(result.context_scope.get("instruction_sources") or []),
            "delivery": result.context_scope.get("delivery"),
            "explicit_files": result.context_scope.get("explicit_files") or [],
            "explicit_file_bytes": result.context_scope.get("explicit_file_bytes"),
            "prompt_characters": result.context_scope.get("prompt_characters"),
        },
        "context_warning": result.context_warning,
        "rerouted": result.rerouted,
    }


def benchmark_regressions(
    records: list[dict[str, Any]], baseline_path: Path, *, factor: float
) -> list[dict[str, Any]]:
    if factor <= 1:
        raise FeatureConfigError("benchmark regression factor must be greater than one")
    try:
        payload = json.loads(baseline_path.expanduser().resolve().read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    except (OSError, json.JSONDecodeError) as error:
        raise FeatureConfigError(f"cannot load benchmark baseline {baseline_path}: {error}") from error
    baseline_results = payload.get("results") if isinstance(payload, dict) else None
    if not isinstance(baseline_results, list):
        raise FeatureConfigError("benchmark baseline must contain results")
    by_id = {
        str(item.get("id")): item
        for item in baseline_results
        if isinstance(item, dict) and item.get("id")
    }
    findings: list[dict[str, Any]] = []
    for record in records:
        baseline = by_id.get(str(record.get("id")))
        if not isinstance(baseline, dict):
            continue
        current_tokens = record.get("tokens")
        baseline_tokens = baseline.get("tokens")
        current_input = current_tokens.get("input") if isinstance(current_tokens, dict) else None
        baseline_input = baseline_tokens.get("input") if isinstance(baseline_tokens, dict) else None
        if (
            isinstance(current_input, int)
            and isinstance(baseline_input, int)
            and current_input > baseline_input * factor
        ):
            findings.append(
                {
                    "id": record.get("id"),
                    "kind": "input_token_regression",
                    "baseline_input_tokens": baseline_input,
                    "current_input_tokens": current_input,
                    "absolute_change_tokens": current_input - baseline_input,
                    "relative_change_percent": round(
                        ((current_input - baseline_input) / baseline_input) * 100, 2
                    ),
                    "warning_factor": factor,
                }
            )
    return findings


def benchmark_comparison(
    records: list[dict[str, Any]], baseline_path: Path
) -> dict[str, Any]:
    """Report absolute and relative input changes without turning warnings into runtime failures."""

    try:
        payload = json.loads(baseline_path.expanduser().resolve().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise FeatureConfigError(f"cannot load benchmark baseline {baseline_path}: {error}") from error
    baseline_results = payload.get("results") if isinstance(payload, dict) else None
    if not isinstance(baseline_results, list):
        raise FeatureConfigError("benchmark baseline must contain results")
    baseline_by_id = {
        str(item.get("id")): item
        for item in baseline_results
        if isinstance(item, dict) and item.get("id")
    }
    operations: list[dict[str, Any]] = []
    current_total = 0
    baseline_total = 0
    for record in records:
        baseline = baseline_by_id.get(str(record.get("id")))
        current_tokens = record.get("tokens")
        baseline_tokens = baseline.get("tokens") if isinstance(baseline, dict) else None
        current = current_tokens.get("input") if isinstance(current_tokens, dict) else None
        prior = baseline_tokens.get("input") if isinstance(baseline_tokens, dict) else None
        if not isinstance(current, int) or not isinstance(prior, int) or prior <= 0:
            continue
        change = current - prior
        current_total += current
        baseline_total += prior
        operations.append(
            {
                "id": record.get("id"),
                "baseline_input_tokens": prior,
                "current_input_tokens": current,
                "absolute_change_tokens": change,
                "relative_change_percent": round((change / prior) * 100, 2),
            }
        )
    aggregate_change = current_total - baseline_total
    return {
        "operations": operations,
        "aggregate": {
            "baseline_input_tokens": baseline_total,
            "current_input_tokens": current_total,
            "absolute_change_tokens": aggregate_change,
            "relative_change_percent": (
                round((aggregate_change / baseline_total) * 100, 2)
                if baseline_total
                else None
            ),
        },
    }


def parse_command_json(value: str) -> tuple[str, ...]:
    try:
        payload = json.loads(value)
    except json.JSONDecodeError as error:
        raise argparse.ArgumentTypeError(f"verification command is not valid JSON: {error}") from error
    if not isinstance(payload, list) or not payload or any(
        not isinstance(item, str) or not item for item in payload
    ):
        raise argparse.ArgumentTypeError(
            "verification command must be a non-empty JSON array of non-empty strings"
        )
    return tuple(payload)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--policy", type=Path, default=ROOT / "adapters" / "codex-model-policy.json")
    parser.add_argument("--codex", default="codex")
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument("--telemetry", type=Path, default=default_telemetry_path())
    parser.add_argument(
        "--enable-app-server",
        action="store_true",
        help="Enable App Server for this invocation without changing the default-off config.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    route = subparsers.add_parser("route", help="Show the selected execution backend.")
    route.add_argument("--role", required=True)
    route.add_argument("--request", default="")
    route.add_argument("--sandbox", default="read-only")

    run = subparsers.add_parser("run", help="Run only when the feature policy selects App Server.")
    run.add_argument("--role", required=True)
    run.add_argument("--prompt", required=True)
    run.add_argument("--request", default="")
    run.add_argument("--cwd", type=Path, default=Path.cwd())
    run.add_argument("--thread-id")
    run.add_argument("--program")
    run.add_argument("--camp")
    run.add_argument("--campaign")
    run.add_argument("--qualification-id")
    run.add_argument("--file", type=Path, action="append", default=[])
    run.add_argument("--summary-file", type=Path, action="append", default=[])
    run.add_argument("--summary-source-file", type=Path, action="append", default=[])
    run.add_argument(
        "--additional-context-requested",
        action="store_true",
        help="Record that the operation needed context after receiving its focused summary.",
    )
    run.add_argument(
        "--retain-thread",
        action="store_true",
        help="Persist a focused inline-context thread for a controlled later resume.",
    )
    run.add_argument("--sandbox", default="read-only")

    camp_run = subparsers.add_parser(
        "camp-run", help="Run one scoped, journaled App Server CAMP step."
    )
    camp_run.add_argument("--prompt", required=True)
    camp_run.add_argument("--cwd", type=Path, default=Path.cwd())
    camp_run.add_argument("--campaign", required=True)
    camp_run.add_argument("--camp", required=True)
    camp_run.add_argument("--expected-path", type=Path, action="append", required=True)
    camp_run.add_argument("--file", type=Path, action="append", default=[])
    camp_run.add_argument(
        "--verify-command-json",
        type=parse_command_json,
        action="append",
        default=[],
        help="Shell-free deterministic verification argv as a JSON string array; repeatable.",
    )
    camp_run.add_argument("--attempt", type=int, choices=(1, 2), default=1)

    benchmark = subparsers.add_parser("benchmark", help="Run the four repeatable token baselines.")
    benchmark.add_argument("--tasks", type=Path, default=DEFAULT_BENCHMARKS)
    benchmark.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    benchmark.add_argument("--cwd", type=Path, default=Path.cwd())
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        config = AppServerFeatureConfig.load(args.config)
        enabled = True if args.enable_app_server else None
        if args.command == "route":
            decision = config.route(
                args.role,
                request_text=args.request,
                sandbox=args.sandbox,
                enable_override=enabled,
            )
            if decision.use_app_server:
                warning = config.compatibility_warning(args.codex)
                if warning:
                    decision = replace(decision, compatibility_warning=warning)
            print(
                json.dumps(
                    asdict(decision),
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
        policy = ModelPolicy.load(args.policy)
        config.validate_model_policy(policy)
        if args.command == "run":
            decision, result = execute_if_enabled(
                args.prompt,
                role=args.role,
                cwd=args.cwd,
                request_text=args.request,
                sandbox=args.sandbox,
                enable_override=enabled,
                thread_id=args.thread_id,
                program=args.program,
                camp=args.camp,
                campaign=args.campaign,
                qualification_id=args.qualification_id,
                explicit_files=tuple(args.file),
                summary_files=tuple(args.summary_file),
                summary_source_files=tuple(args.summary_source_file),
                additional_context_requested=(
                    True
                    if args.additional_context_requested
                    else (False if args.summary_file else None)
                ),
                retain_thread=args.retain_thread,
                config=config,
                policy=policy,
                codex=args.codex,
                timeout=args.timeout,
                telemetry_path=args.telemetry,
            )
            payload: dict[str, Any] = {"route": asdict(decision)}
            if result is not None:
                payload["result"] = asdict(result)
            else:
                payload["fallback"] = "continue in the existing Tool Shed/Codex GUI path"
            print(json.dumps(payload, indent=2, sort_keys=True))
            return 0

        if args.command == "camp-run":
            payload = execute_camp_if_enabled(
                args.prompt,
                cwd=args.cwd,
                campaign=args.campaign,
                camp=args.camp,
                expected_paths=tuple(args.expected_path),
                explicit_files=tuple(args.file),
                verification_commands=tuple(args.verify_command_json),
                attempt=args.attempt,
                enable_override=enabled,
                config=config,
                policy=policy,
                codex=args.codex,
                timeout=args.timeout,
                telemetry_path=args.telemetry,
            )
            print(json.dumps(payload, indent=2, sort_keys=True))
            journal = payload.get("mutation_journal")
            successful_actions = {
                "advance_to_next_camp_step",
                "verify_before_campaign_transition",
            }
            return (
                0
                if isinstance(journal, dict)
                and journal.get("safe")
                and payload.get("next_action") in successful_actions
                else 2
            )

        tasks = load_benchmarks(args.tasks)
        decisions = [
            config.route(
                str(task["role"]),
                request_text="",
                sandbox="read-only",
                enable_override=enabled,
            )
            for task in tasks
        ]
        if not all(item.use_app_server for item in decisions):
            print(
                json.dumps(
                    {
                        "error": "benchmark requires App Server routing; pass --enable-app-server",
                        "routes": [asdict(item) for item in decisions],
                    },
                    indent=2,
                ),
                file=os.sys.stderr,
            )
            return 2
        warning = config.compatibility_warning(args.codex)
        if warning:
            print(f"WARNING: {warning}", file=os.sys.stderr)
        records: list[dict[str, Any]] = []
        with CodexExecutionAdapter(
            policy=policy,
            codex=args.codex,
            timeout=args.timeout,
            telemetry_path=args.telemetry,
        ) as adapter:
            for task in tasks:
                files = tuple(Path(item) for item in task.get("files") or [])
                effective_prompt = inline_context_prompt(
                    config, args.cwd, files, str(task["prompt"])
                )
                with context_target(config, args.cwd, files) as target:
                    result = adapter.execute(
                        effective_prompt,
                        role=str(task["role"]),
                        cwd=target.execution_cwd,
                        operation="benchmark",
                        explicit_files=target.explicit_files,
                        context_mode=target.mode,
                        context_delivery=config.context_delivery,
                        warning_input_tokens=config.warning_threshold(str(task["role"])),
                        restricted_read=config.restricted_read,
                        ephemeral=target.ephemeral,
                        source_cwd=target.source_cwd,
                    )
                records.append(benchmark_record(task, result))
        context = config.payload.get("context")
        factor = (
            float(context.get("regression_factor", 1.5))
            if isinstance(context, dict)
            else 1.5
        )
        regressions = benchmark_regressions(records, args.baseline, factor=factor)
        comparison = benchmark_comparison(records, args.baseline)
        print(
            json.dumps(
                {
                    "schema_version": 1,
                    "config": str(config.source),
                    "tasks": str(args.tasks.expanduser().resolve()),
                    "baseline": str(args.baseline.expanduser().resolve()),
                    "results": records,
                    "comparison": comparison,
                    "regressions": regressions,
                    "compatibility_warning": warning,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    except (AppServerError, AuthenticationError, FeatureConfigError, ModelPolicyError) as error:
        print(json.dumps({"error": str(error)}, indent=2), file=os.sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
