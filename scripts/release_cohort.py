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
from pathlib import Path
from typing import Any, Sequence

import hybrid_state
from project_identity import bind_state_token, load_project_identity, resolved_workspace


SCHEMA_VERSION = 1
KIND = "tool-shed-release-cohort-status"
OPERATION = "hybrid-state"
COHORT_KIND = "release-cohort"
ACTIVE_STATES = {"working", "frozen", "released-pending-reconciliation"}
TERMINAL_DISPOSITIONS = {
    "satisfied",
    "satisfied-with-approved-change",
    "not-applicable",
}
SEMVER_TAG = re.compile(r"^v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")


class ReleaseCohortError(RuntimeError):
    pass


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _sha(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _git(workspace: Path, *arguments: str, check: bool = True) -> str:
    result = subprocess.run(
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
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", older, newer],
        cwd=workspace,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def _base_tag(workspace: Path, commit: str) -> str:
    candidates: list[tuple[tuple[int, int, int], str]] = []
    for tag in _git(workspace, "tag", "--merged", commit, "--list", "v[0-9]*").splitlines():
        match = SEMVER_TAG.fullmatch(tag.strip())
        if match:
            candidates.append((tuple(int(value) for value in match.groups()), tag.strip()))
    if candidates:
        return max(candidates)[1]
    roots = _git(workspace, "rev-list", "--max-parents=0", commit).splitlines()
    if not roots:
        raise ReleaseCohortError("repository has no reachable root commit")
    return f"root:{roots[0]}"


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
        item["origin_ready_to_finalize"] = (
            outcome["lifecycle_state"] == "terminal"
            and outcome["disposition"] in TERMINAL_DISPOSITIONS
            and outcome["state"] == "reconciled"
        )
        results.append(item)
    return results


def _cohort_capsule(connection: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
    cycle_id = str(row["cycle_id"])
    base = _cohort_evidence(connection, cycle_id, "release-base-tag")
    frozen = _cohort_evidence(connection, cycle_id, "release-content-commit")
    publication = _cohort_evidence(connection, cycle_id, "release-publication")
    return {
        "cycle_id": cycle_id,
        "origin_artifact_id": str(row["origin_artifact_id"]),
        "lifecycle_state": str(row["lifecycle_state"]),
        "accepted_outcome": str(row["accepted_outcome"]),
        "base_tag": str(base[-1]["reference"]) if base else None,
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
    findings: list[str] = []
    if len(active) > 1:
        findings.append(f"multiple active release cohorts: {len(active)}")
    for cohort in active:
        if not cohort["base_tag"]:
            findings.append(f"cohort {cohort['cycle_id']} lacks a base tag")
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

    if origin_cycles and len(snapshot["active"]) == 1:
        cohort_id = snapshot["active"][0]["cycle_id"]
        project_id = load_project_identity(workspace)["project_id"]
        with contextlib.closing(
            hybrid_state.connect(hybrid_state.database_path(workspace), writable=False)
        ) as connection:
            resolved: list[str] = []
            for cycle_id in dict.fromkeys(origin_cycles):
                for member in _open_chain(connection, cycle_id):
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
        if len(rows) > 1:
            raise ReleaseCohortError("multiple active release cohorts require repair")
        created_cohort = not rows
        if rows:
            cohort_id = str(rows[0]["cycle_id"])
            cohort_artifact_id = str(rows[0]["origin_artifact_id"])
            if rows[0]["lifecycle_state"] != "working":
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
        for cycle_id in supplied:
            try:
                uuid.UUID(cycle_id)
            except ValueError as error:
                raise ReleaseCohortError(f"origin cycle is not a UUID: {cycle_id}") from error
            for member in _open_chain(connection, cycle_id):
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
) -> dict[str, Any]:
    workspace = resolved_workspace(workspace)
    snapshot = _require_snapshot(workspace, expected)
    if len(snapshot["active"]) != 1:
        raise ReleaseCohortError("freeze requires exactly one active release cohort")
    cohort = snapshot["active"][0]
    if cohort["lifecycle_state"] != "working":
        if cohort["lifecycle_state"] == "frozen" and cohort["content_commit"] == _commit(workspace, content_commitish):
            return {"kind": "tool-shed-release-cohort-freeze", "idempotent": True, "status": snapshot, "writes_performed": False}
        raise ReleaseCohortError("release cohort is not in working state")
    if not cohort["candidates"]:
        raise ReleaseCohortError("cannot freeze an empty release cohort")
    if _git(workspace, "status", "--porcelain", "--untracked-files=normal"):
        raise ReleaseCohortError("tracked worktree must be clean before freezing a release cohort")
    content_commit = _commit(workspace, content_commitish)
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
        connection.execute(
            "UPDATE cycle SET lifecycle_state = 'frozen' WHERE id = ? AND lifecycle_state = 'working'",
            (cohort["cycle_id"],),
        )
        connection.execute(
            "UPDATE artifact SET lifecycle_state = 'frozen', updated_at = ? WHERE id = ?",
            (hybrid_state.now(), cohort["origin_artifact_id"]),
        )
        connection.execute(
            "INSERT INTO evidence_reference VALUES (?, ?, 'release-content-commit', ?, NULL, ?, ?)",
            (
                hybrid_state.random_uuid(), cohort["cycle_id"], f"git:{content_commit}",
                cohort["cycle_id"], hybrid_state.now(),
            ),
        )
        return {"cohort_id": cohort["cycle_id"], "content_commit": content_commit}

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
    if not SEMVER_TAG.fullmatch(tag):
        raise ReleaseCohortError("release tag must be a stable vMAJOR.MINOR.PATCH tag")
    tag_commit = _commit(workspace, f"refs/tags/{tag}")
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
    snapshot = _require_snapshot(workspace, expected)
    if len(snapshot["active"]) != 1:
        raise ReleaseCohortError("release recording requires exactly one active cohort")
    cohort = snapshot["active"][0]
    if cohort["lifecycle_state"] == "released-pending-reconciliation":
        if cohort["release_tag"] == tag and cohort["release_evidence"] == evidence:
            return {"kind": "tool-shed-release-cohort-publication", "idempotent": True, "status": snapshot, "writes_performed": False}
        raise ReleaseCohortError("release cohort already records different publication evidence")
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
) -> dict[str, Any]:
    workspace = resolved_workspace(workspace)
    snapshot = _require_snapshot(workspace, expected)
    if len(snapshot["active"]) != 1:
        raise ReleaseCohortError("finalization requires exactly one active release cohort")
    cohort = snapshot["active"][0]
    if cohort["lifecycle_state"] != "released-pending-reconciliation":
        raise ReleaseCohortError("release publication must be recorded before finalization")
    pending = [
        {
            "cycle_id": item["origin_cycle_id"],
            "path": item["origin_path"],
            "lifecycle": item["origin_lifecycle"],
            "verdict": item["origin_verdict"],
            "reconciliation": item["origin_reconciliation"],
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
    freeze_parser = commands.add_parser("freeze", help="Freeze the exact Work5 content commit.")
    freeze_parser.add_argument("--expect", required=True)
    freeze_parser.add_argument("--project-binding", required=True)
    freeze_parser.add_argument("--content-commit", default="HEAD")
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
    return parser


def _print(result: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(result, indent=2, sort_keys=True))
        return
    if result.get("kind") == KIND:
        print(
            f"Release cohort: {len(result['active'])} active, "
            f"{len(result['recent_terminal'])} recent terminal, {result['finding_count']} finding(s)"
        )
        for cohort in result["active"]:
            print(
                f"- {cohort['cycle_id']} — {cohort['lifecycle_state']} — "
                f"{len(cohort['candidates'])} candidate(s) — base {cohort['base_tag']}"
            )
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
