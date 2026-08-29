#!/usr/bin/env python3
"""Run deterministic Tool Shed Work1/Work2 preparation and closeout phases."""

from __future__ import annotations

import sys as _runtime_sys

_runtime_sys.dont_write_bytecode = True

import argparse
import contextlib
import hashlib
import json
import os
import socket
import shutil
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Sequence

import ci_validation_policy
import document_store
import doctor
import hybrid_state
import release_cohort
import work_level_config
from project_identity import (
    ProjectIdentityError,
    bind_state_token,
    binding_token,
    load_project_identity,
    require_path_within,
    require_project_binding,
    resolved_workspace,
    target_capsule,
)


SCHEMA_VERSION = 1
OPERATION = "work-orchestration"
ENDPOINTS = ("work1", "work2")
STAGES = ("prepare", "closeout")
CLASSIFICATIONS = (
    "reasoning-required",
    "deterministic-script",
    "recovery-retry",
    "external-wait",
)
RESULTS = ("passed", "failed", "skipped")
REMEDIAL_CLASSES = frozenset({"deterministic-script", "recovery-retry"})
JOURNAL_RELATIVE = Path(".tool-shed/orchestration/journal-v1.jsonl")
RUNS_RELATIVE = Path(".tool-shed/orchestration/runs")
LOCK_RELATIVE = Path(".tool-shed/orchestration/active.lock")
EPOCH_RELATIVE = Path(".tool-shed/orchestration/counter-epoch.json")
REPORT_RELATIVE = Path(".tool-shed/reports/work-efficiency-v1.json")
CHECKPOINT_RELATIVE = Path("work/state/checkpoints/state-v2.json")
MAX_DIAGNOSTIC_BYTES = 4096
MAX_JOURNAL_EVENTS = 10_000
RETENTION_DAYS = 30
TARGET_EVIDENCE_MAX_AGE = timedelta(hours=2)


