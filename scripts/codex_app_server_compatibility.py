#!/usr/bin/env python3
"""Status and compatibility smoke checks for Tool Shed's opt-in Codex App Server path."""

from __future__ import annotations

import argparse
import json
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any

try:
    from scripts.codex_app_server import AppServerError, AuthenticationError
    from scripts.codex_execution import (
        ApprovalBridge,
        CodexExecutionAdapter,
        ModelPolicy,
        ModelPolicyError,
        default_telemetry_path,
        detect_codex_version,
        flatten_token_usage,
        sandbox_policy,
        sanitized_probe,
    )
    from scripts.codex_orchestration import AppServerFeatureConfig, FeatureConfigError
except ModuleNotFoundError:  # Direct execution: python scripts/codex_app_server_compatibility.py
    from codex_app_server import AppServerError, AuthenticationError  # type: ignore[no-redef]
    from codex_execution import (  # type: ignore[no-redef]
        ApprovalBridge,
        CodexExecutionAdapter,
        ModelPolicy,
        ModelPolicyError,
        default_telemetry_path,
        detect_codex_version,
        flatten_token_usage,
        sandbox_policy,
        sanitized_probe,
    )
    from codex_orchestration import (  # type: ignore[no-redef]
        AppServerFeatureConfig,
        FeatureConfigError,
    )


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "adapters" / "codex-app-server-config.json"
DEFAULT_POLICY = ROOT / "adapters" / "codex-model-policy.json"
DEFAULT_QUALIFICATIONS = ROOT / "adapters" / "codex-app-server-qualifications.json"


class CompatibilityError(ValueError):
    pass


def load_qualifications(path: Path = DEFAULT_QUALIFICATIONS) -> list[dict[str, Any]]:
    resolved = path.expanduser().resolve()
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CompatibilityError(f"cannot load App Server qualifications {resolved}: {error}") from error
    records = payload.get("records") if isinstance(payload, dict) else None
    if not isinstance(payload, dict) or payload.get("schema_version") != 1 or not isinstance(records, list):
        raise CompatibilityError("App Server qualification registry must use schema_version 1")
    versions: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for record in records:
        if not isinstance(record, dict) or not isinstance(record.get("codex_version"), str):
            raise CompatibilityError("every App Server qualification requires codex_version")
        version = str(record["codex_version"])
        if version in versions:
            raise CompatibilityError(f"duplicate App Server qualification for Codex {version}")
        versions.add(version)
        if record.get("status") not in {"qualified", "qualified_with_blockers", "unqualified"}:
            raise CompatibilityError(f"invalid App Server qualification status for Codex {version}")
        normalized.append(dict(record))
    return normalized


def qualification_for_version(
    records: list[dict[str, Any]], version: str | None
) -> dict[str, Any] | None:
    return next((record for record in records if record.get("codex_version") == version), None)


def status_report(
    *,
    codex: str = "codex",
    config_path: Path = DEFAULT_CONFIG,
    policy_path: Path = DEFAULT_POLICY,
    qualifications_path: Path = DEFAULT_QUALIFICATIONS,
) -> dict[str, Any]:
    config = AppServerFeatureConfig.load(config_path)
    policy = ModelPolicy.load(policy_path)
    records = load_qualifications(qualifications_path)
    installed = detect_codex_version(codex)
    record = qualification_for_version(records, installed)
    planning = policy.select("planning")
    verification = policy.select("verification")
    camp_execution = policy.select("camp_execution")
    configured_qualified = config.qualified_codex_version
    blockers = list(record.get("known_blockers") or []) if record else [
        "installed Codex version has no qualification record"
    ]
    savings = record.get("qualified_savings") if record else None
    camp_record = (record.get("routing") or {}).get("camp_execution", {}) if record else {}
    camp_enabled = bool(
        config.role_enabled("camp_execution")
        and camp_record.get("qualified")
        and record.get("workspace_writing")
    ) if record else False
    enabled_roles: dict[str, Any] = {
        "planning": {"model": planning.model, "reasoning": planning.reasoning},
        "verification": {
            "model": verification.model,
            "reasoning": verification.reasoning,
        },
    }
    if camp_enabled:
        enabled_roles["camp_execution"] = {
            "model": camp_execution.model,
            "reasoning": camp_execution.reasoning,
            "sandbox": "workspace-write",
            "scope": "explicit paths with Git mutation journal",
        }
    disabled = ["implementation", "testing", "build", "deployment"]
    if not camp_enabled:
        disabled.insert(0, "CAMP execution")
    return {
        "schema_version": 1,
        "title": "CODEX APP SERVER",
        "status": "OPT-IN",
        "global_default": "disabled" if not config.globally_enabled else "enabled",
        "installed_codex": installed,
        "qualified_codex": configured_qualified,
        "compatibility": record.get("status") if record else "unqualified_version",
        "version_warning": config.compatibility_warning(codex),
        "enabled_roles": enabled_roles,
        "disabled": disabled,
        "known_blockers": blockers,
        "experimental_status": "unsupported for production workloads",
        "qualified_savings": savings,
        "qualification_record": record,
    }


