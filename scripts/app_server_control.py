#!/usr/bin/env python3
"""Resolve Tool Shed's explicit, default-off Codex App Server command controls."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

try:
    from scripts.codex_app_server_compatibility import (
        CompatibilityError,
        DEFAULT_QUALIFICATIONS,
        codex_version_at_least,
        dirty_read_qualification_report,
        load_qualifications,
        qualification_for_version,
        status_report,
        resolve_codex_cli,
    )
    from scripts.codex_execution import DEFAULT_POLICY, ModelPolicy, ModelPolicyError
    from scripts.codex_orchestration import (
        DEFAULT_CONFIG,
        AppServerFeatureConfig,
        FeatureConfigError,
    )
except ModuleNotFoundError:  # Direct execution: python scripts/app_server_control.py
    from codex_app_server_compatibility import (  # type: ignore[no-redef]
        CompatibilityError,
        DEFAULT_QUALIFICATIONS,
        codex_version_at_least,
        dirty_read_qualification_report,
        load_qualifications,
        qualification_for_version,
        status_report,
        resolve_codex_cli,
    )
    from codex_execution import (  # type: ignore[no-redef]
        DEFAULT_POLICY,
        ModelPolicy,
        ModelPolicyError,
    )
    from codex_orchestration import (  # type: ignore[no-redef]
        DEFAULT_CONFIG,
        AppServerFeatureConfig,
        FeatureConfigError,
    )


COMMAND_ROUTES: dict[str, tuple[str, str, str, str]] = {
    "plan": ("planning", "planning", "read-only", "run"),
    "verify": ("verification", "verification", "read-only", "run"),
    "camp-run": ("camp_execution", "CAMP execution", "workspace-write", "camp-run"),
    "discuss": ("discussion", "discussion", "read-only", "none"),
}


class AppServerControlError(ValueError):
    pass


@dataclass(frozen=True)
class CommandSelection:
    schema_version: int
    command: str
    requested_execution: str
    execution: str
    role: str
    model: str | None
    reasoning: str | None
    opt_in: str
    allowed: bool
    reason: str
    fallback_available: bool
    global_default: str
    session_opt_in: str
    installed_codex: str | None
    qualified_codex: str
    compatibility: str | None
    qualification_mode: str
    minimum_dirty_read_codex: str
    dirty_qualification: dict[str, Any] | None
    api_fallback: bool
    orchestrator_subcommand: str


def _global_default(config: AppServerFeatureConfig) -> str:
    return "ON" if config.globally_enabled else "OFF"


def select_role(
    role: str,
    *,
    command: str,
    display_role: str,
    sandbox: str,
    orchestrator_subcommand: str,
    app_server_requested: bool,
    codex: str | None = None,
    config_path: Path = DEFAULT_CONFIG,
    policy_path: Path = DEFAULT_POLICY,
    qualifications_path: Path = DEFAULT_QUALIFICATIONS,
) -> CommandSelection:
    """Resolve one command without executing either backend."""

    config = AppServerFeatureConfig.load(config_path)
    policy = ModelPolicy.load(policy_path)
    api_fallback = bool(policy.payload["authentication"]["allow_api_key_fallback"])
    common: dict[str, Any] = {
        "schema_version": 1,
        "command": command,
        "requested_execution": "App Server" if app_server_requested else "GUI",
        "role": display_role,
        "opt_in": "explicit" if app_server_requested else "default",
        "fallback_available": True,
        "global_default": _global_default(config),
        "session_opt_in": "OFF",
        "qualified_codex": ", ".join(config.qualified_codex_versions),
        "minimum_dirty_read_codex": config.minimum_dirty_read_codex_version,
        "api_fallback": api_fallback,
        "orchestrator_subcommand": orchestrator_subcommand,
    }
    if not app_server_requested:
        return CommandSelection(
            **common,
            execution="GUI",
            model=None,
            reasoning=None,
            allowed=True,
            reason="default_gui",
            installed_codex=None,
            compatibility=None,
            qualification_mode="not_requested",
            dirty_qualification=None,
        )
    if role == "discussion":
        return CommandSelection(
            **common,
            execution="GUI",
            model=None,
            reasoning=None,
            allowed=False,
            reason="discussion_is_gui_native",
            installed_codex=None,
            compatibility=None,
            qualification_mode="not_applicable",
            dirty_qualification=None,
        )

    selected = policy.select(role)
    decision = config.route(
        role,
        request_text=f"ts: {command}",
        sandbox=sandbox,
        enable_override=True,
    )
    if not decision.use_app_server:
        return CommandSelection(
            **common,
            execution="GUI",
            model=selected.model,
            reasoning=selected.reasoning,
            allowed=False,
            reason=decision.reason,
            installed_codex=None,
            compatibility=None,
            qualification_mode="feature_blocked",
            dirty_qualification=None,
        )

    records = load_qualifications(qualifications_path)
    resolution = resolve_codex_cli(codex, records)
    # Pass the concrete resolver result throughout this decision; never fall
    # back to an independent bare-`codex` lookup.
    installed = resolution.version
    record = qualification_for_version(records, installed)
    dirty_qualification: dict[str, Any] | None = None
    qualification_mode = "exact_record" if record else "none"
    compatibility = (
        str(record.get("status")) if record
        else ("unqualified_version" if resolution.found else resolution.readiness.value)
    )
    route_record = (record.get("routing") or {}).get(role) if record else None
    version_matches = installed in config.qualified_codex_versions
    dirty_read_allowed = bool(
        role in {"planning", "verification"}
        and record is None
        and resolution.app_server_available
        and resolution.executable is not None
        and codex_version_at_least(installed, config.minimum_dirty_read_codex_version)
    )
    if dirty_read_allowed:
        dirty_qualification = dirty_read_qualification_report(
            codex=str(resolution.executable),
            cwd=Path.cwd(),
            config_path=config_path,
            policy_path=policy_path,
            qualifications_path=qualifications_path,
        )
        qualification_mode = "dirty_read"
        compatibility = str(dirty_qualification["outcome"])
        if compatibility in {"qualified", "qualified_with_blockers"}:
            route_record = {
                "model": selected.model,
                "reasoning": selected.reasoning,
                "qualified": True,
            }
            version_matches = True
    elif role in {"planning", "verification"} and record is None and installed is not None:
        qualification_mode = "below_minimum"
    route_qualified = isinstance(route_record, dict) and route_record.get("qualified") is True
    policy_matches = bool(
        route_qualified
        and route_record.get("model") == selected.model
        and route_record.get("reasoning") == selected.reasoning
    )
    camp_write_qualified = role != "camp_execution" or bool(
        record
        and record.get("workspace_writing")
        and installed in config.qualified_write_codex_versions
    )
    compatible = compatibility in {"qualified", "qualified_with_blockers"}
    if not resolution.app_server_available:
        reason = "codex_app_server_unavailable"
    elif qualification_mode == "dirty_read" and not compatible:
        reason = (
            "dirty_qualification_unknown"
            if compatibility == "unqualified_unknown"
            else "dirty_qualification_failed"
        )
    elif qualification_mode == "below_minimum":
        reason = "codex_below_minimum_dirty_read_version"
    elif not version_matches or not compatible:
        reason = "codex_version_not_qualified"
    elif not route_qualified or not camp_write_qualified:
        reason = "role_not_qualified"
    elif not policy_matches:
        reason = "qualification_policy_mismatch"
    elif qualification_mode == "dirty_read":
        reason = "explicit_dirty_qualified_opt_in"
    else:
        reason = "explicit_qualified_opt_in"
    allowed = reason in {"explicit_qualified_opt_in", "explicit_dirty_qualified_opt_in"}
    return CommandSelection(
        **common,
        execution="App Server" if allowed else "GUI",
        model=selected.model,
        reasoning=selected.reasoning,
        allowed=allowed,
        reason=reason,
        installed_codex=installed,
        compatibility=compatibility,
        qualification_mode=qualification_mode,
        dirty_qualification=dirty_qualification,
    )


def select_command(
    command: str,
    *,
    app_server_requested: bool,
    codex: str | None = None,
    config_path: Path = DEFAULT_CONFIG,
    policy_path: Path = DEFAULT_POLICY,
    qualifications_path: Path = DEFAULT_QUALIFICATIONS,
) -> CommandSelection:
    try:
        role, display_role, sandbox, orchestrator = COMMAND_ROUTES[command]
    except KeyError as error:
        raise AppServerControlError(f"unknown Tool Shed command route: {command}") from error
    return select_role(
        role,
        command=command,
        display_role=display_role,
        sandbox=sandbox,
        orchestrator_subcommand=orchestrator,
        app_server_requested=app_server_requested,
        codex=codex,
        config_path=config_path,
        policy_path=policy_path,
        qualifications_path=qualifications_path,
    )


def control_status(
    *,
    codex: str | None = None,
    config_path: Path = DEFAULT_CONFIG,
    policy_path: Path = DEFAULT_POLICY,
    qualifications_path: Path = DEFAULT_QUALIFICATIONS,
) -> dict[str, Any]:
    report = status_report(
        codex=codex,
        config_path=config_path,
        policy_path=policy_path,
        qualifications_path=qualifications_path,
    )
    policy = ModelPolicy.load(policy_path)
    report.update(
        {
            "global_default": "ON" if report["global_default"] == "enabled" else "OFF",
            "session_opt_in": "OFF",
            "session_control_supported": False,
            "session_note": (
                "Codex does not expose reliable skill-owned session storage; use --app-server "
                "on each qualified command."
            ),
            "current_execution_default": "GUI",
            "discussion_execution": "GUI-native",
            "api_fallback": bool(
                policy.payload["authentication"]["allow_api_key_fallback"]
            ),
        }
    )
    return report


def session_control(action: str) -> dict[str, Any]:
    if action not in {"on", "off"}:
        raise AppServerControlError(f"unknown session action: {action}")
    return {
        "schema_version": 1,
        "accepted": False,
        "requested": action.upper(),
        "session_opt_in": "OFF",
        "session_control_supported": False,
        "persistent_changes": False,
        "reason": "reliable skill-owned Codex-session storage is unavailable",
        "next_action": "use --app-server on each qualified plan, verify, or camp run command",
    }


def format_selection(selection: CommandSelection) -> str:
    if selection.allowed and selection.execution == "App Server":
        return "\n".join(
            [
                "Execution: App Server",
                f"Role: {selection.role}",
                f"Model: {selection.model}",
                f"Reasoning: {selection.reasoning}",
                "Opt-in: explicit",
                f"Qualification: {selection.qualification_mode}",
            ]
        )
    if selection.allowed:
        return "Execution: GUI"
    lines = [
        "Execution: GUI",
        "App Server request: BLOCKED",
        f"Reason: {selection.reason}",
    ]
    if selection.compatibility is not None:
        lines.extend(
            [
                f"Installed Codex: {selection.installed_codex or 'not detected'}",
                f"Qualified Codex: {selection.qualified_codex}",
                f"Minimum dirty-read Codex: {selection.minimum_dirty_read_codex}",
                f"Compatibility: {selection.compatibility}",
            ]
        )
    lines.append("Fallback: rerun the command without --app-server")
    return "\n".join(lines)


def format_control_status(report: dict[str, Any]) -> str:
    roles = report["enabled_roles"]
    lines = [
        f"App Server global default: {report['global_default']}",
        f"Session opt-in: {report['session_opt_in']}",
        "Session controls: unavailable; explicit per-command only",
        f"Session note: {report['session_note']}",
        "",
        f"Codex CLI: {report.get('codex_cli', 'NOT FOUND')}",
        f"Discovery: {report.get('codex_discovery', 'not found')}",
        f"Executable: {report.get('codex_executable') or 'not detected'}",
        f"App Server: {'AVAILABLE' if report.get('app_server_available') else 'UNAVAILABLE'}",
        f"Installed Codex: {report.get('installed_codex') or 'not detected'}",
        f"Qualified Codex: {report['qualified_codex']}",
        f"Minimum dirty-read Codex: {report['minimum_dirty_read_codex']}",
        f"Compatibility: {str(report['compatibility']).replace('_', ' ')}",
        "",
        "Qualified roles:",
        f"  planning        {roles['planning']['model']} / {roles['planning']['reasoning']}",
        f"  verification    {roles['verification']['model']} / {roles['verification']['reasoning']}",
    ]
    camp = roles.get("camp_execution")
    if camp:
        lines.append(f"  camp_execution  {camp['model']} / {camp['reasoning']}")
    lines.extend(
        [
            "",
            f"Current execution default: {report['current_execution_default']}",
            f"ts: discuss: {report['discussion_execution']}",
            f"API fallback: {'enabled' if report['api_fallback'] else 'disabled'}",
        ]
    )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex", default=None)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--qualifications", type=Path, default=DEFAULT_QUALIFICATIONS)
    subparsers = parser.add_subparsers(dest="operation", required=True)

    select = subparsers.add_parser("select", help="Resolve one user-facing Tool Shed command.")
    select.add_argument("command", choices=tuple(COMMAND_ROUTES))
    select.add_argument("--app-server", action="store_true")
    select.add_argument("--json", action="store_true")

    status = subparsers.add_parser("status", help="Show user-facing App Server control status.")
    status.add_argument("--json", action="store_true")

    session = subparsers.add_parser(
        "session", help="Explain why session on/off is unavailable without reliable session storage."
    )
    session.add_argument("action", choices=("on", "off"))
    session.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.operation == "select":
            selection = select_command(
                args.command,
                app_server_requested=args.app_server,
                codex=args.codex,
                config_path=args.config,
                policy_path=args.policy,
                qualifications_path=args.qualifications,
            )
            print(
                json.dumps(asdict(selection), indent=2, sort_keys=True)
                if args.json
                else format_selection(selection)
            )
            return 0 if selection.allowed else 2
        if args.operation == "status":
            report = control_status(
                codex=args.codex,
                config_path=args.config,
                policy_path=args.policy,
                qualifications_path=args.qualifications,
            )
            print(
                json.dumps(report, indent=2, sort_keys=True)
                if args.json
                else format_control_status(report)
            )
            return 0
        report = session_control(args.action)
        print(
            json.dumps(report, indent=2, sort_keys=True)
            if args.json
            else "\n".join(
                [
                    f"Session opt-in: {report['session_opt_in']}",
                    f"Reason: {report['reason']}",
                    f"Use: {report['next_action']}",
                ]
            )
        )
        return 2
    except (
        AppServerControlError,
        CompatibilityError,
        FeatureConfigError,
        ModelPolicyError,
    ) as error:
        print(json.dumps({"error": str(error)}, indent=2), file=__import__("sys").stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