class WorkOrchestrationError(RuntimeError):
    pass


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _sha(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _stamp() -> str:
    return _utc_now().isoformat().replace("+00:00", "Z")


def _parse_stamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as error:
        raise WorkOrchestrationError(f"invalid UTC timestamp: {value!r}") from error
    if parsed.tzinfo is None:
        raise WorkOrchestrationError("timestamp must include a timezone")
    return parsed.astimezone(timezone.utc)


def _git(workspace: Path, *arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", *arguments],
        cwd=workspace,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if check and result.returncode:
        raise WorkOrchestrationError(
            result.stderr.strip() or result.stdout.strip() or "Git operation failed"
        )
    return result


def _git_state(workspace: Path) -> dict[str, str]:
    head = _git(workspace, "rev-parse", "--verify", "HEAD").stdout.strip()
    status = _git(workspace, "status", "--porcelain=v1", "-z", "--untracked-files=all").stdout
    diff = _git(workspace, "diff", "--binary", "HEAD").stdout
    return {
        "head": head,
        "status_digest": hashlib.sha256(status.encode()).hexdigest(),
        "diff_digest": hashlib.sha256(diff.encode()).hexdigest(),
    }


def _paths_from_git(workspace: Path) -> list[str]:
    result = _git(workspace, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    parts = [item for item in result.stdout.split("\0") if item]
    paths: list[str] = []
    index = 0
    while index < len(parts):
        raw = parts[index]
        status = raw[:2]
        path = raw[3:]
        if status[0] in {"R", "C"} and index + 1 < len(parts):
            index += 1
            path = parts[index]
        paths.append(Path(path).as_posix())
        index += 1
    return sorted(dict.fromkeys(paths))


def _plan_material(
    workspace: Path,
    *,
    endpoint: str,
    stage: str,
    changed_paths: list[str],
    commit: str | None = None,
    origin_cycle: str | None = None,
    target_evidence: Path | None = None,
) -> dict[str, Any]:
    if endpoint not in ENDPOINTS:
        raise WorkOrchestrationError(f"unsupported endpoint: {endpoint}")
    if stage not in STAGES:
        raise WorkOrchestrationError(f"unsupported stage: {stage}")
    identity = target_capsule(workspace, operation=OPERATION)
    level = work_level_config.resolve_workspace_level(workspace, endpoint)
    audit = document_store.audit(workspace)
    git = _git_state(workspace)
    selected = ci_validation_policy.classify(changed_paths)
    external: dict[str, Any] | None = None
    if target_evidence:
        evidence_path = require_path_within(workspace, workspace / target_evidence)
        external = {
            "relative": evidence_path.relative_to(workspace).as_posix(),
            "sha256": hashlib.sha256(evidence_path.read_bytes()).hexdigest()
            if evidence_path.is_file()
            else None,
        }
    return {
        "endpoint": endpoint,
        "stage": stage,
        "project_id": identity["project_id"],
        "resolved_root": identity["resolved_root"],
        "work_level": {
            "source": level["source"],
            "work_model": level["work_model"],
            "development_target": level["development_target"],
            "production_target": level["production_target"],
            "configured": level["configured"],
            "run_default": level["run_default"],
            "before": level["before"],
            "after": level["after"],
        },
        "database": {
            "revision": audit["current_revision"],
            "domain_digest": audit["domain_digest"],
            "classification": audit["classification"],
        },
        "git": git,
        "changed_paths": changed_paths,
        "validation": {
            "profile": selected["profile"],
            "reason": selected["reason"],
        },
        "candidate": {"commit": commit, "origin_cycle": origin_cycle},
        "target_evidence": external,
    }


def build_plan(
    workspace: Path,
    *,
    endpoint: str,
    stage: str,
    changed_paths: list[str] | None = None,
    commit: str | None = None,
    origin_cycle: str | None = None,
    target_evidence: Path | None = None,
) -> dict[str, Any]:
    workspace = resolved_workspace(workspace)
    paths = sorted(dict.fromkeys(changed_paths or _paths_from_git(workspace)))
    material = _plan_material(
        workspace,
        endpoint=endpoint,
        stage=stage,
        changed_paths=paths,
        commit=commit,
        origin_cycle=origin_cycle,
        target_evidence=target_evidence,
    )
    phases = (
        [
            {"id": "identity-audit", "skip_class": "always-run"},
            {"id": "resolve-work-level", "skip_class": "always-run"},
            {"id": "document-audit", "skip_class": "always-run"},
            {"id": "render-disposable-views", "skip_class": "exact-local-digest"},
            {"id": "changed-path-validation", "skip_class": "exact-local-digest"},
        ]
        if stage == "prepare"
        else [
            {"id": "candidate-commit", "skip_class": "always-run"},
            *(
                [{"id": "target-evidence", "skip_class": "current-external-evidence"}]
                if endpoint == "work2"
                else []
            ),
            *(
                [{"id": "release-cohort-register", "skip_class": "exact-local-digest"}]
                if endpoint == "work2"
                else []
            ),
            {"id": "logical-checkpoint", "skip_class": "exact-local-digest"},
            {"id": "checkpoint-rebuild-proof", "skip_class": "exact-local-digest"},
            {"id": "checkpoint-commit", "skip_class": "exact-local-digest"},
            {"id": "strict-doctor", "skip_class": "always-run"},
        ]
    )
    digest = _sha(material)
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "tool-shed-work-orchestration-plan",
        "endpoint": endpoint,
        "stage": stage,
        "state_token": bind_state_token(workspace, "work-orchestration-plan", digest),
        "material_digest": digest,
        "material": material,
        "phases": phases,
        "authority": {
            "script_may": [
                "inspect exact project and state",
                "run settled local validation",
                "refresh disposable views",
                "checkpoint and rebuild authoritative state",
                "register an already-committed Work2 candidate",
                "commit only the exact logical checkpoint and its referenced immutable objects",
            ],
            "script_may_not": [
                "choose product behavior or semantic version",
                "judge evidence sufficiency",
                "select deployment scope or perform deployment",
                "authorize push, release, or production promotion",
                "declare an owning outcome satisfied",
            ],
        },
        "writes_performed": False,
    }


def _journal_path(workspace: Path) -> Path:
    return require_path_within(workspace, workspace / JOURNAL_RELATIVE)


def _read_events(workspace: Path) -> list[dict[str, Any]]:
    path = _journal_path(workspace)
    if not path.is_file():
        return []
    events: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as error:
            raise WorkOrchestrationError(
                f"workflow journal line {line_number} is invalid JSON"
            ) from error
        if not isinstance(item, dict) or item.get("schema_version") != SCHEMA_VERSION:
            raise WorkOrchestrationError(f"workflow journal line {line_number} is unsupported")
        events.append(item)
    return events


def _counter_epoch(workspace: Path) -> str:
    path = require_path_within(workspace, workspace / EPOCH_RELATIVE)
    if path.is_file():
        payload = json.loads(path.read_text(encoding="utf-8"))
        value = payload.get("counter_epoch")
        if isinstance(value, str) and value:
            return value
        raise WorkOrchestrationError("counter epoch file is invalid")
    path.parent.mkdir(parents=True, exist_ok=True)
    value = str(uuid.uuid4())
    path.write_text(
        json.dumps(
            {"schema_version": SCHEMA_VERSION, "counter_epoch": value, "created_at": _stamp()},
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return value


def _append_event(workspace: Path, event: dict[str, Any]) -> None:
    path = _journal_path(workspace)
    path.parent.mkdir(parents=True, exist_ok=True)
    events = _read_events(workspace)
    cutoff = _utc_now() - timedelta(days=RETENTION_DAYS)
    retained = [
        item
        for item in events
        if _parse_stamp(str(item.get("recorded_at"))) >= cutoff
    ][-(MAX_JOURNAL_EVENTS - 1) :]
    retained.append(event)
    temporary = path.with_suffix(".next")
    temporary.write_text(
        "".join(json.dumps(item, sort_keys=True) + "\n" for item in retained),
        encoding="utf-8",
    )
    os.replace(temporary, path)


def record_event(
    workspace: Path,
    *,
    run_id: str,
    phase_id: str,
    classification: str,
    result: str,
    duration_ms: int,
    tool_calls: int,
    output_bytes: int,
    retry_count: int = 0,
    input_token: str | None = None,
    output_token: str | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    diagnostic: str | None = None,
) -> dict[str, Any]:
    workspace = resolved_workspace(workspace)
    if classification not in CLASSIFICATIONS:
        raise WorkOrchestrationError(f"unsupported phase classification: {classification}")
    if result not in RESULTS:
        raise WorkOrchestrationError(f"unsupported phase result: {result}")
    numeric = (duration_ms, tool_calls, output_bytes, retry_count)
    if any(not isinstance(value, int) or value < 0 for value in numeric):
        raise WorkOrchestrationError("duration, calls, output bytes, and retries must be nonnegative")
    if (input_tokens is None) != (output_tokens is None):
        raise WorkOrchestrationError("provider token usage requires both input and output tokens")
    if input_tokens is not None and (input_tokens < 0 or output_tokens is None or output_tokens < 0):
        raise WorkOrchestrationError("provider token usage must be nonnegative")
    bounded = None
    if diagnostic:
        bounded = diagnostic.encode("utf-8")[-MAX_DIAGNOSTIC_BYTES:].decode(
            "utf-8", errors="replace"
        )
    event = {
        "schema_version": SCHEMA_VERSION,
        "kind": "tool-shed-work-orchestration-event",
        "event_id": str(uuid.uuid4()),
        "counter_epoch": _counter_epoch(workspace),
        "project_id": load_project_identity(workspace)["project_id"],
        "run_id": run_id,
        "phase_id": phase_id,
        "classification": classification,
        "result": result,
        "duration_ms": duration_ms,
        "tool_calls": tool_calls,
        "output_bytes": output_bytes,
        "retry_count": retry_count,
        "input_state_token": input_token,
        "output_state_token": output_token,
        "provider_usage": (
            None
            if input_tokens is None
            else {"input_tokens": input_tokens, "output_tokens": output_tokens}
        ),
        "diagnostic": bounded,
        "recorded_at": _stamp(),
    }
    _append_event(workspace, event)
    return event


@dataclass
class PhaseResult:
    phase_id: str
    result: str
    duration_ms: int
    output_bytes: int
    skipped: bool = False


def _completed_event(
    events: list[dict[str, Any]], run_id: str, phase_id: str, input_token: str
) -> dict[str, Any] | None:
    for event in reversed(events):
        if (
            event.get("run_id") == run_id
            and event.get("phase_id") == phase_id
            and event.get("input_state_token") == input_token
            and event.get("result") == "passed"
        ):
            return event
    return None


def _run_phase(
    workspace: Path,
    *,
    run_id: str,
    phase_id: str,
    input_material: object,
    action: Callable[[], object],
    resume: bool,
    always_run: bool = False,
) -> tuple[PhaseResult, object | None]:
    input_token = _sha(input_material)
    if resume and not always_run and _completed_event(
        _read_events(workspace), run_id, phase_id, input_token
    ):
        return PhaseResult(phase_id, "skipped", 0, 0, True), None
    started = time.monotonic()
    try:
        payload = action()
        encoded = _canonical(payload)
    except BaseException as error:
        elapsed = int((time.monotonic() - started) * 1000)
        diagnostic = f"{type(error).__name__}: {error}"
        record_event(
            workspace,
            run_id=run_id,
            phase_id=phase_id,
            classification="deterministic-script",
            result="failed",
            duration_ms=elapsed,
            tool_calls=1,
            output_bytes=len(diagnostic.encode()),
            input_token=input_token,
            diagnostic=diagnostic,
        )
        raise
    elapsed = int((time.monotonic() - started) * 1000)
    output_token = _sha(payload)
    record_event(
        workspace,
        run_id=run_id,
        phase_id=phase_id,
        classification="deterministic-script",
        result="passed",
        duration_ms=elapsed,
        tool_calls=1,
        output_bytes=len(encoded),
        input_token=input_token,
        output_token=output_token,
    )
    return PhaseResult(phase_id, "passed", elapsed, len(encoded)), payload


@contextlib.contextmanager
def _exclusive_run(workspace: Path, run_id: str):
    lock = require_path_within(workspace, workspace / LOCK_RELATIVE)
    lock.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "run_id": run_id,
        "pid": os.getpid(),
        "hostname": socket.gethostname(),
        "started_at": _stamp(),
    }

    def create() -> int:
        return os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)

    try:
        descriptor = create()
    except FileExistsError as error:
        try:
            owner = json.loads(lock.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            owner = {"run_id": "unknown", "pid": "unknown"}
        owner_pid = owner.get("pid")
        same_host = owner.get("hostname") == socket.gethostname()
        alive = True
        if same_host and isinstance(owner_pid, int) and owner_pid > 0:
            try:
                os.kill(owner_pid, 0)
            except ProcessLookupError:
                alive = False
            except (OSError, PermissionError):
                alive = True
        if same_host and not alive:
            lock.unlink(missing_ok=True)
            try:
                descriptor = create()
            except FileExistsError as retry_error:
                raise WorkOrchestrationError(
                    "another orchestration run acquired the recovered lock"
                ) from retry_error
        else:
            raise WorkOrchestrationError(
                f"another orchestration run is active: {owner.get('run_id')} "
                f"(pid {owner.get('pid')})"
            ) from error
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, sort_keys=True)
        handle.write("\n")
    try:
        yield
    finally:
        lock.unlink(missing_ok=True)


def _verify_plan(current: dict[str, Any], expected: str) -> None:
    if expected != current["state_token"]:
        raise WorkOrchestrationError("work orchestration plan state token is stale")
    database = current["material"]["database"]
    if database["classification"] in {"INVALID", "UNJOURNALED"}:
        raise WorkOrchestrationError(
            f"document state is not safe to orchestrate: {database['classification']}"
        )


def _subprocess_payload(command: list[str], workspace: Path) -> dict[str, Any]:
    result = subprocess.run(
        command,
        cwd=workspace,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode:
        combined = (result.stdout + "\n" + result.stderr).encode("utf-8")
        tail = combined[-MAX_DIAGNOSTIC_BYTES:].decode("utf-8", errors="replace")
        raise WorkOrchestrationError(
            f"command failed ({result.returncode}): {' '.join(command[:3])}\n{tail}"
        )
    return {
        "returncode": result.returncode,
        "stdout_bytes": len(result.stdout.encode()),
        "stderr_bytes": len(result.stderr.encode()),
        "output_digest": hashlib.sha256((result.stdout + result.stderr).encode()).hexdigest(),
    }


def _write_run_summary(workspace: Path, payload: dict[str, Any]) -> Path:
    directory = require_path_within(workspace, workspace / RUNS_RELATIVE)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{payload['run_id']}.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def prepare(
    workspace: Path,
    *,
    endpoint: str,
    expected: str,
    project_binding: str,
    changed_paths: list[str] | None,
    run_id: str,
    resume: bool,
) -> dict[str, Any]:
    workspace = resolved_workspace(workspace)
    require_project_binding(workspace, project_binding, operation=OPERATION)
    plan = build_plan(
        workspace,
        endpoint=endpoint,
        stage="prepare",
        changed_paths=changed_paths,
    )
    _verify_plan(plan, expected)
    phases: list[PhaseResult] = []
    with _exclusive_run(workspace, run_id):
        result, _ = _run_phase(
            workspace,
            run_id=run_id,
            phase_id="identity-audit",
            input_material=plan["material"]["project_id"],
            action=lambda: target_capsule(workspace, operation=OPERATION),
            resume=resume,
            always_run=True,
        )
        phases.append(result)
        result, _ = _run_phase(
            workspace,
            run_id=run_id,
            phase_id="resolve-work-level",
            input_material=plan["material"]["work_level"],
            action=lambda: work_level_config.resolve_workspace_level(workspace, endpoint),
            resume=resume,
            always_run=True,
        )
        phases.append(result)
        result, _ = _run_phase(
            workspace,
            run_id=run_id,
            phase_id="document-audit",
            input_material=plan["material"]["database"],
            action=lambda: document_store.audit(workspace),
            resume=resume,
            always_run=True,
        )
        phases.append(result)
        result, _ = _run_phase(
            workspace,
            run_id=run_id,
            phase_id="render-disposable-views",
            input_material=plan["material"]["database"]["domain_digest"],
            action=lambda: document_store.render_views(workspace),
            resume=resume,
        )
        phases.append(result)
        profile = plan["material"]["validation"]["profile"]
        result, _ = _run_phase(
            workspace,
            run_id=run_id,
            phase_id="changed-path-validation",
            input_material={
                "profile": profile,
                "git": plan["material"]["git"],
                "paths": plan["material"]["changed_paths"],
            },
            action=lambda: _subprocess_payload(
                [sys.executable, str(workspace / "scripts/validate_tool_shed.py"), "--profile", profile],
                workspace,
            ),
            resume=resume,
        )
        phases.append(result)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "kind": "tool-shed-work-orchestration-result",
        "run_id": run_id,
        "endpoint": endpoint,
        "stage": "prepare",
        "status": "passed",
        "validation_profile": profile,
        "phases": [item.__dict__ for item in phases],
        "counts": {
            "passed": sum(item.result == "passed" for item in phases),
            "skipped": sum(item.skipped for item in phases),
            "failed": 0,
        },
        "journal": JOURNAL_RELATIVE.as_posix(),
        "writes_performed": True,
    }
    _write_run_summary(workspace, payload)
    return payload


def validate_target_evidence(
    workspace: Path, path: Path, *, endpoint: str, expected_target: str | None
) -> dict[str, Any]:
    absolute = require_path_within(workspace, workspace / path)
    if not absolute.is_file():
        raise WorkOrchestrationError(f"target evidence does not exist: {path}")
    try:
        payload = json.loads(absolute.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise WorkOrchestrationError("target evidence is invalid JSON") from error
    if payload.get("schema_version") != 1 or payload.get("kind") != "tool-shed-target-evidence":
        raise WorkOrchestrationError("target evidence has an unsupported contract")
    if payload.get("endpoint") != endpoint:
        raise WorkOrchestrationError("target evidence endpoint does not match the run")
    if expected_target and payload.get("target") != expected_target:
        raise WorkOrchestrationError("target evidence does not match the configured target")
    checked_at = _parse_stamp(str(payload.get("checked_at")))
    age = _utc_now() - checked_at
    if age < timedelta(minutes=-5) or age > TARGET_EVIDENCE_MAX_AGE:
        raise WorkOrchestrationError("target evidence is not current")
    checks = payload.get("checks")
    if not isinstance(checks, list) or not checks:
        raise WorkOrchestrationError("target evidence requires at least one check")
    for item in checks:
        if not isinstance(item, dict) or set(item) != {"id", "status", "reference"}:
            raise WorkOrchestrationError("target evidence check fields are invalid")
        if item["status"] != "passed" or not str(item["id"]).strip() or not str(item["reference"]).strip():
            raise WorkOrchestrationError("every target evidence check must be passed and referenced")
    return {
        "target": payload.get("target"),
        "endpoint": endpoint,
        "checked_at": payload["checked_at"],
        "check_count": len(checks),
        "evidence_digest": hashlib.sha256(absolute.read_bytes()).hexdigest(),
    }


def _candidate_commit(workspace: Path, commitish: str) -> dict[str, Any]:
    commit = _git(workspace, "rev-parse", "--verify", f"{commitish}^{{commit}}").stdout.strip()
    head = _git(workspace, "rev-parse", "--verify", "HEAD").stdout.strip()
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", commit, head], cwd=workspace, check=False
    ).returncode == 0
    if not ancestor:
        raise WorkOrchestrationError("candidate commit is not reachable from HEAD")
    return {"commit": commit, "head": head, "reachable": True}


def _checkpoint_commit(workspace: Path, message: str) -> dict[str, Any]:
    relative = CHECKPOINT_RELATIVE.as_posix()
    checkpoint = workspace / CHECKPOINT_RELATIVE
    if not checkpoint.is_file():
        raise WorkOrchestrationError("logical checkpoint file does not exist")
    payload = json.loads(checkpoint.read_text(encoding="utf-8"))
    referenced = set(payload.get("envelope", {}).get("objects", []))
    allowed = {relative, *referenced}
    status = _git(workspace, "status", "--porcelain=v1", "--untracked-files=all").stdout.splitlines()
    changed = [line[3:] for line in status]
    unrelated = [path for path in changed if path not in allowed]
    if unrelated:
        raise WorkOrchestrationError(
            "checkpoint commit refused because unrelated tracked changes remain: "
            + ", ".join(unrelated[:5])
        )
    if not status:
        return {"commit": _git(workspace, "rev-parse", "HEAD").stdout.strip(), "created": False}
    _git(workspace, "add", "--", *changed)
    staged = _git(workspace, "diff", "--cached", "--name-only").stdout.splitlines()
    if sorted(staged) != sorted(changed):
        raise WorkOrchestrationError("checkpoint commit staging escaped the logical checkpoint set")
    _git(workspace, "commit", "-m", message)
    return {
        "commit": _git(workspace, "rev-parse", "HEAD").stdout.strip(),
        "created": True,
        "path_count": len(changed),
    }


def _logical_checkpoint(workspace: Path, *, project_binding: str) -> dict[str, Any]:
    audit = document_store.audit(workspace)
    checkpoint = workspace / CHECKPOINT_RELATIVE
    if (
        audit["classification"] == "CLEAN"
        and checkpoint.is_file()
        and audit["current_revision"] == audit["last_checkpoint_revision"]
    ):
        payload = json.loads(checkpoint.read_text(encoding="utf-8"))
        return {
            "schema_version": 2,
            "kind": "tool-shed-document-checkpoint-result",
            "path": CHECKPOINT_RELATIVE.as_posix(),
            "digest": payload["envelope"]["digest"],
            "revision": audit["current_revision"],
            "objects": payload["envelope"]["objects"],
            "idempotent": True,
            "writes_performed": False,
        }
    return document_store.write_checkpoint(
        workspace,
        project_binding=project_binding,
        output=CHECKPOINT_RELATIVE,
    )


def closeout(
    workspace: Path,
    *,
    endpoint: str,
    expected: str,
    project_binding: str,
    commit: str,
    origin_cycle: str | None,
    target_evidence: Path | None,
    checkpoint_message: str,
    run_id: str,
    resume: bool,
) -> dict[str, Any]:
    workspace = resolved_workspace(workspace)
    require_project_binding(workspace, project_binding, operation=OPERATION)
    if endpoint == "work2" and (not origin_cycle or not target_evidence):
        raise WorkOrchestrationError(
            "Work2 closeout requires --origin-cycle and --target-evidence"
        )
    plan = build_plan(
        workspace,
        endpoint=endpoint,
        stage="closeout",
        commit=commit,
        origin_cycle=origin_cycle,
        target_evidence=target_evidence,
    )
    _verify_plan(plan, expected)
    phases: list[PhaseResult] = []
    hybrid_binding = binding_token(workspace, operation="hybrid-state")
    with _exclusive_run(workspace, run_id):
        result, candidate_payload = _run_phase(
            workspace,
            run_id=run_id,
            phase_id="candidate-commit",
            input_material={"commit": commit, "head": plan["material"]["git"]["head"]},
            action=lambda: _candidate_commit(workspace, commit),
            resume=resume,
            always_run=True,
        )
        phases.append(result)
        if endpoint == "work2":
            target = plan["material"]["work_level"]["development_target"]
            result, _ = _run_phase(
                workspace,
                run_id=run_id,
                phase_id="target-evidence",
                input_material=plan["material"]["target_evidence"],
                action=lambda: validate_target_evidence(
                    workspace, target_evidence or Path(), endpoint=endpoint, expected_target=target
                ),
                resume=resume,
                always_run=True,
            )
            phases.append(result)

            cohort_before = release_cohort.status(workspace)
            result, _ = _run_phase(
                workspace,
                run_id=run_id,
                phase_id="release-cohort-register",
                input_material={
                    "state_token": cohort_before["state_token"],
                    "commit": candidate_payload["commit"] if candidate_payload else commit,
                    "origin_cycle": origin_cycle,
                },
                action=lambda: release_cohort.register(
                    workspace,
                    expected=cohort_before["state_token"],
                    project_binding=hybrid_binding,
                    commitish=candidate_payload["commit"] if candidate_payload else commit,
                    origin_cycles=[origin_cycle or ""],
                    accepted_outcome=None,
                    summary=None,
                ),
                resume=resume,
            )
            phases.append(result)

        audit = document_store.audit(workspace)
        result, checkpoint_payload = _run_phase(
            workspace,
            run_id=run_id,
            phase_id="logical-checkpoint",
            input_material=audit["domain_digest"],
            action=lambda: _logical_checkpoint(
                workspace, project_binding=hybrid_binding
            ),
            resume=resume,
        )
        phases.append(result)
        checkpoint_digest = (
            checkpoint_payload["digest"]
            if checkpoint_payload
            else json.loads((workspace / CHECKPOINT_RELATIVE).read_text(encoding="utf-8"))["envelope"]["digest"]
        )
        rebuild_path = Path(f".tool-shed/orchestration/rebuild-{run_id}.sqlite3")

        def prove_rebuild() -> dict[str, Any]:
            absolute = workspace / rebuild_path
            absolute.unlink(missing_ok=True)
            try:
                rebuilt = document_store.rebuild(
                    workspace,
                    project_binding=hybrid_binding,
                    checkpoint=CHECKPOINT_RELATIVE,
                    output=rebuild_path,
                )
                live = document_store.audit(workspace)
                if rebuilt["domain_digest"] != live["domain_digest"]:
                    raise WorkOrchestrationError("logical checkpoint rebuild differs from live state")
                return {
                    "checkpoint_digest": rebuilt["checkpoint_digest"],
                    "domain_digest": rebuilt["domain_digest"],
                }
            finally:
                absolute.unlink(missing_ok=True)

        result, _ = _run_phase(
            workspace,
            run_id=run_id,
            phase_id="checkpoint-rebuild-proof",
            input_material=checkpoint_digest,
            action=prove_rebuild,
            resume=resume,
        )
        phases.append(result)
        result, state_commit = _run_phase(
            workspace,
            run_id=run_id,
            phase_id="checkpoint-commit",
            input_material={"checkpoint_digest": checkpoint_digest, "message": checkpoint_message},
            action=lambda: _checkpoint_commit(workspace, checkpoint_message),
            resume=resume,
        )
        phases.append(result)

        result, doctor_payload = _run_phase(
            workspace,
            run_id=run_id,
            phase_id="strict-doctor",
            input_material=_git_state(workspace),
            action=lambda: doctor.inspect(workspace),
            resume=resume,
            always_run=True,
        )
        phases.append(result)
        if not doctor_payload or doctor_payload["verdict"] != "HEALTHY":
            raise WorkOrchestrationError("strict Doctor is not HEALTHY after closeout")

    payload = {
        "schema_version": SCHEMA_VERSION,
        "kind": "tool-shed-work-orchestration-result",
        "run_id": run_id,
        "endpoint": endpoint,
        "stage": "closeout",
        "status": "passed",
        "candidate_commit": candidate_payload["commit"] if candidate_payload else commit,
        "checkpoint_commit": state_commit["commit"] if state_commit else None,
        "checkpoint_digest": checkpoint_digest,
        "doctor": doctor_payload["verdict"] if doctor_payload else None,
        "phases": [item.__dict__ for item in phases],
        "counts": {
            "passed": sum(item.result == "passed" for item in phases),
            "skipped": sum(item.skipped for item in phases),
            "failed": 0,
        },
        "journal": JOURNAL_RELATIVE.as_posix(),
        "writes_performed": True,
    }
    _write_run_summary(workspace, payload)
    return payload


def efficiency_report(
    workspace: Path, *, hours: int = 24, output: Path | None = None
) -> dict[str, Any]:
    workspace = resolved_workspace(workspace)
    if hours < 1:
        raise WorkOrchestrationError("report window must be at least one hour")
    end = _utc_now()
    start = end - timedelta(hours=hours)
    events = [
        item
        for item in _read_events(workspace)
        if _parse_stamp(str(item.get("recorded_at"))) >= start
    ]
    remedial = [item for item in events if item.get("classification") in REMEDIAL_CLASSES]
    measured = [item for item in remedial if isinstance(item.get("provider_usage"), dict)]
    actual = (
        sum(
            int(item["provider_usage"]["input_tokens"])
            + int(item["provider_usage"]["output_tokens"])
            for item in measured
        )
        if measured
        else None
    )
    coverage = len(measured) / len(remedial) if remedial else 0.0
    result_counts = {name: sum(item.get("result") == name for item in events) for name in RESULTS}
    payload = {
        "schema_version": SCHEMA_VERSION,
        "kind": "tool-shed-project-efficiency-aggregate",
        "project_id": load_project_identity(workspace)["project_id"],
        "counter_epoch": _counter_epoch(workspace),
        "window": {
            "started_at": start.isoformat().replace("+00:00", "Z"),
            "ended_at": end.isoformat().replace("+00:00", "Z"),
            "hours": hours,
        },
        "freshness": {"generated_at": _stamp(), "event_count": len(events)},
        "remedial_tokens_actual": actual,
        "remedial_token_coverage": round(coverage, 6),
        "remedial_proxy": {
            "interactions": len(remedial),
            "tool_calls": sum(int(item.get("tool_calls", 0)) for item in remedial),
            "output_bytes": sum(int(item.get("output_bytes", 0)) for item in remedial),
            "duration_ms": sum(int(item.get("duration_ms", 0)) for item in remedial),
            "retry_count": sum(int(item.get("retry_count", 0)) for item in remedial),
        },
        "classification_counts": {
            name: sum(item.get("classification") == name for item in events)
            for name in CLASSIFICATIONS
        },
        "result_counts": result_counts,
        "measurement_state": (
            "unmeasured"
            if not measured
            else "measured"
            if len(measured) == len(remedial)
            else "partial"
        ),
        "privacy": {
            "contains_prompts": False,
            "contains_commands": False,
            "contains_paths": False,
            "contains_source": False,
            "contains_raw_diagnostics": False,
        },
        "writes_performed": bool(output),
    }
    if output:
        absolute = require_path_within(workspace, workspace / output)
        absolute.parent.mkdir(parents=True, exist_ok=True)
        absolute.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def reset_telemetry(workspace: Path, *, project_binding: str, confirmed: bool) -> dict[str, Any]:
    workspace = resolved_workspace(workspace)
    require_project_binding(workspace, project_binding, operation=OPERATION)
    if not confirmed:
        raise WorkOrchestrationError("telemetry reset requires --confirm-reset")
    for relative in (JOURNAL_RELATIVE, EPOCH_RELATIVE, REPORT_RELATIVE):
        require_path_within(workspace, workspace / relative).unlink(missing_ok=True)
    shutil.rmtree(require_path_within(workspace, workspace / RUNS_RELATIVE), ignore_errors=True)
    epoch = _counter_epoch(workspace)
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "tool-shed-work-orchestration-telemetry-reset",
        "counter_epoch": epoch,
        "writes_performed": True,
    }


def benchmark(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1 or payload.get("kind") != "tool-shed-work-orchestration-baseline":
        raise WorkOrchestrationError("benchmark fixture has an unsupported contract")
    rows = []
    for case in payload.get("cases", []):
        before = case["manual"]
        after = case["scripted"]
        deterministic_percent = 100.0 * after["deterministic_interactions"] / after["total_interactions"]
        output_reduction = 100.0 * (1.0 - after["output_bytes"] / before["output_bytes"])
        call_reduction = 100.0 * (1.0 - after["total_interactions"] / before["total_interactions"])
        passed = (
            deterministic_percent < 15.0
            and after["known_retry_count"] == 0
            and output_reduction > 50.0
            and call_reduction > 25.0
        )
        rows.append(
            {
                "id": case["id"],
                "deterministic_interaction_percent": round(deterministic_percent, 2),
                "output_reduction_percent": round(output_reduction, 2),
                "interaction_reduction_percent": round(call_reduction, 2),
                "known_retry_count": after["known_retry_count"],
                "passed": passed,
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "tool-shed-work-orchestration-benchmark",
        "cases": rows,
        "passed": bool(rows) and all(item["passed"] for item in rows),
        "writes_performed": False,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--json", action="store_true")
    commands = parser.add_subparsers(dest="command", required=True)
    plan_parser = commands.add_parser("plan")
    plan_parser.add_argument("endpoint", choices=ENDPOINTS)
    plan_parser.add_argument("--stage", choices=STAGES, required=True)
    plan_parser.add_argument("--changed-path", action="append")
    plan_parser.add_argument("--commit")
    plan_parser.add_argument("--origin-cycle")
    plan_parser.add_argument("--target-evidence", type=Path)

    prepare_parser = commands.add_parser("prepare")
    prepare_parser.add_argument("endpoint", choices=ENDPOINTS)
    prepare_parser.add_argument("--expect", required=True)
    prepare_parser.add_argument("--project-binding", required=True)
    prepare_parser.add_argument("--changed-path", action="append")
    prepare_parser.add_argument("--run-id", required=True)
    prepare_parser.add_argument("--resume", action="store_true")

    closeout_parser = commands.add_parser("closeout")
    closeout_parser.add_argument("endpoint", choices=ENDPOINTS)
    closeout_parser.add_argument("--expect", required=True)
    closeout_parser.add_argument("--project-binding", required=True)
    closeout_parser.add_argument("--commit", required=True)
    closeout_parser.add_argument("--origin-cycle")
    closeout_parser.add_argument("--target-evidence", type=Path)
    closeout_parser.add_argument("--checkpoint-message", required=True)
    closeout_parser.add_argument("--run-id", required=True)
    closeout_parser.add_argument("--resume", action="store_true")

    record_parser = commands.add_parser("record")
    record_parser.add_argument("--project-binding", required=True)
    record_parser.add_argument("--run-id", required=True)
    record_parser.add_argument("--phase-id", required=True)
    record_parser.add_argument("--classification", choices=CLASSIFICATIONS, required=True)
    record_parser.add_argument("--result", choices=RESULTS, required=True)
    record_parser.add_argument("--duration-ms", type=int, required=True)
    record_parser.add_argument("--tool-calls", type=int, required=True)
    record_parser.add_argument("--output-bytes", type=int, required=True)
    record_parser.add_argument("--retry-count", type=int, default=0)
    record_parser.add_argument("--input-tokens", type=int)
    record_parser.add_argument("--output-tokens", type=int)

    report_parser = commands.add_parser("report")
    report_parser.add_argument("--hours", type=int, default=24)
    report_parser.add_argument("--output", type=Path)

    reset_parser = commands.add_parser("reset-telemetry")
    reset_parser.add_argument("--project-binding", required=True)
    reset_parser.add_argument("--confirm-reset", action="store_true")

    benchmark_parser = commands.add_parser("benchmark")
    benchmark_parser.add_argument(
        "--fixture",
        type=Path,
        default=Path("tests/fixtures/work-orchestration-baseline-v1.json"),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    workspace = Path(args.workspace).expanduser().resolve()
    try:
        if args.command == "plan":
            result = build_plan(
                workspace,
                endpoint=args.endpoint,
                stage=args.stage,
                changed_paths=args.changed_path,
                commit=args.commit,
                origin_cycle=args.origin_cycle,
                target_evidence=args.target_evidence,
            )
        elif args.command == "prepare":
            result = prepare(
                workspace,
                endpoint=args.endpoint,
                expected=args.expect,
                project_binding=args.project_binding,
                changed_paths=args.changed_path,
                run_id=args.run_id,
                resume=args.resume,
            )
        elif args.command == "closeout":
            result = closeout(
                workspace,
                endpoint=args.endpoint,
                expected=args.expect,
                project_binding=args.project_binding,
                commit=args.commit,
                origin_cycle=args.origin_cycle,
                target_evidence=args.target_evidence,
                checkpoint_message=args.checkpoint_message,
                run_id=args.run_id,
                resume=args.resume,
            )
        elif args.command == "record":
            root = resolved_workspace(workspace)
            require_project_binding(root, args.project_binding, operation=OPERATION)
            result = record_event(
                root,
                run_id=args.run_id,
                phase_id=args.phase_id,
                classification=args.classification,
                result=args.result,
                duration_ms=args.duration_ms,
                tool_calls=args.tool_calls,
                output_bytes=args.output_bytes,
                retry_count=args.retry_count,
                input_tokens=args.input_tokens,
                output_tokens=args.output_tokens,
            )
        elif args.command == "report":
            result = efficiency_report(workspace, hours=args.hours, output=args.output)
        elif args.command == "reset-telemetry":
            result = reset_telemetry(
                workspace,
                project_binding=args.project_binding,
                confirmed=args.confirm_reset,
            )
        else:
            result = benchmark(require_path_within(workspace, workspace / args.fixture))
        print(json.dumps(result, indent=2, sort_keys=True))
        return 1 if args.command == "benchmark" and not result["passed"] else 0
    except (
        WorkOrchestrationError,
        ProjectIdentityError,
        work_level_config.WorkLevelConfigError,
        document_store.DocumentStoreError,
        hybrid_state.HybridStateError,
        release_cohort.ReleaseCohortError,
        OSError,
        ValueError,
        json.JSONDecodeError,
    ) as error:
        print(f"Work orchestration failed: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
