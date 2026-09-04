#!/usr/bin/env python3
"""Deterministic hooks-only risk classification for closure verification policy."""

from __future__ import annotations

import sys as _runtime_sys

_runtime_sys.dont_write_bytecode = True

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from project_identity import require_path_within, resolved_workspace


SCHEMA_VERSION = 1
INPUT_KIND = "tool-shed-verification-policy-input"
DECISION_KIND = "tool-shed-verification-policy-decision"
POLICY_ID = "tool-shed-risk-adaptive-verification"
POLICY_VERSION = 1
AUTOMATIC_LOWERING_ENABLED = False
PROFILES = ("mechanical", "normal", "high-risk")
PROFILE_RANK = {profile: rank for rank, profile in enumerate(PROFILES)}
MECHANICAL_SUFFIXES = {".md", ".rst", ".txt"}
CODE_SUFFIXES = {
    ".c", ".cc", ".cpp", ".cs", ".go", ".java", ".js", ".jsx", ".kt", ".php",
    ".py", ".rb", ".rs", ".sh", ".sql", ".swift", ".ts", ".tsx",
}
MECHANICAL_COMPONENTS = {"copy", "documentation", "formatting", "label", "labels", "text"}
HIGH_RISK_TERMS = {
    "architecture", "auth", "controller", "credential", "database", "deploy", "migration",
    "orchestration", "production", "recovery", "release", "schema", "security",
}
SAFE_SIDE_EFFECTS = {"none", "read-only", "local-read"}
HIGH_RISK_TARGETS = {"external", "production", "protected", "unknown"}
ESCALATION_FLAGS = (
    "unexpected_scope",
    "failed_checks",
    "stale_evidence",
    "dependencies_changed",
)
INPUT_FIELDS = {
    "schema_version",
    "kind",
    "changed_paths",
    "components",
    "side_effect_classes",
    "target_class",
    "protected_boundaries",
    "behavior_neutral",
    "requested_profile",
    "parent_minimum_profile",
    *ESCALATION_FLAGS,
}


class VerificationPolicyError(RuntimeError):
    pass


def canonical_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def digest(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _policy_definition() -> dict[str, Any]:
    return {
        "policy_id": POLICY_ID,
        "policy_version": POLICY_VERSION,
        "automatic_lowering_enabled": AUTOMATIC_LOWERING_ENABLED,
        "profiles": {
            "mechanical": ["edit", "targeted-verification"],
            "normal": ["edit", "targeted-verification", "applicable-tests", "diff-review"],
            "high-risk": [
                "edit",
                "targeted-verification",
                "applicable-tests",
                "diff-review",
                "recursive-closure",
                "independent-verification",
            ],
        },
        "composition": "highest-applicable-profile",
        "unknown_scope": "high-risk",
        "protected_floor": "high-risk",
        "disabled_lowering_default": "high-risk",
    }


POLICY_DEFINITION = _policy_definition()
POLICY_DIGEST = digest(POLICY_DEFINITION)


def _string_list(value: object, label: str) -> list[str]:
    if not isinstance(value, list):
        raise VerificationPolicyError(f"{label} must be a list")
    result: list[str] = []
    for index, item in enumerate(value, start=1):
        if not isinstance(item, str) or not item.strip():
            raise VerificationPolicyError(f"{label} item {index} must be a non-empty string")
        result.append(item.strip())
    return sorted(set(result))


def _profile(value: object, label: str, *, default: str | None = None) -> str:
    if value is None and default is not None:
        return default
    if value not in PROFILE_RANK:
        raise VerificationPolicyError(f"{label} must be one of: {', '.join(PROFILES)}")
    return str(value)


def normalize_input(payload: dict[str, Any]) -> dict[str, Any]:
    unknown = sorted(set(payload) - INPUT_FIELDS)
    if unknown:
        raise VerificationPolicyError("unknown verification policy fields: " + ", ".join(unknown))
    if payload.get("schema_version") != SCHEMA_VERSION or payload.get("kind") != INPUT_KIND:
        raise VerificationPolicyError("unsupported verification policy input envelope")
    target = payload.get("target_class")
    if not isinstance(target, str) or not target.strip():
        raise VerificationPolicyError("target_class must be a non-empty string")
    normalized: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "kind": INPUT_KIND,
        "changed_paths": _string_list(payload.get("changed_paths", []), "changed_paths"),
        "components": _string_list(payload.get("components", []), "components"),
        "side_effect_classes": _string_list(payload.get("side_effect_classes", []), "side_effect_classes"),
        "target_class": target.strip().casefold(),
        "protected_boundaries": _string_list(payload.get("protected_boundaries", []), "protected_boundaries"),
        "behavior_neutral": payload.get("behavior_neutral", False),
        "requested_profile": _profile(payload.get("requested_profile"), "requested_profile", default="mechanical"),
        "parent_minimum_profile": _profile(
            payload.get("parent_minimum_profile"), "parent_minimum_profile", default="mechanical"
        ),
    }
    if not isinstance(normalized["behavior_neutral"], bool):
        raise VerificationPolicyError("behavior_neutral must be boolean")
    for flag in ESCALATION_FLAGS:
        value = payload.get(flag, False)
        if not isinstance(value, bool):
            raise VerificationPolicyError(f"{flag} must be boolean")
        normalized[flag] = value
    return normalized


