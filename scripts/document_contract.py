#!/usr/bin/env python3
"""Validate the frozen database-owned work-collateral contract fixture."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


GENERATED = {
    "idea-brief": "IDEA", "project-map": "MAP", "program-roadmap": "PRM",
    "campaign": "CAMP", "ticket": "TKT", "checklist": "CHK", "spike": "SPK",
    "adr": "ADR", "decision": "DEC", "inventory": "INV", "runbook": "RUN",
    "workpackage": "WP", "incident": "INC", "q-and-a": "QNA",
    "evidence-summary": "EVD", "focus-area": "FOC",
}
READ = {"list", "show", "search", "context", "related", "history", "diff", "resolve", "render-views"}
WRITE = {"create", "export-edit", "apply-edit", "set-lifecycle", "relate", "unrelate", "import-plan", "import-apply", "checkpoint"}
MAINTENANCE = {"audit", "migrate", "rebuild", "rollback-export", "qualify-conversion"}


class ContractError(ValueError):
    pass


def _exact(payload: dict[str, Any], required: set[str], label: str) -> None:
    missing = required - payload.keys()
    extra = payload.keys() - required
    if missing or extra:
        raise ContractError(f"{label} fields mismatch: missing={sorted(missing)} extra={sorted(extra)}")


def _false(payload: dict[str, Any], key: str) -> None:
    if payload.get(key) is not False:
        raise ContractError(f"{key} must be false")


def _true(payload: dict[str, Any], key: str) -> None:
    if payload.get(key) is not True:
        raise ContractError(f"{key} must be true")


def validate_contract(payload: object) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ContractError("contract must be an object")
    fields = {"schema_version", "kind", "hybrid_schema", "generated_types", "file_owned_classes", "projection_classes", "commands", "checkpoint", "conversion", "retirement"}
    _exact(payload, fields, "contract")
    if payload["schema_version"] != 1 or payload["kind"] != "tool-shed-document-authority-contract":
        raise ContractError("unsupported contract identity")
    if payload["hybrid_schema"] != 2:
        raise ContractError("document authority requires Hybrid schema 2")

    rows = payload["generated_types"]
    if not isinstance(rows, list):
        raise ContractError("generated_types must be a list")
    observed: dict[str, str] = {}
    namespaces: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ContractError("generated type must be an object")
        _exact(row, {"type", "namespace", "authority"}, "generated type")
        artifact_type, namespace = row["type"], row["namespace"]
        if artifact_type in observed or namespace in namespaces:
            raise ContractError("generated type and namespace must be unique")
        if row["authority"] != "sqlite":
            raise ContractError(f"generated type {artifact_type} must be SQLite-authoritative")
        if not isinstance(namespace, str) or not re.fullmatch(r"[A-Z]{2,5}", namespace):
            raise ContractError("namespace must be 2..5 uppercase letters")
        observed[str(artifact_type)] = namespace
        namespaces.add(namespace)
    if observed != GENERATED:
        raise ContractError("generated type inventory or namespace mapping differs from the frozen contract")

    file_owned = payload["file_owned_classes"]
    projections = payload["projection_classes"]
    if not isinstance(file_owned, list) or not isinstance(projections, list):
        raise ContractError("authority class inventories must be lists")
    overlap = set(observed) & set(map(str, file_owned))
    if overlap:
        raise ContractError(f"dual authority classes: {sorted(overlap)}")
    if not {"queue", "index", "lifecycle-view"}.issubset(set(map(str, projections))):
        raise ContractError("required disposable projections are missing")

    commands = payload["commands"]
    if not isinstance(commands, dict):
        raise ContractError("commands must be an object")
    _exact(commands, {"read", "write", "maintenance", "direct_sql_normal_operation"}, "commands")
    if set(commands["read"]) != READ or set(commands["write"]) != WRITE or set(commands["maintenance"]) != MAINTENANCE:
        raise ContractError("managed command surface differs from the frozen contract")
    _false(commands, "direct_sql_normal_operation")

    checkpoint = payload["checkpoint"]
    conversion = payload["conversion"]
    retirement = payload["retirement"]
    if not all(isinstance(item, dict) for item in (checkpoint, conversion, retirement)):
        raise ContractError("checkpoint, conversion, and retirement must be objects")
    _exact(checkpoint, {"live_database_tracked", "format", "content_objects", "read_creates_checkpoint", "git_required"}, "checkpoint")
    _false(checkpoint, "live_database_tracked")
    _false(checkpoint, "read_creates_checkpoint")
    _false(checkpoint, "git_required")
    if checkpoint["format"] != "state-v2-logical-json" or checkpoint["content_objects"] != "sha256-immutable":
        raise ContractError("checkpoint format differs from the frozen contract")
    _exact(conversion, {"single_writer", "retains_original_bytes", "idempotent", "shadow_first", "rollback_export_required"}, "conversion")
    for key in conversion:
        _true(conversion, key)
    _exact(retirement, {"automatic", "separate_owner_decision", "allowed_before_final_reconciliation"}, "retirement")
    _false(retirement, "automatic")
    _true(retirement, "separate_owner_decision")
    _false(retirement, "allowed_before_final_reconciliation")
    return {"schema_version": 1, "kind": "tool-shed-document-contract-validation", "valid": True, "generated_types": len(observed)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        result = validate_contract(json.loads(args.path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError, ContractError, TypeError) as error:
        result = {"schema_version": 1, "kind": "tool-shed-document-contract-validation", "valid": False, "error": str(error)}
        print(json.dumps(result, sort_keys=True) if args.json else f"INVALID: {error}")
        return 1
    print(json.dumps(result, sort_keys=True) if args.json else "VALID")
    return 0


if __name__ == "__main__":
    sys.exit(main())
