#!/usr/bin/env python3
"""Role-aware Tool Shed execution through Codex app-server."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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
    ) -> None:
        self.policy = policy or ModelPolicy.load()
        self.client = CodexAppServerClient(
            codex,
            timeout=timeout,
            client_name="tool_shed_execution",
            client_title="Tool Shed Execution Adapter",
            client_version="0.1.0",
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
    ) -> ExecutionResult:
        if self.account is None:
            self.start()
        started = utc_now()
        run_id = str(uuid.uuid4())
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
            )
        active_thread_id = str(thread["id"])
        turn_id: str | None = None
        try:
            turn_id = self.client.start_turn(
                active_thread_id,
                prompt,
                model=selection.model,
                effort=selection.reasoning,
                cwd=cwd,
                approval_policy=approval_policy,
                sandbox_policy=sandbox_policy(sandbox, cwd),
            )
            turn = self.client.wait_for_turn(active_thread_id, turn_id)
            actual_model = (
                str(turn.reroutes[-1].get("toModel")) if turn.reroutes else selection.model
            )
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
            )
            self._record(
                result,
                started=started,
                operation=operation,
                program=program,
                camp=camp,
                error=turn.error,
            )
            if turn.status != "completed":
                raise AppServerError(
                    f"Codex turn {turn.turn_id} ended with status {turn.status}",
                    details=turn.error,
                )
            return result
        except Exception as error:
            if turn_id is None or not isinstance(error, AppServerError) or not error.details:
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
        )

    def cancel(self, thread_id: str, turn_id: str) -> None:
        self.client.interrupt(thread_id, turn_id)

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
            "rerouted": result.rerouted,
            "token_usage": result.token_usage,
            "error": error,
        }
        self.telemetry.append(record)


def sandbox_policy(sandbox: str, cwd: Path) -> dict[str, Any]:
    if sandbox == "read-only":
        return {"type": "readOnly", "networkAccess": False}
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex", default="codex")
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument("--telemetry", type=Path, default=default_telemetry_path())
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("probe", help="Verify ChatGPT auth and configured model availability.")

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
