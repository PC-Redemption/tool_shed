#!/usr/bin/env python3
"""Status and compatibility smoke checks for Tool Shed's opt-in Codex App Server path."""

from __future__ import annotations

import sys as _runtime_sys

_runtime_sys.dont_write_bytecode = True

import argparse
import hashlib
import json
import os
import re
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any

try:
    from scripts.codex_app_server import AppServerError, AuthenticationError
    from scripts.codex_cli_resolver import (
        CodexCliResolver,
        CodexQualificationState,
        CodexReadiness,
    )
    from scripts.codex_qualification_cache import (
        QualificationCache,
        QualificationCacheError,
        build_qualification_identity,
    )
    from scripts.codex_execution import (
        ApprovalBridge,
        CodexExecutionAdapter,
        ModelPolicy,
        ModelPolicyError,
        default_telemetry_path,
        flatten_token_usage,
        sandbox_policy,
        sanitized_probe,
    )
    from scripts.codex_orchestration import AppServerFeatureConfig, FeatureConfigError
except ModuleNotFoundError:  # Direct execution: python scripts/codex_app_server_compatibility.py
    from codex_app_server import AppServerError, AuthenticationError  # type: ignore[no-redef]
    from codex_cli_resolver import (  # type: ignore[no-redef]
        CodexCliResolver,
        CodexQualificationState,
        CodexReadiness,
    )
    from codex_qualification_cache import (  # type: ignore[no-redef]
        QualificationCache,
        QualificationCacheError,
        build_qualification_identity,
    )
    from codex_execution import (  # type: ignore[no-redef]
        ApprovalBridge,
        CodexExecutionAdapter,
        ModelPolicy,
        ModelPolicyError,
        default_telemetry_path,
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


CODEX_VERSION_PATTERN = re.compile(
    r"^(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)(?:[-+][0-9A-Za-z.-]+)?$"
)


def codex_version_core(version: str | None) -> tuple[int, int, int] | None:
    """Parse the numeric Codex release core while accepting prerelease suffixes."""

    if not isinstance(version, str):
        return None
    match = CODEX_VERSION_PATTERN.fullmatch(version)
    if match is None:
        return None
    return tuple(int(match.group(name)) for name in ("major", "minor", "patch"))


def codex_version_at_least(version: str | None, minimum: str) -> bool:
    parsed = codex_version_core(version)
    floor = codex_version_core(minimum)
    if floor is None:
        raise CompatibilityError(f"invalid minimum Codex version: {minimum}")
    return parsed is not None and parsed >= floor


def _workspace_snapshot(root: Path) -> dict[str, dict[str, Any]]:
    """Capture a compact content and metadata fingerprint for a disposable tree."""

    snapshot: dict[str, dict[str, Any]] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        metadata = path.lstat()
        if path.is_symlink():
            snapshot[relative] = {
                "kind": "symlink",
                "target": os.readlink(path),
                "mode": metadata.st_mode & 0o777,
            }
        elif path.is_dir():
            snapshot[relative] = {
                "kind": "directory",
                "mode": metadata.st_mode & 0o777,
            }
        elif path.is_file():
            snapshot[relative] = {
                "kind": "file",
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "size": metadata.st_size,
                "mode": metadata.st_mode & 0o777,
            }
        else:
            snapshot[relative] = {"kind": "other", "mode": metadata.st_mode & 0o777}
    return snapshot


def negotiate_read_only_permission(
    adapter: CodexExecutionAdapter, cwd: Path
) -> dict[str, Any]:
    """Prefer the experimental named read-only profile, or validate legacy fallback."""

    try:
        profiles = adapter.client.list_permission_profiles(cwd=cwd)
    except AppServerError as error:
        details = error.details if isinstance(error.details, dict) else {}
        message = str(details.get("message") or error).lower()
        if details.get("code") == -32601 or "method not found" in message:
            return {
                "mode": "legacy_sandbox_policy",
                "permission_profile": None,
                "profile_api_supported": False,
                "reason": "permissionProfile/list is unavailable; validated legacy read-only policy",
            }
        raise
    allowed = {
        str(item.get("id"))
        for item in profiles
        if item.get("allowed") is True and isinstance(item.get("id"), str)
    }
    if ":read-only" not in allowed:
        raise AppServerError(
            "Codex app-server exposes permission profiles but no allowed :read-only profile",
            details={"allowed_profiles": sorted(allowed)},
            kind="read_only_permission_profile_unavailable",
        )
    return {
        "mode": "named_permission_profile",
        "permission_profile": ":read-only",
        "profile_api_supported": True,
        "allowed_profiles": sorted(allowed),
    }


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
        if record.get("status") == "unqualified" and (
            not isinstance(record.get("evidence"), str)
            or not str(record.get("evidence")).strip()
        ):
            raise CompatibilityError(
                f"unqualified Codex {version} requires reviewed evidence"
            )
        normalized.append(dict(record))
    return normalized


def qualification_for_version(
    records: list[dict[str, Any]], version: str | None
) -> dict[str, Any] | None:
    return next((record for record in records if record.get("codex_version") == version), None)


def resolve_codex_cli(
    codex: str | None,
    records: list[dict[str, Any]],
    minimum_version: str = "0.146.0",
):
    """Resolve once for a reporting or execution operation.

    ``None`` deliberately means bounded discovery; a supplied ``--codex`` value
    remains the resolver's authoritative override.
    """

    return CodexCliResolver().resolve(
        executable_override=codex,
        is_qualified=lambda version: bool(
            (record := qualification_for_version(records, version))
            and record.get("status") in {"qualified", "qualified_with_blockers"}
        ),
        minimum_version=minimum_version,
    )


def _compatibility_for_resolution(resolution, record: dict[str, Any] | None) -> str:
    if resolution.readiness is CodexReadiness.NOT_FOUND:
        return "not_installed_or_not_found"
    if resolution.readiness is CodexReadiness.INVALID_EXECUTABLE:
        return "invalid_executable"
    if resolution.readiness is CodexReadiness.APP_SERVER_UNAVAILABLE:
        return "app_server_unavailable"
    return str(record.get("status")) if record else "unqualified_version"


def write_executable_identity_matches(
    record: dict[str, Any] | None,
    executable: Path | None,
) -> bool:
    """Enforce an optional project-scoped workspace-write executable digest."""

    qualification = (record or {}).get("workspace_write_qualification")
    if not isinstance(qualification, dict):
        return True
    expected = qualification.get("executable_sha256")
    if expected is None:
        return True
    if (
        not isinstance(expected, str)
        or re.fullmatch(r"[0-9A-Fa-f]{64}", expected) is None
        or executable is None
    ):
        return False
    try:
        actual = hashlib.sha256(executable.read_bytes()).hexdigest()
    except OSError:
        return False
    return actual == expected.lower()


def _recorded_role_usable(
    *,
    role: str,
    record: dict[str, Any] | None,
    config: AppServerFeatureConfig,
    policy: ModelPolicy,
    installed: str | None,
    executable: Path | None = None,
) -> bool:
    if not record or record.get("status") not in {"qualified", "qualified_with_blockers"}:
        return False
    selected = policy.select(role)
    route = (record.get("routing") or {}).get(role)
    usable = bool(
        config.role_enabled(role)
        and installed in config.qualified_codex_versions
        and isinstance(route, dict)
        and route.get("qualified") is True
        and route.get("model") == selected.model
        and route.get("reasoning") == selected.reasoning
    )
    if role == "camp_execution":
        usable = bool(
            usable
            and record.get("workspace_writing") is True
            and installed in config.qualified_write_codex_versions
            and write_executable_identity_matches(record, executable)
        )
    return usable


def _status_qualification_state(
    resolution, record: dict[str, Any] | None
) -> str:
    if record and record.get("status") in {"qualified", "qualified_with_blockers"}:
        return "exact-qualified"
    if record and record.get("status") == "unqualified":
        return "unsafe-blocked"
    mapping = {
        CodexQualificationState.DIRTY_QUALIFYING: "dirty-qualifying",
        CodexQualificationState.BELOW_MINIMUM: "below-minimum",
        CodexQualificationState.APP_SERVER_UNAVAILABLE: "transient-fallback",
        CodexQualificationState.INVALID: "unsafe-blocked",
    }
    return mapping.get(resolution.qualification_state, "unsafe-blocked")


def _runtime_failure_classification(error: Exception) -> str:
    if isinstance(error, (AuthenticationError, ModelPolicyError)):
        return "transient"
    if isinstance(error, AppServerError) and error.kind == "read_only_permission_profile_unavailable":
        return "unsafe"
    message = str(error).lower()
    transient_markers = (
        "authentication",
        "network",
        "timeout",
        "timed out",
        "temporarily",
        "unavailable",
        "service",
        "rate limit",
        "model catalog",
    )
    return "transient" if any(marker in message for marker in transient_markers) else "unknown"


def status_report(
    *,
    codex: str | None = None,
    config_path: Path = DEFAULT_CONFIG,
    policy_path: Path = DEFAULT_POLICY,
    qualifications_path: Path = DEFAULT_QUALIFICATIONS,
    qualification_cache_path: Path | None = None,
    operator_trust: bool = False,
    strict_certification: bool = False,
) -> dict[str, Any]:
    config = AppServerFeatureConfig.load(config_path)
    policy = ModelPolicy.load(policy_path)
    certification_warning: str | None = None
    try:
        records = load_qualifications(qualifications_path)
    except CompatibilityError as error:
        if not operator_trust or strict_certification:
            raise
        records = []
        certification_warning = f"registry-unavailable:{type(error).__name__}"
    resolution = resolve_codex_cli(
        codex, records, config.minimum_dirty_read_codex_version
    )
    installed = resolution.version
    record = qualification_for_version(records, installed)
    planning = policy.select("planning")
    verification = policy.select("verification")
    camp_execution = policy.select("camp_execution")
    configured_versions = config.qualified_codex_versions
    configured_qualified = ", ".join(configured_versions)
    qualification_state = _status_qualification_state(resolution, record)
    certification_state = (
        "exact-certified"
        if record and record.get("status") in {"qualified", "qualified_with_blockers"}
        else "explicitly-unqualified"
        if record and record.get("status") == "unqualified"
        else "not-certified"
    )
    cache_status: dict[str, Any] = {
        "status": "not-applicable",
        "source": "user-local-cache",
        "invalidation_reason": None,
        "record": None,
    }
    if (
        not operator_trust
        and record is None
        and resolution.app_server_available
        and resolution.executable is not None
        and installed is not None
        and qualification_state == "dirty-qualifying"
    ):
        try:
            identity = build_qualification_identity(
                executable=resolution.executable,
                codex_version=installed,
                config_path=config_path,
                model_policy_path=policy_path,
            )
            cache = QualificationCache(
                qualification_cache_path,
                max_age_seconds=config.dirty_read_cache_max_age_seconds,
            )
            lookup = cache.lookup(identity)
            cache_status = lookup.as_dict()
            if lookup.status == "hit" and lookup.record:
                qualification_state = (
                    "dirty-qualified"
                    if lookup.record.get("state") == "qualified"
                    else "unsafe-blocked"
                )
        except (OSError, QualificationCacheError) as error:
            cache_status = {
                "status": "unavailable",
                "source": "user-local-cache",
                "invalidation_reason": type(error).__name__,
                "record": None,
            }
    denylisted = bool(record and record.get("status") == "unqualified")
    if operator_trust and not strict_certification and denylisted:
        blockers = ["selected Codex version is explicitly denylisted by reviewed evidence"]
    elif operator_trust and not strict_certification:
        blockers = [] if resolution.app_server_available else [
            resolution.error or "selected Codex App Server startup probe failed"
        ]
    elif record:
        blockers = list(record.get("known_blockers") or [])
    elif qualification_state == "dirty-qualified":
        blockers = list((cache_status.get("record") or {}).get("safe_blockers") or [])
        blockers.append("workspace-write is not qualified")
    elif (
        qualification_state == "unsafe-blocked"
        and (cache_status.get("record") or {}).get("state") == "unsafe_denied"
    ):
        blockers = ["reviewed unsafe dirty-qualification denial is cached"]
    elif qualification_state == "dirty-qualifying":
        blockers = [
            "read-only roles require live dirty qualification",
            "workspace-write is not qualified",
        ]
    elif qualification_state == "below-minimum":
        blockers = ["selected Codex is below the minimum dirty-read version"]
    else:
        blockers = [resolution.error or "selected Codex is not qualified"]
    savings = record.get("qualified_savings") if record else None
    role_selections = {
        "planning": planning,
        "verification": verification,
        "camp_execution": camp_execution,
    }
    enabled_roles: dict[str, Any] = {}
    for role in ("planning", "verification"):
        selected = role_selections[role]
        exact_usable = _recorded_role_usable(
            role=role,
            record=record,
            config=config,
            policy=policy,
            installed=installed,
            executable=resolution.executable,
        )
        dirty_usable = bool(
            qualification_state == "dirty-qualified" and config.role_enabled(role)
        )
        operator_usable = bool(
            operator_trust
            and not strict_certification
            and not denylisted
            and config.role_enabled(role)
        )
        if resolution.app_server_available and (operator_usable or exact_usable or dirty_usable):
            enabled_roles[role] = {
                "model": selected.model,
                "reasoning": selected.reasoning,
                **(
                    {
                        "admission": "operator-runtime",
                        "certification": certification_state,
                    }
                    if operator_usable
                    else {"qualification": qualification_state}
                ),
            }
    camp_enabled = bool(
        resolution.app_server_available
        and (
            (
                operator_trust
                and not strict_certification
                and not denylisted
                and config.role_enabled("camp_execution")
            )
            or _recorded_role_usable(
                role="camp_execution",
                record=record,
                config=config,
                policy=policy,
                installed=installed,
                executable=resolution.executable,
            )
        )
    )
    if camp_enabled:
        enabled_roles["camp_execution"] = {
            "model": camp_execution.model,
            "reasoning": camp_execution.reasoning,
            "sandbox": "workspace-write",
            "scope": "explicit paths with Git mutation journal",
            **(
                {
                    "admission": "operator-runtime",
                    "certification": certification_state,
                }
                if operator_trust and not strict_certification
                else {"qualification": "exact-qualified"}
            ),
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
        "minimum_dirty_read_codex": config.minimum_dirty_read_codex_version,
        "dirty_read_eligible": codex_version_at_least(
            installed, config.minimum_dirty_read_codex_version
        ),
        "qualification_state": qualification_state,
        "write_qualification_state": (
            "exact-qualified"
            if camp_enabled
            and certification_state == "exact-certified"
            and not operator_trust
            else "write-not-qualified"
        ),
        "compatibility": (
            "denylisted_unsafe_behavior"
            if operator_trust and not strict_certification and denylisted
            else
            "runtime_candidate"
            if operator_trust and not strict_certification and resolution.app_server_available
            else "dirty_qualified"
            if qualification_state == "dirty-qualified"
            else _compatibility_for_resolution(resolution, record)
        ),
        "runtime_readiness": (
            "startup-probed" if resolution.app_server_available else "blocked"
        ),
        "observed_safety": "denylisted" if denylisted else "clear",
        "operator_trust": operator_trust and not strict_certification,
        "certification_required": strict_certification,
        "certification_state": certification_state,
        "certification_warning": certification_warning,
        "version_warning": (
            None
            if (
                record and record.get("status") in {"qualified", "qualified_with_blockers"}
            ) or qualification_state == "dirty-qualified"
            else (
                "Codex CLI is not detected."
                if installed is None
                else f"Selected Codex {installed} is {qualification_state}."
            )
        ),
        "codex_cli": (
            "INVALID" if resolution.readiness is CodexReadiness.INVALID_EXECUTABLE
            else ("AVAILABLE" if resolution.found else "NOT FOUND")
        ),
        "codex_discovery": (
            "OpenAI VS Code extension" if resolution.source and resolution.source.value == "openai_vscode_extension"
            else (resolution.source.value.replace("_", " ").title() if resolution.source else "not found")
        ),
        "codex_executable": str(resolution.executable) if resolution.executable else None,
        "app_server_available": resolution.app_server_available,
        "codex_readiness": resolution.readiness.value,
        "codex_error": resolution.error,
        "codex_inventory": [candidate.as_dict() for candidate in resolution.inventory],
        "qualification_cache": cache_status,
        "enabled_roles": enabled_roles,
        "dirty_qualifying_roles": (
            ["planning", "verification"]
            if qualification_state == "dirty-qualifying" and resolution.app_server_available
            else []
        ),
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
        f"Codex CLI: {report['codex_cli']}",
        f"Discovery: {report['codex_discovery']}",
        f"Executable: {report.get('codex_executable') or 'not detected'}",
        f"Installed Codex: {report.get('installed_codex') or 'not detected'}",
        f"App Server: {'AVAILABLE' if report['app_server_available'] else 'UNAVAILABLE'}",
        f"Qualified Codex: {report['qualified_codex']}",
        f"Minimum dirty-read Codex: {report['minimum_dirty_read_codex']}",
        f"Qualification state: {report['qualification_state']}",
        f"Write qualification: {report['write_qualification_state']}",
        f"Qualification cache: {report['qualification_cache']['status']} "
        f"from {report['qualification_cache']['source']} "
        f"({report['qualification_cache'].get('invalidation_reason') or 'current'})",
        f"Compatibility: {str(report['compatibility']).replace('_', ' ')}",
        "Experimental: unsupported for production workloads",
        "",
        "Enabled roles:",
    ]
    for role in ("planning", "verification", "camp_execution"):
        item = roles.get(role)
        if item:
            detail = f"  {role.replace('_', ' ')} {item['model']} / {item['reasoning']}"
            if item.get("scope"):
                detail += f" ({item['scope']})"
            lines.append(detail)
    if not roles:
        lines.append("  none")
    if report.get("dirty_qualifying_roles"):
        lines.extend(
            [
                "",
                "Dirty qualification available:",
                *(f"  {role}" for role in report["dirty_qualifying_roles"]),
            ]
        )
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
    codex: str | None = None,
    cwd: Path = ROOT,
    config_path: Path = DEFAULT_CONFIG,
    policy_path: Path = DEFAULT_POLICY,
    qualifications_path: Path = DEFAULT_QUALIFICATIONS,
    telemetry_path: Path | None = None,
    timeout: float = 120.0,
    retest_restricted_read: bool = False,
    dirty_qualification: bool = False,
) -> dict[str, Any]:
    source_workspace = cwd.expanduser().resolve()
    if not source_workspace.is_dir():
        raise CompatibilityError(f"smoke workspace is not a directory: {source_workspace}")
    config = AppServerFeatureConfig.load(config_path)
    policy = ModelPolicy.load(policy_path)
    records = load_qualifications(qualifications_path)
    resolution = resolve_codex_cli(
        codex, records, config.minimum_dirty_read_codex_version
    )
    resolved_codex = str(resolution.executable) if resolution.executable else None
    installed = resolution.version
    record = qualification_for_version(records, installed)
    configured_versions = config.qualified_codex_versions
    configured_version = ", ".join(configured_versions)
    version_changed = installed not in configured_versions
    minimum_dirty_read = config.minimum_dirty_read_codex_version
    version_eligible = codex_version_at_least(installed, minimum_dirty_read)
    checks: list[dict[str, Any]] = [
        check(
            "codex_cli_resolution",
            resolution.app_server_available,
            resolution.as_dict(),
            blocker=not resolution.app_server_available,
        ),
        check("codex_version_detection", installed is not None, installed or "not detected"),
        check(
            "minimum_dirty_read_version",
            version_eligible,
            {
                "installed": installed,
                "minimum": minimum_dirty_read,
                "prerelease_uses_numeric_release_core": True,
            },
        ),
        check(
            "qualification_record",
            record is not None or (dirty_qualification and version_eligible),
            (
                record.get("status")
                if record
                else (
                    "unseen eligible version accepted for bounded dirty read qualification"
                    if dirty_qualification and version_eligible
                    else f"no record for {installed}"
                )
            ),
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
    permission_negotiation: dict[str, Any] | None = None
    server_state: dict[str, Any] | None = None
    try:
        if not resolution.app_server_available or resolved_codex is None:
            detail = resolution.error or resolution.readiness.value.replace("_", " ")
            raise AppServerError(f"Codex App Server is unavailable: {detail}", kind="codex_not_ready")
        with tempfile.TemporaryDirectory(prefix="tool-shed-app-server-smoke-") as temporary_name:
            smoke_cwd = Path(temporary_name)
            (smoke_cwd / "AGENTS.md").write_text(
                "# Compatibility smoke\n\nRead-only checks only. Do not use tools.\n",
                encoding="utf-8",
            )
            workspace_before = _workspace_snapshot(smoke_cwd)
            with CodexExecutionAdapter(
                policy=policy,
                codex=resolved_codex,
                timeout=timeout,
                telemetry_path=telemetry,
            ) as adapter:
                probe = sanitized_probe(adapter)
                if dirty_qualification:
                    permission_negotiation = negotiate_read_only_permission(adapter, smoke_cwd)
                    checks.append(
                        check(
                            "read_only_permission_negotiation",
                            True,
                            permission_negotiation,
                        )
                    )
                permission_profile = (
                    str(permission_negotiation["permission_profile"])
                    if permission_negotiation
                    and isinstance(permission_negotiation.get("permission_profile"), str)
                    else None
                )
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
                    permission_profile=permission_profile,
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
                    permission_profile=permission_profile,
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
                    "planning",
                    cwd=smoke_cwd,
                    sandbox="read-only",
                    permission_profile=permission_profile,
                    ephemeral=False,
                )
                turn_id = adapter.client.start_turn(
                    str(thread["id"]),
                    (
                        "ACTIVE_CANCELLATION_PROBE: remain active while reasoning through a long "
                        "read-only compatibility checklist. Do not use tools or write files."
                    ),
                    model=selection.model,
                    effort=selection.reasoning,
                    cwd=smoke_cwd,
                    approval_policy="never",
                    sandbox_policy=sandbox_policy("read-only", smoke_cwd),
                    permission_profile=permission_profile,
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
                checks.append(
                    check(
                        "cancellation_acknowledgement",
                        bool(cancellation["diagnostics"].get("cancel_acknowledged")),
                        {
                            "acknowledged": cancellation["diagnostics"].get(
                                "cancel_acknowledged"
                            ),
                            "safe_reconciliation": cancellation_safe,
                        },
                        blocker=(
                            cancellation_safe
                            and not bool(
                                cancellation["diagnostics"].get("cancel_acknowledged")
                            )
                        ),
                    )
                )
                should_retest_restricted = (
                    retest_restricted_read or version_changed or dirty_qualification
                )
                if dirty_qualification:
                    restricted_result = {
                        "retested": True,
                        "accepted": True,
                        "mode": permission_negotiation["mode"] if permission_negotiation else None,
                        "permission_profile": permission_profile,
                        "validated_by": "planning, verification, and cancellation turns",
                    }
                elif should_retest_restricted:
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
                no_mutation_events = not planning.mutation_events and not verification.mutation_events
                checks.append(
                    check(
                        "read_only_no_mutation_events",
                        no_mutation_events,
                        {
                            "planning": len(planning.mutation_events),
                            "verification": len(verification.mutation_events),
                        },
                    )
                )
                server_state = adapter.client.process_state()
            workspace_after = _workspace_snapshot(smoke_cwd)
            checks.append(
                check(
                    "read_only_workspace_unchanged",
                    workspace_after == workspace_before,
                    {
                        "unchanged": workspace_after == workspace_before,
                        "before_entries": len(workspace_before),
                        "after_entries": len(workspace_after),
                    },
                )
            )
    except (AppServerError, AuthenticationError, ModelPolicyError) as error:
        runtime_classification = _runtime_failure_classification(error)
        checks.append(
            check(
                "app_server_runtime",
                False,
                {
                    "error": str(error),
                    "kind": getattr(error, "kind", None),
                    "classification": runtime_classification,
                },
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
            blocker=dirty_qualification and not baseline_ok,
        )
    )
    failed = [item for item in checks if item["status"] == "fail"]
    blockers = [item for item in checks if item["status"] == "blocked"]
    safe_blocker_names = {
        "cancellation_acknowledgement",
        "tiny_operation_token_baseline",
    }
    safe_blockers = [
        item for item in blockers if item["name"] in safe_blocker_names
    ]
    fatal_failures: list[dict[str, Any]] = []
    transient_failures: list[dict[str, Any]] = []
    unknown_failures: list[dict[str, Any]] = []
    if dirty_qualification:
        for item in checks:
            if item["status"] == "pass" or item["name"] in safe_blocker_names:
                continue
            if (
                item["name"] == "app_server_runtime"
                and isinstance(item.get("detail"), dict)
                and item["detail"].get("classification") == "transient"
            ):
                transient_failures.append(item)
            elif (
                item["name"] == "app_server_runtime"
                and isinstance(item.get("detail"), dict)
                and item["detail"].get("classification") == "unknown"
            ):
                unknown_failures.append(item)
            else:
                fatal_failures.append(item)
        if not version_eligible:
            outcome = "ineligible"
        elif transient_failures:
            outcome = "unqualified_transient"
        elif unknown_failures:
            outcome = "unqualified_unknown"
        elif fatal_failures:
            outcome = "unqualified_fatal"
        elif safe_blockers:
            outcome = "qualified_with_blockers"
        else:
            outcome = "qualified"
    elif installed is None or record is None or failed:
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
        "qualification_mode": "dirty_read" if dirty_qualification else "exact_record_smoke",
        "minimum_dirty_read_codex": minimum_dirty_read,
        "version_eligible": version_eligible,
        "outcome": outcome,
        "checks": checks,
        "safe_blockers": [item["name"] for item in safe_blockers],
        "fatal_failures": [item["name"] for item in fatal_failures],
        "transient_failures": [item["name"] for item in transient_failures],
        "unknown_failures": [item["name"] for item in unknown_failures],
        "cacheable_unsafe": bool(fatal_failures) and not transient_failures and not unknown_failures,
        "permission_negotiation": permission_negotiation,
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
            "Continue the original explicit read-only request in this invocation."
            if dirty_qualification and outcome in {"qualified", "qualified_with_blockers"}
            else "Fail closed; inspect the classified dirty-qualification checks."
            if dirty_qualification
            else "Review smoke evidence and add a version-specific qualification record."
            if record is None
            else "Keep App Server opt-in until recorded blockers are cleared and requalified."
        ),
    }


def dirty_read_qualification_report(
    *,
    codex: str,
    cwd: Path = ROOT,
    config_path: Path = DEFAULT_CONFIG,
    policy_path: Path = DEFAULT_POLICY,
    qualifications_path: Path = DEFAULT_QUALIFICATIONS,
    telemetry_path: Path | None = None,
    timeout: float = 120.0,
) -> dict[str, Any]:
    """Run an ephemeral, non-writing qualification for one unseen eligible CLI."""

    return smoke_report(
        codex=codex,
        cwd=cwd,
        config_path=config_path,
        policy_path=policy_path,
        qualifications_path=qualifications_path,
        telemetry_path=telemetry_path,
        timeout=timeout,
        retest_restricted_read=True,
        dirty_qualification=True,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex", default=None)
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
