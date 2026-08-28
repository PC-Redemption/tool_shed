#!/usr/bin/env python3
"""Validate and resolve workspace-local Tool Shed work-level customization."""

from __future__ import annotations

import sys as _runtime_sys

_runtime_sys.dont_write_bytecode = True

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

try:
    from project_identity import ProjectIdentityError, target_capsule
except ModuleNotFoundError:  # Package import used by unit tests and embedders.
    from scripts.project_identity import ProjectIdentityError, target_capsule


CONFIG_RELATIVE = Path("work") / "tool-shed.yaml"
SCHEMA_VERSION = 1
LEVELS = ("work1", "work2", "work3", "work4", "work5")
ALIASES = {
    "work": "work2",
    "freeze": "work3",
    "push": "work4",
    "ship": "work5",
}
ROOT_KEYS = {
    "schema_version",
    "work_model",
    "development_target",
    "production_target",
    "work_levels",
}
LEVEL_KEYS = {"before", "run_default", "after"}
MAX_CONFIG_BYTES = 64 * 1024
MAX_ACTIONS_PER_PHASE = 32
MAX_ACTION_LENGTH = 1000


class WorkLevelConfigError(ValueError):
    """Raised when work/tool-shed.yaml does not match the portable contract."""


def _field(line: str, line_number: int) -> tuple[str, str]:
    if ":" not in line:
        raise WorkLevelConfigError(f"line {line_number}: expected 'key: value'")
    key, value = line.split(":", 1)
    key = key.strip()
    if not re.fullmatch(r"[a-z][a-z0-9_]*", key):
        raise WorkLevelConfigError(f"line {line_number}: invalid key {key!r}")
    return key, value.strip()


def _scalar(value: str, line_number: int) -> object:
    if not value:
        raise WorkLevelConfigError(f"line {line_number}: missing scalar value")
    if value == "[]":
        return []
    if value in {"true", "false"}:
        return value == "true"
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    if value.startswith('"') or value.endswith('"'):
        if not (value.startswith('"') and value.endswith('"')):
            raise WorkLevelConfigError(f"line {line_number}: unterminated double-quoted value")
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as error:
            raise WorkLevelConfigError(
                f"line {line_number}: invalid double-quoted value: {error.msg}"
            ) from error
        if not isinstance(parsed, str):
            raise WorkLevelConfigError(f"line {line_number}: expected a string")
        return parsed
    if value.startswith("'") or value.endswith("'"):
        if not (value.startswith("'") and value.endswith("'")):
            raise WorkLevelConfigError(f"line {line_number}: unterminated single-quoted value")
        return value[1:-1].replace("''", "'")
    if value[0] in "[{" or value[-1] in "]}":
        raise WorkLevelConfigError(
            f"line {line_number}: inline collections are unsupported except []"
        )
    return value


