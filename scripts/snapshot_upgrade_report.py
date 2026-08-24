#!/usr/bin/env python3
"""Render one protected snapshot-upgrade transaction as a sanitized issue draft."""

from __future__ import annotations

import argparse
import json
import math
import os
import platform
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from snapshot_upgrade_state import (
    ISSUE_CODE_REGISTRY,
    SnapshotStateError,
    issue_code_for,
    state_root,
)


REPORT_SCHEMA_VERSION = 1
MAX_REPORT_BYTES = 128 * 1024
TRANSACTION_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
SAFE_VALUE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+:/-]{0,255}$")
STAGE_NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
COMMIT = re.compile(r"^[0-9a-f]{7,40}$")
VERSION = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
TAG = re.compile(r"^v[0-9]+\.[0-9]+\.[0-9]+$")

TOP_LEVEL_KEYS = {
    "schema_version",
    "kind",
    "transaction_id",
    "state",
    "started_at",
    "updated_at",
    "elapsed_seconds",
    "stage_durations_seconds",
    "platform",
    "architecture",
    "python",
    "failed_stage",
    "error_class",
    "rollback_outcome",
    "issue_code",
    "updater",
    "release",
}
FINAL_STATES = {"installed", "current", "prune-preview", "failed"}
ERROR_CLASSES = {
    "concurrent-upgrade",
    "timeout",
    "network",
    "integrity",
    "validation",
    "permission",
    "filesystem",
    "unknown",
}
ROLLBACK_OUTCOMES = {"not-required", "restored", "not-started", "not-restored"}


class UpgradeReportError(RuntimeError):
    pass


def _bounded_string(value: object, name: str, *, maximum: int = 256) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum:
        raise UpgradeReportError(f"transaction {name} must be a bounded non-empty string")
    return value


def _safe_value(value: object, name: str) -> str:
    text = _bounded_string(value, name)
    if not SAFE_VALUE.fullmatch(text):
        raise UpgradeReportError(f"transaction {name} contains unsupported characters")
    return text


def _timestamp(value: object, name: str) -> str:
    text = _bounded_string(value, name, maximum=64)
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as error:
        raise UpgradeReportError(f"transaction {name} is not an ISO-8601 timestamp") from error
    return text


