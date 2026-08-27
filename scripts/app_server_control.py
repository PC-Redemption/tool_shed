#!/usr/bin/env python3
"""Resolve Tool Shed's explicit and user-persisted Codex App Server controls."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, replace
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
        write_executable_identity_matches,
    )
    from scripts.codex_execution import DEFAULT_POLICY, ModelPolicy, ModelPolicyError
    from scripts.codex_qualification_cache import (
        QualificationCache,
        QualificationCacheError,
        build_qualification_identity,
    )
    from scripts.codex_orchestration import (
        DEFAULT_CONFIG,
        AppServerFeatureConfig,
        FeatureConfigError,
    )
    from scripts.app_server_user_state import (
        AppServerPreferenceStore,
        AppServerUserStateError,
        default_app_server_event_path,
        record_app_server_event_best_effort,
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
        write_executable_identity_matches,
    )
    from codex_execution import (  # type: ignore[no-redef]
        DEFAULT_POLICY,
        ModelPolicy,
        ModelPolicyError,
    )
    from codex_qualification_cache import (  # type: ignore[no-redef]
        QualificationCache,
        QualificationCacheError,
        build_qualification_identity,
    )
    from codex_orchestration import (  # type: ignore[no-redef]
        DEFAULT_CONFIG,
        AppServerFeatureConfig,
        FeatureConfigError,
    )
    from app_server_user_state import (  # type: ignore[no-redef]
        AppServerPreferenceStore,
        AppServerUserStateError,
        default_app_server_event_path,
        record_app_server_event_best_effort,
    )


COMMAND_ROUTES: dict[str, tuple[str, str, str, str]] = {
    "plan": ("planning", "planning", "read-only", "run"),
    "verify": ("verification", "verification", "read-only", "run"),
    "camp-run": ("camp_execution", "CAMP execution", "workspace-write", "camp-run"),
    "discuss": ("discussion", "discussion", "read-only", "none"),
}


class AppServerControlError(ValueError):
    pass


REPOSITORY_POLICY_FILE = ".tool-shed-policy.json"


def _repository_policy_path(explicit: Path | None, workspace: Path | None) -> Path | None:
    if explicit is not None:
        return explicit.expanduser().resolve()
    current = (workspace or Path.cwd()).expanduser().resolve()
    for candidate in (current, *current.parents):
        policy = candidate / REPOSITORY_POLICY_FILE
        if policy.is_file():
            return policy
        if (candidate / ".git").exists():
            break
    return None


def repository_certification_policy(
    *,
    policy_path: Path | None = None,
    workspace: Path | None = None,
) -> dict[str, Any]:
    """Load the optional repository-level exact-certification policy."""

    resolved = _repository_policy_path(policy_path, workspace)
    default = {
        "mode": "operator-runtime",
        "strict": False,
        "source": "default",
        "path": str(resolved) if resolved else None,
        "reason": None,
    }
    if resolved is None:
        return default
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AppServerControlError(
            f"cannot load repository App Server policy {resolved}: {error}"
        ) from error
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise AppServerControlError(
            f"repository App Server policy {resolved} must use schema_version 1"
        )
    app_server = payload.get("app_server")
    if app_server is None:
        return {**default, "source": "repository-default"}
    if not isinstance(app_server, dict):
        raise AppServerControlError("repository app_server policy must be an object")
    mode = app_server.get("certification_mode", "operator-runtime")
    if mode not in {"operator-runtime", "strict-certified"}:
        raise AppServerControlError(
            "repository app_server.certification_mode must be operator-runtime or strict-certified"
        )
    reason = app_server.get("reason")
    if mode == "strict-certified" and (not isinstance(reason, str) or not reason.strip()):
        raise AppServerControlError(
            "strict-certified repository App Server policy requires a non-empty reason"
        )
    return {
        "mode": mode,
        "strict": mode == "strict-certified",
        "source": "repository-policy",
        "path": str(resolved),
        "reason": reason.strip() if isinstance(reason, str) and reason.strip() else None,
    }


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
    codex_executable: str | None
    codex_discovery: str | None
    qualified_codex: str
    compatibility: str | None
    qualification_mode: str
    qualification_state: str
    minimum_dirty_read_codex: str
    dirty_qualification: dict[str, Any] | None
    qualification_cache: dict[str, Any]
    codex_inventory: tuple[dict[str, Any], ...]
    api_fallback: bool
    orchestrator_subcommand: str
    trust_policy: str
    trust_source: str
    operator_trust: bool
    runtime_readiness: str
    observed_safety: str
    certification_mode: str
    certification_state: str
    certification_required: bool
    certification_warning: str | None
    strict_request: bool = False
    preference_mode: str = "OFF"
    preference_source: str = "default-off"
    preference_path: str | None = None
    preference_warning: str | None = None
    fallback_used: bool = False
    fallback_reason: str | None = None


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
    gui_requested: bool = False,
    codex: str | None = None,
    config_path: Path = DEFAULT_CONFIG,
    policy_path: Path = DEFAULT_POLICY,
    qualifications_path: Path = DEFAULT_QUALIFICATIONS,
    qualification_cache_path: Path | None = None,
    preference_path: Path | None = None,
    repository_policy_path: Path | None = None,
    workspace: Path | None = None,
    force_requalification: bool = False,
) -> CommandSelection:
    """Resolve one command without executing either backend."""

    if app_server_requested and gui_requested:
        raise AppServerControlError("--app-server and --gui are mutually exclusive")
    preference = AppServerPreferenceStore(preference_path).status()
    certification_policy = repository_certification_policy(
        policy_path=repository_policy_path,
        workspace=workspace,
    )
    operator_runtime = bool(preference.operator_trust and not certification_policy["strict"])
    persisted_request = preference.enabled and not app_server_requested and not gui_requested
    effective_app_server = app_server_requested or persisted_request
    config = AppServerFeatureConfig.load(config_path)
    policy = ModelPolicy.load(policy_path)
    api_fallback = bool(policy.payload["authentication"]["allow_api_key_fallback"])
    common: dict[str, Any] = {
        "schema_version": 1,
        "command": command,
        "requested_execution": "App Server" if effective_app_server else "GUI",
        "role": display_role,
        "opt_in": (
            "explicit" if app_server_requested
            else "persistent" if persisted_request
            else "explicit-gui" if gui_requested
            else "default"
        ),
        "fallback_available": True,
        "global_default": _global_default(config),
        "session_opt_in": "OFF",
        "qualified_codex": ", ".join(config.qualified_codex_versions),
        "minimum_dirty_read_codex": config.minimum_dirty_read_codex_version,
        "api_fallback": api_fallback,
        "orchestrator_subcommand": orchestrator_subcommand,
        "trust_policy": (
            "strict-certified" if certification_policy["strict"] else preference.trust_policy
        ),
        "trust_source": (
            "repository-policy" if certification_policy["strict"] else preference.source
        ),
        "operator_trust": operator_runtime,
        "runtime_readiness": "not-checked",
        "observed_safety": "clear",
        "certification_mode": certification_policy["mode"],
        "certification_state": "not-checked",
        "certification_required": bool(certification_policy["strict"]),
        "certification_warning": None,
        "strict_request": app_server_requested,
        "preference_mode": preference.mode,
        "preference_source": preference.source,
        "preference_path": preference.path,
        "preference_warning": preference.warning,
    }
    if not effective_app_server:
        return CommandSelection(
            **common,
            execution="GUI",
            model=None,
            reasoning=None,
            allowed=True,
            reason="explicit_gui" if gui_requested else "default_gui",
            installed_codex=None,
            codex_executable=None,
            codex_discovery=None,
            compatibility=None,
            qualification_mode="not_requested",
            qualification_state="not-requested",
            dirty_qualification=None,
            qualification_cache={"status": "not-applicable", "source": "none"},
            codex_inventory=(),
        )
    if role == "discussion":
        if not app_server_requested:
            return CommandSelection(
                **{
                    **common,
                    "requested_execution": "GUI",
                    "opt_in": "persistent-bypass" if persisted_request else common["opt_in"],
                },
                execution="GUI",
                model=None,
                reasoning=None,
                allowed=True,
                reason="discussion_is_gui_native",
                installed_codex=None,
                codex_executable=None,
                codex_discovery=None,
                compatibility=None,
                qualification_mode="not_applicable",
                qualification_state="not-applicable",
                dirty_qualification=None,
                qualification_cache={"status": "not-applicable", "source": "none"},
                codex_inventory=(),
            )
        return CommandSelection(
            **common,
            execution="GUI",
            model=None,
            reasoning=None,
            allowed=False,
            reason="discussion_is_gui_native",
            installed_codex=None,
            codex_executable=None,
            codex_discovery=None,
            compatibility=None,
            qualification_mode="not_applicable",
            qualification_state="not-applicable",
            dirty_qualification=None,
            qualification_cache={"status": "not-applicable", "source": "none"},
            codex_inventory=(),
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
            codex_executable=None,
            codex_discovery=None,
            compatibility=None,
            qualification_mode="feature_blocked",
            qualification_state="unsafe-blocked",
            dirty_qualification=None,
            qualification_cache={"status": "not-applicable", "source": "none"},
            codex_inventory=(),
        )

    certification_warning: str | None = None
    try:
        records = load_qualifications(qualifications_path)
    except CompatibilityError as error:
        if not operator_runtime:
            raise
        records = []
        certification_warning = f"registry-unavailable:{type(error).__name__}"
    resolution = resolve_codex_cli(
        codex, records, config.minimum_dirty_read_codex_version
    )
    # Pass the concrete resolver result throughout this decision; never fall
    # back to an independent bare-`codex` lookup.
    installed = resolution.version
    record = qualification_for_version(records, installed)
    certification_state = (
        "exact-certified"
        if record and record.get("status") in {"qualified", "qualified_with_blockers"}
        else "explicitly-unqualified"
        if record and record.get("status") == "unqualified"
        else "not-certified"
    )
    dirty_qualification: dict[str, Any] | None = None
    cache_summary: dict[str, Any] = {
        "status": "not-applicable",
        "source": "user-local-cache",
        "invalidation_reason": None,
        "record": None,
        "decision_source": "exact-record" if record else "none",
    }
    qualification_mode = "exact_record" if record else "none"
    qualification_state = (
        "exact-qualified"
        if record and record.get("status") in {"qualified", "qualified_with_blockers"}
        else "unsafe-blocked"
    )
    compatibility = (
        str(record.get("status")) if record
        else ("unqualified_version" if resolution.found else resolution.readiness.value)
    )
    route_record = (record.get("routing") or {}).get(role) if record else None
    version_matches = installed in config.qualified_codex_versions
    dirty_read_allowed = bool(
        role in {"planning", "verification"}
        and not operator_runtime
        and record is None
        and resolution.app_server_available
        and resolution.executable is not None
        and codex_version_at_least(installed, config.minimum_dirty_read_codex_version)
    )
    if dirty_read_allowed:
        qualification_state = "dirty-qualifying"
        cache: QualificationCache | None = None
        identity = None
        try:
            identity = build_qualification_identity(
                executable=resolution.executable,
                codex_version=str(installed),
                config_path=config_path,
                model_policy_path=policy_path,
            )
            cache = QualificationCache(
                qualification_cache_path,
                max_age_seconds=config.dirty_read_cache_max_age_seconds,
            )
            lookup = cache.lookup(identity)
            cache_summary = {**lookup.as_dict(), "decision_source": "cache"}
        except (OSError, QualificationCacheError) as error:
            lookup = None
            cache_summary = {
                "status": "unavailable",
                "source": "user-local-cache",
                "invalidation_reason": type(error).__name__,
                "record": None,
                "decision_source": "live",
            }
        if not force_requalification and lookup and lookup.status == "hit" and lookup.record:
            cached_state = str(lookup.record.get("state"))
            dirty_qualification = {
                "outcome": lookup.record.get("outcome"),
                "safe_blockers": list(lookup.record.get("safe_blockers") or []),
                "fatal_failures": ["cached_reviewed_unsafe_denial"]
                if cached_state == "unsafe_denied"
                else [],
                "transient_failures": [],
                "unknown_failures": [],
                "cacheable_unsafe": cached_state == "unsafe_denied",
                "qualification_record_updated": False,
                "source": "user-local-cache",
            }
        else:
            dirty_qualification = dirty_read_qualification_report(
                codex=str(resolution.executable),
                cwd=Path.cwd(),
                config_path=config_path,
                policy_path=policy_path,
                qualifications_path=qualifications_path,
            )
            cache_summary["decision_source"] = (
                "live-requalification" if force_requalification else "live"
            )
            outcome = str(dirty_qualification.get("outcome"))
            if cache is not None and identity is not None:
                try:
                    if outcome in {"qualified", "qualified_with_blockers"}:
                        stored = cache.store(
                            identity,
                            state="qualified",
                            outcome=outcome,
                            safe_blockers=dirty_qualification.get("safe_blockers") or [],
                        )
                        cache_summary = {
                            **stored.as_dict(),
                            "decision_source": cache_summary["decision_source"],
                        }
                    elif outcome == "unqualified_fatal" and dirty_qualification.get(
                        "cacheable_unsafe"
                    ):
                        stored = cache.store(
                            identity,
                            state="unsafe_denied",
                            outcome=outcome,
                        )
                        cache_summary = {
                            **stored.as_dict(),
                            "decision_source": cache_summary["decision_source"],
                        }
                except (OSError, QualificationCacheError) as error:
                    cache_summary = {
                        "status": "unavailable",
                        "source": "user-local-cache",
                        "invalidation_reason": type(error).__name__,
                        "record": None,
                        "decision_source": "live",
                    }
        qualification_mode = "dirty_read"
        compatibility = str(dirty_qualification["outcome"])
        if compatibility in {"qualified", "qualified_with_blockers"}:
            qualification_state = "dirty-qualified"
            route_record = {
                "model": selected.model,
                "reasoning": selected.reasoning,
                "qualified": True,
            }
            version_matches = True
        elif compatibility in {"unqualified_unknown", "unqualified_transient"}:
            qualification_state = "transient-fallback"
        else:
            qualification_state = "unsafe-blocked"
    elif role in {"planning", "verification"} and record is None and installed is not None:
        qualification_mode = "below_minimum"
        qualification_state = "below-minimum"
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
        and write_executable_identity_matches(record, resolution.executable)
    )
    write_identity_matches = bool(
        role != "camp_execution"
        or write_executable_identity_matches(record, resolution.executable)
    )
    if (
        role == "camp_execution"
        and resolution.app_server_available
        and not camp_write_qualified
        and not operator_runtime
    ):
        qualification_state = "write-not-qualified"
    compatible = compatibility in {"qualified", "qualified_with_blockers"}
    if (
        operator_runtime
        and record is not None
        and record.get("status") == "unqualified"
    ):
        reason = "codex_version_denylisted"
        qualification_mode = "operator_runtime"
        qualification_state = "denylisted"
        compatibility = "denylisted_unsafe_behavior"
        common["observed_safety"] = "denylisted"
    elif operator_runtime and resolution.app_server_available:
        reason = (
            "explicit_operator_runtime_trust"
            if app_server_requested
            else "persistent_operator_runtime_trust"
        )
        qualification_mode = "operator_runtime"
        qualification_state = "certification-telemetry-only"
        compatibility = "runtime_candidate"
    elif not resolution.app_server_available:
        reason = "codex_app_server_unavailable"
        qualification_state = (
            "unsafe-blocked"
            if resolution.readiness.value == "invalid_executable"
            else "transient-fallback"
        )
    elif qualification_mode == "dirty_read" and not compatible:
        reason = {
            "unqualified_unknown": "dirty_qualification_unknown",
            "unqualified_transient": "dirty_qualification_transient",
        }.get(compatibility, "dirty_qualification_failed")
    elif qualification_mode == "below_minimum":
        reason = "codex_below_minimum_dirty_read_version"
    elif not version_matches or not compatible:
        reason = "codex_version_not_qualified"
    elif role == "camp_execution" and not write_identity_matches:
        reason = "codex_executable_hash_mismatch"
    elif not route_qualified or not camp_write_qualified:
        reason = "role_not_qualified"
    elif not policy_matches:
        reason = "qualification_policy_mismatch"
    elif qualification_mode == "dirty_read":
        reason = (
            "explicit_dirty_qualified_opt_in"
            if app_server_requested
            else "persistent_dirty_qualified_preference"
        )
    else:
        reason = (
            "explicit_qualified_opt_in"
            if app_server_requested
            else "persistent_qualified_preference"
        )
    allowed = reason in {
        "explicit_operator_runtime_trust",
        "persistent_operator_runtime_trust",
        "explicit_qualified_opt_in",
        "explicit_dirty_qualified_opt_in",
        "persistent_qualified_preference",
        "persistent_dirty_qualified_preference",
    }
    common.update(
        {
            "runtime_readiness": (
                "startup-probed" if resolution.app_server_available else "blocked"
            ),
            "certification_state": certification_state,
            "certification_warning": certification_warning,
        }
    )
    return CommandSelection(
        **common,
        execution="App Server" if allowed else "GUI",
        model=selected.model,
        reasoning=selected.reasoning,
        allowed=allowed,
        reason=reason,
        installed_codex=installed,
        codex_executable=str(resolution.executable) if resolution.executable else None,
        codex_discovery=resolution.source.value if resolution.source else None,
        compatibility=compatibility,
        qualification_mode=qualification_mode,
        qualification_state=qualification_state,
        dirty_qualification=dirty_qualification,
        qualification_cache=cache_summary,
        codex_inventory=tuple(candidate.as_dict() for candidate in resolution.inventory),
    )


def select_command(
    command: str,
    *,
    app_server_requested: bool,
    gui_requested: bool = False,
    codex: str | None = None,
    config_path: Path = DEFAULT_CONFIG,
    policy_path: Path = DEFAULT_POLICY,
    qualifications_path: Path = DEFAULT_QUALIFICATIONS,
    qualification_cache_path: Path | None = None,
    preference_path: Path | None = None,
    repository_policy_path: Path | None = None,
    workspace: Path | None = None,
    force_requalification: bool = False,
) -> CommandSelection:
    try:
        role, display_role, sandbox, orchestrator = COMMAND_ROUTES[command]
    except KeyError as error:
        raise AppServerControlError(f"unknown Tool Shed command route: {command}") from error
    selection = select_role(
        role,
        command=command,
        display_role=display_role,
        sandbox=sandbox,
        orchestrator_subcommand=orchestrator,
        app_server_requested=app_server_requested,
        gui_requested=gui_requested,
        codex=codex,
        config_path=config_path,
        policy_path=policy_path,
        qualifications_path=qualifications_path,
        qualification_cache_path=qualification_cache_path,
        preference_path=preference_path,
        repository_policy_path=repository_policy_path,
        workspace=workspace,
        force_requalification=force_requalification,
    )
    if selection.opt_in == "persistent" and not selection.allowed:
        return replace(
            selection,
            allowed=True,
            execution="GUI",
            reason="persistent_gui_fallback",
            fallback_used=True,
            fallback_reason=selection.reason,
        )
    return selection


def control_status(
    *,
    codex: str | None = None,
    config_path: Path = DEFAULT_CONFIG,
    policy_path: Path = DEFAULT_POLICY,
    qualifications_path: Path = DEFAULT_QUALIFICATIONS,
    qualification_cache_path: Path | None = None,
    preference_path: Path | None = None,
    event_path: Path | None = None,
    repository_policy_path: Path | None = None,
    workspace: Path | None = None,
) -> dict[str, Any]:
    preference = AppServerPreferenceStore(preference_path).status()
    certification_policy = repository_certification_policy(
        policy_path=repository_policy_path,
        workspace=workspace,
    )
    operator_trust = bool(
        preference.operator_trust and not certification_policy["strict"]
    )
    report = status_report(
        codex=codex,
        config_path=config_path,
        policy_path=policy_path,
        qualifications_path=qualifications_path,
        qualification_cache_path=qualification_cache_path,
        operator_trust=operator_trust,
        strict_certification=bool(certification_policy["strict"]),
    )
    policy = ModelPolicy.load(policy_path)
    report.update(
        {
            "global_default": "ON" if report["global_default"] == "enabled" else "OFF",
            "session_opt_in": preference.mode,
            "session_control_supported": True,
            "session_note": "Persistent user-local preference; --gui overrides it once.",
            "preference": preference.as_dict(),
            "trust_policy": (
                "strict-certified"
                if certification_policy["strict"]
                else preference.trust_policy
            ),
            "trust_source": (
                "repository-policy"
                if certification_policy["strict"]
                else preference.source
            ),
            "operator_trust": operator_trust,
            "certification_policy": certification_policy,
            "event_log_path": str(
                (event_path or default_app_server_event_path()).expanduser().resolve()
            ),
            "current_execution_default": "App Server" if preference.enabled else "GUI",
            "discussion_execution": "GUI-native",
            "api_fallback": bool(
                policy.payload["authentication"]["allow_api_key_fallback"]
            ),
        }
    )
    return report


def preference_control(action: str, *, preference_path: Path | None = None) -> dict[str, Any]:
    if action not in {"on", "off"}:
        raise AppServerControlError(f"unknown preference action: {action}")
    state = AppServerPreferenceStore(preference_path).set(action == "on")
    return {
        "schema_version": 2,
        "accepted": True,
        "requested": action.upper(),
        "session_opt_in": state.mode,
        "session_control_supported": True,
        "persistent_changes": True,
        "preference": state.as_dict(),
        "reason": (
            "operator-runtime trust recorded for supported local App Server roles"
            if action == "on"
            else "user-local App Server preference disabled"
        ),
        "next_action": "use --gui on any one eligible command to override this preference",
    }


def session_control(action: str, *, preference_path: Path | None = None) -> dict[str, Any]:
    """Compatibility alias for the former session-control entrypoint."""

    return preference_control(action, preference_path=preference_path)


def format_selection(selection: CommandSelection) -> str:
    if selection.allowed and selection.execution == "App Server":
        return "\n".join(
            [
                "Execution: App Server",
                f"Role: {selection.role}",
                f"Model: {selection.model}",
                f"Reasoning: {selection.reasoning}",
                f"API fallback: {'enabled' if selection.api_fallback else 'disabled'}",
                f"Opt-in: {selection.opt_in}",
                f"Reason: {selection.reason}",
                f"Trust policy: {selection.trust_policy}",
                f"Runtime readiness: {selection.runtime_readiness}",
                f"Observed safety: {selection.observed_safety}",
                f"Certification: {selection.certification_state}",
                f"Executable: {selection.codex_executable or 'not detected'}",
                f"Discovery: {selection.codex_discovery or 'not found'}",
                f"Qualification cache: {selection.qualification_cache.get('status')} "
                f"({selection.qualification_cache.get('decision_source')})",
            ]
        )
    if selection.allowed:
        if selection.fallback_used:
            return "\n".join(
                [
                    "Execution: GUI",
                    "App Server preference fallback: ACTIVE",
                    f"Reason: {selection.fallback_reason}",
                    "Action: continue the same request immediately in GUI",
                ]
            )
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
                f"Executable: {selection.codex_executable or 'not detected'}",
                f"Discovery: {selection.codex_discovery or 'not found'}",
                f"Trust policy: {selection.trust_policy}",
                f"Runtime readiness: {selection.runtime_readiness}",
                f"Observed safety: {selection.observed_safety}",
                f"Certification: {selection.certification_state}",
                f"Qualification state: {selection.qualification_state}",
                f"Compatibility: {selection.compatibility}",
                f"Qualification cache: {selection.qualification_cache.get('status')} "
                f"({selection.qualification_cache.get('decision_source')})",
            ]
        )
    if selection.strict_request:
        lines.append("Fallback: rerun the command without --app-server or use --gui")
    else:
        lines.append("Fallback: GUI will be used automatically when safe")
    return "\n".join(lines)


def format_control_status(report: dict[str, Any]) -> str:
    roles = report["enabled_roles"]
    lines = [
        f"App Server global default: {report['global_default']}",
        f"Persistent preference: {report['session_opt_in']}",
        f"Preference path: {report['preference']['path']}",
        f"Preference source: {report['preference']['source']}",
        f"Trust policy: {report['trust_policy']}",
        f"Operator trust: {'ACTIVE' if report['operator_trust'] else 'INACTIVE'}",
        f"Fallback event log: {report['event_log_path']}",
        "",
        f"Codex CLI: {report.get('codex_cli', 'NOT FOUND')}",
        f"Discovery: {report.get('codex_discovery', 'not found')}",
        f"Executable: {report.get('codex_executable') or 'not detected'}",
        f"App Server: {'AVAILABLE' if report.get('app_server_available') else 'UNAVAILABLE'}",
        f"Installed Codex: {report.get('installed_codex') or 'not detected'}",
        f"Runtime readiness: {report['runtime_readiness']}",
        f"Observed safety: {report['observed_safety']}",
        f"Certification required: {'yes' if report['certification_required'] else 'no'}",
        f"Certification state: {report['certification_state']}",
        f"Certified-version telemetry: {report['qualified_codex']}",
        f"Compatibility: {str(report['compatibility']).replace('_', ' ')}",
        "",
        "Eligible roles:",
    ]
    for role in ("planning", "verification", "camp_execution"):
        selected = roles.get(role)
        if selected:
            lines.append(
                f"  {role:<16}{selected['model']} / {selected['reasoning']}"
            )
    if not roles:
        lines.append("  none")
    inventory = report.get("codex_inventory") or []
    lines.extend(["", "Candidate inventory:"])
    if inventory:
        lines.extend(
            f"  {item['version'] or 'unknown'} | {item['source']} | "
            f"app-server={'available' if item['app_server_available'] else 'unavailable'} | "
            f"{item['qualification_state']} | {item['executable']}"
            for item in inventory
        )
    else:
        lines.append("  none")
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
    parser.add_argument("--qualification-cache", type=Path, default=None)
    parser.add_argument("--preference", type=Path, default=None)
    parser.add_argument("--repository-policy", type=Path, default=None)
    parser.add_argument("--events", type=Path, default=None)
    subparsers = parser.add_subparsers(dest="operation", required=True)

    select = subparsers.add_parser("select", help="Resolve one user-facing Tool Shed command.")
    select.add_argument("command", choices=tuple(COMMAND_ROUTES))
    execution = select.add_mutually_exclusive_group()
    execution.add_argument("--app-server", action="store_true")
    execution.add_argument("--gui", action="store_true")
    select.add_argument("--json", action="store_true")
    select.add_argument("--requalify", action="store_true")

    status = subparsers.add_parser("status", help="Show user-facing App Server control status.")
    status.add_argument("--json", action="store_true")

    preference = subparsers.add_parser(
        "preference", help="Persistently enable or disable passive App Server use."
    )
    preference.add_argument("action", choices=("on", "off"))
    preference.add_argument("--json", action="store_true")

    session = subparsers.add_parser("session", help="Compatibility alias for preference.")
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
                gui_requested=args.gui,
                codex=args.codex,
                config_path=args.config,
                policy_path=args.policy,
                qualifications_path=args.qualifications,
                qualification_cache_path=args.qualification_cache,
                preference_path=args.preference,
                repository_policy_path=args.repository_policy,
                force_requalification=args.requalify,
            )
            record_app_server_event_best_effort(
                path=args.events,
                command=args.command,
                outcome=(
                    "gui_fallback" if selection.fallback_used
                    else "selected" if selection.execution == "App Server"
                    else "gui"
                ),
                category=selection.fallback_reason or selection.reason,
                mutation_state="none",
                backend="app_server" if selection.execution == "App Server" else "gui",
                preference_mode=selection.preference_mode,
                strict_request=selection.strict_request,
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
                qualification_cache_path=args.qualification_cache,
                preference_path=args.preference,
                event_path=args.events,
                repository_policy_path=args.repository_policy,
            )
            print(
                json.dumps(report, indent=2, sort_keys=True)
                if args.json
                else format_control_status(report)
            )
            return 0
        report = preference_control(args.action, preference_path=args.preference)
        record_app_server_event_best_effort(
            path=args.events,
            command="preference",
            outcome="updated",
            category=f"preference_{args.action}",
            mutation_state="none",
            backend="control",
            preference_mode=report["session_opt_in"],
            strict_request=False,
        )
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
        return 0
    except (
        AppServerControlError,
        CompatibilityError,
        FeatureConfigError,
        ModelPolicyError,
        AppServerUserStateError,
    ) as error:
        record_app_server_event_best_effort(
            path=getattr(args, "events", None),
            command=getattr(args, "command", args.operation),
            outcome="failed",
            category=type(error).__name__,
            mutation_state="none",
            backend="none",
            preference_mode="UNKNOWN",
            strict_request=bool(getattr(args, "app_server", False)),
        )
        print(json.dumps({"error": str(error)}, indent=2), file=__import__("sys").stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
