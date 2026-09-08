#!/usr/bin/env python3
"""Persist Work2 candidates and reconcile their owning outcomes at Work5."""

from __future__ import annotations

import sys as _runtime_sys

_runtime_sys.dont_write_bytecode = True

import argparse
import contextlib
import hashlib
import json
import re
import sqlite3
import subprocess
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Sequence

import document_store
import hybrid_state
import release_projection
from app_server_user_state import (
    AppServerUserStateError,
    require_no_app_server_dispatch_debt,
)
try:
    from scripts import subprocess_launch
except ModuleNotFoundError:  # Direct execution: python scripts/release_cohort.py
    import subprocess_launch  # type: ignore[no-redef]
from project_identity import bind_state_token, load_project_identity, resolved_workspace


SCHEMA_VERSION = 1
KIND = "tool-shed-release-cohort-status"
OPERATION = "hybrid-state"
COHORT_KIND = "release-cohort"
ACTIVE_STATES = {"working", "frozen", "released-pending-reconciliation"}
MUTABLE_STATES = {"working", "frozen"}
TERMINAL_DISPOSITIONS = {
    "satisfied",
    "satisfied-with-approved-change",
    "not-applicable",
}
SEMVER_TAG = re.compile(r"^v([0-9]+)\.([0-9]+)\.([0-9]+)$")