def parse_config(text: str) -> dict[str, Any]:
    if "\0" in text:
        raise WorkLevelConfigError("configuration contains a NUL byte")
    root: dict[str, Any] = {}
    work_levels: dict[str, dict[str, Any]] | None = None
    current_level: str | None = None
    current_list: str | None = None
    in_work_levels = False

    for line_number, raw in enumerate(text.splitlines(), start=1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if "\t" in raw:
            raise WorkLevelConfigError(f"line {line_number}: tabs are not allowed")
        indent = len(raw) - len(raw.lstrip(" "))
        content = raw[indent:]
        if indent == 0:
            key, value = _field(content, line_number)
            if key not in ROOT_KEYS:
                raise WorkLevelConfigError(f"line {line_number}: unknown root key {key!r}")
            if key in root:
                raise WorkLevelConfigError(f"line {line_number}: duplicate root key {key!r}")
            current_level = None
            current_list = None
            in_work_levels = key == "work_levels"
            if key == "work_levels":
                if value:
                    raise WorkLevelConfigError(
                        f"line {line_number}: work_levels must be a nested mapping"
                    )
                work_levels = {}
                root[key] = work_levels
            else:
                root[key] = _scalar(value, line_number)
            continue
        if indent == 2:
            if not in_work_levels or work_levels is None:
                raise WorkLevelConfigError(
                    f"line {line_number}: level entries must be nested under work_levels"
                )
            key, value = _field(content, line_number)
            if key not in LEVELS:
                raise WorkLevelConfigError(f"line {line_number}: unknown work level {key!r}")
            if value:
                raise WorkLevelConfigError(
                    f"line {line_number}: {key} must be a nested mapping"
                )
            if key in work_levels:
                raise WorkLevelConfigError(f"line {line_number}: duplicate work level {key!r}")
            work_levels[key] = {}
            current_level = key
            current_list = None
            continue
        if indent == 4:
            if work_levels is None or current_level is None:
                raise WorkLevelConfigError(
                    f"line {line_number}: level settings require a work-level entry"
                )
            key, value = _field(content, line_number)
            if key not in LEVEL_KEYS:
                raise WorkLevelConfigError(f"line {line_number}: unknown level key {key!r}")
            level = work_levels[current_level]
            if key in level:
                raise WorkLevelConfigError(
                    f"line {line_number}: duplicate {current_level}.{key} declaration"
                )
            if key in {"before", "after"}:
                if value and value != "[]":
                    raise WorkLevelConfigError(
                        f"line {line_number}: {current_level}.{key} must be a block list or []"
                    )
                level[key] = []
                current_list = key
            else:
                parsed = _scalar(value, line_number)
                if not isinstance(parsed, bool):
                    raise WorkLevelConfigError(
                        f"line {line_number}: {current_level}.run_default must be true or false"
                    )
                level[key] = parsed
                current_list = None
            continue
        if indent == 6:
            if work_levels is None or current_level is None or current_list is None:
                raise WorkLevelConfigError(
                    f"line {line_number}: action must follow a before or after declaration"
                )
            if not content.startswith("- "):
                raise WorkLevelConfigError(f"line {line_number}: expected '- action'")
            action = _scalar(content[2:].strip(), line_number)
            if not isinstance(action, str) or not action.strip():
                raise WorkLevelConfigError(f"line {line_number}: actions must be non-empty strings")
            if len(action) > MAX_ACTION_LENGTH:
                raise WorkLevelConfigError(
                    f"line {line_number}: action exceeds {MAX_ACTION_LENGTH} characters"
                )
            actions = work_levels[current_level][current_list]
            if len(actions) >= MAX_ACTIONS_PER_PHASE:
                raise WorkLevelConfigError(
                    f"line {line_number}: {current_level}.{current_list} exceeds "
                    f"{MAX_ACTIONS_PER_PHASE} actions"
                )
            actions.append(action.strip())
            continue
        raise WorkLevelConfigError(
            f"line {line_number}: unsupported indentation; use 0, 2, 4, or 6 spaces"
        )

    if root.get("schema_version") != SCHEMA_VERSION:
        raise WorkLevelConfigError(
            f"schema_version must equal {SCHEMA_VERSION}"
        )
    work_model = root.get("work_model")
    if work_model is not None and work_model not in {"combined", "split"}:
        raise WorkLevelConfigError("work_model must be combined or split")
    for target in ("development_target", "production_target"):
        value = root.get(target)
        if value is not None and (not isinstance(value, str) or not value.strip()):
            raise WorkLevelConfigError(f"{target} must be a non-empty string")
    for level, settings in (work_levels or {}).items():
        settings.setdefault("before", [])
        settings.setdefault("run_default", True)
        settings.setdefault("after", [])
        if not settings["run_default"] and not settings["before"] and not settings["after"]:
            raise WorkLevelConfigError(
                f"{level} disables its default but declares no replacement actions"
            )
    return root


def load_config(workspace: Path) -> tuple[Path, dict[str, Any] | None]:
    path = workspace / CONFIG_RELATIVE
    if not path.exists():
        return path, None
    if path.is_symlink() or not path.is_file():
        raise WorkLevelConfigError(f"{CONFIG_RELATIVE.as_posix()} must be a regular file")
    if path.stat().st_size > MAX_CONFIG_BYTES:
        raise WorkLevelConfigError(
            f"{CONFIG_RELATIVE.as_posix()} exceeds {MAX_CONFIG_BYTES} bytes"
        )
    try:
        return path, parse_config(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError as error:
        raise WorkLevelConfigError(
            f"{CONFIG_RELATIVE.as_posix()} must be UTF-8 text"
        ) from error


def validate_workspace_config(workspace: Path) -> dict[str, Any]:
    _, config = load_config(workspace)
    return {
        "valid": True,
        "configured": config is not None,
        "source": CONFIG_RELATIVE.as_posix() if config is not None else None,
        "schema_version": config.get("schema_version") if config else None,
        "work_model": config.get("work_model") if config else None,
        "configured_levels": sorted((config or {}).get("work_levels", {})),
    }


def canonical_route(value: str) -> tuple[str, str]:
    requested = value.strip().lower()
    if requested.startswith("ts:"):
        requested = requested[3:].strip()
    requested = requested.split(maxsplit=1)[0] if requested else ""
    canonical = ALIASES.get(requested, requested)
    if canonical not in LEVELS:
        choices = ", ".join((*LEVELS, *ALIASES))
        raise WorkLevelConfigError(f"unknown work-level route {value!r}; choose from: {choices}")
    return requested, canonical


def resolve_workspace_level(workspace: Path, route: str) -> dict[str, Any]:
    _, config = load_config(workspace)
    requested, canonical = canonical_route(route)
    levels = (config or {}).get("work_levels", {})
    settings = levels.get(canonical, {})
    before = list(settings.get("before", []))
    run_default = settings.get("run_default", True)
    after = list(settings.get("after", []))
    order: list[dict[str, Any]] = [
        {"phase": "before", "position": index + 1, "action": action}
        for index, action in enumerate(before)
    ]
    order.append({"phase": "default", "enabled": run_default})
    order.extend(
        {"phase": "after", "position": index + 1, "action": action}
        for index, action in enumerate(after)
    )
    return {
        "valid": True,
        "source": CONFIG_RELATIVE.as_posix() if config is not None else None,
        "requested_route": requested,
        "canonical_level": canonical,
        "alias_resolved": requested != canonical,
        "configured": canonical in levels,
        "work_model": config.get("work_model") if config else None,
        "development_target": config.get("development_target") if config else None,
        "production_target": config.get("production_target") if config else None,
        "customization_scope": "selected-canonical-endpoint",
        "before": before,
        "run_default": run_default,
        "after": after,
        "execution_order": order,
        "failure_policy": "stop-on-first-failure",
        "safety_policy": "configured actions cannot bypass scope, credentials, approvals, or safety controls",
        "project": target_capsule(workspace, operation=f"work-level:{canonical}"),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", default=".", help="Workspace root. Defaults to current directory.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate", help="Validate work/tool-shed.yaml when present.")
    validate.add_argument("--json", action="store_true")
    resolve = subparsers.add_parser("resolve", help="Resolve a work level or alias into its execution envelope.")
    resolve.add_argument("route")
    resolve.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    workspace = Path(args.workspace).expanduser().resolve()
    try:
        payload = (
            validate_workspace_config(workspace)
            if args.command == "validate"
            else resolve_workspace_level(workspace, args.route)
        )
    except (WorkLevelConfigError, ProjectIdentityError) as error:
        payload = {"valid": False, "error": str(error), "source": CONFIG_RELATIVE.as_posix()}
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(f"Work-level configuration invalid: {error}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif args.command == "validate":
        state = "valid" if payload["configured"] else "absent; standard work-level behavior applies"
        print(f"Work-level configuration: {state}")
    else:
        print(f"{payload['requested_route']} -> {payload['canonical_level']}")
        for item in payload["execution_order"]:
            if item["phase"] == "default":
                print(f"default: {'run' if item['enabled'] else 'suppressed'}")
            else:
                print(f"{item['phase']} {item['position']}: {item['action']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
