#!/usr/bin/env python3
"""Bounded, redacted lifecycle evidence and deterministic replay minimization."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence


ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "schemas/lifecycle-qualification/v1/evidence-policy.json"
SECRET_KEY = re.compile(r"(?:authorization|cookie|credential|password|secret|token)", re.I)
BODY_KEY = re.compile(r"(?:body|body_markdown|document_body|prompt)$", re.I)
BEARER = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+\-/]+=*")
SECRET_LITERAL = re.compile(r"\b(?:sk|gh[opasu]|github_pat)-[A-Za-z0-9_\-]{8,}\b")
COMMAND_SECRET = re.compile(r"(?i)(--(?:password|secret|token)(?:=|\s+))\S+")
ABSOLUTE_PATH = re.compile(r"(?<![A-Za-z0-9])(?:/[A-Za-z0-9._-]+){2,}|[A-Za-z]:\\(?:[^\\\s]+\\)+[^\\\s]+")
VERDICTS = {"PASS", "PRODUCT-FAIL", "HARNESS-FAIL", "INFRA-BLOCKED"}


class EvidenceError(RuntimeError):
    pass


def canonical_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()


def digest(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def load_policy(path: Path = POLICY_PATH) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("schema_version") != 1 or value.get("kind") != "tool-shed-qualification-evidence-policy":
        raise EvidenceError("unsupported qualification evidence policy")
    return value


def _sanitize_string(value: str) -> str:
    value = BEARER.sub("[REDACTED]", value)
    value = SECRET_LITERAL.sub("[REDACTED]", value)
    value = COMMAND_SECRET.sub(r"\1[REDACTED]", value)
    return ABSOLUTE_PATH.sub(lambda match: f"<path:{Path(match.group(0).replace('\\\\', '/')).name}>", value)


def sanitize(value: object, *, key: str = "") -> object:
    """Return a bounded evidence-safe structure before any evidence digest is calculated."""
    if SECRET_KEY.search(key):
        return "[REDACTED]"
    if BODY_KEY.search(key):
        raw = value if isinstance(value, str) else json.dumps(value, sort_keys=True)
        return {"redacted": True, "length": len(raw), "sha256": hashlib.sha256(raw.encode()).hexdigest()}
    if isinstance(value, dict):
        return {str(name): sanitize(item, key=str(name)) for name, item in sorted(value.items())}
    if isinstance(value, list):
        return [sanitize(item, key=key) for item in value]
    if isinstance(value, str):
        return _sanitize_string(value)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return _sanitize_string(str(value))


def _unsafe_paths(value: object, *, location: str = "$") -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            child = f"{location}.{key}"
            if SECRET_KEY.search(str(key)) and item != "[REDACTED]":
                findings.append(child)
            if BODY_KEY.search(str(key)) and not (
                isinstance(item, dict) and item.get("redacted") is True and set(item) == {"redacted", "length", "sha256"}
            ):
                findings.append(child)
            findings.extend(_unsafe_paths(item, location=child))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            findings.extend(_unsafe_paths(item, location=f"{location}[{index}]"))
    elif isinstance(value, str) and (BEARER.search(value) or SECRET_LITERAL.search(value) or COMMAND_SECRET.search(value) or ABSOLUTE_PATH.search(value)):
        findings.append(location)
    return findings


def _checkpoint_window(records: Iterable[dict[str, Any]], first_divergence: str | None) -> list[dict[str, Any]]:
    ordered = list(records)
    if not first_divergence:
        return ordered[-2:]
    failing = next(
        (index for index, record in enumerate(ordered) if record.get("checkpoint_id") == first_divergence or record.get("id") == first_divergence),
        None,
    )
    if failing is None:
        return ordered[-2:]
    end = failing + 1
    while end < len(ordered) and ordered[end].get("persistence_required") is True:
        end += 1
    return ordered[max(0, failing - 1):end]


def seal_bundle(
    manifest: dict[str, Any],
    result: dict[str, Any],
    records: Iterable[dict[str, Any]],
    *,
    created_at: str,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    policy = policy or load_policy()
    verdict = str(result.get("verdict"))
    if verdict not in VERDICTS:
        raise EvidenceError("evidence result has an invalid verdict")
    if manifest.get("run_id") != result.get("run_id") or manifest.get("manifest_digest") != result.get("manifest_digest"):
        raise EvidenceError("evidence result is not bound to its sealed manifest")
    selected = _checkpoint_window(records, result.get("first_divergence"))
    safe = sanitize(selected)
    unsafe = _unsafe_paths(safe)
    if unsafe:
        raise EvidenceError("redaction or scope validation failed: " + ", ".join(unsafe[:10]))
    bundle: dict[str, Any] = {
        "schema_version": 1,
        "kind": "tool-shed-qualification-evidence-bundle",
        "run_id": manifest["run_id"],
        "manifest_digest": manifest["manifest_digest"],
        "result_digest": result.get("result_digest"),
        "candidate_commit": manifest.get("candidate", {}).get("commit"),
        "scenario_id": manifest.get("scenario", {}).get("id"),
        "platform": manifest.get("fixture", {}).get("platform"),
        "verdict": verdict,
        "created_at": created_at,
        "first_divergence": result.get("first_divergence"),
        "records": safe,
        "replay": sanitize(result.get("replay", [])),
        "policy_digest": digest(policy),
    }
    encoded = canonical_bytes(bundle)
    if len(encoded) > int(policy["capture"]["per_run_bytes"]):
        raise EvidenceError("evidence exceeds the per-run storage cap")
    bundle["content_bytes"] = len(encoded)
    bundle["bundle_digest"] = digest(bundle)
    return bundle


def retention_state(
    bundle: dict[str, Any],
    *,
    now: datetime,
    newer_accepted_at: datetime | None = None,
    fixing_pass_at: datetime | None = None,
    infrastructure_recovered_at: datetime | None = None,
) -> dict[str, Any]:
    policy = load_policy()
    created = datetime.fromisoformat(str(bundle["created_at"]).replace("Z", "+00:00"))
    verdict = str(bundle["verdict"])
    protected = False
    if verdict == "PASS":
        base = created + timedelta(days=int(policy["retention_days"]["PASS"]))
        expires = max(base, newer_accepted_at) if newer_accepted_at else None
        reason = "awaiting-newer-accepted-candidate" if newer_accepted_at is None else "pass-retention-satisfied"
    elif verdict == "PRODUCT-FAIL":
        protected = fixing_pass_at is None
        expires = fixing_pass_at + timedelta(days=int(policy["retention_days"]["PRODUCT-FAIL_AFTER_FIX"])) if fixing_pass_at else None
        reason = "protected-product-failure-replay" if protected else "fixed-product-failure-retention"
    elif verdict == "HARNESS-FAIL":
        expires = created + timedelta(days=int(policy["retention_days"]["HARNESS-FAIL"]))
        reason = "harness-failure-retention"
    else:
        anchor = infrastructure_recovered_at
        expires = anchor + timedelta(days=int(policy["retention_days"]["INFRA-BLOCKED"])) if anchor else None
        reason = "awaiting-infrastructure-recovery" if anchor is None else "infrastructure-retention"
    return {
        "protected": protected,
        "expires_at": expires.astimezone(timezone.utc).isoformat().replace("+00:00", "Z") if expires else None,
        "eligible": bool(expires and now >= expires and not protected),
        "reason": reason,
    }


def reclaim_plan(
    root: Path,
    *,
    incoming_bytes: int,
    now: datetime,
    newer_accepted_at: datetime | None = None,
) -> dict[str, Any]:
    policy = load_policy()
    cap = int(policy["capture"]["per_fixture_bytes"])
    manifests: list[tuple[Path, dict[str, Any], int]] = []
    used = 0
    for path in sorted(root.glob("*/bundle.json")):
        value = json.loads(path.read_text(encoding="utf-8"))
        size = sum(item.stat().st_size for item in path.parent.rglob("*") if item.is_file())
        used += size
        manifests.append((path, value, size))
    required = max(0, used + incoming_bytes - cap)
    candidates = []
    for path, value, size in manifests:
        state = retention_state(
            value,
            now=now,
            newer_accepted_at=newer_accepted_at if value.get("verdict") == "PASS" else None,
        )
        if value.get("verdict") == "PASS" and state["eligible"]:
            candidates.append((str(value.get("created_at")), path.parent, size))
    candidates.sort()
    selected, reclaimed = [], 0
    for _, path, size in candidates:
        if reclaimed >= required:
            break
        selected.append({"relative_path": path.relative_to(root).as_posix(), "bytes": size})
        reclaimed += size
    return {
        "schema_version": 1,
        "kind": "tool-shed-qualification-reclaim-plan",
        "fixture_bytes": used,
        "incoming_bytes": incoming_bytes,
        "cap_bytes": cap,
        "required_bytes": required,
        "reclaimable_bytes": reclaimed,
        "eligible": selected,
        "verdict": "PASS" if reclaimed >= required else "INFRA-BLOCKED",
        "writes_performed": False,
    }


def _dependencies_satisfied(actions: list[dict[str, Any]]) -> bool:
    ids = {str(item["id"]) for item in actions}
    return all(set(map(str, item.get("depends_on", []))) <= ids for item in actions)


def minimize(
    actions: list[dict[str, Any]],
    *,
    signature: dict[str, Any],
    replay: Callable[[list[dict[str, Any]]], dict[str, Any]],
    original_sealed: bool,
    isolated_copy: bool,
    maximum_attempts: int = 100,
    maximum_seconds: float = 600,
) -> dict[str, Any]:
    required_signature = {"invariant_id", "layer", "selector", "reason_code"}
    if set(signature) != required_signature or any(not str(signature[name]).strip() for name in required_signature):
        raise EvidenceError("failure signature must contain invariant_id, layer, selector, and reason_code")
    if not original_sealed:
        raise EvidenceError("the original failure bundle must be sealed before minimization")
    if not isolated_copy:
        raise EvidenceError("minimization is restricted to an isolated copy")
    target = digest(signature)
    started = time.monotonic()
    attempts = 0
    removed: list[list[str]] = []
    parameter_reductions: list[dict[str, Any]] = []

    def reproduces(candidate: list[dict[str, Any]]) -> bool:
        nonlocal attempts
        if attempts >= maximum_attempts or time.monotonic() - started >= maximum_seconds:
            return False
        if not _dependencies_satisfied(candidate):
            return False
        attempts += 1
        return all(digest(replay(candidate)) == target for _ in range(3))

    current = list(actions)
    failing = next((index for index, item in enumerate(current) if item.get("failure_signature") == signature), None)
    if failing is not None and failing + 1 < len(current):
        tail = current[failing + 1:]
        candidate = current[:failing + 1]
        if reproduces(candidate):
            removed.append([str(item["id"]) for item in tail])
            current = candidate
    granularity = 2
    while len(current) > 1 and attempts < maximum_attempts and time.monotonic() - started < maximum_seconds:
        width = max(1, (len(current) + granularity - 1) // granularity)
        reduced = False
        for start in range(0, len(current), width):
            chunk = current[start:start + width]
            if any(item.get("mandatory") for item in chunk):
                continue
            candidate = current[:start] + current[start + width:]
            if candidate and reproduces(candidate):
                removed.append([str(item["id"]) for item in chunk])
                current = candidate
                granularity = max(2, granularity - 1)
                reduced = True
                break
        if reduced:
            continue
        if granularity >= len(current):
            break
        granularity = min(len(current), granularity * 2)
    simplifiable = ("graph_width", "graph_depth", "payload_size", "retry_count", "delay_ms")
    for index, action in enumerate(list(current)):
        for field in simplifiable:
            original = action.get(field)
            if not isinstance(original, int) or isinstance(original, bool) or original <= 0:
                continue
            for proposed in dict.fromkeys((original // 2, 1, 0)):
                if proposed >= original:
                    continue
                candidate = [dict(item) for item in current]
                candidate[index][field] = proposed
                if reproduces(candidate):
                    parameter_reductions.append({"action_id": str(action["id"]), "field": field, "from": original, "to": proposed})
                    current = candidate
                    action = current[index]
                    original = proposed
                if attempts >= maximum_attempts or time.monotonic() - started >= maximum_seconds:
                    break
    stable = reproduces(current)
    return {
        "schema_version": 1,
        "kind": "tool-shed-qualification-minimization",
        "signature": signature,
        "original_action_ids": [str(item["id"]) for item in actions],
        "minimum_action_ids": [str(item["id"]) for item in current],
        "removed_action_ranges": removed,
        "parameter_reductions": parameter_reductions,
        "attempts": attempts,
        "reproductions_required": 3,
        "stable": stable,
        "classification": "minimized" if stable and len(current) < len(actions) else ("reproducible-but-unminimized" if stable else "non-deterministic"),
        "original_retained": True,
        "isolated_copy": True,
    }


def _write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    seal = commands.add_parser("seal")
    seal.add_argument("--manifest", required=True); seal.add_argument("--result", required=True); seal.add_argument("--records", required=True); seal.add_argument("--created-at", required=True); seal.add_argument("--output", required=True)
    reclaim = commands.add_parser("reclaim-plan")
    reclaim.add_argument("--root", required=True); reclaim.add_argument("--incoming-bytes", required=True, type=int); reclaim.add_argument("--now", required=True); reclaim.add_argument("--newer-accepted-at"); reclaim.add_argument("--output")
    args = parser.parse_args(argv)
    try:
        if args.command == "seal":
            manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
            result = json.loads(Path(args.result).read_text(encoding="utf-8"))
            records = json.loads(Path(args.records).read_text(encoding="utf-8"))
            if not isinstance(records, list):
                raise EvidenceError("records must be a JSON array")
            value = seal_bundle(manifest, result, records, created_at=args.created_at)
            _write(Path(args.output), value)
        else:
            now = datetime.fromisoformat(args.now.replace("Z", "+00:00"))
            newer = datetime.fromisoformat(args.newer_accepted_at.replace("Z", "+00:00")) if args.newer_accepted_at else None
            value = reclaim_plan(Path(args.root), incoming_bytes=args.incoming_bytes, now=now, newer_accepted_at=newer)
            if args.output:
                _write(Path(args.output), value)
            else:
                print(json.dumps(value, indent=2, sort_keys=True))
        return 0 if value.get("verdict", "PASS") == "PASS" else 3
    except (OSError, ValueError, EvidenceError, json.JSONDecodeError) as error:
        print(f"lifecycle evidence error: {error}", file=os.sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