def _nonnegative_number(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise UpgradeReportError(f"transaction {name} must be numeric")
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise UpgradeReportError(f"transaction {name} must be finite and nonnegative")
    return number


def _exact_keys(payload: dict[str, Any], allowed: set[str], name: str) -> None:
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise UpgradeReportError(f"transaction {name} contains unsupported fields")


def _validate_updater(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise UpgradeReportError("transaction updater identity is missing")
    _exact_keys(value, {"schema_version", "shed_version", "protocol", "script_sha256"}, "updater")
    if value.get("schema_version") != 1:
        raise UpgradeReportError("transaction updater schema is unsupported")
    version = _bounded_string(value.get("shed_version"), "updater.shed_version", maximum=32)
    if not VERSION.fullmatch(version):
        raise UpgradeReportError("transaction updater version is invalid")
    protocol = value.get("protocol")
    if isinstance(protocol, bool) or not isinstance(protocol, int) or protocol < 1:
        raise UpgradeReportError("transaction updater protocol is invalid")
    digest = _bounded_string(value.get("script_sha256"), "updater.script_sha256", maximum=64)
    if not SHA256.fullmatch(digest):
        raise UpgradeReportError("transaction updater digest is invalid")
    return dict(value)


def _validate_release(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise UpgradeReportError("transaction release identity must be an object")
    _exact_keys(
        value,
        {"selected_tag", "selected_version", "content_commit", "release_validation"},
        "release",
    )
    result: dict[str, Any] = {}
    if "selected_tag" in value:
        tag = _bounded_string(value["selected_tag"], "release.selected_tag", maximum=32)
        if not TAG.fullmatch(tag):
            raise UpgradeReportError("transaction selected release tag is invalid")
        result["selected_tag"] = tag
    if "selected_version" in value:
        version = _bounded_string(
            value["selected_version"], "release.selected_version", maximum=32
        )
        if not VERSION.fullmatch(version):
            raise UpgradeReportError("transaction selected release version is invalid")
        result["selected_version"] = version
    if "content_commit" in value:
        commit = _bounded_string(value["content_commit"], "release.content_commit", maximum=40)
        if not COMMIT.fullmatch(commit):
            raise UpgradeReportError("transaction release commit is invalid")
        result["content_commit"] = commit
    if "release_validation" in value:
        validation = value["release_validation"]
        if not isinstance(validation, dict):
            raise UpgradeReportError("transaction release validation must be an object")
        _exact_keys(validation, {"mode", "selection_reason", "cache", "identity"}, "release validation")
        mode = _safe_value(validation.get("mode"), "release_validation.mode")
        reason = _safe_value(
            validation.get("selection_reason"), "release_validation.selection_reason"
        )
        cache = _safe_value(validation.get("cache"), "release_validation.cache")
        if cache not in {"hit", "stored"}:
            raise UpgradeReportError("transaction release validation cache state is invalid")
        identity = validation.get("identity")
        if not isinstance(identity, dict):
            raise UpgradeReportError("transaction release validation identity is missing")
        _exact_keys(
            identity,
            {"release_commit", "validator_sha256", "platform", "architecture", "python"},
            "release validation identity",
        )
        commit = _bounded_string(
            identity.get("release_commit"), "release_validation.identity.release_commit", maximum=40
        )
        validator = _bounded_string(
            identity.get("validator_sha256"),
            "release_validation.identity.validator_sha256",
            maximum=64,
        )
        if not COMMIT.fullmatch(commit) or not SHA256.fullmatch(validator):
            raise UpgradeReportError("transaction release validation identity is invalid")
        for field in ("platform", "architecture", "python"):
            _safe_value(identity.get(field), f"release_validation.identity.{field}")
        result["validation"] = {
            "mode": mode,
            "selection_reason": reason,
            "cache": cache,
        }
    return result


def validate_transaction(payload: object, *, expected_id: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise UpgradeReportError("transaction report must be a JSON object")
    _exact_keys(payload, TOP_LEVEL_KEYS, "report")
    if payload.get("schema_version") != 1:
        raise UpgradeReportError("transaction report schema is unsupported")
    if payload.get("kind") != "tool-shed-snapshot-upgrade-transaction":
        raise UpgradeReportError("transaction report kind is invalid")
    transaction_id = _bounded_string(payload.get("transaction_id"), "transaction_id", maximum=128)
    if transaction_id != expected_id or not TRANSACTION_ID.fullmatch(transaction_id):
        raise UpgradeReportError("transaction identity does not match its protected filename")
    state = _bounded_string(payload.get("state"), "state", maximum=32)
    if state not in FINAL_STATES:
        raise UpgradeReportError("transaction is not in a supported final state")
    started_at = _timestamp(payload.get("started_at"), "started_at")
    updated_at = _timestamp(payload.get("updated_at"), "updated_at")
    elapsed = _nonnegative_number(payload.get("elapsed_seconds"), "elapsed_seconds")
    current_platform = platform.system().lower()
    recorded_platform = _safe_value(payload.get("platform"), "platform")
    if recorded_platform != current_platform:
        raise UpgradeReportError(
            f"transaction platform {recorded_platform!r} does not match {current_platform!r}"
        )
    architecture = _safe_value(payload.get("architecture"), "architecture")
    if architecture != platform.machine().lower():
        raise UpgradeReportError("transaction architecture does not match the current platform")
    python_identity = _safe_value(payload.get("python"), "python")
    rollback = _bounded_string(payload.get("rollback_outcome"), "rollback_outcome", maximum=32)
    if rollback not in ROLLBACK_OUTCOMES:
        raise UpgradeReportError("transaction rollback outcome is invalid")
    error_class = payload.get("error_class")
    if error_class is not None:
        error_class = _bounded_string(error_class, "error_class", maximum=32)
        if error_class not in ERROR_CLASSES:
            raise UpgradeReportError("transaction error class is invalid")
    failed_stage = payload.get("failed_stage")
    if failed_stage is not None:
        failed_stage = _bounded_string(failed_stage, "failed_stage", maximum=64)
        if not STAGE_NAME.fullmatch(failed_stage):
            raise UpgradeReportError("transaction failed stage is invalid")
    if state == "failed" and (error_class is None or failed_stage is None):
        raise UpgradeReportError("failed transaction lacks a sanitized class or stage")
    if state != "failed" and (error_class is not None or failed_stage is not None):
        raise UpgradeReportError("successful transaction contains failure-only fields")
    durations = payload.get("stage_durations_seconds")
    if not isinstance(durations, dict) or not durations or len(durations) > 64:
        raise UpgradeReportError("transaction stage durations are invalid")
    clean_durations: dict[str, float] = {}
    for stage, duration in sorted(durations.items()):
        if not isinstance(stage, str) or not STAGE_NAME.fullmatch(stage):
            raise UpgradeReportError("transaction contains an invalid stage name")
        clean_durations[stage] = round(
            _nonnegative_number(duration, f"stage duration {stage}"), 3
        )
    issue_code = _bounded_string(payload.get("issue_code"), "issue_code", maximum=7)
    expected_code = issue_code_for(
        state=state,
        error_class=error_class,
        rollback_outcome=rollback,
    )
    if issue_code != expected_code or issue_code not in ISSUE_CODE_REGISTRY:
        raise UpgradeReportError("transaction issue code does not match its sanitized outcome")
    updater = _validate_updater(payload.get("updater"))
    release = _validate_release(payload["release"]) if "release" in payload else None
    return {
        "transaction_id": transaction_id,
        "state": state,
        "started_at": started_at,
        "updated_at": updated_at,
        "elapsed_seconds": round(elapsed, 3),
        "stage_durations_seconds": clean_durations,
        "platform": recorded_platform,
        "architecture": architecture,
        "python": python_identity,
        "failed_stage": failed_stage,
        "error_class": error_class,
        "rollback_outcome": rollback,
        "issue_code": issue_code,
        "updater": updater,
        "release": release,
    }


def transaction_path(selector: str) -> Path:
    try:
        root = state_root(create=False)
    except SnapshotStateError as error:
        raise UpgradeReportError("protected Tool Shed state root is invalid") from error
    directory = root / "snapshot-upgrade-transactions"
    if not directory.exists() or directory.is_symlink() or not directory.is_dir():
        raise UpgradeReportError("protected snapshot-upgrade transaction directory is unavailable")
    if os.name != "nt" and (root.stat().st_mode & 0o077 or directory.stat().st_mode & 0o077):
        raise UpgradeReportError("protected snapshot-upgrade state permissions are not private")
    if selector == "latest":
        entries: list[Path] = []
        try:
            for item in directory.iterdir():
                if item.suffix != ".json":
                    continue
                if item.is_symlink() or not item.is_file():
                    raise UpgradeReportError(
                        "protected transaction directory contains an unsafe report entry"
                    )
                entries.append(item)
            entries.sort(key=lambda item: item.stat().st_mtime_ns, reverse=True)
        except OSError as error:
            raise UpgradeReportError("protected transaction directory cannot be read safely") from error
        if not entries:
            raise UpgradeReportError("no snapshot-upgrade transaction reports are available")
        path = entries[0]
    else:
        if not TRANSACTION_ID.fullmatch(selector):
            raise UpgradeReportError("transaction selector must be 'latest' or an exact transaction ID")
        path = directory / f"{selector}.json"
    if not path.exists() or path.is_symlink() or not path.is_file():
        raise UpgradeReportError("selected transaction report is not a protected regular file")
    if os.name != "nt" and path.stat().st_mode & 0o077:
        raise UpgradeReportError("selected transaction report permissions are not private")
    if path.stat().st_size > MAX_REPORT_BYTES:
        raise UpgradeReportError("selected transaction report exceeds the supported size")
    return path


def load_transaction(selector: str) -> dict[str, Any]:
    path = transaction_path(selector)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise UpgradeReportError(f"selected transaction report is malformed: {error}") from error
    return validate_transaction(payload, expected_id=path.stem)


def issue_report(transaction: dict[str, Any]) -> dict[str, Any]:
    code = transaction["issue_code"]
    catalog = ISSUE_CODE_REGISTRY[code]
    stage = transaction.get("failed_stage") or "complete"
    version = (transaction.get("release") or {}).get("selected_version")
    version_text = f" {version}" if version else ""
    title = f"[Tool Shed upgrade {code}] {catalog['name']} at {stage}{version_text}"
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "kind": "tool-shed-snapshot-upgrade-issue-report",
        "suggested_title": title,
        "issue": {
            "code": code,
            "name": catalog["name"],
            "summary": catalog["summary"],
        },
        "transaction": transaction,
        "privacy": {
            "sanitized": True,
            "excluded": [
                "credentials and secrets",
                "prompts and responses",
                "raw command output and exception text",
                "workspace paths, usernames, and dirty filenames",
            ],
        },
        "publication": {
            "automatic": False,
            "review_required": True,
            "repository": "PC-Redemption/tool_shed",
        },
    }


def markdown_report(report: dict[str, Any]) -> str:
    transaction = report["transaction"]
    issue = report["issue"]
    release = transaction.get("release") or {}
    lines = [
        f"Suggested title: {report['suggested_title']}",
        "",
        "## Sanitized upgrade summary",
        "",
        f"- Issue code: `{issue['code']}` (`{issue['name']}`)",
        f"- Classification: {issue['summary']}",
        f"- Transaction: `{transaction['transaction_id']}`",
        f"- State: `{transaction['state']}`",
        f"- Failed stage: `{transaction.get('failed_stage') or 'none'}`",
        f"- Error class: `{transaction.get('error_class') or 'none'}`",
        f"- Rollback outcome: `{transaction['rollback_outcome']}`",
        f"- Elapsed: `{transaction['elapsed_seconds']:.3f}s`",
        f"- Platform: `{transaction['platform']} / {transaction['architecture']}`",
        f"- Python: `{transaction['python']}`",
        (
            f"- Updater: `{transaction['updater']['shed_version']}` / "
            f"protocol `{transaction['updater']['protocol']}`"
        ),
        f"- Updater SHA-256: `{transaction['updater']['script_sha256']}`",
    ]
    if release:
        lines.extend(
            [
                f"- Selected release: `{release.get('selected_tag') or 'not-selected'}`",
                f"- Content commit: `{release.get('content_commit') or 'not-selected'}`",
            ]
        )
        validation = release.get("validation")
        if validation:
            lines.extend(
                [
                    f"- Validation mode: `{validation['mode']}`",
                    f"- Validation reason: `{validation['selection_reason']}`",
                    f"- Validation cache: `{validation['cache']}`",
                ]
            )
    lines.extend(["", "## Stage durations", ""])
    lines.extend(
        f"- `{stage}`: `{duration:.3f}s`"
        for stage, duration in transaction["stage_durations_seconds"].items()
    )
    lines.extend(
        [
            "",
            "## Privacy and review",
            "",
            (
                "This draft is generated from an allowlisted local transaction schema. It "
                "excludes credentials, secrets, prompts, responses, raw output, exception text, "
                "workspace paths, usernames, and dirty filenames."
            ),
            "",
            (
                "Review this draft before separately authorizing GitHub publication. The "
                "reporter does not create or modify any GitHub issue."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render a protected Tool Shed snapshot-upgrade transaction without publishing it."
    )
    parser.add_argument(
        "transaction",
        nargs="?",
        default="latest",
        help="'latest' (default) or an exact transaction ID.",
    )
    parser.add_argument(
        "--format",
        choices=("markdown", "json"),
        default="markdown",
        help="Output format (default: markdown).",
    )
    parser.add_argument("--json", action="store_true", help="Alias for --format json.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report = issue_report(load_transaction(args.transaction))
    except UpgradeReportError as error:
        print(f"Tool Shed upgrade report failed: {error}", file=sys.stderr)
        return 1
    if args.json or args.format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(markdown_report(report), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
