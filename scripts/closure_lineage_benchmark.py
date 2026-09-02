#!/usr/bin/env python3
"""Deterministic provisional performance corpus for recursive closure projections."""

from __future__ import annotations

import sys as _runtime_sys

_runtime_sys.dont_write_bytecode = True

import argparse
import json
import sqlite3
import statistics
import time

import closure_lineage
import closure_lineage_schema
import document_store_schema
import hybrid_state_schema


def build_connection(elements: int, edges: int, depth: int) -> tuple[sqlite3.Connection, str]:
    if elements < 4 or elements % 2:
        raise ValueError("elements must be an even integer of at least 4")
    cycle_count = elements // 2
    if depth < 1 or depth >= cycle_count:
        raise ValueError("depth must be positive and smaller than the cycle count")
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    hybrid_state_schema.create_schema(connection, include_triggers=False)
    document_store_schema.create_document_schema(connection, include_triggers=False)
    closure_lineage_schema.create_closure_schema(connection, include_triggers=False)
    stamp = "2026-09-02T00:00:00Z"
    blank = "0" * 64
    artifacts = []
    cycles = []
    requirements = []
    elements_rows = []
    requirement_digests: list[str] = []
    for index in range(cycle_count):
        artifact_id = f"artifact-{index:08d}"
        cycle_id = f"cycle-{index:08d}"
        requirement_id = f"requirement-{index:08d}"
        artifacts.append((artifact_id, "benchmark", None, f"benchmark/{index}", "sqlite", "active", blank, stamp, stamp))
        cycles.append((cycle_id, "benchmark", artifact_id, "Benchmark closure", "working", stamp, None))
        requirement = (requirement_id, cycle_id, artifact_id, "Benchmark requirement", "accepted", 1, f"M{index}", f"G{index}")
        requirements.append(requirement)
        requirement_digests.append(
            closure_lineage.digest(
                {
                    "id": requirement_id,
                    "cycle_id": cycle_id,
                    "origin_artifact_id": artifact_id,
                    "accepted_outcome": "Benchmark requirement",
                    "disposition": "accepted",
                    "accepted_revision": 1,
                    "milestone_key": f"M{index}",
                    "evidence_gate_key": f"G{index}",
                }
            )
        )
        for prefix, role, cycle_value, requirement_value in (
            ("cycle-element", "cycle", cycle_id, None),
            ("obligation-element", "obligation", None, requirement_id),
        ):
            element_id = f"{prefix}-{index:08d}"
            envelope = {"element_id": element_id, "parents": []}
            elements_rows.append(
                (
                    element_id, role, "benchmark", artifact_id, cycle_value, requirement_value,
                    1, blank, json.dumps(envelope, sort_keys=True), closure_lineage.digest(envelope), 1, 1,
                )
            )
    connection.executemany("INSERT INTO artifact VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", artifacts)
    connection.executemany("INSERT INTO cycle VALUES (?, ?, ?, ?, ?, ?, ?)", cycles)
    connection.executemany("INSERT INTO requirement VALUES (?, ?, ?, ?, ?, ?, ?, ?)", requirements)
    connection.executemany("INSERT INTO closure_element VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", elements_rows)

    chain_edges = max(1, depth // 2)
    chain_start = cycle_count - chain_edges - 1
    pairs: list[tuple[int, int]] = [
        (chain_start + offset + 1, chain_start + offset) for offset in range(chain_edges)
    ]
    wide_parent_count = min(1024, max(1, cycle_count // 10))
    child_start = wide_parent_count
    cursor = 0
    while len(pairs) < edges:
        child = child_start + (cursor % max(1, chain_start - child_start))
        parent = (cursor // max(1, chain_start - child_start)) % wide_parent_count
        pairs.append((child, parent))
        cursor += 1
    pairs = list(dict.fromkeys(pairs))
    while len(pairs) < edges:
        child = child_start + (len(pairs) % max(1, chain_start - child_start))
        parent = (len(pairs) * 17) % wide_parent_count
        candidate = (child, parent)
        if candidate not in pairs:
            pairs.append(candidate)
    claims = []
    for ordinal, (child, parent) in enumerate(pairs[:edges]):
        claims.append(
            (
                f"claim-{ordinal:08d}", f"cycle-element-{child:08d}", f"cycle-element-{parent:08d}",
                f"requirement-{parent:08d}", "fulfills", 1, requirement_digests[parent], blank, 1, None,
            )
        )
    connection.executemany("INSERT INTO lineage_claim VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", claims)
    connection.execute(
        "INSERT INTO closure_graph_meta VALUES (1, 1, 0, ?, ?, ?)",
        (closure_lineage.EVALUATOR_VERSION, blank, stamp),
    )
    return connection, f"cycle-element-{chain_start + chain_edges:08d}"


def run(elements: int, edges: int, depth: int, repeats: int) -> dict[str, object]:
    connection, leaf = build_connection(elements, edges, depth)
    started = time.perf_counter()
    rebuilt = closure_lineage.rebuild_projection(connection, revision=1)
    rebuild_ms = (time.perf_counter() - started) * 1000
    status_times = []
    blocker_times = []
    for _ in range(repeats):
        started = time.perf_counter()
        connection.execute("SELECT * FROM closure_rollup WHERE element_id=?", (leaf,)).fetchone()
        status_times.append((time.perf_counter() - started) * 1000)
        started = time.perf_counter()
        list(
            connection.execute(
                "SELECT * FROM closure_blocker WHERE ancestor_element_id=? "
                "ORDER BY depth, reason_code, id LIMIT 100",
                (leaf,),
            )
        )
        blocker_times.append((time.perf_counter() - started) * 1000)
    mutation_times = []
    for revision in range(2, repeats + 2):
        started = time.perf_counter()
        closure_lineage.refresh_projection(
            connection, revision=revision, changed_element_ids=[leaf]
        )
        mutation_times.append((time.perf_counter() - started) * 1000)
    recursive = closure_lineage.evaluate_recursive(connection)
    parity = all(
        bool(row["effective_closed"]) == bool(recursive[str(row["element_id"])]["effective_closed"])
        and json.loads(row["reason_codes_json"]) == recursive[str(row["element_id"])]["reasons"]
        for row in connection.execute("SELECT * FROM closure_rollup")
    )
    return {
        "schema_version": 1,
        "kind": "tool-shed-closure-lineage-benchmark",
        "corpus": {"elements": elements, "edges": edges, "maximum_depth": depth},
        "results_ms": {
            "summary_p95": statistics.quantiles(status_times, n=20)[18] if repeats >= 2 else status_times[0],
            "first_100_blockers_p95": statistics.quantiles(blocker_times, n=20)[18] if repeats >= 2 else blocker_times[0],
            "mutation_p95": statistics.quantiles(mutation_times, n=20)[18] if repeats >= 2 else mutation_times[0],
            "full_rebuild": rebuild_ms,
        },
        "budgets_ms": {"summary": 20, "first_100_blockers": 50, "mutation": 250, "full_rebuild": 60_000},
        "parity": parity,
        "projection": rebuilt,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elements", type=int, default=25_000)
    parser.add_argument("--edges", type=int, default=100_000)
    parser.add_argument("--depth", type=int, default=128)
    parser.add_argument("--repeats", type=int, default=10)
    args = parser.parse_args()
    result = run(args.elements, args.edges, args.depth, args.repeats)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["parity"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
