#!/usr/bin/env python3
"""Accumulate retained QH-002 lifecycles and measure database truth at scale."""

from __future__ import annotations

import argparse
import contextlib
import json
import math
import os
import sqlite3
import time
from pathlib import Path
from typing import Any, Sequence

import document_store
import hybrid_state
import lifecycle_qualification as qualification


APPEND_ONLY_TABLES = (
    "structural_change",
    "event",
    "document_revision",
    "evidence_reference",
    "verification_result",
    "outcome_verdict",
    "reconciliation",
    "closure_record",
    "proof_attempt",
    "lineage_tombstone",
)


class ScaleError(RuntimeError):
    pass


def _write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _nearest_rank(values: list[float], quantile: float) -> float:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * quantile) - 1)] if ordered else 0.0


def _table_counts(database: Path) -> dict[str, int]:
    with contextlib.closing(hybrid_state.connect(database, writable=False)) as connection:
        tables = {str(row[0]) for row in connection.execute("SELECT name FROM sqlite_schema WHERE type='table'")}
        return {
            table: int(connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
            for table in sorted(tables)
        }


def _query_plans(database: Path) -> dict[str, list[str]]:
    with contextlib.closing(hybrid_state.connect(database, writable=False)) as connection:
        queries = {
            "run_documents": "SELECT * FROM document WHERE metadata_json LIKE '%qualification_run_id%' ORDER BY visible_id",
            "current_closure": "SELECT * FROM closure_rollup WHERE element_id=?",
            "open_cycles": "SELECT * FROM cycle WHERE lifecycle_state='working' ORDER BY id",
        }
        result: dict[str, list[str]] = {}
        for name, sql in queries.items():
            params = ("missing",) if "?" in sql else ()
            result[name] = [str(row[3]) for row in connection.execute("EXPLAIN QUERY PLAN " + sql, params)]
        return result


def _history_count(counts: dict[str, int]) -> int:
    return sum(counts.get(table, 0) for table in APPEND_ONLY_TABLES)


def _run_owned_state(database: Path, run_ids: list[str]) -> dict[str, Any]:
    expected_documents = len(run_ids) * 4
    with contextlib.closing(hybrid_state.connect(database, writable=False)) as connection:
        documents = []
        for run_id in run_ids:
            rows = list(
                connection.execute(
                    "SELECT id,visible_id,lifecycle_state,metadata_json FROM document "
                    "WHERE json_extract(metadata_json,'$.qualification_run_id')=? ORDER BY visible_id",
                    (run_id,),
                )
            )
            documents.extend(dict(row) for row in rows)
        artifact_ids = [str(item["id"]) for item in documents]
        open_cycles = 0
        unreconciled = 0
        if artifact_ids:
            placeholders = ",".join("?" for _ in artifact_ids)
            cycles = list(connection.execute(f"SELECT id,lifecycle_state FROM cycle WHERE origin_artifact_id IN ({placeholders})", artifact_ids))
            open_cycles = sum(str(row["lifecycle_state"]) != "terminal" for row in cycles)
            cycle_ids = [str(row["id"]) for row in cycles]
            if cycle_ids:
                placeholders = ",".join("?" for _ in cycle_ids)
                unreconciled = int(
                    connection.execute(
                        f"SELECT COUNT(*) FROM cycle c WHERE c.id IN ({placeholders}) AND NOT EXISTS "
                        "(SELECT 1 FROM reconciliation r WHERE r.cycle_id=c.id AND r.state='reconciled')",
                        cycle_ids,
                    ).fetchone()[0]
                )
        return {
            "expected_documents": expected_documents,
            "actual_documents": len(documents),
            "completed_documents": sum(str(item["lifecycle_state"]) == "completed" for item in documents),
            "open_cycles": open_cycles,
            "unreconciled_cycles": unreconciled,
        }


def _probe_mutations(workspace: Path, binding: str, *, run_key: str, samples: int) -> list[float]:
    timings: list[float] = []
    for index in range(samples):
        started = time.perf_counter()
        created = document_store.create_document(
            workspace,
            project_binding=binding,
            document_type="ticket",
            title=f"Scale mutation probe {run_key} {index:03d}",
            body=f"# Scale mutation probe\n\nQualification Scale Run: {run_key}\n",
            lifecycle="active",
            metadata={"qualification_scale_run": run_key, "probe": True},
            actor="lifecycle-scale-qualification",
            reason="ordinary guarded mutation timing after accumulated state",
        )["result"]
        timings.append((time.perf_counter() - started) * 1000)
        started = time.perf_counter()
        document_store.set_lifecycle(
            workspace,
            project_binding=binding,
            identity=str(created["visible_id"]),
            lifecycle="completed",
            expected_revision=int(created["document_revision"]),
            actor="lifecycle-scale-qualification",
            reason="leave no active mutation probe residue",
        )
        timings.append((time.perf_counter() - started) * 1000)
    return timings


def run(
    workspace: Path,
    *,
    project_binding: str,
    candidate_commit: str,
    candidate_version: str,
    platform_name: str,
    instance_id: str,
    serial_start: int,
    lifecycle_count: int,
    minimum_history_delta: int,
    mutation_samples: int,
    output: Path,
) -> dict[str, Any]:
    workspace = workspace.resolve()
    if lifecycle_count < 1 or mutation_samples < 1:
        raise ScaleError("lifecycle count and mutation samples must be positive")
    identity = json.loads((workspace / "work/tool-shed-project.json").read_text(encoding="utf-8"))
    project_id = str(identity["project_id"])
    database = hybrid_state.database_path(workspace)
    if hybrid_state.audit(workspace)["classification"] not in {"CLEAN", "VALID_DIRTY", "CHECKPOINT_DUE"}:
        raise ScaleError("fixture database is not safe for accumulated qualification")
    state_path = output.with_name(output.stem + "-state.json")
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.is_file() else {
        "schema_version": 1,
        "candidate_commit": candidate_commit,
        "platform": platform_name,
        "serial_start": serial_start,
        "lifecycle_count": lifecycle_count,
        "baseline_counts": _table_counts(database),
        "runs": [],
        "elapsed_ms": [],
    }
    expected_state = (candidate_commit, platform_name, serial_start, lifecycle_count)
    actual_state = (state.get("candidate_commit"), state.get("platform"), state.get("serial_start"), state.get("lifecycle_count"))
    if actual_state != expected_state:
        raise ScaleError("existing scale state belongs to different immutable inputs")
    scenario = qualification.load_json(qualification.scenario_path("QH-002"), label="scenario")
    for offset in range(len(state["runs"]), lifecycle_count):
        serial = serial_start + offset
        baseline = document_store.audit(workspace)["domain_digest"]
        manifest = qualification.seal_manifest(
            scenario,
            candidate_commit=candidate_commit,
            candidate_version=candidate_version,
            platform_name=platform_name,
            project_id=project_id,
            instance_id=instance_id,
            serial=serial,
            seed=0,
            target_environment="development",
            baseline_digest=baseline,
        )
        started = time.perf_counter()
        driven = qualification.drive_qh002(workspace, manifest, project_binding=project_binding)
        elapsed = (time.perf_counter() - started) * 1000
        if not all(item.get("passed") for item in driven["checks"]):
            raise ScaleError(f"QH-002 serial {serial} failed semantic checks")
        state["runs"].append({"serial": serial, "run_id": manifest["run_id"], "manifest_digest": manifest["manifest_digest"]})
        state["elapsed_ms"].append(elapsed)
        _write(state_path, state)

    run_ids = [str(item["run_id"]) for item in state["runs"]]
    local = _run_owned_state(database, run_ids)
    with contextlib.closing(hybrid_state.connect(database, writable=False)) as connection:
        started = time.perf_counter()
        oracle = qualification.independent_closure(connection)
        oracle_ms = (time.perf_counter() - started) * 1000
        mismatches = qualification.compare_closure_projection(connection, oracle)
        recovery_open = int(connection.execute("SELECT COUNT(*) FROM recovery_case WHERE state='open'").fetchone()[0])
        graph_revision = int(connection.execute("SELECT graph_revision FROM closure_graph_meta WHERE id=1").fetchone()[0])
    mutation_ms = _probe_mutations(workspace, project_binding, run_key=f"{candidate_commit[:12]}-{serial_start}-{lifecycle_count}", samples=mutation_samples)
    before_counts = state["baseline_counts"]
    after_counts = _table_counts(database)
    history_delta = _history_count(after_counts) - _history_count(before_counts)
    audit = document_store.audit(workspace)
    size = database.stat().st_size
    wal = database.with_name(database.name + "-wal")
    result: dict[str, Any] = {
        "schema_version": 1,
        "kind": "tool-shed-lifecycle-scale-qualification",
        "candidate_commit": candidate_commit,
        "candidate_version": candidate_version,
        "platform": platform_name,
        "project_id": project_id,
        "instance_id": instance_id,
        "serial_range": [serial_start, serial_start + lifecycle_count - 1],
        "retained_lifecycles": lifecycle_count,
        "run_ids_digest": qualification.digest(run_ids),
        "semantic": {
            **local,
            "oracle_available": oracle.get("available") is True,
            "projection_mismatch_count": len(mismatches),
            "open_recovery_cases": recovery_open,
            "database_classification": audit["classification"],
            "passed": (
                local["actual_documents"] == local["expected_documents"] == local["completed_documents"]
                and local["open_cycles"] == local["unreconciled_cycles"] == 0
                and oracle.get("available") is True and not mismatches and recovery_open == 0
            ),
        },
        "history": {
            "minimum_delta": minimum_history_delta,
            "actual_delta": history_delta,
            "passed": history_delta >= minimum_history_delta,
            "append_only_tables": list(APPEND_ONLY_TABLES),
            "baseline_counts": before_counts,
            "final_counts": after_counts,
        },
        "timing_ms": {
            "lifecycle_p50": _nearest_rank(state["elapsed_ms"], 0.50),
            "lifecycle_p95": _nearest_rank(state["elapsed_ms"], 0.95),
            "guarded_mutation_p95": _nearest_rank(mutation_ms, 0.95),
            "guarded_mutation_ceiling": 1000,
            "guarded_mutation_passed": _nearest_rank(mutation_ms, 0.95) <= 1000,
            "truth_vector": oracle_ms,
            "truth_vector_ceiling": 1000,
            "truth_vector_passed": oracle_ms <= 1000,
            "samples": {"lifecycles": len(state["elapsed_ms"]), "mutations": len(mutation_ms)},
        },
        "storage": {
            "database_bytes": size,
            "wal_bytes": wal.stat().st_size if wal.exists() else 0,
        },
        "graph_revision": graph_revision,
        "query_plans": _query_plans(database),
        "resumed_runs": sum(bool(item.get("resumed")) for item in state.get("runs", [])),
    }
    result["verdict"] = "PASS" if (
        result["semantic"]["passed"]
        and result["history"]["passed"]
        and result["timing_ms"]["guarded_mutation_passed"]
        and result["timing_ms"]["truth_vector_passed"]
    ) else "PRODUCT-FAIL"
    result["result_digest"] = qualification.digest(result)
    _write(output, result)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--project-binding", required=True)
    parser.add_argument("--candidate-commit", required=True)
    parser.add_argument("--candidate-version", required=True)
    parser.add_argument("--platform", required=True)
    parser.add_argument("--instance-id", required=True)
    parser.add_argument("--serial-start", type=int, required=True)
    parser.add_argument("--lifecycle-count", type=int, required=True)
    parser.add_argument("--minimum-history-delta", type=int, default=0)
    parser.add_argument("--mutation-samples", type=int, default=10)
    parser.add_argument("--output", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = run(
            Path(args.workspace), project_binding=args.project_binding,
            candidate_commit=args.candidate_commit, candidate_version=args.candidate_version,
            platform_name=args.platform, instance_id=args.instance_id,
            serial_start=args.serial_start, lifecycle_count=args.lifecycle_count,
            minimum_history_delta=args.minimum_history_delta,
            mutation_samples=args.mutation_samples, output=Path(args.output),
        )
        print(json.dumps({key: result[key] for key in ("verdict", "platform", "retained_lifecycles", "semantic", "history", "timing_ms", "storage", "result_digest")}, indent=2, sort_keys=True))
        return 0 if result["verdict"] == "PASS" else 3
    except (OSError, ValueError, sqlite3.Error, ScaleError, qualification.QualificationError) as error:
        print(f"lifecycle scale error: {error}", file=os.sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