class ReleaseCohortError(RuntimeError):
    pass


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _sha(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _git(workspace: Path, *arguments: str, check: bool = True) -> str:
    result = subprocess_launch.run(
        ["git", *arguments],
        cwd=workspace,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if check and result.returncode:
        raise ReleaseCohortError(result.stderr.strip() or "Git operation failed")
    return result.stdout.strip()


def _commit(workspace: Path, value: str) -> str:
    resolved = _git(workspace, "rev-parse", "--verify", f"{value}^{{commit}}")
    if not re.fullmatch(r"[0-9a-f]{40}", resolved):
        raise ReleaseCohortError(f"Git did not resolve a full commit for {value}")
    return resolved


def _is_ancestor(workspace: Path, older: str, newer: str) -> bool:
    result = subprocess_launch.run(
        ["git", "merge-base", "--is-ancestor", older, newer],
        cwd=workspace,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def _base_tag(workspace: Path, commit: str) -> str:
    candidates: dict[tuple[int, int, int], list[str]] = {}
    for tag in _git(workspace, "tag", "--merged", commit, "--list", "v[0-9]*").splitlines():
        match = SEMVER_TAG.fullmatch(tag.strip())
        if match:
            candidates.setdefault(tuple(int(value) for value in match.groups()), []).append(tag.strip())
    if candidates:
        version = max(candidates)
        exact_tags = sorted(set(candidates[version]))
        if len(exact_tags) != 1:
            raise ReleaseCohortError(
                "release tags normalize to the same version: " + ", ".join(exact_tags)
            )
        return exact_tags[0]
    roots = _git(workspace, "rev-list", "--max-parents=0", commit).splitlines()
    if not roots:
        raise ReleaseCohortError("repository has no reachable root commit")
    return f"root:{roots[0]}"


def _semver_tuple(tag: str) -> tuple[int, int, int]:
    match = SEMVER_TAG.fullmatch(tag)
    if not match:
        raise ReleaseCohortError("release tag must contain three digit-only version segments")
    return tuple(int(value) for value in match.groups())


def _require_unambiguous_tag(workspace: Path, tag: str) -> str:
    version = _semver_tuple(tag)
    aliases = sorted(
        candidate
        for candidate in _git(workspace, "tag", "--list", "v[0-9]*").splitlines()
        if SEMVER_TAG.fullmatch(candidate) and _semver_tuple(candidate) == version
    )
    if tag not in aliases:
        raise ReleaseCohortError(f"release tag does not exist: {tag}")
    if len(aliases) != 1:
        raise ReleaseCohortError(
            "release tags normalize to the same version: " + ", ".join(aliases)
        )
    return _commit(workspace, f"refs/tags/{tag}")


def _base_commit(workspace: Path, reference: str) -> str:
    if reference.startswith("root:"):
        return _commit(workspace, reference.removeprefix("root:"))
    return _require_unambiguous_tag(workspace, reference)


def _latest_outcome(connection: sqlite3.Connection, cycle_id: str) -> dict[str, Any]:
    row = connection.execute(
        "SELECT c.lifecycle_state, c.origin_artifact_id, a.current_path, v.disposition, r.state "
        "FROM cycle c JOIN artifact a ON a.id = c.origin_artifact_id "
        "LEFT JOIN reconciliation r ON r.cycle_id = c.id AND r.origin_revision = "
        "(SELECT MAX(r2.origin_revision) FROM reconciliation r2 WHERE r2.cycle_id = c.id) "
        "LEFT JOIN outcome_verdict v ON v.id = r.verdict_id WHERE c.id = ?",
        (cycle_id,),
    ).fetchone()
    if row is None:
        raise ReleaseCohortError(f"outcome cycle does not exist: {cycle_id}")
    return dict(row)


def _active_cohort_rows(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    placeholders = ",".join("?" for _ in ACTIVE_STATES)
    return connection.execute(
        "SELECT c.id AS cycle_id, c.lifecycle_state, c.accepted_outcome, "
        "c.origin_artifact_id, a.current_path FROM cycle c "
        "JOIN artifact a ON a.id = c.origin_artifact_id "
        f"WHERE c.kind = ? AND c.lifecycle_state IN ({placeholders}) "
        "ORDER BY c.opened_at, c.id",
        (COHORT_KIND, *sorted(ACTIVE_STATES)),
    ).fetchall()


def _cohort_evidence(connection: sqlite3.Connection, cycle_id: str, kind: str) -> list[sqlite3.Row]:
    return connection.execute(
        "SELECT id, reference, target_identity, collected_at FROM evidence_reference "
        "WHERE cycle_id = ? AND kind = ? ORDER BY collected_at, id",
        (cycle_id, kind),
    ).fetchall()


def _next_evidence_time(connection: sqlite3.Connection, cycle_id: str, kind: str) -> str:
    """Return a second-resolution timestamp newer than prior evidence of this kind."""
    current = hybrid_state.now()
    previous = connection.execute(
        "SELECT MAX(collected_at) FROM evidence_reference WHERE cycle_id = ? AND kind = ?",
        (cycle_id, kind),
    ).fetchone()[0]
    if previous is None or current > str(previous):
        return current
    previous_time = datetime.fromisoformat(str(previous).replace("Z", "+00:00"))
    return (previous_time + timedelta(seconds=1)).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _candidate_rows(connection: sqlite3.Connection, cohort_id: str) -> list[dict[str, Any]]:
    rows = connection.execute(
        "SELECT q.id AS requirement_id, q.origin_artifact_id, q.accepted_outcome, "
        "q.disposition, e.reference AS commit_reference, e.target_identity AS origin_cycle_id, "
        "a.current_path AS origin_path "
        "FROM requirement q JOIN verification_result v ON v.requirement_id = q.id "
        "AND v.command_or_test_id = 'work2-checkpoint' "
        "JOIN evidence_reference e ON e.id = v.evidence_id "
        "JOIN artifact a ON a.id = q.origin_artifact_id "
        "WHERE q.cycle_id = ? ORDER BY q.accepted_revision, q.id",
        (cohort_id,),
    ).fetchall()
    results: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item["commit"] = str(item.pop("commit_reference")).removeprefix("git:")
        outcome = _latest_outcome(connection, str(item["origin_cycle_id"]))
        item["origin_lifecycle"] = outcome["lifecycle_state"]
        item["origin_verdict"] = outcome["disposition"]
        item["origin_reconciliation"] = outcome["state"]
        document = connection.execute(
            "SELECT lifecycle_state FROM document WHERE id=?",
            (item["origin_artifact_id"],),
        ).fetchone() if connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='document'"
        ).fetchone() else None
        closure_available = bool(connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='closure_rollup'"
        ).fetchone())
        closure = connection.execute(
            "SELECT cr.effective_closed FROM closure_element ce JOIN closure_rollup cr "
            "ON cr.element_id=ce.id WHERE ce.cycle_id=? AND ce.role='cycle' "
            "ORDER BY ce.subject_revision DESC, ce.id LIMIT 1",
            (item["origin_cycle_id"],),
        ).fetchone() if closure_available else None
        item["origin_document_lifecycle"] = (
            str(document["lifecycle_state"]) if document is not None else None
        )
        item["origin_recursive_closure"] = (
            bool(closure["effective_closed"]) if closure is not None else None
        )
        item["origin_ready_to_finalize"] = (
            outcome["lifecycle_state"] == "terminal"
            and outcome["disposition"] in TERMINAL_DISPOSITIONS
            and outcome["state"] == "reconciled"
            and (
                document is None
                or str(document["lifecycle_state"])
                in document_store.TERMINAL_DOCUMENT_LIFECYCLES
            )
            and (not closure_available or bool(closure and closure["effective_closed"]))
        )
        results.append(item)
    return results


def _projection_inventory(connection: sqlite3.Connection) -> dict[str, Any]:
    """Return the complete ID-only document graph needed for release grouping."""
    if connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='document'"
    ).fetchone() is None:
        return {"artifacts": []}
    rows = connection.execute(
        "SELECT a.id, d.visible_id, a.type FROM artifact a JOIN document d ON d.id=a.id "
        "WHERE a.current_path LIKE 'sqlite/documents/%' ORDER BY d.visible_id"
    ).fetchall()
    visible_by_id = {str(row["id"]): str(row["visible_id"]) for row in rows}
    artifacts = {
        str(row["id"]): {
            "visible_id": str(row["visible_id"]),
            "artifact_type": str(row["type"]),
            "parent_ids": [],
            "produces_ids": [],
        }
        for row in rows
    }
    if artifacts:
        for relation in connection.execute(
            "SELECT from_artifact_id, relation_type, to_artifact_id FROM relationship "
            "WHERE retired_revision IS NULL AND relation_type IN ('outcome-parent','produces')"
        ):
            source = str(relation["from_artifact_id"])
            target = str(relation["to_artifact_id"])
            if source not in artifacts or target not in artifacts:
                continue
            if relation["relation_type"] == "outcome-parent":
                artifacts[source]["parent_ids"].append(visible_by_id[target])
            else:
                artifacts[source]["produces_ids"].append(visible_by_id[target])
                artifacts[target]["parent_ids"].append(visible_by_id[source])
    return {"artifacts": list(artifacts.values())}


def _cohort_capsule(connection: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
    cycle_id = str(row["cycle_id"])
    base = _cohort_evidence(connection, cycle_id, "release-base-tag")
    corrections = _cohort_evidence(connection, cycle_id, "release-base-tag-correction")
    frozen = _cohort_evidence(connection, cycle_id, "release-content-commit")
    publication = _cohort_evidence(connection, cycle_id, "release-publication")
    return {
        "cycle_id": cycle_id,
        "origin_artifact_id": str(row["origin_artifact_id"]),
        "lifecycle_state": str(row["lifecycle_state"]),
        "accepted_outcome": str(row["accepted_outcome"]),
        "base_tag": str((corrections or base)[-1]["reference"]) if (corrections or base) else None,
        "original_base_tag": str(base[-1]["reference"]) if base else None,
        "base_correction_count": len(corrections),
        "content_commit": str(frozen[-1]["reference"]).removeprefix("git:") if frozen else None,
        "release_tag": str(publication[-1]["target_identity"]) if publication else None,
        "release_evidence": str(publication[-1]["reference"]) if publication else None,
        "candidates": _candidate_rows(connection, cycle_id),
    }


def status(workspace: Path) -> dict[str, Any]:
    workspace = resolved_workspace(workspace)
    audit = hybrid_state.audit(workspace)
    head = _commit(workspace, "HEAD")
    with contextlib.closing(
        hybrid_state.connect(hybrid_state.database_path(workspace), writable=False)
    ) as connection:
        active = [_cohort_capsule(connection, row) for row in _active_cohort_rows(connection)]
        terminal_rows = connection.execute(
            "SELECT c.id AS cycle_id, c.lifecycle_state, c.accepted_outcome, "
            "c.origin_artifact_id, a.current_path FROM cycle c "
            "JOIN artifact a ON a.id = c.origin_artifact_id "
            "WHERE c.kind = ? AND c.lifecycle_state = 'terminal' ORDER BY c.closed_at DESC LIMIT 5",
            (COHORT_KIND,),
        ).fetchall()
        terminal = [_cohort_capsule(connection, row) for row in terminal_rows]
        projection_inventory = _projection_inventory(connection)
    findings: list[str] = []
    mutable = [item for item in active if item["lifecycle_state"] in MUTABLE_STATES]
    if len(mutable) > 1:
        findings.append(f"multiple mutable release cohorts: {len(mutable)}")
    for cohort in active:
        if not cohort["base_tag"]:
            findings.append(f"cohort {cohort['cycle_id']} lacks a base tag")
            cohort["base_commit"] = None
        else:
            try:
                cohort["base_commit"] = _base_commit(workspace, str(cohort["base_tag"]))
            except ReleaseCohortError as error:
                cohort["base_commit"] = None
                findings.append(f"cohort {cohort['cycle_id']} has invalid base evidence: {error}")
        if not cohort["candidates"]:
            findings.append(f"cohort {cohort['cycle_id']} has no Work2 candidates")
        if cohort["lifecycle_state"] in {"frozen", "released-pending-reconciliation"} and not cohort["content_commit"]:
            findings.append(f"cohort {cohort['cycle_id']} is frozen without a content commit")
        if cohort["lifecycle_state"] == "released-pending-reconciliation" and not cohort["release_tag"]:
            findings.append(f"cohort {cohort['cycle_id']} lacks release evidence")
        for item in cohort["candidates"]:
            if not _is_ancestor(workspace, item["commit"], head):
                findings.append(
                    f"candidate {item['requirement_id']} commit is not reachable from HEAD"
                )
            if cohort.get("base_commit") and not _is_ancestor(
                workspace, str(cohort["base_commit"]), item["commit"]
            ):
                findings.append(
                    f"cohort {cohort['cycle_id']} base is not an ancestor of candidate {item['requirement_id']}"
                )
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "kind": KIND,
        "revision": audit["current_revision"],
        "domain_digest": audit["domain_digest"],
        "head": head,
        "current_base_tag": _base_tag(workspace, head),
        "active": active,
        "recent_terminal": terminal,
        "findings": findings,
        "finding_count": len(findings),
        "projection": release_projection.build(
            {
                "active": active,
                "revision": audit["current_revision"],
                "domain_digest": audit["domain_digest"],
            },
            projection_inventory,
        ),
        "writes_performed": False,
    }
    token_material = dict(payload)
    token_material.pop("writes_performed")
    payload["state_token"] = bind_state_token(workspace, "release-cohort", _sha(token_material))
    return payload


def _require_snapshot(workspace: Path, expected: str) -> dict[str, Any]:
    current = status(workspace)
    if expected != current["state_token"]:
        raise ReleaseCohortError("release cohort state token is stale")
    if current["findings"]:
        raise ReleaseCohortError("release cohort state is invalid: " + "; ".join(current["findings"]))
    return current


def preview_base_repair(
    workspace: Path, *, tag: str, cohort_id: str | None = None
) -> dict[str, Any]:
    """Build a read-only, state-bound correction plan for one working cohort."""
    workspace = resolved_workspace(workspace)
    snapshot = status(workspace)
    cohorts = [
        item for item in snapshot["active"]
        if (cohort_id is None or item["cycle_id"] == cohort_id)
    ]
    if len(cohorts) != 1:
        raise ReleaseCohortError("base repair preview requires exactly one selected active cohort")
    cohort = cohorts[0]
    if cohort["lifecycle_state"] != "working":
        raise ReleaseCohortError("base correction is allowed only while a cohort is working")
    unrelated_findings = [
        finding for finding in snapshot["findings"]
        if f"cohort {cohort['cycle_id']} base" not in finding
        and f"cohort {cohort['cycle_id']} has invalid base evidence" not in finding
    ]
    if unrelated_findings:
        raise ReleaseCohortError(
            "release cohort has unrelated findings: " + "; ".join(unrelated_findings)
        )
    proposed_commit = _require_unambiguous_tag(workspace, tag)
    current_tag = str(cohort.get("base_tag") or "")
    if not current_tag:
        raise ReleaseCohortError("working cohort has no existing base evidence to correct")
    if current_tag == tag:
        raise ReleaseCohortError("proposed base tag already is the effective cohort base")
    if not current_tag.startswith("root:") and _semver_tuple(tag) <= _semver_tuple(current_tag):
        raise ReleaseCohortError("corrected base tag must be numerically newer than the effective base")
    if not _is_ancestor(workspace, proposed_commit, snapshot["head"]):
        raise ReleaseCohortError("proposed base tag is not an ancestor of HEAD")
    for candidate in cohort["candidates"]:
        if not _is_ancestor(workspace, proposed_commit, candidate["commit"]):
            raise ReleaseCohortError(
                f"proposed base tag is not an ancestor of candidate {candidate['requirement_id']}"
            )
    material = {
        "schema_version": 1,
        "kind": "tool-shed-release-base-repair-plan",
        "cohort_id": cohort["cycle_id"],
        "expected_revision": snapshot["revision"],
        "expected_state_token": snapshot["state_token"],
        "current_base_tag": current_tag,
        "current_base_commit": cohort.get("base_commit"),
        "proposed_base_tag": tag,
        "proposed_base_commit": proposed_commit,
        "candidate_membership_digest": _sha(
            sorted(
                (item["requirement_id"], item["origin_cycle_id"], item["commit"])
                for item in cohort["candidates"]
            )
        ),
        "candidate_count": len(cohort["candidates"]),
        "writes_performed": False,
    }
    material["plan_token"] = bind_state_token(
        workspace, "release-base-repair", _sha(material)
    )
    return material


def repair_base(
    workspace: Path,
    *,
    project_binding: str,
    expected_plan_token: str,
    manifest: dict[str, Any],
) -> dict[str, Any]:
    """Apply an exact previewed correction by appending immutable evidence."""
    workspace = resolved_workspace(workspace)
    if manifest.get("kind") != "tool-shed-release-base-repair-plan":
        raise ReleaseCohortError("base repair manifest has the wrong kind")
    preview = preview_base_repair(
        workspace,
        tag=str(manifest.get("proposed_base_tag") or ""),
        cohort_id=str(manifest.get("cohort_id") or ""),
    )
    if manifest != preview:
        raise ReleaseCohortError("base repair manifest is stale or does not match current authority")
    if expected_plan_token != preview["plan_token"]:
        raise ReleaseCohortError("base repair plan token does not match")

    def write(connection: sqlite3.Connection, revision: int) -> dict[str, Any]:
        if hybrid_state.meta_row(connection)["current_revision"] != preview["expected_revision"]:
            raise ReleaseCohortError("release cohort revision changed before base correction")
        row = connection.execute(
            "SELECT lifecycle_state FROM cycle WHERE id=?", (preview["cohort_id"],)
        ).fetchone()
        if row is None or row["lifecycle_state"] != "working":
            raise ReleaseCohortError("base correction target is no longer a working cohort")
        connection.execute(
            "INSERT INTO evidence_reference VALUES (?, ?, 'release-base-tag-correction', ?, NULL, ?, ?)",
            (
                hybrid_state.random_uuid(),
                preview["cohort_id"],
                preview["proposed_base_tag"],
                preview["proposed_base_commit"],
                _next_evidence_time(
                    connection, preview["cohort_id"], "release-base-tag-correction"
                ),
            ),
        )
        return {
            "cohort_id": preview["cohort_id"],
            "previous_base_tag": preview["current_base_tag"],
            "base_tag": preview["proposed_base_tag"],
            "base_commit": preview["proposed_base_commit"],
            "candidate_membership_digest": preview["candidate_membership_digest"],
        }

    result = hybrid_state.managed_write(
        workspace,
        project_binding=project_binding,
        command="repair-release-cohort-base",
        actor="release-cohort",
        callback=write,
        expected_writes=1,
    )
    result["status"] = status(workspace)
    return result


def _parent_cycles(connection: sqlite3.Connection, cycle_id: str) -> list[str]:
    outcome = _latest_outcome(connection, cycle_id)
    rows = connection.execute(
        "SELECT c.id FROM relationship r JOIN cycle c ON c.origin_artifact_id = r.to_artifact_id "
        "WHERE r.from_artifact_id = ? AND r.relation_type = 'outcome-parent' "
        "AND r.retired_revision IS NULL ORDER BY c.opened_at, c.id",
        (outcome["origin_artifact_id"],),
    ).fetchall()
    return [str(row["id"]) for row in rows]


def _open_chain(connection: sqlite3.Connection, starting_cycle: str) -> list[str]:
    pending = [starting_cycle]
    visited: set[str] = set()
    selected: list[str] = []
    while pending:
        cycle_id = pending.pop(0)
        if cycle_id in visited:
            raise ReleaseCohortError("outcome-parent cycle detected while resolving release ownership")
        visited.add(cycle_id)
        outcome = _latest_outcome(connection, cycle_id)
        if not (
            outcome["lifecycle_state"] == "terminal"
            and outcome["disposition"] in TERMINAL_DISPOSITIONS
            and outcome["state"] == "reconciled"
        ):
            selected.append(cycle_id)
        parents = _parent_cycles(connection, cycle_id)
        if len(parents) > 1:
            raise ReleaseCohortError(f"outcome cycle has multiple active parents: {cycle_id}")
        pending.extend(parents)
    return selected


def _open_release_extension(connection: sqlite3.Connection, original_cycle: str) -> str | None:
    original = _latest_outcome(connection, original_cycle)
    rows = connection.execute(
        "SELECT c.id FROM relationship r JOIN cycle c ON c.origin_artifact_id = r.from_artifact_id "
        "WHERE r.to_artifact_id = ? AND r.relation_type = 'release-extension-of' "
        "AND r.retired_revision IS NULL AND c.lifecycle_state <> 'terminal' ORDER BY c.opened_at, c.id",
        (original["origin_artifact_id"],),
    ).fetchall()
    if len(rows) > 1:
        raise ReleaseCohortError(
            f"terminal outcome has multiple open release extensions: {original_cycle}"
        )
    return str(rows[0]["id"]) if rows else None


def _insert_open_cycle(
    connection: sqlite3.Connection,
    revision: int,
    *,
    kind: str,
    accepted_outcome: str,
    summary: str,
    path_prefix: str,
) -> tuple[str, str]:
    cycle_id = hybrid_state.random_uuid()
    artifact_id = hybrid_state.random_uuid()
    stamp = hybrid_state.now()
    path = f"sqlite/{path_prefix}/{artifact_id}"
    connection.execute(
        "INSERT INTO artifact VALUES (?, ?, NULL, ?, 'sqlite', 'working', ?, ?, ?)",
        (artifact_id, kind, path, _sha({"summary": summary, "accepted_outcome": accepted_outcome}), stamp, stamp),
    )
    connection.execute(
        "INSERT INTO cycle VALUES (?, ?, ?, ?, 'working', ?, NULL)",
        (cycle_id, kind, artifact_id, accepted_outcome, stamp),
    )
    verdict_id = hybrid_state.random_uuid()
    connection.execute(
        "INSERT INTO outcome_verdict VALUES (?, ?, ?, 'open', ?, 'work2-release-cohort', ?, ?)",
        (verdict_id, cycle_id, kind, summary, revision, stamp),
    )
    connection.execute(
        "INSERT INTO reconciliation VALUES (?, ?, ?, '[]', ?, 'open', ?, '[]')",
        (hybrid_state.random_uuid(), cycle_id, revision, verdict_id, stamp),
    )
    return cycle_id, artifact_id


def register(
    workspace: Path,
    *,
    expected: str,
    project_binding: str,
    commitish: str,
    origin_cycles: list[str],
    accepted_outcome: str | None,
    summary: str | None,
) -> dict[str, Any]:
    workspace = resolved_workspace(workspace)
    snapshot = _require_snapshot(workspace, expected)
    commit = _commit(workspace, commitish)
    if not _is_ancestor(workspace, commit, snapshot["head"]):
        raise ReleaseCohortError("Work2 commit is not reachable from current HEAD")
    if bool(origin_cycles) == bool(accepted_outcome):
        raise ReleaseCohortError("register requires origin cycle(s) or one direct accepted outcome")
    if accepted_outcome and not (summary or "").strip():
        raise ReleaseCohortError("direct Work2 registration requires --summary")

    mutable = [
        item for item in snapshot["active"]
        if item["lifecycle_state"] in MUTABLE_STATES
    ]
    if origin_cycles and len(mutable) == 1 and mutable[0]["lifecycle_state"] == "working":
        cohort_id = mutable[0]["cycle_id"]
        project_id = load_project_identity(workspace)["project_id"]
        with contextlib.closing(
            hybrid_state.connect(hybrid_state.database_path(workspace), writable=False)
        ) as connection:
            resolved: list[str] = []
            for cycle_id in dict.fromkeys(origin_cycles):
                chain = _open_chain(connection, cycle_id)
                if not chain:
                    extension = _open_release_extension(connection, cycle_id)
                    chain = _open_chain(connection, extension) if extension else []
                for member in chain:
                    if member not in resolved:
                        resolved.append(member)
            requirement_ids = [
                hybrid_state.stable_uuid(
                    project_id, f"release-candidate:{cohort_id}:{cycle_id}:{commit}"
                )
                for cycle_id in resolved
            ]
            if requirement_ids and all(
                connection.execute("SELECT 1 FROM requirement WHERE id = ?", (item,)).fetchone()
                for item in requirement_ids
            ):
                return {
                    "schema_version": SCHEMA_VERSION,
                    "kind": "tool-shed-release-cohort-registration",
                    "cohort_id": cohort_id,
                    "commit": commit,
                    "registered": [
                        {
                            "origin_cycle_id": cycle_id,
                            "requirement_id": requirement_id,
                            "idempotent": True,
                        }
                        for cycle_id, requirement_id in zip(resolved, requirement_ids)
                    ],
                    "status": snapshot,
                    "writes_performed": False,
                }

    def write(connection: sqlite3.Connection, revision: int) -> dict[str, Any]:
        if hybrid_state.meta_row(connection)["current_revision"] != snapshot["revision"]:
            raise ReleaseCohortError("release cohort revision changed before registration")
        rows = _active_cohort_rows(connection)
        mutable_rows = [row for row in rows if row["lifecycle_state"] in MUTABLE_STATES]
        if len(mutable_rows) > 1:
            raise ReleaseCohortError("multiple mutable release cohorts require repair")
        created_cohort = not mutable_rows
        if mutable_rows:
            cohort_id = str(mutable_rows[0]["cycle_id"])
            cohort_artifact_id = str(mutable_rows[0]["origin_artifact_id"])
            if mutable_rows[0]["lifecycle_state"] != "working":
                raise ReleaseCohortError("cannot register Work2 work after the cohort is frozen")
        else:
            cohort_id, cohort_artifact_id = _insert_open_cycle(
                connection,
                revision,
                kind=COHORT_KIND,
                accepted_outcome=(
                    f"Release and production-verify every registered Work2 candidate after "
                    f"{snapshot['current_base_tag']}."
                ),
                summary="Accumulated unreleased Work2 candidate cohort.",
                path_prefix="release-cohorts",
            )
            connection.execute(
                "INSERT INTO evidence_reference VALUES (?, ?, 'release-base-tag', ?, NULL, ?, ?)",
                (
                    hybrid_state.random_uuid(), cohort_id, snapshot["current_base_tag"],
                    cohort_id, hybrid_state.now(),
                ),
            )

        supplied = list(dict.fromkeys(origin_cycles))
        created_direct = None
        if accepted_outcome:
            direct_cycle, _ = _insert_open_cycle(
                connection,
                revision,
                kind="direct-work",
                accepted_outcome=accepted_outcome.strip(),
                summary=(summary or "").strip(),
                path_prefix="outcome-capsules",
            )
            supplied = [direct_cycle]
            created_direct = direct_cycle
        resolved: list[str] = []
        release_extensions: list[dict[str, str]] = []
        for cycle_id in supplied:
            try:
                uuid.UUID(cycle_id)
            except ValueError as error:
                raise ReleaseCohortError(f"origin cycle is not a UUID: {cycle_id}") from error
            chain = _open_chain(connection, cycle_id)
            if not chain:
                extension = _open_release_extension(connection, cycle_id)
                if extension is None:
                    source = connection.execute(
                        "SELECT accepted_outcome FROM cycle WHERE id = ?", (cycle_id,)
                    ).fetchone()
                    if source is None:
                        raise ReleaseCohortError(f"origin cycle does not exist: {cycle_id}")
                    original = _latest_outcome(connection, cycle_id)
                    extension, extension_artifact = _insert_open_cycle(
                        connection,
                        revision,
                        kind="direct-work",
                        accepted_outcome=(
                            "Production-release and reconcile prior Work2 outcome: "
                            + str(source["accepted_outcome"])
                        ),
                        summary=f"Release extension for terminal pre-cohort outcome {cycle_id}.",
                        path_prefix="outcome-capsules",
                    )
                    connection.execute(
                        "INSERT INTO relationship VALUES (?, ?, 'release-extension-of', ?, ?, ?, NULL)",
                        (
                            hybrid_state.random_uuid(), extension_artifact,
                            original["origin_artifact_id"], "release-cohort-v1", revision,
                        ),
                    )
                    connection.execute(
                        "INSERT INTO evidence_reference VALUES (?, ?, 'prior-work2-outcome', ?, NULL, ?, ?)",
                        (
                            hybrid_state.random_uuid(), extension, f"cycle:{cycle_id}", cycle_id,
                            hybrid_state.now(),
                        ),
                    )
                    release_extensions.append(
                        {"original_cycle_id": cycle_id, "extension_cycle_id": extension}
                    )
                chain = _open_chain(connection, extension)
            for member in chain:
                if member not in resolved:
                    resolved.append(member)
        if not resolved:
            raise ReleaseCohortError("origin chain has no open outcome awaiting release")

        project_id = load_project_identity(workspace)["project_id"]
        registered: list[dict[str, Any]] = []
        for cycle_id in resolved:
            outcome = _latest_outcome(connection, cycle_id)
            requirement_id = hybrid_state.stable_uuid(
                project_id, f"release-candidate:{cohort_id}:{cycle_id}:{commit}"
            )
            exists = connection.execute(
                "SELECT disposition FROM requirement WHERE id = ?", (requirement_id,)
            ).fetchone()
            if exists:
                registered.append(
                    {"origin_cycle_id": cycle_id, "requirement_id": requirement_id, "idempotent": True}
                )
                continue
            connection.execute(
                "INSERT INTO requirement VALUES (?, ?, ?, ?, 'awaiting-release', ?, ?, 'work5-production-release')",
                (
                    requirement_id, cohort_id, outcome["origin_artifact_id"],
                    f"Production-release Work2 outcome: {outcome['current_path']}", revision,
                    f"work2:{commit}",
                ),
            )
            evidence_id = hybrid_state.stable_uuid(project_id, f"{requirement_id}:work2-evidence")
            connection.execute(
                "INSERT INTO evidence_reference VALUES (?, ?, 'work2-checkpoint', ?, NULL, ?, ?)",
                (evidence_id, cohort_id, f"git:{commit}", cycle_id, hybrid_state.now()),
            )
            connection.execute(
                "INSERT INTO verification_result VALUES (?, ?, ?, 'passed', 'work2-checkpoint', ?, ?, ?)",
                (
                    hybrid_state.stable_uuid(project_id, f"{requirement_id}:work2-verification"),
                    evidence_id, requirement_id, revision, hybrid_state.now(),
                    json.dumps({"work_level": "work2", "commit": commit}, sort_keys=True),
                ),
            )
            if hybrid_state.active_relationship(
                connection, str(outcome["origin_artifact_id"]), "release-candidate-member", cohort_artifact_id
            ) is None:
                connection.execute(
                    "INSERT INTO relationship VALUES (?, ?, 'release-candidate-member', ?, ?, ?, NULL)",
                    (
                        hybrid_state.random_uuid(), outcome["origin_artifact_id"], cohort_artifact_id,
                        "release-cohort-v1", revision,
                    ),
                )
            registered.append(
                {"origin_cycle_id": cycle_id, "requirement_id": requirement_id, "idempotent": False}
            )
        return {
            "cohort_id": cohort_id,
            "created_cohort": created_cohort,
            "created_direct_cycle": created_direct,
            "release_extensions": release_extensions,
            "commit": commit,
            "registered": registered,
        }

    result = hybrid_state.managed_write(
        workspace,
        project_binding=project_binding,
        command="register-work2-release-candidate",
        actor="release-cohort",
        callback=write,
    )
    result["status"] = status(workspace)
    return result


def freeze(
    workspace: Path,
    *,
    expected: str,
    project_binding: str,
    content_commitish: str,
    failure_evidence: str | None = None,
) -> dict[str, Any]:
    workspace = resolved_workspace(workspace)
    try:
        require_no_app_server_dispatch_debt(operation="release cohort freeze")
    except AppServerUserStateError as error:
        raise ReleaseCohortError(str(error)) from error
    snapshot = _require_snapshot(workspace, expected)
    mutable = [
        item for item in snapshot["active"]
        if item["lifecycle_state"] in MUTABLE_STATES
    ]
    if len(mutable) != 1:
        raise ReleaseCohortError("freeze requires exactly one working or frozen release cohort")
    cohort = mutable[0]
    content_commit = _commit(workspace, content_commitish)
    retrying = cohort["lifecycle_state"] == "frozen" and cohort["content_commit"] != content_commit
    if cohort["lifecycle_state"] != "working" and not retrying:
        if cohort["lifecycle_state"] == "frozen" and cohort["content_commit"] == content_commit:
            return {"kind": "tool-shed-release-cohort-freeze", "idempotent": True, "status": snapshot, "writes_performed": False}
        raise ReleaseCohortError("release cohort is not in working state")
    if retrying and not failure_evidence:
        raise ReleaseCohortError(
            "rebinding a frozen release cohort requires durable failed-CI evidence"
        )
    if not cohort["candidates"]:
        raise ReleaseCohortError("cannot freeze an empty release cohort")
    if _git(workspace, "status", "--porcelain", "--untracked-files=normal"):
        raise ReleaseCohortError("tracked worktree must be clean before freezing a release cohort")
    if content_commit != snapshot["head"]:
        raise ReleaseCohortError("release content commit must equal current HEAD")
    for candidate in cohort["candidates"]:
        if not _is_ancestor(workspace, candidate["commit"], content_commit):
            raise ReleaseCohortError(
                f"candidate commit is not included in content commit: {candidate['requirement_id']}"
            )

    def write(connection: sqlite3.Connection, revision: int) -> dict[str, Any]:
        if hybrid_state.meta_row(connection)["current_revision"] != snapshot["revision"]:
            raise ReleaseCohortError("release cohort revision changed before freeze")
        if not retrying:
            connection.execute(
                "UPDATE cycle SET lifecycle_state = 'frozen' WHERE id = ? AND lifecycle_state = 'working'",
                (cohort["cycle_id"],),
            )
        else:
            connection.execute(
                "INSERT INTO evidence_reference VALUES (?, ?, 'release-content-rejected', ?, NULL, ?, ?)",
                (
                    hybrid_state.random_uuid(), cohort["cycle_id"], failure_evidence,
                    cohort["cycle_id"], hybrid_state.now(),
                ),
            )
        connection.execute(
            "UPDATE artifact SET lifecycle_state = 'frozen', updated_at = ? WHERE id = ?",
            (hybrid_state.now(), cohort["origin_artifact_id"]),
        )
        connection.execute(
            "INSERT INTO evidence_reference VALUES (?, ?, 'release-content-commit', ?, NULL, ?, ?)",
            (
                hybrid_state.random_uuid(), cohort["cycle_id"], f"git:{content_commit}",
                cohort["cycle_id"],
                _next_evidence_time(connection, cohort["cycle_id"], "release-content-commit"),
            ),
        )
        return {
            "cohort_id": cohort["cycle_id"],
            "content_commit": content_commit,
            "previous_content_commit": cohort["content_commit"] if retrying else None,
        }

    result = hybrid_state.managed_write(
        workspace,
        project_binding=project_binding,
        command="freeze-release-cohort",
        actor="release-cohort",
        callback=write,
        expected_writes=3,
    )
    result["status"] = status(workspace)
    return result


def _verify_release_tag(workspace: Path, tag: str, content_commit: str) -> dict[str, str]:
    tag_commit = _require_unambiguous_tag(workspace, tag)
    if tag_commit == content_commit:
        mode = "tagged-content-commit"
    else:
        parents = _git(workspace, "show", "-s", "--format=%P", tag_commit).split()
        if not parents or parents[0] != content_commit:
            raise ReleaseCohortError("release tag does not identify the frozen content commit")
        mode = "provenance-commit"
    return {"tag_commit": tag_commit, "mode": mode}


def record_release(
    workspace: Path,
    *,
    expected: str,
    project_binding: str,
    tag: str,
    evidence: str,
) -> dict[str, Any]:
    workspace = resolved_workspace(workspace)
    try:
        require_no_app_server_dispatch_debt(operation="release publication recording")
    except AppServerUserStateError as error:
        raise ReleaseCohortError(str(error)) from error
    snapshot = _require_snapshot(workspace, expected)
    frozen = [
        item for item in snapshot["active"] if item["lifecycle_state"] == "frozen"
    ]
    if not frozen:
        matches = [
            item for item in snapshot["active"]
            if item["lifecycle_state"] == "released-pending-reconciliation"
            and item["release_tag"] == tag
            and item["release_evidence"] == evidence
        ]
        if len(matches) == 1:
            return {"kind": "tool-shed-release-cohort-publication", "idempotent": True, "status": snapshot, "writes_performed": False}
        raise ReleaseCohortError("release recording requires exactly one frozen cohort")
    if len(frozen) != 1:
        raise ReleaseCohortError("release recording requires exactly one frozen cohort")
    cohort = frozen[0]
    if cohort["lifecycle_state"] != "frozen" or not cohort["content_commit"]:
        raise ReleaseCohortError("release cohort must be frozen before publication is recorded")
    if not evidence.strip() or len(evidence) > 2048 or any(ord(char) < 32 for char in evidence):
        raise ReleaseCohortError("release evidence must be a bounded printable reference")
    tag_result = _verify_release_tag(workspace, tag, cohort["content_commit"])

    def write(connection: sqlite3.Connection, revision: int) -> dict[str, Any]:
        if hybrid_state.meta_row(connection)["current_revision"] != snapshot["revision"]:
            raise ReleaseCohortError("release cohort revision changed before publication recording")
        project_id = load_project_identity(workspace)["project_id"]
        unique_origins: dict[str, str] = {}
        for candidate in cohort["candidates"]:
            unique_origins[candidate["origin_cycle_id"]] = candidate["origin_artifact_id"]
        evidence_ids: dict[str, str] = {}
        for cycle_id in sorted(unique_origins):
            evidence_id = hybrid_state.stable_uuid(
                project_id, f"release-publication:{cohort['cycle_id']}:{cycle_id}:{tag}"
            )
            connection.execute(
                "INSERT INTO evidence_reference VALUES (?, ?, 'production-release', ?, NULL, ?, ?)",
                (evidence_id, cycle_id, evidence.strip(), tag, hybrid_state.now()),
            )
            evidence_ids[cycle_id] = evidence_id
        for candidate in cohort["candidates"]:
            connection.execute(
                "UPDATE requirement SET disposition = 'released-pending-reconciliation' WHERE id = ?",
                (candidate["requirement_id"],),
            )
            connection.execute(
                "INSERT INTO verification_result VALUES (?, ?, ?, 'passed', 'work5-production-release', ?, ?, ?)",
                (
                    hybrid_state.stable_uuid(
                        project_id, f"{candidate['requirement_id']}:work5:{tag}"
                    ),
                    evidence_ids[candidate["origin_cycle_id"]], candidate["requirement_id"],
                    revision, hybrid_state.now(),
                    json.dumps(
                        {
                            "release_tag": tag,
                            "content_commit": cohort["content_commit"],
                            "tag_commit": tag_result["tag_commit"],
                            "tag_mode": tag_result["mode"],
                        },
                        sort_keys=True,
                    ),
                ),
            )
        connection.execute(
            "UPDATE cycle SET lifecycle_state = 'released-pending-reconciliation' WHERE id = ?",
            (cohort["cycle_id"],),
        )
        connection.execute(
            "UPDATE artifact SET lifecycle_state = 'released-pending-reconciliation', updated_at = ? WHERE id = ?",
            (hybrid_state.now(), cohort["origin_artifact_id"]),
        )
        connection.execute(
            "INSERT INTO evidence_reference VALUES (?, ?, 'release-publication', ?, NULL, ?, ?)",
            (
                hybrid_state.random_uuid(), cohort["cycle_id"], evidence.strip(), tag,
                hybrid_state.now(),
            ),
        )
        return {
            "cohort_id": cohort["cycle_id"],
            "release_tag": tag,
            "content_commit": cohort["content_commit"],
            "origins_with_release_evidence": sorted(unique_origins),
        }

    result = hybrid_state.managed_write(
        workspace,
        project_binding=project_binding,
        command="record-release-cohort-publication",
        actor="release-cohort",
        callback=write,
    )
    result["status"] = status(workspace)
    return result


def finalize(
    workspace: Path,
    *,
    expected: str,
    project_binding: str,
    authorization: str,
    cohort_id: str | None = None,
) -> dict[str, Any]:
    workspace = resolved_workspace(workspace)
    try:
        require_no_app_server_dispatch_debt(operation="release cohort finalization")
    except AppServerUserStateError as error:
        raise ReleaseCohortError(str(error)) from error
    snapshot = _require_snapshot(workspace, expected)
    pending_cohorts = [
        item for item in snapshot["active"]
        if item["lifecycle_state"] == "released-pending-reconciliation"
        and (cohort_id is None or item["cycle_id"] == cohort_id)
    ]
    if len(pending_cohorts) != 1:
        if cohort_id is None and len(pending_cohorts) > 1:
            raise ReleaseCohortError(
                "multiple released cohorts await reconciliation; specify --cohort-id"
            )
        raise ReleaseCohortError(
            "release publication must be recorded for the selected cohort"
        )
    cohort = pending_cohorts[0]
    pending = [
        {
            "cycle_id": item["origin_cycle_id"],
            "path": item["origin_path"],
            "lifecycle": item["origin_lifecycle"],
            "verdict": item["origin_verdict"],
            "reconciliation": item["origin_reconciliation"],
            "document_lifecycle": item["origin_document_lifecycle"],
            "recursive_closure": item["origin_recursive_closure"],
        }
        for item in cohort["candidates"]
        if not item["origin_ready_to_finalize"]
    ]
    if pending:
        raise ReleaseCohortError(
            "owning outcomes still require closed-loop reconciliation: "
            + json.dumps(pending, sort_keys=True)
        )
    if not authorization.strip():
        raise ReleaseCohortError("finalization requires an authorization reference")

    def write(connection: sqlite3.Connection, revision: int) -> dict[str, Any]:
        if hybrid_state.meta_row(connection)["current_revision"] != snapshot["revision"]:
            raise ReleaseCohortError("release cohort revision changed before finalization")
        stamp = hybrid_state.now()
        for candidate in cohort["candidates"]:
            connection.execute(
                "UPDATE requirement SET disposition = 'released-reconciled' WHERE id = ?",
                (candidate["requirement_id"],),
            )
        connection.execute(
            "UPDATE cycle SET lifecycle_state = 'terminal', closed_at = ? WHERE id = ?",
            (stamp, cohort["cycle_id"]),
        )
        connection.execute(
            "UPDATE artifact SET lifecycle_state = 'terminal', updated_at = ? WHERE id = ?",
            (stamp, cohort["origin_artifact_id"]),
        )
        verdict_id = hybrid_state.random_uuid()
        connection.execute(
            "INSERT INTO outcome_verdict VALUES (?, ?, 'release-cohort', 'satisfied', ?, ?, ?, ?)",
            (
                verdict_id, cohort["cycle_id"],
                f"Released {len(cohort['candidates'])} Work2 outcome record(s) as {cohort['release_tag']}.",
                authorization.strip(), revision, stamp,
            ),
        )
        origin_artifacts = sorted({item["origin_artifact_id"] for item in cohort["candidates"]})
        connection.execute(
            "INSERT INTO reconciliation VALUES (?, ?, ?, ?, ?, 'reconciled', ?, '[]')",
            (
                hybrid_state.random_uuid(), cohort["cycle_id"], revision,
                json.dumps(origin_artifacts, sort_keys=True), verdict_id, stamp,
            ),
        )
        return {
            "cohort_id": cohort["cycle_id"],
            "release_tag": cohort["release_tag"],
            "candidate_count": len(cohort["candidates"]),
            "origin_cycles": sorted({item["origin_cycle_id"] for item in cohort["candidates"]}),
            "lifecycle": "terminal",
            "verdict": "satisfied",
            "reconciliation": "reconciled",
        }

    result = hybrid_state.managed_write(
        workspace,
        project_binding=project_binding,
        command="finalize-release-cohort",
        actor="release-cohort",
        callback=write,
    )
    result["status"] = status(workspace)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--json", action="store_true")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status", help="Inspect active and recent release cohorts.")
    register_parser = commands.add_parser("register", help="Register a Work2 checkpoint.")
    register_parser.add_argument("--expect", required=True)
    register_parser.add_argument("--project-binding", required=True)
    register_parser.add_argument("--commit", default="HEAD")
    register_parser.add_argument("--origin-cycle", action="append", default=[])
    register_parser.add_argument("--accepted-outcome")
    register_parser.add_argument("--summary")
    preview_parser = commands.add_parser(
        "preview-base-repair", help="Preview an exact append-only working-cohort base correction."
    )
    preview_parser.add_argument("--tag", required=True)
    preview_parser.add_argument("--cohort-id")
    repair_parser = commands.add_parser(
        "repair-base", help="Apply a previously previewed base-correction manifest."
    )
    repair_parser.add_argument("--manifest", required=True)
    repair_parser.add_argument("--expect", required=True)
    repair_parser.add_argument("--project-binding", required=True)
    freeze_parser = commands.add_parser("freeze", help="Freeze the exact Work5 content commit.")
    freeze_parser.add_argument("--expect", required=True)
    freeze_parser.add_argument("--project-binding", required=True)
    freeze_parser.add_argument("--content-commit", default="HEAD")
    freeze_parser.add_argument("--failure-evidence")
    release_parser = commands.add_parser(
        "record-release", help="Attach verified production publication evidence to every origin."
    )
    release_parser.add_argument("--expect", required=True)
    release_parser.add_argument("--project-binding", required=True)
    release_parser.add_argument("--tag", required=True)
    release_parser.add_argument("--evidence", required=True)
    finalize_parser = commands.add_parser(
        "finalize", help="Close a cohort only after every owning outcome is reconciled."
    )
    finalize_parser.add_argument("--expect", required=True)
    finalize_parser.add_argument("--project-binding", required=True)
    finalize_parser.add_argument("--authorization", required=True)
    finalize_parser.add_argument("--cohort-id")
    return parser


