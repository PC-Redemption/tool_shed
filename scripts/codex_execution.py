#!/usr/bin/env python3
"""Role-aware Tool Shed execution through Codex app-server."""

from __future__ import annotations

import argparse
import json
import os
import queue
import tempfile
import threading
import uuid
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

try:
    from scripts.codex_app_server import (
        AppServerError,
        AuthenticationError,
        CodexAppServerClient,
        TurnResult,
    )
except ModuleNotFoundError:  # Direct execution: python scripts/codex_execution.py
    from codex_app_server import (  # type: ignore[no-redef]
        AppServerError,
        AuthenticationError,
        CodexAppServerClient,
        TurnResult,
    )


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY = ROOT / "adapters" / "codex-model-policy.json"


class ModelPolicyError(ValueError):
    pass


@dataclass(frozen=True)
class ModelSelection:
    role: str
    model_class: str
    model: str
    reasoning: str


@dataclass(frozen=True)
class ExecutionResult:
    run_id: str
    role: str
    model_class: str
    requested_model: str
    actual_model: str
    reasoning: str
    thread_id: str
    turn_id: str
    status: str
    text: str
    token_usage: dict[str, Any] | None
    rerouted: bool
    escalation: bool
    escalation_reason: str | None
    thread_reused: bool
    context_scope: dict[str, Any]
    recovery_action: str
    context_warning: dict[str, Any] | None
    attempt: int


@dataclass(frozen=True)
class ApprovalRequest:
    kind: str
    method: str
    thread_id: str
    turn_id: str
    item_id: str
    params: dict[str, Any]


ApprovalResolver = Callable[[ApprovalRequest], str | dict[str, Any]]