def format_status(report: dict[str, Any]) -> str:
    roles = report["enabled_roles"]
    savings = report.get("qualified_savings") or {}
    lines = [
        "CODEX APP SERVER",
        "",
        f"Status: {report['status']}",
        f"Global default: {report['global_default']}",
        "",
        f"Installed Codex: {report.get('installed_codex') or 'not detected'}",
        f"Qualified Codex: {report['qualified_codex']}",
        f"Compatibility: {str(report['compatibility']).replace('_', ' ')}",
        "Experimental: unsupported for production workloads",
        "",
        "Enabled roles:",
        f"  planning      {roles['planning']['model']} / {roles['planning']['reasoning']}",
        f"  verification  {roles['verification']['model']} / {roles['verification']['reasoning']}",
    ]
    camp = roles.get("camp_execution")
    if camp:
        lines.append(
            f"  camp execution {camp['model']} / {camp['reasoning']} ({camp['scope']})"
        )
    lines.extend(
        [
            "",
            "Disabled:",
            *(f"  {item}" for item in report["disabled"]),
            "",
            "Known blockers:",
            *(f"  {item}" for item in report["known_blockers"]),
        ]
    )
    if savings:
        lines.extend(
            [
                "",
                "Qualified savings:",
                f"  input reduction: {savings['input_reduction_percent']:.2f}%",
                f"  elapsed reduction: {savings['elapsed_reduction_percent']:.2f}%",
            ]
        )
    warning = report.get("version_warning")
    if warning:
        lines.extend(["", f"WARNING: {warning}"])
    return "\n".join(lines)


def check(name: str, passed: bool, detail: Any, *, blocker: bool = False) -> dict[str, Any]:
    return {
        "name": name,
        "status": "pass" if passed else ("blocked" if blocker else "fail"),
        "detail": detail,
    }


