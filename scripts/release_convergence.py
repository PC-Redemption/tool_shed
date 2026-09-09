#!/usr/bin/env python3
"""Plan and resume release-wide Tool Shed capability convergence."""

from __future__ import annotations

import sys as _runtime_sys

_runtime_sys.dont_write_bytecode = True

import argparse
import contextlib
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any, Sequence

import authority_resolver
import campaign_execution
import closure_lineage
import document_conversion
import document_store
import hybrid_state
import loop_findings
import subprocess_launch
from project_identity import (
    ProjectIdentityError,
    load_project_identity,
    require_path_within,
    require_project_binding,
    resolved_workspace,
)


SCHEMA_VERSION = 1
KIND = "tool-shed-release-convergence"
INVENTORY_RELATIVE = Path("schemas/release-convergence/v1/capabilities.json")
JOURNAL_RELATIVE = Path(".tool-shed/convergence/journal-v1.jsonl")
CHECKPOINT_RELATIVE = Path("work/state/checkpoints/state-v2.json")
ACTION_CLASSES = {
    "schema-migration",
    "required-compatibility-backfill",
    "optional-semantic-enrichment",
}
class ConvergenceError(RuntimeError):
    pass


def canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()


def digest(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def shed_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_inventory(path: Path | None = None) -> dict[str, Any]:
    source = (path or shed_root() / INVENTORY_RELATIVE).resolve()
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ConvergenceError(f"cannot load release capability inventory: {error}") from error
    if (
        payload.get("schema_version") != 1
        or payload.get("kind") != "tool-shed-release-capability-inventory"
        or not isinstance(payload.get("capabilities"), list)
    ):
        raise ConvergenceError("unsupported release capability inventory")
    schemas: dict[int, str] = {}
    identifiers: set[str] = set()
    for capability in payload["capabilities"]:
        if not isinstance(capability, dict):
            raise ConvergenceError("release capability entries must be objects")
        identifier = str(capability.get("id") or "")
        action_class = str(capability.get("action_class") or "")
        if not identifier or identifier in identifiers:
            raise ConvergenceError("release capability IDs must be unique and non-empty")
        if action_class not in ACTION_CLASSES:
            raise ConvergenceError(f"unsupported capability action class: {action_class}")
        identifiers.add(identifier)
        if action_class == "schema-migration":
            from_schema = int(capability.get("from_schema", -1))
            to_schema = int(capability.get("to_schema", -1))
            if to_schema != from_schema + 1 or from_schema in schemas:
                raise ConvergenceError("schema capability inventory is not a linear unique chain")
            schemas[from_schema] = identifier
    target = int(payload.get("target_hybrid_schema", -1))
    if sorted(schemas) != list(range(target)):
        raise ConvergenceError("schema capability inventory does not reach its declared target")
    payload["inventory_sha256"] = digest(
        {key: value for key, value in payload.items() if key != "inventory_sha256"}
    )
    return payload


def _schema_capability(inventory: dict[str, Any], schema: int) -> dict[str, Any]:
    matches = [
        item
        for item in inventory["capabilities"]
        if item["action_class"] == "schema-migration"
        and int(item["from_schema"]) == schema
    ]
    if len(matches) != 1:
        raise ConvergenceError(f"release inventory has no unique migration from schema {schema}")
    return matches[0]


PROBE_CODE = r"""
import json, os, sqlite3, tempfile
result = {
    "python_version": ".".join(str(v) for v in __import__("sys").version_info[:3]),
    "sqlite_version": sqlite3.sqlite_version,
    "read_healthy": False,
    "mutation_ready": False,
    "diagnostic_code": None,
}
name = None
try:
    descriptor, name = tempfile.mkstemp(prefix="tool-shed-runtime-probe-", suffix=".sqlite3")
    os.close(descriptor)
    connection = sqlite3.connect(name)
    connection.execute("SELECT json_object('probe', 1)").fetchone()
    result["read_healthy"] = True
    connection.execute("PRAGMA trusted_schema=OFF")
    connection.execute("CREATE TABLE source (id INTEGER PRIMARY KEY)")
    connection.execute("CREATE TABLE events (payload TEXT NOT NULL CHECK (json_valid(payload)))")
    connection.execute(
        "CREATE TRIGGER account AFTER INSERT ON source BEGIN "
        "INSERT INTO events VALUES (json_object('operation','insert')); END"
    )
    connection.execute("INSERT INTO source DEFAULT VALUES")
    connection.commit()
    payload = connection.execute("SELECT payload FROM events").fetchone()[0]
    result["mutation_ready"] = json.loads(payload) == {"operation": "insert"}
except sqlite3.DatabaseError as error:
    lowered = str(error).casefold()
    result["diagnostic_code"] = (
        "SQLITE_TRUSTED_SCHEMA_TRIGGER_UNSAFE"
        if "unsafe use of" in lowered
        else "SQLITE_GUARDED_WRITE_FAILED"
    )
finally:
    try:
        connection.close()
    except Exception:
        pass
    if name:
        try:
            os.unlink(name)
        except OSError:
            pass
print(json.dumps(result, sort_keys=True))
"""


def probe_runtime(executable: str, *, role: str) -> dict[str, Any]:
    selected = str(Path(executable).expanduser())
    try:
        completed = subprocess_launch.run(
            [selected, "-B", "-c", PROBE_CODE],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=20,
            check=False,
            windowless=role == "background",
        )
    except (OSError, subprocess.TimeoutExpired):
        return {
            "role": role,
            "executable": selected,
            "python_version": None,
            "sqlite_version": None,
            "read_healthy": False,
            "mutation_ready": False,
            "diagnostic_code": "INTERPRETER_UNAVAILABLE",
            "next_action": f"configure an available Python executable for Tool Shed {role} work",
        }
    try:
        payload = json.loads(completed.stdout.strip()) if completed.returncode == 0 else {}
    except json.JSONDecodeError:
        payload = {}
    code = payload.get("diagnostic_code")
    if not payload or completed.returncode:
        code = "RUNTIME_PROBE_FAILED"
    next_action = None
    if code == "SQLITE_TRUSTED_SCHEMA_TRIGGER_UNSAFE":
        next_action = (
            f"select a newer Python/SQLite runtime for Tool Shed {role} writes; "
            "the current runtime cannot execute hardened accounting triggers"
        )
    elif code:
        next_action = f"repair or replace the configured Tool Shed {role} Python runtime"
    return {
        "role": role,
        "executable": str(Path(selected).resolve()),
        "python_version": payload.get("python_version"),
        "sqlite_version": payload.get("sqlite_version"),
        "read_healthy": bool(payload.get("read_healthy")),
        "mutation_ready": bool(payload.get("mutation_ready")),
        "diagnostic_code": code,
        "next_action": next_action,
    }


def configured_runtime_probes(
    *, interactive: str | None = None, background: str | None = None
) -> list[dict[str, Any]]:
    interactive_executable = interactive or sys.executable
    background_executable = background or subprocess_launch.background_python_executable(
        interactive_executable
    )
    return [
        probe_runtime(interactive_executable, role="interactive"),
        probe_runtime(background_executable, role="background"),
    ]


def _work_digest(workspace: Path) -> str:
    value = hashlib.sha256()
    work = workspace / "work"
    if not work.is_dir():
        return value.hexdigest()
    for path in sorted(work.rglob("*.md")):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(workspace).as_posix()
        value.update(relative.encode())
        value.update(b"\0")
        value.update(path.read_bytes())
        value.update(b"\0")
    return value.hexdigest()


def _git_status_digest(workspace: Path) -> str:
    completed = subprocess.run(
        ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"],
        cwd=workspace,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return hashlib.sha256(completed.stdout if completed.returncode == 0 else b"unavailable").hexdigest()


def _git_workspace_eligible(workspace: Path) -> bool:
    completed = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=workspace,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if completed.returncode:
        return False
    try:
        return Path(completed.stdout.strip()).resolve() == workspace
    except OSError:
        return False


def _database_state(workspace: Path) -> dict[str, Any]:
    database = hybrid_state.database_path(workspace)
    if not database.is_file():
        return {
            "present": False,
            "schema": 0,
            "revision": 0,
            "domain_digest": hybrid_state.EMPTY_SHA256,
            "classification": "ABSENT",
            "storage_mode": "file",
        }
    audit = hybrid_state.audit(workspace)
    return {
        "present": True,
        "schema": int(audit["schema_version"]),
        "revision": int(audit["current_revision"]),
        "domain_digest": str(audit["domain_digest"]),
        "classification": str(audit["classification"]),
        "storage_mode": str(audit["storage_mode"]),
    }


def _converted_document_state(workspace: Path, schema: int) -> dict[str, Any]:
    if schema < 2:
        return {"converted": 0, "pending": None, "relationships": None}
    database = hybrid_state.database_path(workspace)
    with contextlib.closing(hybrid_state.connect(database, writable=False)) as connection:
        converted = int(
            connection.execute(
                "SELECT COUNT(*) FROM document_conversion "
                "WHERE classification='generated' AND status IN ('verified','cutover')"
            ).fetchone()[0]
        )
    relationship_plan = document_conversion.build_relationship_plan(
        workspace, database=database
    )
    return {
        "converted": converted,
        "pending": None,
        "relationships": {
            "candidate_count": len(relationship_plan["candidates"]),
            "finding_count": len(relationship_plan["findings"]),
            "manifest_token": relationship_plan["manifest_token"],
        },
    }


def _state_material(
    workspace: Path,
    inventory: dict[str, Any],
    database: dict[str, Any],
    authority: dict[str, Any],
    runtimes: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "project_id": load_project_identity(workspace)["project_id"],
        "inventory_sha256": inventory["inventory_sha256"],
        "database": database,
        "authority": {
            key: authority.get(key)
            for key in (
                "authority",
                "state",
                "storage_mode",
                "hybrid_schema",
                "feature_limits",
                "next_action",
            )
        },
        "runtimes": [
            {
                key: item.get(key)
                for key in (
                    "role",
                    "executable",
                    "python_version",
                    "sqlite_version",
                    "read_healthy",
                    "mutation_ready",
                    "diagnostic_code",
                )
            }
            for item in runtimes
        ],
        "work_digest": _work_digest(workspace),
        "git_status_digest": _git_status_digest(workspace),
        "workspace_eligible": _git_workspace_eligible(workspace),
    }


def build_plan(
    workspace: Path,
    *,
    inventory_path: Path | None = None,
    interactive: str | None = None,
    background: str | None = None,
) -> dict[str, Any]:
    workspace = resolved_workspace(workspace)
    inventory = load_inventory(inventory_path)
    database = _database_state(workspace)
    authority = authority_resolver.resolve(workspace)
    runtimes = configured_runtime_probes(
        interactive=interactive, background=background
    )
    runtime_ready = all(item["mutation_ready"] for item in runtimes)
    actions: list[dict[str, Any]] = []
    schema = int(database["schema"])
    target_schema = int(inventory["target_hybrid_schema"])
    workspace_eligible = _git_workspace_eligible(workspace)
    for from_schema in range(target_schema):
        capability = _schema_capability(inventory, from_schema)
        if schema >= int(capability["to_schema"]):
            state, reason = "satisfied", "schema level is present"
        elif schema == from_schema and from_schema == 0 and not workspace_eligible:
            state = "deferred"
            reason = "Hybrid state requires this path to be the exact Git workspace root"
        elif schema == from_schema:
            state = "ready" if runtime_ready else "blocked"
            reason = (
                "safe guarded migration is ready"
                if runtime_ready
                else "configured runtime cannot execute guarded SQLite writes"
            )
        else:
            state, reason = "waiting", "an earlier schema capability must complete first"
        actions.append(
            {
                "id": capability["id"],
                "action_class": capability["action_class"],
                "automatic": bool(capability["automatic"]),
                "state": state,
                "reason": reason,
                "command": capability["command"],
            }
        )

    document_state = _converted_document_state(workspace, schema)
    by_id = {item["id"]: item for item in inventory["capabilities"]}
    document_capability = by_id["document-authority"]
    if database["storage_mode"] == "hybrid":
        document_action_state = "satisfied"
        document_reason = "guarded Hybrid cutover is active"
    elif schema < int(document_capability["minimum_schema"]):
        document_action_state = "waiting"
        document_reason = "database document schema is not present"
    else:
        document_action_state = "deferred"
        document_reason = (
            "file authority remains active until one explicit archived conversion and cutover"
        )
    actions.append(
        {
            "id": "document-authority",
            "action_class": document_capability["action_class"],
            "automatic": False,
            "state": document_action_state,
            "reason": document_reason,
            "command": document_capability["command"],
        }
    )

    relationships = document_state.get("relationships")
    relationship_candidates = (
        int(relationships["candidate_count"]) if relationships else 0
    )
    relationship_findings = int(relationships["finding_count"]) if relationships else 0
    if schema < 2:
        relationship_state, relationship_reason = (
            "waiting",
            "database document schema is not present",
        )
    elif relationship_candidates:
        relationship_state, relationship_reason = (
            "ready",
            f"{relationship_candidates} unambiguous relationship backfill(s) are ready",
        )
    elif relationship_findings:
        relationship_state, relationship_reason = (
            "blocked",
            f"{relationship_findings} relationship reference(s) require resolution",
        )
    else:
        relationship_state, relationship_reason = (
            "satisfied",
            "all extractable document relationships have parity",
        )
    actions.append(
        {
            "id": "document-relationships",
            "action_class": "required-compatibility-backfill",
            "automatic": True,
            "state": relationship_state,
            "reason": relationship_reason,
            "command": "document_conversion.py relationships-plan/relationships-apply",
        }
    )
    optional_capability = by_id["historical-outcome-enrichment"]
    optional_state = (
        "available"
        if schema >= int(optional_capability["minimum_schema"])
        else "waiting"
    )
    actions.append(
        {
            "id": optional_capability["id"],
            "action_class": optional_capability["action_class"],
            "automatic": bool(optional_capability["automatic"]),
            "state": optional_state,
            "reason": (
                "optional readiness and historical outcome enrichment is never fabricated"
                if optional_state == "available"
                else "required outcome schema is not present"
            ),
            "command": optional_capability["command"],
        }
    )

    decisions = []
    if document_action_state == "deferred":
        decisions.append(
            {
                "id": "document-authority",
                "impact": (
                    "import retained generated work with stable identities, verify semantic parity, "
                    "checkpoint, and switch every consumer from file to SQLite authority"
                ),
                "fallback": "retain coherent file authority with Hybrid-only features unavailable",
                "rollback": "restore the verified retained-source archive and pre-cutover SQLite backup",
                "continuation_command": (
                    "python3 scripts/release_convergence.py --workspace . apply "
                    "--plan <plan.json> --expect <plan-token> --project-binding "
                    "<hybrid-state-binding> --allow document-authority "
                    "--archive <outside-workspace-path>"
                ),
            }
        )

    material = _state_material(workspace, inventory, database, authority, runtimes)
    plan_token = digest(material)[:16]
    counts = {
        state: sum(item["state"] == state for item in actions)
        for state in ("satisfied", "ready", "waiting", "deferred", "blocked", "available")
    }
    if counts["blocked"]:
        state = "blocked"
    elif counts["ready"]:
        state = "actionable"
    elif counts["deferred"]:
        state = "deferred"
    else:
        state = "converged"
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": f"{KIND}-plan",
        "release_contract": inventory["release_contract"],
        "inventory_sha256": inventory["inventory_sha256"],
        "project_id": material["project_id"],
        "plan_token": plan_token,
        "state_material": material,
        "state": state,
        "authority": authority,
        "database": database,
        "runtime_capability": {
            "read_healthy": all(item["read_healthy"] for item in runtimes),
            "mutation_ready": runtime_ready,
            "probes": runtimes,
        },
        "document_integrity": document_state,
        "actions": actions,
        "decisions": decisions,
        "summary": {
            "state": state,
            "satisfied": counts["satisfied"],
            "ready": counts["ready"],
            "waiting": counts["waiting"],
            "deferred": counts["deferred"],
            "blocked": counts["blocked"],
            "optional_available": counts["available"],
        },
        "writes_performed": False,
    }


def _load_plan(workspace: Path, supplied: Path) -> dict[str, Any]:
    path = require_path_within(
        workspace, supplied if supplied.is_absolute() else workspace / supplied
    )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ConvergenceError(f"cannot load convergence plan: {error}") from error
    if payload.get("schema_version") != 1 or payload.get("kind") != f"{KIND}-plan":
        raise ConvergenceError("unsupported convergence plan")
    return payload


def _journal_path(workspace: Path) -> Path:
    path = require_path_within(workspace, workspace / JOURNAL_RELATIVE)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _journal_rows(workspace: Path) -> list[dict[str, Any]]:
    path = _journal_path(workspace)
    if not path.is_file():
        return []
    rows = []
    prior = "0" * 64
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        try:
            row = json.loads(line)
        except json.JSONDecodeError as error:
            raise ConvergenceError(f"convergence journal line {number} is invalid") from error
        observed = row.pop("event_sha256", None)
        if row.get("previous_sha256") != prior or digest(row) != observed:
            raise ConvergenceError(f"convergence journal line {number} breaks its hash chain")
        row["event_sha256"] = observed
        prior = str(observed)
        rows.append(row)
    return rows


def _append_journal(workspace: Path, event: dict[str, Any]) -> dict[str, Any]:
    rows = _journal_rows(workspace)
    bounded = {
        "schema_version": 1,
        "kind": "tool-shed-release-convergence-event",
        "sequence": len(rows) + 1,
        "run_id": str(event["run_id"]),
        "plan_token": str(event["plan_token"]),
        "step": str(event["step"]),
        "state": str(event["state"]),
        "attempt": int(event.get("attempt", 1)),
        "diagnostic_code": event.get("diagnostic_code"),
        "before_schema": event.get("before_schema"),
        "after_schema": event.get("after_schema"),
        "previous_sha256": rows[-1]["event_sha256"] if rows else "0" * 64,
    }
    bounded["event_sha256"] = digest(bounded)
    path = _journal_path(workspace)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(bounded, sort_keys=True, separators=(",", ":")) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return bounded


def _attempt(rows: list[dict[str, Any]], step: str) -> int:
    return 1 + max(
        (int(row["attempt"]) for row in rows if row.get("step") == step),
        default=0,
    )


def _run_schema_step(
    workspace: Path, schema: int, *, project_binding: str
) -> dict[str, Any]:
    if schema == 0:
        return hybrid_state.initialize(
            workspace, project_binding=project_binding, storage_mode="shadow"
        )
    if schema == 1:
        return document_store.migrate(workspace, project_binding=project_binding)
    if schema == 2:
        manifest = closure_lineage.prepare_migration(workspace)
        validation = closure_lineage.validate_manifest(workspace, manifest)
        if not validation["applicable"]:
            raise ConvergenceError("SEMANTIC_MIGRATION_AMBIGUITY")
        return closure_lineage.apply_migration(
            workspace,
            manifest,
            expected_token=manifest["manifest_token"],
            project_binding=project_binding,
        )
    if schema in {3, 4}:
        return loop_findings.migrate(workspace, project_binding=project_binding)
    if schema == 5:
        return campaign_execution.migrate(workspace, project_binding=project_binding)
    raise ConvergenceError(f"no guarded schema step exists for schema {schema}")


def _apply_relationships(
    workspace: Path, *, project_binding: str, actor: str
) -> dict[str, Any] | None:
    plan = document_conversion.build_relationship_plan(workspace)
    if not plan["candidates"]:
        return None
    return document_conversion.apply_relationship_plan(
        workspace,
        project_binding=project_binding,
        manifest=plan,
        actor=actor,
    )


def _convert_and_cutover(
    workspace: Path,
    *,
    project_binding: str,
    archive: Path,
    actor: str,
) -> dict[str, Any]:
    resolved_archive = archive.expanduser().resolve()
    if workspace == resolved_archive or workspace in resolved_archive.parents or resolved_archive in workspace.parents:
        raise ConvergenceError("document authority archive must be outside the workspace")
    database = hybrid_state.database_path(workspace)
    conversion = document_conversion.build_plan(workspace, database=database)
    archive_result = document_conversion.create_archive(
        workspace, manifest=conversion, destination=resolved_archive
    )
    apply_result = document_conversion.apply_plan(
        workspace,
        project_binding=project_binding,
        manifest=conversion,
        database=database,
        actor=actor,
    )
    relationships = _apply_relationships(
        workspace, project_binding=project_binding, actor=actor
    )
    qualification = document_conversion.qualify(
        workspace, manifest=conversion, database=database
    )
    if not qualification["passed"]:
        raise ConvergenceError("SEMANTIC_PARITY_FAILED")
    checkpoint = document_store.write_checkpoint(
        workspace,
        project_binding=project_binding,
        output=workspace / CHECKPOINT_RELATIVE,
    )
    cutover = hybrid_state.activate_hybrid_mode(
        workspace,
        project_binding=project_binding,
        expected_checkpoint_digest=checkpoint["digest"],
    )
    return {
        "archive": archive_result,
        "conversion": apply_result,
        "relationships": relationships,
        "qualification": qualification,
        "checkpoint": checkpoint,
        "cutover": cutover,
    }


def apply_plan(
    workspace: Path,
    *,
    supplied_plan: dict[str, Any],
    expected_token: str,
    project_binding: str,
    allow: set[str] | None = None,
    archive: Path | None = None,
    actor: str = "release-convergence",
    stop_after_journal: str | None = None,
) -> dict[str, Any]:
    workspace = resolved_workspace(workspace)
    require_project_binding(workspace, project_binding, operation="hybrid-state")
    if supplied_plan.get("plan_token") != expected_token:
        raise ConvergenceError("convergence plan token does not match --expect")
    probes = supplied_plan.get("runtime_capability", {}).get("probes") or []
    roles = {str(item.get("role")): str(item.get("executable")) for item in probes}
    current = build_plan(
        workspace,
        interactive=roles.get("interactive"),
        background=roles.get("background"),
    )
    if current["plan_token"] != expected_token:
        raise ConvergenceError("convergence plan is stale; prepare a fresh plan")
    run_id = str(uuid.uuid4())
    rows = _journal_rows(workspace)
    results: list[dict[str, Any]] = []
    while True:
        database = _database_state(workspace)
        schema = int(database["schema"])
        if schema >= int(load_inventory()["target_hybrid_schema"]):
            break
        step = str(_schema_capability(load_inventory(), schema)["id"])
        attempt = _attempt(rows, step)
        _append_journal(
            workspace,
            {
                "run_id": run_id,
                "plan_token": expected_token,
                "step": step,
                "state": "running",
                "attempt": attempt,
                "before_schema": schema,
                "after_schema": schema,
            },
        )
        if stop_after_journal == step:
            return {
                "schema_version": 1,
                "kind": f"{KIND}-result",
                "state": "interrupted",
                "run_id": run_id,
                "step": step,
                "journal": JOURNAL_RELATIVE.as_posix(),
                "writes_performed": True,
            }
        try:
            result = _run_schema_step(
                workspace, schema, project_binding=project_binding
            )
        except Exception as error:
            diagnostic = (
                str(error)
                if str(error).isupper() and " " not in str(error)
                else "GUARDED_STEP_FAILED"
            )
            _append_journal(
                workspace,
                {
                    "run_id": run_id,
                    "plan_token": expected_token,
                    "step": step,
                    "state": "failed",
                    "attempt": attempt,
                    "diagnostic_code": diagnostic,
                    "before_schema": schema,
                    "after_schema": _database_state(workspace)["schema"],
                },
            )
            raise ConvergenceError(
                f"{step} failed ({diagnostic}); inspect its guarded backup or stale shadow before resume"
            ) from error
        after_schema = int(_database_state(workspace)["schema"])
        _append_journal(
            workspace,
            {
                "run_id": run_id,
                "plan_token": expected_token,
                "step": step,
                "state": "succeeded",
                "attempt": attempt,
                "before_schema": schema,
                "after_schema": after_schema,
            },
        )
        results.append({"step": step, "from_schema": schema, "to_schema": after_schema})
        rows = _journal_rows(workspace)

    relationship_result = _apply_relationships(
        workspace, project_binding=project_binding, actor=actor
    )
    if relationship_result:
        results.append({"step": "document-relationships", "result": relationship_result})

    authority_result = None
    allowed = allow or set()
    state = _database_state(workspace)
    if "document-authority" in allowed and state["storage_mode"] != "hybrid":
        if archive is None:
            raise ConvergenceError("--allow document-authority requires --archive")
        authority_result = _convert_and_cutover(
            workspace,
            project_binding=project_binding,
            archive=archive,
            actor=actor,
        )
        results.append({"step": "document-authority", "result": authority_result})

    final = build_plan(
        workspace,
        interactive=roles.get("interactive"),
        background=roles.get("background"),
    )
    return {
        "schema_version": 1,
        "kind": f"{KIND}-result",
        "state": final["state"],
        "run_id": run_id,
        "source_plan_token": expected_token,
        "result_count": len(results),
        "results": results,
        "final_plan": final,
        "journal": JOURNAL_RELATIVE.as_posix(),
        "writes_performed": bool(results),
    }


def render_human(payload: dict[str, Any]) -> str:
    summary = payload.get("summary") or payload.get("final_plan", {}).get("summary") or {}
    lines = [
        f"Tool Shed release convergence: {payload.get('state', 'unknown').upper()}",
        (
            "Capabilities: "
            f"{summary.get('satisfied', 0)} satisfied, "
            f"{summary.get('ready', 0)} ready, "
            f"{summary.get('deferred', 0)} deferred, "
            f"{summary.get('blocked', 0)} blocked"
        ),
    ]
    runtime = payload.get("runtime_capability") or payload.get("final_plan", {}).get(
        "runtime_capability", {}
    )
    lines.append(
        "Runtime: "
        + ("read healthy" if runtime.get("read_healthy") else "read unhealthy")
        + "; "
        + ("mutation ready" if runtime.get("mutation_ready") else "mutation unavailable")
    )
    decisions = payload.get("decisions") or payload.get("final_plan", {}).get("decisions") or []
    for decision in decisions:
        lines.extend(
            [
                f"Decision {decision['id']}: {decision['impact']}",
                f"Fallback: {decision['fallback']}",
                f"Rollback: {decision['rollback']}",
                f"Continue: {decision['continuation_command']}",
            ]
        )
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--json", action="store_true")
    commands = parser.add_subparsers(dest="command", required=True)
    probe = commands.add_parser("probe")
    probe.add_argument("--interactive")
    probe.add_argument("--background")
    plan = commands.add_parser("plan")
    plan.add_argument("--inventory")
    plan.add_argument("--interactive")
    plan.add_argument("--background")
    plan.add_argument("--output")
    status = commands.add_parser("status")
    status.add_argument("--interactive")
    status.add_argument("--background")
    apply = commands.add_parser("apply")
    apply.add_argument("--plan", required=True)
    apply.add_argument("--expect", required=True)
    apply.add_argument("--project-binding", required=True)
    apply.add_argument("--allow", action="append", default=[])
    apply.add_argument("--archive")
    apply.add_argument("--actor", default="release-convergence")
    apply.add_argument("--stop-after-journal", help=argparse.SUPPRESS)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        workspace = resolved_workspace(Path(args.workspace))
        if args.command == "probe":
            result = {
                "schema_version": 1,
                "kind": f"{KIND}-runtime-probe",
                "probes": configured_runtime_probes(
                    interactive=args.interactive, background=args.background
                ),
                "writes_performed": False,
            }
        elif args.command in {"plan", "status"}:
            result = build_plan(
                workspace,
                inventory_path=Path(args.inventory) if args.command == "plan" and args.inventory else None,
                interactive=args.interactive,
                background=args.background,
            )
            if args.command == "plan" and args.output:
                output = require_path_within(workspace, workspace / args.output)
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(
                    json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
                )
        else:
            supplied = _load_plan(workspace, Path(args.plan))
            result = apply_plan(
                workspace,
                supplied_plan=supplied,
                expected_token=args.expect,
                project_binding=args.project_binding,
                allow=set(args.allow),
                archive=Path(args.archive) if args.archive else None,
                actor=args.actor,
                stop_after_journal=args.stop_after_journal,
            )
        print(json.dumps(result, indent=2, sort_keys=True) if args.json else render_human(result))
        if args.command == "probe":
            return 1 if any(not item["mutation_ready"] for item in result["probes"]) else 0
        return 0
    except (
        ConvergenceError,
        ProjectIdentityError,
        document_store.DocumentStoreError,
        document_conversion.ConversionError,
        hybrid_state.HybridStateError,
        sqlite3.DatabaseError,
        OSError,
        ValueError,
        json.JSONDecodeError,
    ) as error:
        print(f"Release convergence failed: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
