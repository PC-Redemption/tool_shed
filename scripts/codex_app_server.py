#!/usr/bin/env python3
"""Small synchronous client for the Codex app-server v2 stdio protocol."""

from __future__ import annotations

import json
import queue
import subprocess
import threading
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


class AppServerError(RuntimeError):
    """Raised when app-server cannot satisfy a protocol request."""

    def __init__(self, message: str, *, details: Any = None, kind: str | None = None) -> None:
        super().__init__(message)
        self.details = details
        self.kind = kind


class AuthenticationError(AppServerError):
    """Raised when Codex is not using managed ChatGPT authentication."""


ApprovalHandler = Callable[[str, dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class TurnResult:
    thread_id: str
    turn_id: str
    status: str
    text: str
    error: dict[str, Any] | None
    token_usage: dict[str, Any] | None
    reroutes: tuple[dict[str, Any], ...]
    model_turns: int | None
    model_turns_metric: str
    model_turn_events: tuple[dict[str, Any], ...]
    tool_calls: int
    tool_call_types: tuple[str, ...]
    mutation_events: tuple[dict[str, Any], ...]


class CodexAppServerClient:
    """Own one local app-server subprocess and its JSONL message stream."""

    def __init__(
        self,
        codex: str = "codex",
        *,
        timeout: float = 30.0,
        client_name: str = "tool_shed",
        client_title: str = "Tool Shed",
        client_version: str = "0.1.0",
        approval_handler: ApprovalHandler | None = None,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be greater than zero")
        self.codex = codex
        self.timeout = timeout
        self.client_info = {
            "name": client_name,
            "title": client_title,
            "version": client_version,
        }
        self.approval_handler = approval_handler
        self.process: subprocess.Popen[str] | None = None
        self.user_agent = "unknown"
        self._messages: queue.Queue[dict[str, Any] | None] = queue.Queue()
        self._notifications: deque[dict[str, Any]] = deque()
        self._responses: dict[int, dict[str, Any]] = {}
        self._stderr: deque[str] = deque(maxlen=25)
        self._next_request_id = 0

    def __enter__(self) -> CodexAppServerClient:
        self.start()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def start(self) -> None:
        if self.process is not None:
            return
        # A client object may be restarted after an app-server failure. Never
        # retain the previous reader's EOF marker or unmatched messages.
        self._messages = queue.Queue()
        self._notifications.clear()
        self._responses.clear()
        self._stderr.clear()
        try:
            self.process = subprocess.Popen(
                [self.codex, "app-server", "--stdio"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                bufsize=1,
            )
        except OSError as error:
            raise AppServerError(
                f"cannot start Codex app-server: {error}", kind="server_start_failed"
            ) from error

        process = self.process
        messages = self._messages
        stderr_lines = self._stderr

        def read_stdout() -> None:
            assert process.stdout is not None
            for line in process.stdout:
                try:
                    message = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(message, dict):
                    messages.put(message)
            messages.put(None)

        def read_stderr() -> None:
            assert process.stderr is not None
            for line in process.stderr:
                stderr_lines.append(line.rstrip())

        threading.Thread(target=read_stdout, daemon=True).start()
        threading.Thread(target=read_stderr, daemon=True).start()
        initialized = self.request("initialize", {"clientInfo": self.client_info})
        self.user_agent = str(initialized.get("userAgent") or "unknown")
        self.notify("initialized", {})

    def close(self) -> None:
        process = self.process
        self.process = None
        if process is None:
            return
        if process.stdin is not None:
            try:
                process.stdin.close()
            except OSError:
                pass
        if process.poll() is None:
            process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)
        for stream in (process.stdout, process.stderr):
            if stream is not None:
                try:
                    stream.close()
                except OSError:
                    pass

    def restart(self) -> None:
        """Restart the transport without changing persisted Codex threads."""

        self.close()
        self.start()

    def _send(self, message: dict[str, Any]) -> None:
        process = self.process
        if process is None or process.stdin is None:
            raise AppServerError("Codex app-server stdin is unavailable")
        try:
            process.stdin.write(json.dumps(message, separators=(",", ":")) + "\n")
            process.stdin.flush()
        except (BrokenPipeError, OSError) as error:
            raise AppServerError(
                self._process_failure("Codex app-server pipe closed"),
                kind="transport_closed",
            ) from error

    def _process_failure(self, prefix: str) -> str:
        detail = "\n".join(self._stderr)
        return f"{prefix}: {detail}" if detail else prefix

    def notify(self, method: str, params: dict[str, Any]) -> None:
        self._send({"method": method, "params": params})

    def request(
        self, method: str, params: dict[str, Any] | None = None, *, timeout: float | None = None
    ) -> dict[str, Any]:
        request_id = self._next_request_id
        self._next_request_id += 1
        message: dict[str, Any] = {"method": method, "id": request_id}
        if params is not None:
            message["params"] = params
        self._send(message)
        deadline = time.monotonic() + (self.timeout if timeout is None else timeout)
        while request_id not in self._responses:
            self._pump(deadline)
        response = self._responses.pop(request_id)
        if "error" in response:
            error = response["error"]
            raise AppServerError(
                f"Codex app-server {method} failed: {error}",
                details=error,
                kind="rpc_error",
            )
        result = response.get("result")
        if not isinstance(result, dict):
            raise AppServerError(f"Codex app-server {method} returned no result object")
        return result

    def _pump(self, deadline: float) -> None:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise AppServerError("timed out waiting for Codex app-server", kind="timeout")
        try:
            message = self._messages.get(timeout=remaining)
        except queue.Empty as error:
            raise AppServerError(
                "timed out waiting for Codex app-server", kind="timeout"
            ) from error
        if message is None:
            raise AppServerError(
                self._process_failure("Codex app-server exited"),
                kind="server_terminated",
            )
        if "id" in message and "method" in message:
            self._handle_server_request(message)
        elif "id" in message:
            request_id = message.get("id")
            if isinstance(request_id, int):
                self._responses[request_id] = message
        elif "method" in message:
            self._notifications.append(message)

    def _handle_server_request(self, message: dict[str, Any]) -> None:
        method = str(message.get("method") or "")
        params = message.get("params")
        if not isinstance(params, dict):
            params = {}
        approval_methods = {
            "item/commandExecution/requestApproval",
            "item/fileChange/requestApproval",
            "applyPatchApproval",
            "execCommandApproval",
            "item/permissions/requestApproval",
        }
        if method not in approval_methods:
            self._send(
                {
                    "id": message["id"],
                    "error": {
                        "code": -32000,
                        "message": f"Tool Shed has no handler for server request {method}",
                    },
                }
            )
            return
        if self.approval_handler is not None:
            try:
                result = self.approval_handler(method, params)
            except Exception as error:  # The protocol must still receive a fail-closed answer.
                result = self._fail_closed_approval(method)
                self._stderr.append(f"approval handler failed closed: {error}")
        else:
            result = self._fail_closed_approval(method)
        self._send({"id": message["id"], "result": result})

    @staticmethod
    def _fail_closed_approval(method: str) -> dict[str, Any]:
        if method == "item/permissions/requestApproval":
            return {"permissions": []}
        return {"decision": "cancel"}

    def _next_notification(self, deadline: float) -> dict[str, Any]:
        while not self._notifications:
            self._pump(deadline)
        return self._notifications.popleft()

    def read_account(self, *, refresh_token: bool = False) -> dict[str, Any]:
        return self.request("account/read", {"refreshToken": refresh_token})

    def require_chatgpt_auth(self) -> dict[str, Any]:
        result = self.read_account(refresh_token=False)
        account = result.get("account")
        account_type = account.get("type") if isinstance(account, dict) else None
        if account_type != "chatgpt":
            label = account_type or "not logged in"
            raise AuthenticationError(
                "Tool Shed requires managed ChatGPT authentication; "
                f"app-server reported {label!r}. API-key fallback is disabled."
            )
        return dict(account)

    def list_models(self, *, include_hidden: bool = False) -> list[dict[str, Any]]:
        models: list[dict[str, Any]] = []
        cursor: str | None = None
        while True:
            params: dict[str, Any] = {"limit": 1000, "includeHidden": include_hidden}
            if cursor:
                params["cursor"] = cursor
            result = self.request("model/list", params)
            data = result.get("data")
            if not isinstance(data, list):
                raise AppServerError("Codex app-server model/list returned no data array")
            models.extend(item for item in data if isinstance(item, dict))
            next_cursor = result.get("nextCursor")
            if not isinstance(next_cursor, str) or not next_cursor:
                return models
            cursor = next_cursor

    def start_thread(
        self,
        *,
        model: str,
        cwd: Path,
        approval_policy: str,
        sandbox: str,
        ephemeral: bool = False,
    ) -> dict[str, Any]:
        result = self.request(
            "thread/start",
            {
                "model": model,
                "cwd": str(cwd.resolve()),
                "approvalPolicy": approval_policy,
                "sandbox": sandbox,
                "ephemeral": ephemeral,
                "serviceName": "tool_shed",
            },
        )
        thread = result.get("thread")
        if not isinstance(thread, dict) or not thread.get("id"):
            raise AppServerError("Codex app-server thread/start returned no thread id")
        enriched = dict(thread)
        sources = result.get("instructionSources")
        enriched["instructionSources"] = [
            str(source) for source in sources or [] if isinstance(source, str)
        ]
        return enriched

    def resume_thread(
        self,
        thread_id: str,
        *,
        model: str,
        cwd: Path,
        approval_policy: str,
        sandbox: str,
    ) -> dict[str, Any]:
        result = self.request(
            "thread/resume",
            {
                "threadId": thread_id,
                "model": model,
                "cwd": str(cwd.resolve()),
                "approvalPolicy": approval_policy,
                "sandbox": sandbox,
            },
        )
        thread = result.get("thread")
        if not isinstance(thread, dict) or not thread.get("id"):
            raise AppServerError("Codex app-server thread/resume returned no thread id")
        enriched = dict(thread)
        sources = result.get("instructionSources")
        enriched["instructionSources"] = [
            str(source) for source in sources or [] if isinstance(source, str)
        ]
        return enriched

    def fork_thread(
        self,
        thread_id: str,
        *,
        model: str,
        cwd: Path,
        approval_policy: str,
        sandbox: str,
        ephemeral: bool = False,
    ) -> dict[str, Any]:
        result = self.request(
            "thread/fork",
            {
                "threadId": thread_id,
                "model": model,
                "cwd": str(cwd.resolve()),
                "approvalPolicy": approval_policy,
                "sandbox": sandbox,
                "ephemeral": ephemeral,
            },
        )
        thread = result.get("thread")
        if not isinstance(thread, dict) or not thread.get("id"):
            raise AppServerError("Codex app-server thread/fork returned no thread id")
        enriched = dict(thread)
        sources = result.get("instructionSources")
        enriched["instructionSources"] = [
            str(source) for source in sources or [] if isinstance(source, str)
        ]
        return enriched

    def start_turn(
        self,
        thread_id: str,
        prompt: str,
        *,
        model: str,
        effort: str,
        cwd: Path,
        approval_policy: str,
        sandbox_policy: dict[str, Any],
        output_schema: dict[str, Any] | None = None,
    ) -> str:
        params: dict[str, Any] = {
            "threadId": thread_id,
            "input": [{"type": "text", "text": prompt}],
            "model": model,
            "effort": effort,
            "cwd": str(cwd.resolve()),
            "approvalPolicy": approval_policy,
            "sandboxPolicy": sandbox_policy,
        }
        if output_schema is not None:
            params["outputSchema"] = output_schema
        result = self.request(
            "turn/start",
            params,
        )
        turn = result.get("turn")
        if not isinstance(turn, dict) or not turn.get("id"):
            raise AppServerError("Codex app-server turn/start returned no turn id")
        return str(turn["id"])

    def wait_for_turn(self, thread_id: str, turn_id: str, *, timeout: float | None = None) -> TurnResult:
        started = time.monotonic()
        deadline = time.monotonic() + (self.timeout if timeout is None else timeout)
        deferred: list[dict[str, Any]] = []
        deltas: list[str] = []
        completed_text = ""
        token_usage: dict[str, Any] | None = None
        turn_usage_baseline: dict[str, int] | None = None
        reroutes: list[dict[str, Any]] = []
        model_usage_updates: set[tuple[int, ...]] = set()
        model_turn_events: list[dict[str, Any]] = []
        tool_call_types: list[str] = []
        mutation_events: list[dict[str, Any]] = []
        try:
            while True:
                message = self._next_notification(deadline)
                method = message.get("method")
                params = message.get("params")
                if not isinstance(params, dict):
                    params = {}
                same_thread = params.get("threadId") in {None, thread_id}
                same_turn = params.get("turnId") in {None, turn_id}
                if not (same_thread and same_turn):
                    deferred.append(message)
                    continue
                if method == "item/agentMessage/delta" and isinstance(params.get("delta"), str):
                    deltas.append(params["delta"])
                elif method == "item/completed":
                    item = params.get("item")
                    if isinstance(item, dict):
                        item_type = item.get("type")
                        if item_type == "agentMessage":
                            completed_text = str(item.get("text") or "")
                        elif item_type in {
                            "commandExecution",
                            "fileChange",
                            "mcpToolCall",
                            "dynamicToolCall",
                            "webSearch",
                            "imageView",
                            "imageGeneration",
                        }:
                            tool_call_types.append(str(item_type))
                            event: dict[str, Any] = {
                                "item_id": item.get("id"),
                                "type": str(item_type),
                                "status": item.get("status"),
                                "result_bytes": len(
                                    json.dumps(item, sort_keys=True, separators=(",", ":")).encode(
                                        "utf-8"
                                    )
                                ),
                            }
                            if item_type == "commandExecution":
                                event.update(
                                    {
                                        "command": item.get("command"),
                                        "cwd": item.get("cwd"),
                                        "exit_code": item.get("exitCode"),
                                    }
                                )
                            elif item_type == "fileChange":
                                event["changes"] = [
                                    {
                                        "path": change.get("path"),
                                        "kind": change.get("kind"),
                                    }
                                    for change in item.get("changes") or []
                                    if isinstance(change, dict)
                                ]
                            mutation_events.append(event)
                elif method == "thread/tokenUsage/updated":
                    usage = params.get("tokenUsage")
                    if isinstance(usage, dict):
                        token_usage = dict(usage)
                        last = usage.get("last")
                        if isinstance(last, dict):
                            fields = (
                                "inputTokens",
                                "cachedInputTokens",
                                "outputTokens",
                                "reasoningOutputTokens",
                                "totalTokens",
                            )
                            signature = tuple(int(last.get(key) or 0) for key in fields)
                            if signature not in model_usage_updates:
                                model_usage_updates.add(signature)
                                compact = {
                                    "input": signature[0],
                                    "cached_input": signature[1],
                                    "uncached_input": max(0, signature[0] - signature[1]),
                                    "output": signature[2],
                                    "reasoning_output": signature[3],
                                    "total": signature[4],
                                }
                                model_turn_events.append(
                                    {
                                        "sequence": len(model_turn_events) + 1,
                                        "elapsed_seconds": round(time.monotonic() - started, 3),
                                        "tokens": compact,
                                        "preceding_tool": (
                                            tool_call_types[-1] if tool_call_types else None
                                        ),
                                        "preceding_tool_result_bytes": (
                                            mutation_events[-1].get("result_bytes")
                                            if mutation_events
                                            else None
                                        ),
                                    }
                                )
                        if turn_usage_baseline is None:
                            cumulative = usage.get("total")
                            if isinstance(cumulative, dict) and isinstance(last, dict):
                                turn_usage_baseline = {
                                    key: max(
                                        0,
                                        int(cumulative.get(key) or 0)
                                        - int(last.get(key) or 0),
                                    )
                                    for key in (
                                        "inputTokens",
                                        "cachedInputTokens",
                                        "outputTokens",
                                        "reasoningOutputTokens",
                                        "totalTokens",
                                    )
                                }
                elif method == "model/rerouted":
                    reroutes.append(dict(params))
                elif method == "turn/completed":
                    turn = params.get("turn")
                    if not isinstance(turn, dict) or turn.get("id") != turn_id:
                        deferred.append(message)
                        continue
                    status = str(turn.get("status") or "failed")
                    error = turn.get("error") if isinstance(turn.get("error"), dict) else None
                    if token_usage is not None and turn_usage_baseline is not None:
                        cumulative = token_usage.get("total")
                        if isinstance(cumulative, dict):
                            token_usage["turn"] = {
                                key: max(
                                    0,
                                    int(cumulative.get(key) or 0)
                                    - turn_usage_baseline.get(key, 0),
                                )
                                for key in (
                                    "inputTokens",
                                    "cachedInputTokens",
                                    "outputTokens",
                                    "reasoningOutputTokens",
                                    "totalTokens",
                                )
                            }
                    return TurnResult(
                        thread_id=thread_id,
                        turn_id=turn_id,
                        status=status,
                        text=completed_text or "".join(deltas),
                        error=error,
                        token_usage=token_usage,
                        reroutes=tuple(reroutes),
                        model_turns=(len(model_usage_updates) or None),
                        model_turns_metric="distinct_token_usage_last_updates",
                        model_turn_events=tuple(model_turn_events),
                        tool_calls=len(tool_call_types),
                        tool_call_types=tuple(tool_call_types),
                        mutation_events=tuple(mutation_events),
                    )
        finally:
            self._notifications.extendleft(reversed(deferred))

    def wait_for_notification(
        self,
        predicate: Callable[[dict[str, Any]], bool],
        *,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Return the next matching notification without losing unrelated events."""

        deadline = time.monotonic() + (self.timeout if timeout is None else timeout)
        deferred: list[dict[str, Any]] = []
        try:
            while True:
                message = self._next_notification(deadline)
                if predicate(message):
                    return message
                deferred.append(message)
        finally:
            self._notifications.extendleft(reversed(deferred))

    def command_exec(
        self,
        command: list[str],
        *,
        cwd: Path,
        sandbox_policy: dict[str, Any],
        timeout_ms: int = 10_000,
    ) -> dict[str, Any]:
        if not command:
            raise ValueError("command must not be empty")
        if timeout_ms <= 0:
            raise ValueError("command timeout must be greater than zero")
        return self.request(
            "command/exec",
            {
                "command": list(command),
                "cwd": str(cwd.resolve()),
                "sandboxPolicy": dict(sandbox_policy),
                "timeoutMs": timeout_ms,
            },
            timeout=max(self.timeout, timeout_ms / 1000 + 2),
        )

    def interrupt(
        self, thread_id: str, turn_id: str, *, timeout: float | None = None
    ) -> None:
        self.request(
            "turn/interrupt",
            {"threadId": thread_id, "turnId": turn_id},
            timeout=timeout,
        )

    def pop_turn_terminal_notification(
        self, thread_id: str, turn_id: str
    ) -> dict[str, Any] | None:
        """Consume one queued terminal notification for a specific turn."""

        selected: dict[str, Any] | None = None
        retained: deque[dict[str, Any]] = deque()
        while self._notifications:
            message = self._notifications.popleft()
            params = message.get("params")
            turn = params.get("turn") if isinstance(params, dict) else None
            if (
                selected is None
                and message.get("method") == "turn/completed"
                and isinstance(params, dict)
                and params.get("threadId") in {None, thread_id}
                and isinstance(turn, dict)
                and turn.get("id") == turn_id
            ):
                selected = message
                continue
            retained.append(message)
        self._notifications.extend(retained)
        return selected

    def process_state(self) -> dict[str, Any]:
        process = self.process
        if process is None:
            return {"state": "not_started", "returncode": None}
        return {
            "state": "running" if process.poll() is None else "exited",
            "returncode": process.poll(),
        }

    def read_thread(
        self,
        thread_id: str,
        *,
        include_turns: bool = False,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        result = self.request(
            "thread/read",
            {"threadId": thread_id, "includeTurns": include_turns},
            timeout=timeout,
        )
        thread = result.get("thread")
        if not isinstance(thread, dict):
            raise AppServerError("Codex app-server thread/read returned no thread")
        return thread

    def thread_status(self, thread_id: str) -> dict[str, Any]:
        return self.read_thread(thread_id, include_turns=False)