def smoke_report(
    *,
    codex: str = "codex",
    cwd: Path = ROOT,
    config_path: Path = DEFAULT_CONFIG,
    policy_path: Path = DEFAULT_POLICY,
    qualifications_path: Path = DEFAULT_QUALIFICATIONS,
    telemetry_path: Path | None = None,
    timeout: float = 120.0,
    retest_restricted_read: bool = False,
) -> dict[str, Any]:
    source_workspace = cwd.expanduser().resolve()
    if not source_workspace.is_dir():
        raise CompatibilityError(f"smoke workspace is not a directory: {source_workspace}")
    config = AppServerFeatureConfig.load(config_path)
    policy = ModelPolicy.load(policy_path)
    records = load_qualifications(qualifications_path)
    installed = detect_codex_version(codex)
    record = qualification_for_version(records, installed)
    configured_version = config.qualified_codex_version
    version_changed = installed != configured_version
    checks: list[dict[str, Any]] = [
        check("codex_version_detection", installed is not None, installed or "not detected"),
        check(
            "qualification_record",
            record is not None,
            record.get("status") if record else f"no record for {installed}",
        ),
    ]
    fallback = config.route("planning", enable_override=None)
    checks.append(
        check(
            "existing_gui_fallback",
            fallback.backend == "existing-gui" and fallback.reason == "global_feature_disabled",
            asdict(fallback),
        )
    )
    discussion = config.route(
        "planning", request_text="ts: discuss smoke", enable_override=True
    )
    checks.append(
        check(
            "discussion_remains_gui",
            discussion.backend == "existing-gui",
            asdict(discussion),
        )
    )
    bridge = ApprovalBridge()
    approval_command = bridge(
        "item/commandExecution/requestApproval",
        {"threadId": "smoke", "turnId": "smoke", "itemId": "smoke"},
    )
    approval_permissions = bridge(
        "item/permissions/requestApproval",
        {"threadId": "smoke", "turnId": "smoke", "itemId": "permissions"},
    )
    checks.append(
        check(
            "approval_fail_closed",
            approval_command == {"decision": "cancel"}
            and approval_permissions == {"permissions": []},
            {
                "permission_expansion": "disabled",
                "camp_write_approval_policy": "never",
                "command": approval_command,
                "permissions": approval_permissions,
                "gui_approval_bridge": "NOT AVAILABLE",
            },
        )
    )

    telemetry = telemetry_path or default_telemetry_path()
    planning_tokens: dict[str, Any] = {}
    verification_tokens: dict[str, Any] = {}
    cancellation: dict[str, Any] | None = None
    restricted_result: dict[str, Any]
    server_state: dict[str, Any] | None = None
    try:
        with tempfile.TemporaryDirectory(prefix="tool-shed-app-server-smoke-") as temporary_name:
            smoke_cwd = Path(temporary_name)
            (smoke_cwd / "AGENTS.md").write_text(
                "# Compatibility smoke\n\nRead-only checks only. Do not use tools.\n",
                encoding="utf-8",
            )
            with CodexExecutionAdapter(
                policy=policy,
                codex=codex,
                timeout=timeout,
                telemetry_path=telemetry,
            ) as adapter:
                probe = sanitized_probe(adapter)
                checks.extend(
                    [
                        check("app_server_startup", True, probe["app_server_user_agent"]),
                        check(
                            "chatgpt_authentication",
                            probe["authentication"]["type"] == "chatgpt",
                            probe["authentication"]["type"],
                        ),
                        check(
                            "no_api_key_fallback",
                            probe["authentication"]["api_key_fallback"] is False,
                            "disabled",
                        ),
                    ]
                )
                catalog = {item["id"]: item for item in probe["models"]}
                for role in ("planning", "verification"):
                    selection = policy.select(role)
                    model = catalog.get(selection.model)
                    efforts = model.get("supported_reasoning_efforts") if isinstance(model, dict) else []
                    checks.append(
                        check(
                            f"{role}_model_and_reasoning",
                            model is not None and selection.reasoning in efforts,
                            {
                                "model": selection.model,
                                "reasoning": selection.reasoning,
                                "available": model is not None,
                            },
                        )
                    )
                planning = adapter.execute(
                    "Reply with exactly APP_SERVER_PLANNING_SMOKE_OK.",
                    role="planning",
                    cwd=smoke_cwd,
                    sandbox="read-only",
                    ephemeral=True,
                    operation="compatibility_smoke",
                )
                planning_tokens = flatten_token_usage(planning.token_usage)
                checks.append(
                    check(
                        "read_only_planning_turn",
                        planning.status == "completed" and planning.actual_model == policy.select("planning").model,
                        {
                            "status": planning.status,
                            "model": planning.actual_model,
                            "reasoning": planning.reasoning,
                            "thread_mode": "new",
                        },
                    )
                )
                verification = adapter.execute(
                    "Reply with exactly APP_SERVER_VERIFICATION_SMOKE_OK.",
                    role="verification",
                    cwd=smoke_cwd,
                    sandbox="read-only",
                    ephemeral=True,
                    operation="compatibility_smoke",
                )
                verification_tokens = flatten_token_usage(verification.token_usage)
                checks.append(
                    check(
                        "new_thread_creation",
                        not planning.thread_reused
                        and not verification.thread_reused
                        and planning.thread_id != verification.thread_id,
                        {
                            "planning_thread": planning.thread_id,
                            "verification_thread": verification.thread_id,
                            "both_new": not planning.thread_reused
                            and not verification.thread_reused,
                        },
                    )
                )
                checks.append(
                    check(
                        "read_only_verification_turn",
                        verification.status == "completed"
                        and verification.actual_model == policy.select("verification").model,
                        {
                            "status": verification.status,
                            "model": verification.actual_model,
                            "reasoning": verification.reasoning,
                            "thread_mode": "new",
                        },
                    )
                )
                selection, thread = adapter.start_work(
                    "planning", cwd=smoke_cwd, sandbox="read-only", ephemeral=False
                )
                turn_id = adapter.client.start_turn(
                    str(thread["id"]),
                    "Read-only cancellation compatibility probe. Do not use tools.",
                    model=selection.model,
                    effort=selection.reasoning,
                    cwd=smoke_cwd,
                    approval_policy="never",
                    sandbox_policy=sandbox_policy("read-only", smoke_cwd),
                )
                cancellation = adapter.cancel(
                    str(thread["id"]),
                    turn_id,
                    timeout=min(timeout, 5.0),
                    qualification_id=f"compatibility-smoke-{installed or 'unknown'}",
                    campaign="codex-app-server-compatibility",
                )
                cancellation_safe = cancellation["outcome"] == "cancelled"
                checks.append(
                    check(
                        "cancellation_reconciliation",
                        cancellation_safe,
                        cancellation,
                        blocker=not cancellation_safe,
                    )
                )
                should_retest_restricted = retest_restricted_read or version_changed
                if should_retest_restricted:
                    try:
                        restricted = adapter.execute(
                            "Reply with exactly RESTRICTED_READ_SMOKE_OK.",
                            role="verification",
                            cwd=smoke_cwd,
                            sandbox="read-only",
                            restricted_read=True,
                            ephemeral=True,
                            operation="compatibility_smoke_restricted_read",
                        )
                        restricted_result = {
                            "retested": True,
                            "accepted": restricted.status == "completed",
                            "status": restricted.status,
                        }
                    except AppServerError as error:
                        restricted_result = {
                            "retested": True,
                            "accepted": False,
                            "error_kind": error.kind,
                            "error": str(error),
                        }
                else:
                    restricted_result = {
                        "retested": False,
                        "accepted": bool(record and record.get("restricted_read_consistent")),
                        "reason": "unchanged version; retained version-specific qualification result",
                    }
                checks.append(
                    check(
                        "restricted_read_behavior",
                        bool(restricted_result["accepted"]),
                        restricted_result,
                        blocker=not bool(restricted_result["accepted"]),
                    )
                )
                server_state = adapter.client.process_state()
    except (AppServerError, AuthenticationError, ModelPolicyError) as error:
        checks.append(
            check(
                "app_server_runtime",
                False,
                {"error": str(error), "kind": getattr(error, "kind", None)},
            )
        )

    baseline = int(
        config.payload.get("qualification", {}).get(
            "estimated_codex_baseline_input_tokens", 18_800
        )
    )
    observed_inputs = [
        value
        for value in (planning_tokens.get("input"), verification_tokens.get("input"))
        if isinstance(value, int)
    ]
    tiny_input = min(observed_inputs) if observed_inputs else None
    baseline_factor = 1.5
    baseline_ok = isinstance(tiny_input, int) and tiny_input <= baseline * baseline_factor
    checks.append(
        check(
            "tiny_operation_token_baseline",
            baseline_ok,
            {
                "estimated_baseline_input_tokens": baseline,
                "observed_input_tokens": tiny_input,
                "warning_factor": baseline_factor,
                "estimated_avoidable_input_tokens": (
                    max(0, tiny_input - baseline) if isinstance(tiny_input, int) else None
                ),
            },
        )
    )
    failed = [item for item in checks if item["status"] == "fail"]
    blockers = [item for item in checks if item["status"] == "blocked"]
    if installed is None or record is None or failed:
        outcome = "unqualified"
    elif blockers or record.get("status") == "qualified_with_blockers":
        outcome = "qualified_with_blockers"
    else:
        outcome = "qualified"
    return {
        "schema_version": 1,
        "title": "CODEX APP SERVER COMPATIBILITY SMOKE",
        "installed_codex": installed,
        "configured_qualified_codex": configured_version,
        "source_workspace": str(source_workspace),
        "version_changed": version_changed,
        "outcome": outcome,
        "checks": checks,
        "token_baseline": {
            "planning": planning_tokens,
            "verification": verification_tokens,
            "estimated_fixed_input_tokens_per_operation": baseline,
        },
        "cancellation": cancellation,
        "server_process_state": server_state,
        "telemetry": str(telemetry.expanduser().resolve()),
        "qualification_record_updated": False,
        "next_action": (
            "Review smoke evidence and add a version-specific qualification record."
            if record is None
            else "Keep App Server opt-in until recorded blockers are cleared and requalified."
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex", default="codex")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--qualifications", type=Path, default=DEFAULT_QUALIFICATIONS)
    subparsers = parser.add_subparsers(dest="command", required=True)
    status = subparsers.add_parser("status", help="Show concise opt-in and compatibility status.")
    status.add_argument("--json", action="store_true")
    smoke = subparsers.add_parser("smoke", help="Run live read-only compatibility checks.")
    smoke.add_argument("--cwd", type=Path, default=ROOT)
    smoke.add_argument("--telemetry", type=Path, default=default_telemetry_path())
    smoke.add_argument("--timeout", type=float, default=120.0)
    smoke.add_argument("--retest-restricted-read", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.command == "status":
            report = status_report(
                codex=args.codex,
                config_path=args.config,
                policy_path=args.policy,
                qualifications_path=args.qualifications,
            )
            print(json.dumps(report, indent=2, sort_keys=True) if args.json else format_status(report))
            return 0
        report = smoke_report(
            codex=args.codex,
            cwd=args.cwd,
            config_path=args.config,
            policy_path=args.policy,
            qualifications_path=args.qualifications,
            telemetry_path=args.telemetry,
            timeout=args.timeout,
            retest_restricted_read=args.retest_restricted_read,
        )
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report["outcome"] in {"qualified", "qualified_with_blockers"} else 2
    except (CompatibilityError, FeatureConfigError, ModelPolicyError) as error:
        print(json.dumps({"error": str(error)}, indent=2), file=__import__("sys").stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
