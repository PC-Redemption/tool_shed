#!/usr/bin/env python3
"""Database-heavy local scenarios for the deterministic lifecycle harness.

This module is intentionally a driver, not an oracle.  It mutates only a nested
workspace below an ignored qualification run directory.  The independent oracle
is supplied by ``lifecycle_qualification.py`` after every product operation.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
from typing import Any, Callable
import uuid

import closure_lineage
import document_store
import hybrid_state
import outcome_loop
from project_identity import binding_token


Oracle = Callable[[sqlite3.Connection], dict[str, Any]]
ProjectionComparator = Callable[[sqlite3.Connection, dict[str, Any]], list[dict[str, Any]]]


def _uuid4(*parts: object) -> str:
    raw = hashlib.sha256("\0".join(map(str, parts)).encode()).hexdigest()[:32]
    return str(uuid.UUID(hex=raw, version=4))


def _json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _prepare_workspace(path: Path, *, project_id: str, name: str) -> str:
    if path.exists():
        raise RuntimeError(f"qualification workspace already exists without a result: {path}")
    path.mkdir(parents=True)
    subprocess.run(["git", "init", "--quiet", "-b", "main"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Tool Shed Qualification"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "qualification@example.invalid"], cwd=path, check=True)
    _json(
        path / "work/tool-shed-project.json",
        {"schema_version": 1, "project_id": project_id, "project_name": name},
    )
    (path / ".gitignore").write_text("/.tool-shed/\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=path, check=True)
    subprocess.run(["git", "commit", "--quiet", "-m", "sanitized qualification fixture"], cwd=path, check=True)
    return binding_token(path, operation="hybrid-state")


def _initialize_schema3(path: Path, binding: str) -> None:
    hybrid_state.initialize(path, project_binding=binding)
    document_store.migrate(path, project_binding=binding)
    migration = closure_lineage.prepare_migration(path)
    closure_lineage.apply_migration(
        path,
        migration,
        expected_token=str(migration["manifest_token"]),
        project_binding=binding,
    )


def _create_cycle(path: Path, binding: str, *, title: str, run_id: str) -> tuple[dict[str, Any], str]:
    created = document_store.create_document(
        path,
        project_binding=binding,
        document_type="ticket",
        title=title,
        body=f"# {title}\n\nQualification Run: {run_id}\n",
        lifecycle="active",
        metadata={"qualification_run_id": run_id, "qualification_role": title},
        actor="lifecycle-qualification",
        reason="deterministic local corpus",
    )["result"]
    cycle = document_store.open_outcome(
        path,
        project_binding=binding,
        identity=created["visible_id"],
        accepted_outcome=f"{title} is complete.",
        actor="lifecycle-qualification",
    )["result"]["cycle_id"]
    return created, str(cycle)


def _requirement(path: Path, cycle_id: str, *, database: Path | None = None) -> str:
    target = database or hybrid_state.database_path(path)
    with contextlib.closing(hybrid_state.connect(target, writable=False)) as connection:
        row = connection.execute("SELECT id FROM requirement WHERE cycle_id=? ORDER BY id", (cycle_id,)).fetchone()
        if row is None:
            raise RuntimeError(f"cycle has no requirement: {cycle_id}")
        return str(row[0])


def _close(path: Path, binding: str, element_id: str, *, method: str = "closed-loop") -> None:
    closure_lineage.close_element(
        path,
        project_binding=binding,
        element_id=element_id,
        method=method,
        evidence_health="current" if method == "closed-loop" else "not-required",
        authorization_ref="sealed development qualification manifest",
        evidence=["qualification:deterministic-db-observation"],
        actor="lifecycle-qualification",
    )


def _oracle_parity(path: Path, oracle: Oracle, compare: ProjectionComparator, *, database: Path | None = None) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    target = database or hybrid_state.database_path(path)
    with contextlib.closing(hybrid_state.connect(target, writable=False)) as connection:
        expected = oracle(connection)
        return expected, compare(connection, expected)


def _check(check_id: str, passed: bool, expected: object, actual: object) -> dict[str, Any]:
    return {"id": check_id, "passed": bool(passed), "expected": expected, "actual": actual}


def _qh003(path: Path, binding: str, run_id: str, oracle: Oracle, compare: ProjectionComparator) -> dict[str, Any]:
    root, root_cycle = _create_cycle(path, binding, title="QH003 Root", run_id=run_id)
    first, first_cycle = _create_cycle(path, binding, title="QH003 Governing A", run_id=run_id)
    second, second_cycle = _create_cycle(path, binding, title="QH003 Governing B", run_id=run_id)
    observer, observer_cycle = _create_cycle(path, binding, title="QH003 Non Governing", run_id=run_id)
    for child in (first, second):
        document_store.relate(path, project_binding=binding, source=child["visible_id"], relation="outcome-parent", target=root["visible_id"], actor="lifecycle-qualification")
    document_store.relate(path, project_binding=binding, source=observer["visible_id"], relation="informs", target=root["visible_id"], actor="lifecycle-qualification")

    _close(path, binding, root_cycle, method="closed-manual")
    _close(path, binding, _requirement(path, first_cycle))
    _close(path, binding, first_cycle)
    after_first = closure_lineage.status(path, root_cycle)
    _close(path, binding, _requirement(path, second_cycle), method="closed-manual")
    _close(path, binding, second_cycle, method="closed-manual")
    after_second = closure_lineage.status(path, root_cycle)
    observer_status = closure_lineage.status(path, observer_cycle)
    _, mismatches = _oracle_parity(path, oracle, compare)
    checks = [
        _check("QH003-PARENT-BLOCKED-AFTER-FIRST", not after_first["effective_closed"] and "DESCENDANT_OPEN" in after_first["reason_codes"], False, after_first),
        _check("QH003-PARENT-CLOSES-AFTER-ALL-GOVERNING", after_second["effective_closed"], True, after_second),
        _check("QH003-MANUAL-AND-LOOP-MIX", after_second["local_closure"] == "closed-manual", "closed-manual", after_second["local_closure"]),
        _check("QH003-NON-GOVERNING-DOES-NOT-BLOCK", not observer_status["effective_closed"] and after_second["effective_closed"], {"observer_closed": False, "root_closed": True}, {"observer_closed": observer_status["effective_closed"], "root_closed": after_second["effective_closed"]}),
        _check("QH003-ORACLE-PROJECTION-PARITY", not mismatches, [], mismatches[:20]),
    ]
    return {"checks": checks, "observations": {"after_first": after_first, "after_second": after_second, "observer": observer_status}}


def _qh004(path: Path, binding: str, run_id: str, oracle: Oracle, compare: ProjectionComparator) -> dict[str, Any]:
    root, root_cycle = _create_cycle(path, binding, title="QH004 Root", run_id=run_id)
    left, left_cycle = _create_cycle(path, binding, title="QH004 Left", run_id=run_id)
    right, right_cycle = _create_cycle(path, binding, title="QH004 Right", run_id=run_id)
    leaf, leaf_cycle = _create_cycle(path, binding, title="QH004 Shared Leaf", run_id=run_id)
    for child, parent in ((left, root), (right, root), (leaf, left), (leaf, right)):
        document_store.relate(path, project_binding=binding, source=child["visible_id"], relation="outcome-parent", target=parent["visible_id"], actor="lifecycle-qualification")
    for cycle in (root_cycle, left_cycle, right_cycle):
        _close(path, binding, cycle, method="closed-manual")
    before = closure_lineage.status(path, root_cycle)
    blocking_ids = [item["blocking_element_id"] for item in before["blockers"] if item.get("blocking_element_id")]
    _close(path, binding, _requirement(path, leaf_cycle))
    _close(path, binding, leaf_cycle)
    after = closure_lineage.status(path, root_cycle)
    with contextlib.closing(hybrid_state.connect(hybrid_state.database_path(path), writable=False)) as connection:
        path_row = connection.execute(
            "SELECT shortest_depth,path_count FROM closure_ancestor_path WHERE ancestor_element_id=? AND descendant_element_id=?",
            (root_cycle, leaf_cycle),
        ).fetchone()
    _, mismatches = _oracle_parity(path, oracle, compare)
    actual_path = {"depth": int(path_row["shortest_depth"]), "path_count": int(path_row["path_count"])} if path_row else None
    checks = [
        _check("QH004-DEEP-SHARED-PATHS", bool(path_row and int(path_row["shortest_depth"]) >= 2 and int(path_row["path_count"]) == 2), {"minimum_indexed_depth": 2, "path_count": 2, "document_levels": 3}, actual_path),
        _check("QH004-SHARED-LEAF-BLOCKS-ROOT", not before["effective_closed"] and leaf_cycle in blocking_ids, True, {"root_closed": before["effective_closed"], "blocking_ids": blocking_ids}),
        _check("QH004-BLOCKERS-DEDUPLICATED", len(before["blockers"]) == len({json.dumps(item, sort_keys=True) for item in before["blockers"]}), "unique blockers", before["blockers"]),
        _check("QH004-ROOT-CLOSES-THROUGH-BOTH-PATHS", after["effective_closed"], True, after),
        _check("QH004-ORACLE-PROJECTION-PARITY", not mismatches, [], mismatches[:20]),
    ]
    return {"checks": checks, "observations": {"before": before, "after": after, "shared_path": actual_path}}


def _qh005(path: Path, binding: str, run_id: str, oracle: Oracle, compare: ProjectionComparator) -> dict[str, Any]:
    _, cycle_id = _create_cycle(path, binding, title="QH005 Revision Subject", run_id=run_id)
    requirement_id = _requirement(path, cycle_id)
    _close(path, binding, requirement_id)
    first = closure_lineage.status(path, requirement_id)

    def revise(connection: sqlite3.Connection, revision: int) -> dict[str, Any]:
        connection.execute(
            "UPDATE requirement SET accepted_outcome=accepted_outcome || ' Revised.' WHERE id=?",
            (requirement_id,),
        )
        return {"requirement_id": requirement_id, "revision": revision}

    hybrid_state.managed_write(path, project_binding=binding, command="qualification-revise-subject", actor="lifecycle-qualification", callback=revise)
    revised = closure_lineage.status(path, requirement_id)
    with contextlib.closing(hybrid_state.connect(hybrid_state.database_path(path), writable=False)) as connection:
        history_after_revision = [dict(row) for row in connection.execute("SELECT * FROM closure_record WHERE element_id=? ORDER BY created_revision,id", (requirement_id,))]
    _close(path, binding, requirement_id)
    reproved = closure_lineage.status(path, requirement_id)
    with contextlib.closing(hybrid_state.connect(hybrid_state.database_path(path), writable=False)) as connection:
        history = [dict(row) for row in connection.execute("SELECT * FROM closure_record WHERE element_id=? ORDER BY created_revision,id", (requirement_id,))]
    _, mismatches = _oracle_parity(path, oracle, compare)
    checks = [
        _check("QH005-REVISION-INVALIDATES-PROOF", first["effective_closed"] and not revised["effective_closed"] and first["subject_digest"] != revised["subject_digest"], True, {"before": first, "revised": revised}),
        _check("QH005-OLD-PROOF-SUPERSEDED", len(history_after_revision) == 1 and history_after_revision[0]["superseded_revision"] is not None, "one superseded record", history_after_revision),
        _check("QH005-REPROOF-APPENDS-HISTORY", len(history) == 2 and sum(item["superseded_revision"] is None for item in history) == 1 and reproved["effective_closed"], {"records": 2, "current": 1, "closed": True}, {"records": len(history), "current": sum(item["superseded_revision"] is None for item in history), "closed": reproved["effective_closed"]}),
        _check("QH005-ORACLE-PROJECTION-PARITY", not mismatches, [], mismatches[:20]),
    ]
    return {"checks": checks, "observations": {"before": first, "revised": revised, "reproved": reproved}}


def _qh006(path: Path, binding: str, run_id: str, oracle: Oracle, compare: ProjectionComparator) -> dict[str, Any]:
    parent, parent_cycle = _create_cycle(path, binding, title="QH006 Interrupted Parent", run_id=run_id)
    evidence = path / ".tool-shed/qualification/interrupted-evidence.json"
    _json(evidence, {"schema_version": 1, "run_id": run_id, "status": "passed"})
    source = path / "work/tool-shed-project.json"
    direct = outcome_loop.plan_direct_result(
        path,
        origin_summary=f"QH006 terminal child {run_id}",
        accepted_outcome="Child result is committed before parent reconciliation.",
        product_truth=[source.relative_to(path).as_posix()],
        evidence_paths=[evidence.relative_to(path).as_posix()],
        disposition="satisfied",
        authorization_ref="sealed development qualification manifest",
        parent_cycle_id=parent_cycle,
    )
    applied = outcome_loop.apply_manifest(path, direct, expected_token=direct["manifest_token"], project_binding=binding)
    child_cycle = str(applied["result"]["cycle_id"])
    interrupted = closure_lineage.status(path, parent_cycle)

    def resume() -> bool:
        with contextlib.closing(hybrid_state.connect(hybrid_state.database_path(path), writable=False)) as connection:
            state = str(connection.execute("SELECT lifecycle_state FROM cycle WHERE id=?", (parent_cycle,)).fetchone()[0])
        if state == "terminal":
            return False
        transition = outcome_loop.prepare_transition(
            path,
            parent_cycle,
            lifecycle_state="terminal",
            disposition="satisfied",
            reconciliation_state="reconciled",
            summary="QH006 resumed parent exactly once.",
            authorization_ref="sealed development qualification manifest",
            supporting_cycle_ids=[child_cycle],
            residual_work=[],
        )
        outcome_loop.apply_transition(path, transition, expected_token=transition["manifest_token"], project_binding=binding)
        current = document_store.show(path, parent["visible_id"])
        document_store.set_lifecycle(path, project_binding=binding, identity=parent["visible_id"], lifecycle="completed", expected_revision=current["document_revision"], actor="lifecycle-qualification", reason="QH006 resumed terminal outcome")
        return True

    first_resume = resume()
    second_resume = resume()
    with contextlib.closing(hybrid_state.connect(hybrid_state.database_path(path), writable=False)) as connection:
        terminal_verdicts = int(connection.execute("SELECT COUNT(*) FROM outcome_verdict WHERE cycle_id=? AND disposition='satisfied'", (parent_cycle,)).fetchone()[0])
        reconciled = int(connection.execute("SELECT COUNT(*) FROM reconciliation WHERE cycle_id=? AND state='reconciled'", (parent_cycle,)).fetchone()[0])
        propagated = int(connection.execute("SELECT COUNT(*) FROM relationship r JOIN cycle c ON c.origin_artifact_id=r.from_artifact_id WHERE c.id=? AND r.relation_type='outcome-result-propagated' AND r.retired_revision IS NULL", (child_cycle,)).fetchone()[0])
    final = closure_lineage.status(path, parent_cycle)
    _, mismatches = _oracle_parity(path, oracle, compare)
    checks = [
        _check("QH006-INTERRUPTED-PARENT-OPEN", not interrupted["effective_closed"], False, interrupted),
        _check("QH006-FIRST-RESUME-APPLIED", first_resume, True, first_resume),
        _check("QH006-REPLAY-IDEMPOTENT", not second_resume, False, second_resume),
        _check("QH006-EXACTLY-ONE-TERMINAL-EFFECT", terminal_verdicts == reconciled == propagated == 1, {"terminal_verdicts": 1, "reconciliations": 1, "propagations": 1}, {"terminal_verdicts": terminal_verdicts, "reconciliations": reconciled, "propagations": propagated}),
        _check("QH006-PARENT-TERMINAL-CLOSED", final["effective_closed"], True, final),
        _check("QH006-ORACLE-PROJECTION-PARITY", not mismatches, [], mismatches[:20]),
    ]
    return {"checks": checks, "observations": {"interrupted": interrupted, "final": final, "child_cycle": child_cycle}}


def _qh008(path: Path, binding: str, run_id: str, oracle: Oracle, compare: ProjectionComparator) -> dict[str, Any]:
    _, cycle_id = _create_cycle(path, binding, title="QH008 Rebuild", run_id=run_id)
    _close(path, binding, _requirement(path, cycle_id))
    _close(path, binding, cycle_id)
    checkpoint = document_store.write_checkpoint(path, project_binding=binding, output=Path("work/state/checkpoints/qh008.json"))
    rebuilt_relative = Path(".tool-shed/qualification/qh008-rebuilt.sqlite3")
    (path / rebuilt_relative).parent.mkdir(parents=True, exist_ok=True)
    rebuilt = document_store.rebuild(path, project_binding=binding, checkpoint=Path(checkpoint["path"]), output=rebuilt_relative)
    live_oracle, live_mismatches = _oracle_parity(path, oracle, compare)
    rebuilt_oracle, rebuilt_mismatches = _oracle_parity(path, oracle, compare, database=path / rebuilt_relative)
    live_audit = document_store.audit(path)
    rebuilt_audit = document_store.audit(path, path / rebuilt_relative)
    checks = [
        _check("QH008-DOMAIN-DIGEST-PARITY", live_audit["domain_digest"] == rebuilt_audit["domain_digest"] == rebuilt["domain_digest"], live_audit["domain_digest"], rebuilt_audit["domain_digest"]),
        _check("QH008-CLOSURE-TRUTH-PARITY", live_oracle == rebuilt_oracle, hashlib.sha256(json.dumps(live_oracle, sort_keys=True).encode()).hexdigest(), hashlib.sha256(json.dumps(rebuilt_oracle, sort_keys=True).encode()).hexdigest()),
        _check("QH008-PROJECTION-PARITY", not live_mismatches and not rebuilt_mismatches, [], {"live": live_mismatches[:10], "rebuilt": rebuilt_mismatches[:10]}),
        _check("QH008-REBUILT-CLEAN", rebuilt_audit["classification"] == "CLEAN", "CLEAN", rebuilt_audit["classification"]),
    ]
    return {"checks": checks, "observations": {"checkpoint": checkpoint, "rebuilt": rebuilt}}


def _corrupt_copy(source: Path, target: Path, mutation: str, target_element_id: str, control_element_id: str, oracle: Oracle) -> dict[str, Any]:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    with contextlib.closing(sqlite3.connect(target)) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=OFF")
        for row in list(connection.execute("SELECT name FROM sqlite_schema WHERE type='trigger' AND name LIKE 'ts_%'")):
            connection.execute(f'DROP TRIGGER "{row[0]}"')
        claim = connection.execute("SELECT * FROM lineage_claim WHERE retired_revision IS NULL AND relationship_type='contributes' AND parent_element_id=? ORDER BY id LIMIT 1", (target_element_id,)).fetchone()
        if claim is None:
            raise RuntimeError("malformed-graph fixture lacks a lineage claim")
        if mutation == "missing-parent":
            connection.execute("UPDATE lineage_claim SET parent_element_id=? WHERE id=?", (_uuid4(target, mutation), claim["id"]))
        elif mutation == "conflicting-lineage":
            connection.execute("UPDATE lineage_claim SET observed_requirement_digest=? WHERE id=?", ("f" * 64, claim["id"]))
        elif mutation == "cycle":
            parent_cycle = str(claim["parent_element_id"])
            child_obligation = str(claim["child_element_id"])
            envelope = connection.execute("SELECT envelope_digest FROM closure_element WHERE id=?", (parent_cycle,)).fetchone()[0]
            connection.execute(
                "INSERT INTO lineage_claim VALUES (?,?,?,?,?,?,?,?,?,NULL)",
                (
                    _uuid4(target, mutation), parent_cycle, child_obligation,
                    claim["parent_requirement_id"], "contributes",
                    claim["observed_parent_revision"], claim["observed_requirement_digest"],
                    envelope, claim["created_revision"],
                ),
            )
        else:
            raise RuntimeError(f"unknown graph mutation: {mutation}")
        connection.commit()
        result = oracle(connection)
        reasons = sorted({reason for item in result["elements"].values() for reason in item["reason_codes"]})
        return {"reasons": reasons, "control": result["elements"][control_element_id], "oracle": result}


def _qh009(path: Path, binding: str, run_id: str, oracle: Oracle, compare: ProjectionComparator) -> dict[str, Any]:
    _, target_cycle = _create_cycle(path, binding, title="QH009 Target", run_id=run_id)
    _, control_cycle = _create_cycle(path, binding, title="QH009 Control", run_id=run_id)
    for cycle_id in (target_cycle, control_cycle):
        _close(path, binding, _requirement(path, cycle_id))
        _close(path, binding, cycle_id)
    database = hybrid_state.database_path(path)
    with contextlib.closing(hybrid_state.connect(database)) as connection:
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    healthy_digest = hashlib.sha256(database.read_bytes()).hexdigest()
    control_before = closure_lineage.status(path, control_cycle)
    cases: dict[str, Any] = {}
    for mutation in ("missing-parent", "conflicting-lineage", "cycle"):
        cases[mutation] = _corrupt_copy(database, path / f".tool-shed/qualification/qh009-{mutation}.sqlite3", mutation, target_cycle, control_cycle, oracle)
    control_after = closure_lineage.status(path, control_cycle)
    expected = {"missing-parent": "MISSING_PARENT", "conflicting-lineage": "CONFLICTING_LINEAGE", "cycle": "CYCLE"}
    checks = [
        *[
            _check(f"QH009-{name.upper().replace('-', '_')}-EXPLICIT", code in cases[name]["reasons"], code, cases[name]["reasons"])
            for name, code in expected.items()
        ],
        _check("QH009-HEALTHY-AUTHORITY-UNCHANGED", hashlib.sha256(database.read_bytes()).hexdigest() == healthy_digest, healthy_digest, hashlib.sha256(database.read_bytes()).hexdigest()),
        _check("QH009-CONTROL-UNAFFECTED", control_before == control_after and control_after["effective_closed"], control_before, control_after),
        _check("QH009-FINDINGS-CONTAINED", all(value["control"]["effective_closed"] and not value["control"]["reason_codes"] for value in cases.values()), {"control_closed": True, "control_reasons": []}, {name: value["control"] for name, value in cases.items()}),
    ]
    return {"checks": checks, "observations": {name: {"reasons": value["reasons"]} for name, value in cases.items()}}


def _file_owned_intake(path: Path, project_id: str, run_id: str, oracle: Oracle, compare: ProjectionComparator) -> dict[str, Any]:
    binding = _prepare_workspace(path, project_id=project_id, name="sanitized-file-owned-instance")
    parent_file = path / "work/ideas/existing-parent.md"
    child_file = path / "work/maps/existing-child.md"
    parent_file.parent.mkdir(parents=True)
    child_file.parent.mkdir(parents=True)
    parent_file.write_text("# Existing Parent\n\nSanitized history.\n", encoding="utf-8")
    child_file.write_text("# Existing Child\n\nSanitized history.\n", encoding="utf-8")
    subprocess.run(["git", "add", "work"], cwd=path, check=True)
    subprocess.run(["git", "commit", "--quiet", "-m", "sanitized existing sources"], cwd=path, check=True)
    hybrid_state.initialize(path, project_binding=binding)
    assignments = {
        "work/ideas/existing-parent.md": {"artifact_id": _uuid4(run_id, "file-parent"), "import_id": _uuid4(run_id, "file-parent-import")},
        "work/maps/existing-child.md": {"artifact_id": _uuid4(run_id, "file-child"), "import_id": _uuid4(run_id, "file-child-import")},
    }
    imported = hybrid_state.import_files(path, [Path(item) for item in assignments], project_binding=binding, assigned_ids=assignments)
    hybrid_state.add_relationship(path, project_binding=binding, from_artifact_id=assignments["work/maps/existing-child.md"]["artifact_id"], relation_type="outcome-parent", to_artifact_id=assignments["work/ideas/existing-parent.md"]["artifact_id"], provenance="sanitized-source-envelope")
    document_store.migrate(path, project_binding=binding)
    parent = document_store.import_document(path, project_binding=binding, source=parent_file, document_type="idea-brief", lifecycle="active", actor="lifecycle-qualification", reason="existing instance intake", assigned_number=1, artifact_id=assignments["work/ideas/existing-parent.md"]["artifact_id"])["result"]
    child = document_store.import_document(path, project_binding=binding, source=child_file, document_type="project-map", lifecycle="active", actor="lifecycle-qualification", reason="existing instance intake", assigned_number=1, artifact_id=assignments["work/maps/existing-child.md"]["artifact_id"])["result"]
    parent_cycle = document_store.open_outcome(path, project_binding=binding, identity=parent["visible_id"], accepted_outcome="Existing parent remains governed.", actor="lifecycle-qualification")["result"]["cycle_id"]
    child_cycle = document_store.open_outcome(path, project_binding=binding, identity=child["visible_id"], accepted_outcome="Existing child remains governed.", actor="lifecycle-qualification")["result"]["cycle_id"]
    migration = closure_lineage.prepare_migration(path)
    closure_lineage.apply_migration(path, migration, expected_token=migration["manifest_token"], project_binding=binding)
    recovery = closure_lineage.open_recovery_case(path, project_binding=binding, element_id=child_cycle, reason_code="MISSING_PARENT", detail={"source": "sanitized-external-ancestor", "bounded": True}, actor="lifecycle-qualification")
    revision_before = document_store.audit(path)["current_revision"]
    replay_parent = document_store.import_document(path, project_binding=binding, source=parent_file, document_type="idea-brief", lifecycle="active", actor="lifecycle-qualification", reason="existing instance replay", assigned_number=1, artifact_id=parent["artifact_id"])
    replay_child = document_store.import_document(path, project_binding=binding, source=child_file, document_type="project-map", lifecycle="active", actor="lifecycle-qualification", reason="existing instance replay", assigned_number=1, artifact_id=child["artifact_id"])
    revision_after = document_store.audit(path)["current_revision"]
    with contextlib.closing(hybrid_state.connect(hybrid_state.database_path(path), writable=False)) as connection:
        claim_count = int(connection.execute("SELECT COUNT(*) FROM lineage_claim WHERE child_element_id=? AND retired_revision IS NULL", (child_cycle,)).fetchone()[0])
        invisible = int(connection.execute("SELECT COUNT(*) FROM lineage_claim l LEFT JOIN closure_element c ON c.id=l.child_element_id WHERE l.retired_revision IS NULL AND c.id IS NULL").fetchone()[0])
    _, mismatches = _oracle_parity(path, oracle, compare)
    return {
        "stable_ids": {parent["artifact_id"], child["artifact_id"]} == {item["artifact_id"] for item in imported["result"]},
        "history_preserved": len(document_store.history(path, parent["visible_id"])["revisions"]) == 1 and len(document_store.history(path, child["visible_id"])["revisions"]) == 1,
        "recoverable_claims": claim_count,
        "unresolved_explicit": closure_lineage.status(path, child_cycle)["graph_health"] == "recovery-required" and bool(recovery["result"]["case_id"]),
        "idempotent": not replay_parent["writes_performed"] and not replay_child["writes_performed"] and revision_before == revision_after,
        "invisible_orphans": invisible,
        "projection_mismatches": mismatches,
        "parent_cycle": parent_cycle,
    }


def _hybrid_intake(path: Path, project_id: str, run_id: str, oracle: Oracle, compare: ProjectionComparator) -> dict[str, Any]:
    binding = _prepare_workspace(path, project_id=project_id, name="sanitized-hybrid-instance")
    hybrid_state.initialize(path, project_binding=binding)
    document_store.migrate(path, project_binding=binding)
    parent, parent_cycle = _create_cycle(path, binding, title="Existing Hybrid Parent", run_id=run_id)
    child, child_cycle = _create_cycle(path, binding, title="Existing Hybrid Child", run_id=run_id)
    document_store.relate(path, project_binding=binding, source=child["visible_id"], relation="outcome-parent", target=parent["visible_id"], actor="lifecycle-qualification")
    edit = Path(".tool-shed/existing-parent-edit.md")
    document_store.export_edit(path, parent["visible_id"], edit)
    edit_path = path / edit
    edit_path.write_text(edit_path.read_text(encoding="utf-8").replace("Qualification Run:", "Sanitized prior revision.\n\nQualification Run:"), encoding="utf-8")
    document_store.apply_edit(path, project_binding=binding, edit=edit, actor="lifecycle-qualification", reason="retained sanitized revision")
    ids_before = {parent["visible_id"]: parent["artifact_id"], child["visible_id"]: child["artifact_id"]}
    history_before = len(document_store.history(path, parent["visible_id"])["revisions"])
    checkpoint = document_store.write_checkpoint(path, project_binding=binding, output=Path("work/state/checkpoints/existing-hybrid-v2.json"))
    restored_relative = Path(".tool-shed/restored-existing.sqlite3")
    document_store.rebuild(path, project_binding=binding, checkpoint=Path(checkpoint["path"]), output=restored_relative)
    live = hybrid_state.database_path(path)
    source_snapshot = path / ".tool-shed/sanitized-source-v2.sqlite3"
    os.replace(live, source_snapshot)
    os.replace(path / restored_relative, live)
    migration = closure_lineage.prepare_migration(path)
    closure_lineage.apply_migration(path, migration, expected_token=migration["manifest_token"], project_binding=binding)
    ids_after = {item["visible_id"]: item["artifact_id"] for item in document_store.list_documents(path)["documents"]}
    revision_before = document_store.audit(path)["current_revision"]
    replay = document_store.relate(path, project_binding=binding, source=child["visible_id"], relation="outcome-parent", target=parent["visible_id"], actor="lifecycle-qualification")
    revision_after = document_store.audit(path)["current_revision"]
    with contextlib.closing(hybrid_state.connect(live, writable=False)) as connection:
        claim_count = int(connection.execute("SELECT COUNT(*) FROM lineage_claim WHERE child_element_id=? AND retired_revision IS NULL", (child_cycle,)).fetchone()[0])
        invisible = int(connection.execute("SELECT COUNT(*) FROM lineage_claim l LEFT JOIN closure_element c ON c.id=l.child_element_id WHERE l.retired_revision IS NULL AND c.id IS NULL").fetchone()[0])
    _, mismatches = _oracle_parity(path, oracle, compare)
    return {
        "stable_ids": ids_before == {key: ids_after.get(key) for key in ids_before},
        "history_preserved": history_before == len(document_store.history(path, parent["visible_id"])["revisions"]) == 2,
        "recoverable_claims": claim_count,
        "unresolved_explicit": True,
        "idempotent": not replay["writes_performed"] and revision_before == revision_after,
        "invisible_orphans": invisible,
        "projection_mismatches": mismatches,
        "checkpoint_digest": checkpoint["digest"],
    }


def _qh010(path: Path, _binding: str, run_id: str, project_id: str, oracle: Oracle, compare: ProjectionComparator) -> dict[str, Any]:
    # QH-010 owns two structurally different, sanitized nested snapshots.  The
    # outer path exists only to keep the complete run inside the disposable OS fixture.
    file_owned = _file_owned_intake(path / "file-owned", project_id, run_id, oracle, compare)
    hybrid = _hybrid_intake(path / "hybrid", project_id, run_id, oracle, compare)
    checks = [
        _check("QH010-STABLE-IDENTITIES", file_owned["stable_ids"] and hybrid["stable_ids"], True, {"file_owned": file_owned["stable_ids"], "hybrid": hybrid["stable_ids"]}),
        _check("QH010-HISTORY-PRESERVED", file_owned["history_preserved"] and hybrid["history_preserved"], True, {"file_owned": file_owned["history_preserved"], "hybrid": hybrid["history_preserved"]}),
        _check("QH010-RECOVERABLE-LINEAGE-REBUILT", file_owned["recoverable_claims"] >= 1 and hybrid["recoverable_claims"] >= 1, {"file_owned_min": 1, "hybrid_min": 1}, {"file_owned": file_owned["recoverable_claims"], "hybrid": hybrid["recoverable_claims"]}),
        _check("QH010-UNRESOLVED-ANCESTRY-EXPLICIT", file_owned["unresolved_explicit"], True, file_owned["unresolved_explicit"]),
        _check("QH010-IDEMPOTENT-REPLAY", file_owned["idempotent"] and hybrid["idempotent"], True, {"file_owned": file_owned["idempotent"], "hybrid": hybrid["idempotent"]}),
        _check("QH010-ZERO-INVISIBLE-ORPHANS", file_owned["invisible_orphans"] == hybrid["invisible_orphans"] == 0, {"file_owned": 0, "hybrid": 0}, {"file_owned": file_owned["invisible_orphans"], "hybrid": hybrid["invisible_orphans"]}),
        _check("QH010-ORACLE-PROJECTION-PARITY", not file_owned["projection_mismatches"] and not hybrid["projection_mismatches"], [], {"file_owned": file_owned["projection_mismatches"][:10], "hybrid": hybrid["projection_mismatches"][:10]}),
    ]
    return {"checks": checks, "observations": {"file_owned": file_owned, "hybrid": hybrid}}


def drive(
    outer_workspace: Path,
    manifest: dict[str, Any],
    *,
    oracle: Oracle,
    compare: ProjectionComparator,
) -> dict[str, Any]:
    """Drive one local M2 scenario in an isolated workspace under the fixture."""
    scenario_id = str(manifest["scenario"]["id"])
    run_id = str(manifest["run_id"])
    runtime = outer_workspace.resolve() / ".tool-shed/qualification/runs" / run_id
    result_path = runtime / "drive-result.json"
    if result_path.is_file():
        result = json.loads(result_path.read_text(encoding="utf-8"))
        result["resumed"] = True
        return result
    nested = runtime / "workspace"
    project_id = str(manifest["fixture"]["project_id"])
    if scenario_id == "QH-010":
        nested.mkdir(parents=True)
        result = _qh010(nested, "", run_id, project_id, oracle, compare)
    else:
        binding = _prepare_workspace(nested, project_id=project_id, name=f"{scenario_id.lower()}-qualification")
        _initialize_schema3(nested, binding)
        dispatch = {
            "QH-003": _qh003,
            "QH-004": _qh004,
            "QH-005": _qh005,
            "QH-006": _qh006,
            "QH-008": _qh008,
            "QH-009": _qh009,
        }
        if scenario_id not in dispatch:
            raise RuntimeError(f"local scenario driver is not implemented: {scenario_id}")
        result = dispatch[scenario_id](nested, binding, run_id, oracle, compare)
    result.update({
        "schema_version": 1,
        "kind": "tool-shed-local-qualification-drive",
        "run_id": run_id,
        "scenario_id": scenario_id,
        "resumed": False,
        "runtime": runtime.relative_to(outer_workspace.resolve()).as_posix(),
    })
    _json(result_path, result)
    return result