class ApprovalBridge:
    """Synchronous, bounded bridge for App Server approval requests.

    Workspace-write execution remains disabled unless the caller explicitly
    enables this bridge and supplies an operator-facing resolver.
    """

    METHODS = {
        "item/commandExecution/requestApproval": "command",
        "item/fileChange/requestApproval": "file_change",
        "item/permissions/requestApproval": "permissions",
        "execCommandApproval": "legacy_command",
        "applyPatchApproval": "legacy_file_change",
    }
    DECISIONS = {"accept", "acceptForSession", "decline", "cancel"}

    def __init__(
        self,
        resolver: ApprovalResolver | None = None,
        *,
        workspace_write_enabled: bool = False,
        timeout: float = 120.0,
    ) -> None:
        if timeout <= 0:
            raise ValueError("approval timeout must be greater than zero")
        self.resolver = resolver
        self.workspace_write_enabled = workspace_write_enabled
        self.timeout = timeout
        self.events: list[dict[str, Any]] = []

    def __call__(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        kind = self.METHODS.get(method)
        if kind == "permissions":
            self._record(method, params, "none", "permissions_disabled")
            return {"permissions": []}
        if kind in {"legacy_command", "legacy_file_change"}:
            self._record(method, params, "cancel", "legacy_fail_closed")
            return {"decision": "cancel"}
        thread_id = params.get("threadId")
        turn_id = params.get("turnId")
        item_id = params.get("itemId")
        if (
            kind is None
            or not isinstance(thread_id, str)
            or not thread_id
            or not isinstance(turn_id, str)
            or not turn_id
            or not isinstance(item_id, str)
            or not item_id
        ):
            self._record(method, params, "cancel", "malformed_or_unexpected")
            return {"decision": "cancel"}
        request = ApprovalRequest(kind, method, thread_id, turn_id, item_id, dict(params))
        if not self.workspace_write_enabled or self.resolver is None:
            self._record(method, params, "cancel", "workspace_write_disabled")
            return {"decision": "cancel"}

        answers: queue.Queue[Any] = queue.Queue(maxsize=1)

        def resolve() -> None:
            try:
                answers.put(self.resolver(request))
            except Exception as error:  # pragma: no cover - exact error text is unimportant
                answers.put(error)

        threading.Thread(target=resolve, daemon=True).start()
        try:
            answer = answers.get(timeout=self.timeout)
        except queue.Empty:
            self._record(method, params, "cancel", "timed_out")
            return {"decision": "cancel"}
        if isinstance(answer, Exception):
            self._record(method, params, "cancel", "resolver_failed")
            return {"decision": "cancel"}
        decision = answer.get("decision") if isinstance(answer, dict) else answer
        if decision not in self.DECISIONS:
            self._record(method, params, "cancel", "invalid_decision")
            return {"decision": "cancel"}
        available = params.get("availableDecisions")
        if isinstance(available, list) and available and decision not in available:
            self._record(method, params, "cancel", "decision_not_available")
            return {"decision": "cancel"}
        self._record(method, params, str(decision), "resolved")
        return {"decision": decision}

    def _record(
        self, method: str, params: dict[str, Any], decision: str, outcome: str
    ) -> None:
        self.events.append(
            {
                "time": isoformat(utc_now()),
                "method": method,
                "thread_id": params.get("threadId"),
                "turn_id": params.get("turnId"),
                "item_id": params.get("itemId"),
                "decision": decision,
                "outcome": outcome,
            }
        )

    def events_for(self, thread_id: str, turn_id: str | None) -> list[dict[str, Any]]:
        return [
            dict(event)
            for event in self.events
            if event.get("thread_id") == thread_id
            and (turn_id is None or event.get("turn_id") == turn_id)
        ]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def isoformat(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def default_telemetry_path() -> Path:
    configured = os.environ.get("CODEX_HOME")
    root = Path(configured).expanduser() if configured else Path.home() / ".codex"
    return root / "tool-shed" / "execution-telemetry.jsonl"


class ModelPolicy:
    def __init__(self, payload: dict[str, Any], *, source: Path) -> None:
        self.payload = payload
        self.source = source
        self._validate_structure()

    @classmethod
    def load(cls, path: Path = DEFAULT_POLICY) -> ModelPolicy:
        resolved = path.expanduser().resolve()
        try:
            payload = json.loads(resolved.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ModelPolicyError(f"cannot load Codex model policy {resolved}: {error}") from error
        if not isinstance(payload, dict):
            raise ModelPolicyError("Codex model policy must be a JSON object")
        return cls(payload, source=resolved)

    def _validate_structure(self) -> None:
        if self.payload.get("schema_version") != 1:
            raise ModelPolicyError("Codex model policy schema_version must equal 1")
        auth = self.payload.get("authentication")
        if not isinstance(auth, dict) or auth.get("required_account_type") != "chatgpt":
            raise ModelPolicyError("Codex model policy must require ChatGPT authentication")
        if auth.get("allow_api_key_fallback") is not False:
            raise ModelPolicyError("Codex model policy must disable API-key fallback")
        models = self.payload.get("models")
        routing = self.payload.get("routing")
        if not isinstance(models, dict) or not models:
            raise ModelPolicyError("Codex model policy must define model classes")
        if not isinstance(routing, dict) or not routing:
            raise ModelPolicyError("Codex model policy must define routing roles")
        for role, route in routing.items():
            if not isinstance(route, dict) or route.get("class") not in models:
                raise ModelPolicyError(f"role {role!r} references an unknown model class")
            if not isinstance(route.get("reasoning"), str) or not route["reasoning"]:
                raise ModelPolicyError(f"role {role!r} has no reasoning effort")
        escalation = self.payload.get("escalation")
        if not isinstance(escalation, dict) or escalation.get("max_workhorse_attempts") != 2:
            raise ModelPolicyError("initial escalation policy must cap workhorse attempts at two")

    def select(self, role: str) -> ModelSelection:
        routing = self.payload["routing"]
        route = routing.get(role)
        if not isinstance(route, dict):
            choices = ", ".join(sorted(routing))
            raise ModelPolicyError(f"unknown execution role {role!r}; choose from: {choices}")
        model_class = str(route["class"])
        model = self.payload["models"][model_class].get("model")
        if not isinstance(model, str) or not model:
            raise ModelPolicyError(f"model class {model_class!r} has no model id")
        return ModelSelection(role, model_class, model, str(route["reasoning"]))

    def validate_catalog(self, models: list[dict[str, Any]]) -> None:
        available: dict[str, set[str]] = {}
        for entry in models:
            model_id = entry.get("id") or entry.get("model")
            if not isinstance(model_id, str):
                continue
            efforts = {
                str(item.get("reasoningEffort"))
                for item in entry.get("supportedReasoningEfforts") or []
                if isinstance(item, dict) and item.get("reasoningEffort")
            }
            available[model_id] = efforts
        for role in self.payload["routing"]:
            selection = self.select(role)
            if selection.model not in available:
                raise ModelPolicyError(
                    f"policy model {selection.model!r} for role {role!r} is unavailable"
                )
            if selection.reasoning not in available[selection.model]:
                raise ModelPolicyError(
                    f"effort {selection.reasoning!r} is unavailable for {selection.model!r}"
                )

    @property
    def roles(self) -> tuple[str, ...]:
        return tuple(sorted(self.payload["routing"]))


class TelemetryRecorder:
    def __init__(self, path: Path) -> None:
        self.path = path.expanduser().resolve()

    def append(self, record: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"
        handle, temporary_name = tempfile.mkstemp(prefix=f".{self.path.name}.", dir=self.path.parent)
        temporary = Path(temporary_name)
        try:
            existing = self.path.read_bytes() if self.path.exists() else b""
            with os.fdopen(handle, "wb") as stream:
                stream.write(existing)
                stream.write(line.encode("utf-8"))
                stream.flush()
                os.fsync(stream.fileno())
            temporary.chmod(0o600)
            os.replace(temporary, self.path)
        finally:
            if temporary.exists():
                temporary.unlink()


class CodexExecutionAdapter:
    """Translate Tool Shed lifecycle roles into App Server execution details."""

    def __init__(
        self,
        *,
        policy: ModelPolicy | None = None,
        codex: str = "codex",
        timeout: float = 300.0,
        telemetry_path: Path | None = None,
        approval_bridge: ApprovalBridge | None = None,
    ) -> None:
        self.policy = policy or ModelPolicy.load()
        self.approval_bridge = approval_bridge or ApprovalBridge()
        self.client = CodexAppServerClient(
            codex,
            timeout=timeout,
            client_name="tool_shed_execution",
            client_title="Tool Shed Execution Adapter",
            client_version="0.1.0",
            approval_handler=self.approval_bridge,
        )
        self.telemetry = TelemetryRecorder(telemetry_path or default_telemetry_path())
        self.account: dict[str, Any] | None = None

    def __enter__(self) -> CodexExecutionAdapter:
        self.start()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def start(self) -> None:
        self.client.start()
        self.account = self.client.require_chatgpt_auth()
        self.policy.validate_catalog(self.client.list_models(include_hidden=False))

    def close(self) -> None:
        self.client.close()

    def start_work(
        self,
        role: str,
        *,
        cwd: Path,
        approval_policy: str = "never",
        sandbox: str = "read-only",
        ephemeral: bool = False,
    ) -> tuple[ModelSelection, dict[str, Any]]:
        selection = self.policy.select(role)
        thread = self.client.start_thread(
            model=selection.model,
            cwd=cwd,
            approval_policy=approval_policy,
            sandbox=sandbox,
            ephemeral=ephemeral,
        )
        return selection, thread

    def resume_work(
        self,
        thread_id: str,
        role: str,
        *,
        cwd: Path,
        approval_policy: str = "never",
        sandbox: str = "read-only",
    ) -> tuple[ModelSelection, dict[str, Any]]:
        selection = self.policy.select(role)
        thread = self.client.resume_thread(
            thread_id,
            model=selection.model,
            cwd=cwd,
            approval_policy=approval_policy,
            sandbox=sandbox,
        )
        return selection, thread

    def execute(
        self,
        prompt: str,
        *,
        role: str,
        cwd: Path,
        thread_id: str | None = None,
        approval_policy: str = "never",
        sandbox: str = "read-only",
        program: str | None = None,
        camp: str | None = None,
        operation: str = "execute",
        escalation: bool = False,
        escalation_reason: str | None = None,
        explicit_files: tuple[Path, ...] = (),
        context_mode: str = "workspace",
        context_delivery: str = "reference",
        warning_input_tokens: int | None = None,
        restricted_read: bool = False,
        attempt: int = 1,
        ephemeral: bool = False,
        source_cwd: Path | None = None,
    ) -> ExecutionResult:
        if self.account is None:
            self.start()
        started = utc_now()
        run_id = str(uuid.uuid4())
        thread_reused = thread_id is not None
        if thread_id:
            selection, thread = self.resume_work(
                thread_id,
                role,
                cwd=cwd,
                approval_policy=approval_policy,
                sandbox=sandbox,
            )
        else:
            selection, thread = self.start_work(
                role,
                cwd=cwd,
                approval_policy=approval_policy,
                sandbox=sandbox,
                ephemeral=ephemeral,
            )
        active_thread_id = str(thread["id"])
        context_scope = describe_context_scope(
            cwd,
            prompt=prompt,
            mode=context_mode,
            delivery=context_delivery,
            explicit_files=explicit_files,
            instruction_sources=tuple(thread.get("instructionSources") or ()),
            restricted_read=restricted_read,
            source_cwd=source_cwd,
        )
        turn_id: str | None = None
        recorded = False
        try:
            turn_id = self.client.start_turn(
                active_thread_id,
                prompt,
                model=selection.model,
                effort=selection.reasoning,
                cwd=cwd,
                approval_policy=approval_policy,
                sandbox_policy=sandbox_policy(
                    sandbox, cwd, restricted_read=restricted_read
                ),
            )
            turn = self.client.wait_for_turn(active_thread_id, turn_id)
            actual_model = (
                str(turn.reroutes[-1].get("toModel")) if turn.reroutes else selection.model
            )
            warning = token_context_warning(
                role, turn.token_usage, threshold=warning_input_tokens
            )
            recovery = classify_recovery(turn.status, turn.error)
            result = ExecutionResult(
                run_id=run_id,
                role=role,
                model_class=selection.model_class,
                requested_model=selection.model,
                actual_model=actual_model,
                reasoning=selection.reasoning,
                thread_id=active_thread_id,
                turn_id=turn.turn_id,
                status=turn.status,
                text=turn.text,
                token_usage=turn.token_usage,
                rerouted=bool(turn.reroutes),
                escalation=escalation,
                escalation_reason=escalation_reason,
                thread_reused=thread_reused,
                context_scope=context_scope,
                recovery_action=recovery,
                context_warning=warning,
                attempt=attempt,
            )
            self._record(
                result,
                started=started,
                operation=operation,
                program=program,
                camp=camp,
                error=turn.error,
            )
            recorded = True
            if turn.status != "completed":
                raise AppServerError(
                    f"Codex turn {turn.turn_id} ended with status {turn.status}",
                    details=turn.error,
                    kind=f"turn_{turn.status}",
                )
            return result
        except Exception as error:
            if not recorded:
                self.telemetry.append(
                    {
                        "schema_version": 1,
                        "run_id": run_id,
                        "operation": operation,
                        "program": program,
                        "camp": camp,
                        "role": role,
                        "model_class": selection.model_class,
                        "requested_model": selection.model,
                        "reasoning": selection.reasoning,
                        "thread_id": active_thread_id,
                        "turn_id": turn_id,
                        "started_at": isoformat(started),
                        "ended_at": isoformat(utc_now()),
                        "status": "failed",
                        "escalation": escalation,
                        "escalation_reason": escalation_reason,
                        "thread_reused": thread_reused,
                        "thread_mode": "resumed" if thread_reused else "new",
                        "context_scope": context_scope,
                        "attempt": attempt,
                        "recovery_action": classify_recovery(
                            "failed",
                            error.details if isinstance(error, AppServerError) else None,
                            transport_kind=(
                                error.kind if isinstance(error, AppServerError) else None
                            ),
                        ),
                        "approval_events": self.approval_bridge.events_for(
                            active_thread_id, turn_id
                        ),
                        "error": str(error),
                    }
                )
            raise

    def escalate(
        self,
        prompt: str,
        *,
        source_role: str,
        workhorse_attempts: int,
        reason: str,
        cwd: Path,
        program: str | None = None,
        camp: str | None = None,
        explicit_files: tuple[Path, ...] = (),
        context_mode: str = "workspace",
        context_delivery: str = "reference",
        warning_input_tokens: int | None = None,
        restricted_read: bool = False,
        ephemeral: bool = False,
        source_cwd: Path | None = None,
    ) -> ExecutionResult:
        source = self.policy.select(source_role)
        if source.model_class != "workhorse":
            raise ModelPolicyError("only workhorse execution can escalate to the frontier model")
        escalation = self.policy.payload["escalation"]
        maximum = int(escalation["max_workhorse_attempts"])
        immediate = set(escalation.get("immediate_reasons") or [])
        if reason not in immediate and workhorse_attempts < maximum:
            raise ModelPolicyError(
                f"escalation requires {maximum} bounded workhorse attempts or an immediate reason"
            )
        if workhorse_attempts < 1 or workhorse_attempts > maximum:
            raise ModelPolicyError(f"workhorse attempts must be between 1 and {maximum}")
        return self.execute(
            prompt,
            role="escalation",
            cwd=cwd,
            program=program,
            camp=camp,
            operation="escalate",
            escalation=True,
            escalation_reason=reason,
            explicit_files=explicit_files,
            context_mode=context_mode,
            context_delivery=context_delivery,
            warning_input_tokens=warning_input_tokens,
            restricted_read=restricted_read,
            attempt=workhorse_attempts + 1,
            ephemeral=ephemeral,
            source_cwd=source_cwd,
        )

    def cancel(self, thread_id: str, turn_id: str) -> dict[str, Any]:
        try:
            self.client.interrupt(thread_id, turn_id)
            return {"outcome": "interrupt_requested", "thread_id": thread_id, "turn_id": turn_id}
        except AppServerError as error:
            message = str(error.details or error).lower()
            if "no active turn to interrupt" not in message:
                raise
            thread = self.client.read_thread(thread_id, include_turns=True)
            turns = thread.get("turns")
            matching = next(
                (
                    item
                    for item in turns or []
                    if isinstance(item, dict) and item.get("id") == turn_id
                ),
                None,
            )
            terminal_status = matching.get("status") if isinstance(matching, dict) else None
            return {
                "outcome": (
                    "already_terminal"
                    if terminal_status in {"completed", "failed", "interrupted"}
                    else "no_active_turn"
                ),
                "thread_id": thread_id,
                "turn_id": turn_id,
                "turn_status": terminal_status,
                "thread_status": thread.get("status"),
            }

    def get_status(self, thread_id: str) -> dict[str, Any]:
        return self.client.thread_status(thread_id)

    def _record(
        self,
        result: ExecutionResult,
        *,
        started: datetime,
        operation: str,
        program: str | None,
        camp: str | None,
        error: dict[str, Any] | None,
    ) -> None:
        record = {
            "schema_version": 1,
            "run_id": result.run_id,
            "operation": operation,
            "program": program,
            "camp": camp,
            "role": result.role,
            "model_class": result.model_class,
            "requested_model": result.requested_model,
            "actual_model": result.actual_model,
            "reasoning": result.reasoning,
            "thread_id": result.thread_id,
            "turn_id": result.turn_id,
            "started_at": isoformat(started),
            "ended_at": isoformat(utc_now()),
            "status": result.status,
            "success": result.status == "completed",
            "escalation": result.escalation,
            "escalation_reason": result.escalation_reason,
            "rerouted": result.rerouted,
            "thread_reused": result.thread_reused,
            "thread_mode": "resumed" if result.thread_reused else "new",
            "context_scope": result.context_scope,
            "context_warning": result.context_warning,
            "attempt": result.attempt,
            "recovery_action": result.recovery_action,
            "token_usage": result.token_usage,
            "tokens": flatten_token_usage(result.token_usage),
            "last_request_tokens": last_token_usage(result.token_usage),
            "approval_events": self.approval_bridge.events_for(
                result.thread_id, result.turn_id
            ),
            "error": error,
        }
        self.telemetry.append(record)


def repository_root(cwd: Path) -> Path | None:
    resolved = cwd.resolve()
    for candidate in (resolved, *resolved.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def describe_context_scope(
    cwd: Path,
    *,
    prompt: str,
    mode: str,
    delivery: str,
    explicit_files: tuple[Path, ...],
    instruction_sources: tuple[str, ...],
    restricted_read: bool,
    source_cwd: Path | None,
) -> dict[str, Any]:
    resolved_cwd = cwd.resolve()
    root = repository_root(resolved_cwd)
    metadata_root = source_cwd.resolve() if source_cwd else resolved_cwd
    files: list[dict[str, Any]] = []
    for supplied in explicit_files:
        candidate = supplied if supplied.is_absolute() else metadata_root / supplied
        resolved = candidate.resolve()
        try:
            size = resolved.stat().st_size
        except OSError:
            size = None
        try:
            label = str(resolved.relative_to(metadata_root))
        except ValueError:
            label = str(resolved)
        files.append({"path": label, "bytes": size})
    return {
        "mode": mode,
        "delivery": delivery,
        "cwd": str(resolved_cwd),
        "repository_root": str(root) if root else None,
        "source_cwd": str(source_cwd.resolve()) if source_cwd else str(resolved_cwd),
        "restricted_read": restricted_read,
        "instruction_sources": list(instruction_sources),
        "explicit_files": files,
        "explicit_file_bytes": sum(
            int(item["bytes"]) for item in files if isinstance(item.get("bytes"), int)
        ),
        "prompt_characters": len(prompt),
    }


def flatten_token_usage(token_usage: dict[str, Any] | None) -> dict[str, int | None]:
    usage = token_usage.get("turn") if isinstance(token_usage, dict) else None
    if not isinstance(usage, dict):
        usage = token_usage.get("total") if isinstance(token_usage, dict) else None
    if not isinstance(usage, dict):
        usage = token_usage if isinstance(token_usage, dict) else {}

    def value(name: str) -> int | None:
        raw = usage.get(name)
        return int(raw) if isinstance(raw, (int, float)) else None

    return {
        "input": value("inputTokens"),
        "cached_input": value("cachedInputTokens"),
        "output": value("outputTokens"),
        "reasoning_output": value("reasoningOutputTokens"),
        "total": value("totalTokens"),
    }


def last_token_usage(token_usage: dict[str, Any] | None) -> dict[str, int | None]:
    last = token_usage.get("last") if isinstance(token_usage, dict) else None
    if not isinstance(last, dict):
        last = {}

    def value(name: str) -> int | None:
        raw = last.get(name)
        return int(raw) if isinstance(raw, (int, float)) else None

    return {
        "input": value("inputTokens"),
        "cached_input": value("cachedInputTokens"),
        "output": value("outputTokens"),
        "reasoning_output": value("reasoningOutputTokens"),
        "total": value("totalTokens"),
    }


def token_context_warning(
    role: str,
    token_usage: dict[str, Any] | None,
    *,
    threshold: int | None,
) -> dict[str, Any] | None:
    input_tokens = flatten_token_usage(token_usage)["input"]
    if threshold is None or input_tokens is None or input_tokens <= threshold:
        return None
    return {
        "kind": "input_tokens_above_threshold",
        "role": role,
        "input_tokens": input_tokens,
        "threshold": threshold,
    }


def _error_kind(error: dict[str, Any] | None) -> str | None:
    if not isinstance(error, dict):
        return None
    info = error.get("codexErrorInfo")
    if isinstance(info, dict):
        kind = info.get("type") or info.get("kind")
        if isinstance(kind, str):
            return kind
    kind = error.get("type") or error.get("kind")
    return str(kind) if isinstance(kind, str) else None


def classify_recovery(
    status: str,
    error: dict[str, Any] | None,
    *,
    transport_kind: str | None = None,
) -> str:
    """Map protocol outcomes to the four recovery actions Tool Shed exposes."""

    if status == "completed":
        return "none"
    if status == "interrupted":
        return "safe_to_resume"
    if transport_kind in {
        "timeout",
        "transport_closed",
        "server_terminated",
        "turn_interrupted",
    }:
        # The turn may have reached Codex. Reconcile the stored thread before
        # issuing any new turn; never blindly replay the prompt.
        return "safe_to_resume"
    kind = (_error_kind(error) or "").lower()
    message = str(error or "").lower()
    if (
        "thread" in message
        and any(word in message for word in ("not found", "no rollout found", "stale", "unknown"))
    ):
        return "requires_new_thread"
    if kind in {"contextwindowexceeded", "context_window_exceeded"}:
        return "requires_new_thread"
    if kind in {
        "badrequest",
        "unauthorized",
        "usagelimitexceeded",
        "usage_limit_exceeded",
    }:
        return "requires_user_intervention"
    return "safe_to_retry"


def sandbox_policy(
    sandbox: str, cwd: Path, *, restricted_read: bool = False
) -> dict[str, Any]:
    if sandbox == "read-only":
        policy: dict[str, Any] = {"type": "readOnly", "networkAccess": False}
        if restricted_read:
            policy["access"] = {
                "type": "restricted",
                "includePlatformDefaults": True,
                "readableRoots": [str(cwd.resolve())],
            }
        return policy
    if sandbox == "workspace-write":
        return {
            "type": "workspaceWrite",
            "writableRoots": [str(cwd.resolve())],
            "networkAccess": False,
        }
    if sandbox == "danger-full-access":
        return {"type": "dangerFullAccess"}
    raise ModelPolicyError(f"unsupported sandbox mode {sandbox!r}")


def sanitized_probe(adapter: CodexExecutionAdapter) -> dict[str, Any]:
    assert adapter.account is not None
    selected = {adapter.policy.select(role).model for role in adapter.policy.roles}
    models = []
    for entry in adapter.client.list_models(include_hidden=False):
        model_id = entry.get("id") or entry.get("model")
        if model_id not in selected:
            continue
        models.append(
            {
                "id": model_id,
                "default_reasoning_effort": entry.get("defaultReasoningEffort"),
                "supported_reasoning_efforts": [
                    item.get("reasoningEffort")
                    for item in entry.get("supportedReasoningEfforts") or []
                    if isinstance(item, dict)
                ],
            }
        )
    return {
        "app_server_user_agent": adapter.client.user_agent,
        "authentication": {
            "type": adapter.account.get("type"),
            "plan_type": adapter.account.get("planType"),
            "api_key_fallback": False,
        },
        "policy": str(adapter.policy.source),
        "models": models,
    }


def read_telemetry(path: Path, *, limit: int = 20) -> list[dict[str, Any]]:
    if limit < 1:
        raise ValueError("telemetry limit must be at least one")
    resolved = path.expanduser().resolve()
    try:
        lines = resolved.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return []
    records: list[dict[str, Any]] = []
    for line in lines:
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict):
            records.append(record)
    return records[-limit:]


def activity_report(path: Path, *, limit: int = 20) -> dict[str, Any]:
    records = read_telemetry(path, limit=limit)
    by_model: Counter[str] = Counter()
    by_role: Counter[str] = Counter()
    totals = Counter()
    operations: list[dict[str, Any]] = []
    for record in records:
        model = str(record.get("actual_model") or record.get("requested_model") or "unknown")
        role = str(record.get("role") or "unknown")
        by_model[model] += 1
        by_role[role] += 1
        tokens = record.get("tokens")
        if not isinstance(tokens, dict):
            tokens = flatten_token_usage(record.get("token_usage"))
        for source, target in (
            ("input", "input_tokens"),
            ("cached_input", "cached_input_tokens"),
            ("output", "output_tokens"),
            ("reasoning_output", "reasoning_tokens"),
            ("total", "total_tokens"),
        ):
            value = tokens.get(source)
            if isinstance(value, int):
                totals[target] += value
        operations.append(
            {
                "time": record.get("started_at"),
                "role": role,
                "program": record.get("program"),
                "camp": record.get("camp"),
                "model": model,
                "reasoning": record.get("reasoning"),
                "tokens": tokens,
                "success": bool(record.get("success")),
                "escalated": bool(record.get("escalation")),
                "escalation_reason": record.get("escalation_reason"),
                "thread_reused": bool(record.get("thread_reused")),
                "context_warning": record.get("context_warning"),
            }
        )
    return {
        "title": f"Last {limit} Tool Shed AI operations",
        "telemetry": str(path.expanduser().resolve()),
        "operation_count": len(operations),
        "operations": operations,
        "summary": {
            "by_model": dict(sorted(by_model.items())),
            "by_role": dict(sorted(by_role.items())),
            **dict(totals),
            "escalations": sum(bool(item["escalated"]) for item in operations),
            "reused_threads": sum(bool(item["thread_reused"]) for item in operations),
            "context_warnings": sum(item["context_warning"] is not None for item in operations),
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex", default="codex")
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument("--telemetry", type=Path, default=default_telemetry_path())
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("probe", help="Verify ChatGPT auth and configured model availability.")

    activity = subparsers.add_parser(
        "activity", help="Show recent prompt-free App Server telemetry."
    )
    activity.add_argument("--limit", type=int, default=20)

    run = subparsers.add_parser("run", help="Execute one role-routed Codex turn.")
    run.add_argument("--role", required=True)
    run.add_argument("--prompt", required=True)
    run.add_argument("--cwd", type=Path, default=Path.cwd())
    run.add_argument("--thread-id")
    run.add_argument("--program")
    run.add_argument("--camp")
    run.add_argument(
        "--sandbox",
        choices=("read-only", "workspace-write", "danger-full-access"),
        default="read-only",
    )

    poc = subparsers.add_parser("poc", help="Run one Sol and one Terra read-only proof turn.")
    poc.add_argument("--cwd", type=Path, default=Path.cwd())
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.command == "activity":
            print(json.dumps(activity_report(args.telemetry, limit=args.limit), indent=2, sort_keys=True))
            return 0
        policy = ModelPolicy.load(args.policy)
        with CodexExecutionAdapter(
            policy=policy,
            codex=args.codex,
            timeout=args.timeout,
            telemetry_path=args.telemetry,
        ) as adapter:
            if args.command == "probe":
                print(json.dumps(sanitized_probe(adapter), indent=2, sort_keys=True))
                return 0
            if args.command == "run":
                result = adapter.execute(
                    args.prompt,
                    role=args.role,
                    cwd=args.cwd,
                    thread_id=args.thread_id,
                    sandbox=args.sandbox,
                    program=args.program,
                    camp=args.camp,
                )
                print(json.dumps(asdict(result), indent=2, sort_keys=True))
                return 0

            sol = adapter.execute(
                "Reply with exactly TOOL_SHED_SOL_OK and nothing else.",
                role="planning",
                cwd=args.cwd,
                operation="proof_of_concept",
            )
            terra = adapter.execute(
                "Reply with exactly TOOL_SHED_TERRA_OK and nothing else.",
                role="verification",
                cwd=args.cwd,
                operation="proof_of_concept",
            )
            checks = {
                "sol": asdict(sol),
                "terra": asdict(terra),
                "chatgpt_plan_type": adapter.account.get("planType") if adapter.account else None,
            }
            checks["success"] = (
                sol.text.strip() == "TOOL_SHED_SOL_OK"
                and terra.text.strip() == "TOOL_SHED_TERRA_OK"
                and sol.actual_model == policy.select("planning").model
                and terra.actual_model == policy.select("verification").model
                and not sol.rerouted
                and not terra.rerouted
            )
            print(json.dumps(checks, indent=2, sort_keys=True))
            return 0 if checks["success"] else 1
    except (AppServerError, AuthenticationError, ModelPolicyError) as error:
        print(json.dumps({"error": str(error)}, indent=2), file=os.sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