def _max_profile(*profiles: str) -> str:
    return max(profiles, key=PROFILE_RANK.__getitem__)


def _contains_high_risk_term(values: list[str]) -> bool:
    tokens = " ".join(values).casefold().replace("_", "-")
    return any(term in tokens for term in HIGH_RISK_TERMS)


def _classified_profile(value: dict[str, Any]) -> tuple[str, list[str]]:
    reasons: list[str] = []
    paths = value["changed_paths"]
    components = [item.casefold() for item in value["components"]]
    side_effects = [item.casefold() for item in value["side_effect_classes"]]
    protected = value["protected_boundaries"]

    if protected:
        reasons.append("protected-boundary-floor")
    if value["target_class"] in HIGH_RISK_TARGETS:
        reasons.append("high-risk-target")
    if _contains_high_risk_term(paths + components + protected):
        reasons.append("high-risk-component")
    if not side_effects or any(item not in SAFE_SIDE_EFFECTS for item in side_effects):
        reasons.append("side-effects-not-demonstrably-safe")
    for flag in ESCALATION_FLAGS:
        if value[flag]:
            reasons.append(flag.replace("_", "-"))
    if reasons:
        return "high-risk", sorted(set(reasons))

    suffixes = {Path(path).suffix.casefold() for path in paths}
    only_mechanical_paths = bool(paths) and suffixes <= MECHANICAL_SUFFIXES
    only_mechanical_components = bool(components) and set(components) <= MECHANICAL_COMPONENTS
    if value["behavior_neutral"] and (only_mechanical_paths or only_mechanical_components):
        return "mechanical", ["demonstrably-behavior-neutral"]
    if paths and (suffixes & CODE_SUFFIXES or components):
        return "normal", ["ordinary-code-or-known-component"]
    return "high-risk", ["unknown-scope"]


def classify(payload: dict[str, Any]) -> dict[str, Any]:
    value = normalize_input(payload)
    classified, reasons = _classified_profile(value)
    requested = value["requested_profile"]
    parent = value["parent_minimum_profile"]
    governing = _max_profile(classified, requested, parent)
    escalation_history: list[dict[str, str]] = []
    if PROFILE_RANK[requested] > PROFILE_RANK[classified]:
        escalation_history.append({"from": classified, "to": requested, "reason": "requested-profile-floor"})
    prior = _max_profile(classified, requested)
    if PROFILE_RANK[parent] > PROFILE_RANK[prior]:
        escalation_history.append({"from": prior, "to": parent, "reason": "parent-minimum-floor"})
    effective = governing
    if not AUTOMATIC_LOWERING_ENABLED and effective != "high-risk":
        escalation_history.append(
            {"from": effective, "to": "high-risk", "reason": "automatic-lowering-disabled"}
        )
        effective = "high-risk"
        reasons.append("automatic-lowering-disabled")
    decision: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "kind": DECISION_KIND,
        "policy_id": POLICY_ID,
        "policy_version": POLICY_VERSION,
        "policy_digest": POLICY_DIGEST,
        "automatic_lowering_enabled": AUTOMATIC_LOWERING_ENABLED,
        "inputs": value,
        "input_digest": digest(value),
        "classified_profile": classified,
        "requested_profile": requested,
        "parent_minimum_profile": parent,
        "effective_profile": effective,
        "reason_codes": sorted(set(reasons)),
        "required_recipe_set": POLICY_DEFINITION["profiles"][effective],
        "escalation_history": escalation_history,
    }
    decision["decision_digest"] = digest(decision)
    return decision


def validate_decision(value: object) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("kind") != DECISION_KIND:
        raise VerificationPolicyError("verification policy decision is missing or malformed")
    inputs = value.get("inputs")
    if not isinstance(inputs, dict):
        raise VerificationPolicyError("verification policy decision lacks normalized inputs")
    expected = classify(inputs)
    if value != expected:
        raise VerificationPolicyError("verification policy decision does not match current deterministic policy")
    return expected


def _load_input(workspace: Path, supplied: Path) -> dict[str, Any]:
    path = require_path_within(workspace, supplied if supplied.is_absolute() else workspace / supplied)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise VerificationPolicyError(f"cannot load verification policy input: {error}") from error
    if not isinstance(value, dict):
        raise VerificationPolicyError("verification policy input must be a JSON object")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--json", action="store_true")
    commands = parser.add_subparsers(dest="command", required=True)
    classify_parser = commands.add_parser("classify")
    classify_parser.add_argument("--input", required=True)
    commands.add_parser("policy")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        workspace = resolved_workspace(Path(args.workspace))
        if args.command == "classify":
            result = classify(_load_input(workspace, Path(args.input)))
        else:
            result = {
                "schema_version": SCHEMA_VERSION,
                "kind": "tool-shed-verification-policy",
                **POLICY_DEFINITION,
                "policy_digest": POLICY_DIGEST,
                "writes_performed": False,
            }
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except VerificationPolicyError as error:
        if args.json:
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "kind": "tool-shed-verification-policy-error",
                "error": str(error),
                "writes_performed": False,
            }, indent=2, sort_keys=True))
        else:
            print(f"verification policy error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