def _print(result: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(result, indent=2, sort_keys=True))
        return
    if result.get("kind") == KIND:
        projection = result["projection"]
        print(
            f"Release cohort: {len(result['active'])} active, "
            f"{len(result['recent_terminal'])} recent terminal, {result['finding_count']} finding(s)"
        )
        for cohort in result["active"]:
            print(
                f"- {cohort['cycle_id']} — {cohort['lifecycle_state']} — "
                f"{len(cohort['candidates'])} registration(s) — base {cohort['base_tag']} "
                f"({cohort.get('base_commit') or 'unresolved'})"
            )
        print(
            "Projection: "
            f"{projection['projection_state']} — {projection['registration_count']} registrations, "
            f"{projection['candidate_commit_count']} unique commits, "
            f"{projection['owning_chain_count']} owning chains, "
            f"{projection['display_group_count']} displayed groups"
        )
        for group in projection["release_chains"]:
            labels = {
                "document-chain": group["root_id"],
                "direct-work2": "Direct Work2 outcomes",
                "additional-obligations": "Additional release obligations",
            }
            print(
                f"  - {labels[group['group_kind']]} — {group['stage']} — "
                f"{group['registration_count']} registrations, "
                f"{group['owning_chain_count']} owning chains, "
                f"{group['candidate_count']} unique commits"
            )
        if result["findings"]:
            print("Cohort health:")
            for finding in result["findings"]:
                print(f"  - {finding}")
        print(f"State token: {result['state_token']}")
    else:
        print(json.dumps(result, indent=2, sort_keys=True))


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        workspace = resolved_workspace(Path(args.workspace))
        if args.command == "status":
            result = status(workspace)
        elif args.command == "register":
            result = register(
                workspace,
                expected=args.expect,
                project_binding=args.project_binding,
                commitish=args.commit,
                origin_cycles=args.origin_cycle,
                accepted_outcome=args.accepted_outcome,
                summary=args.summary,
            )
        elif args.command == "freeze":
            result = freeze(
                workspace,
                expected=args.expect,
                project_binding=args.project_binding,
                content_commitish=args.content_commit,
                failure_evidence=args.failure_evidence,
            )
        elif args.command == "preview-base-repair":
            result = preview_base_repair(
                workspace, tag=args.tag, cohort_id=args.cohort_id
            )
        elif args.command == "repair-base":
            manifest_path = Path(args.manifest).resolve()
            if not manifest_path.is_relative_to(workspace):
                raise ReleaseCohortError("base repair manifest must be inside the workspace")
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as error:
                raise ReleaseCohortError(f"cannot read base repair manifest: {error}") from error
            if not isinstance(manifest, dict):
                raise ReleaseCohortError("base repair manifest must be a JSON object")
            result = repair_base(
                workspace,
                project_binding=args.project_binding,
                expected_plan_token=args.expect,
                manifest=manifest,
            )
        elif args.command == "record-release":
            result = record_release(
                workspace,
                expected=args.expect,
                project_binding=args.project_binding,
                tag=args.tag,
                evidence=args.evidence,
            )
        elif args.command == "finalize":
            result = finalize(
                workspace,
                expected=args.expect,
                project_binding=args.project_binding,
                authorization=args.authorization,
                cohort_id=args.cohort_id,
            )
        else:  # pragma: no cover
            raise ReleaseCohortError(f"unsupported command: {args.command}")
        _print(result, args.json)
        return 0
    except (ReleaseCohortError, hybrid_state.HybridStateError, sqlite3.Error) as error:
        print(f"release cohort error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
