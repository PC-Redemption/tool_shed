#!/usr/bin/env python3
"""Measure repeated Tool Shed validation without making routine CI timing-sensitive."""

from __future__ import annotations

import sys as _runtime_sys

_runtime_sys.dont_write_bytecode = True

import argparse
import hashlib
import json
import statistics
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CORPUS = Path("tests/fixtures/validation-performance-corpus-v1.json")


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return parsed


def positive_float(value: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than 0")
    return parsed


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=positive_int, default=3)
    parser.add_argument("--jobs", type=positive_int, default=6)
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--shard-count", type=positive_int, default=8)
    parser.add_argument("--warning-median-seconds", type=positive_float, default=60.0)
    parser.add_argument("--max-median-seconds", type=positive_float, default=180.0)
    parser.add_argument("--corpus", default=DEFAULT_CORPUS.as_posix())
    parser.add_argument("--corpus-only", action="store_true")
    args = parser.parse_args(argv)
    if args.shard_index < 0 or args.shard_index >= args.shard_count:
        parser.error("--shard-index must be between 0 and --shard-count - 1")
    if args.warning_median_seconds >= args.max_median_seconds:
        parser.error("--warning-median-seconds must be less than --max-median-seconds")
    return args


def canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def materialize_corpus(fixture: dict[str, object]) -> list[dict[str, object]]:
    dimensions = fixture["dimensions"]
    records: list[dict[str, object]] = []
    for kind in sorted(dimensions):
        for index in range(int(dimensions[kind])):
            records.append(
                {
                    "id": f"{kind[:3].upper()}-{index:04d}",
                    "kind": kind,
                    "lifecycle": ("active", "working", "completed")[index % 3],
                    "revision": 1 + index % 17,
                    "parent": None if index == 0 else f"{kind[:3].upper()}-{index - 1:04d}",
                }
            )
    return records


def corpus_digest(records: list[dict[str, object]]) -> str:
    return hashlib.sha256(canonical_bytes(records)).hexdigest()


def validate_corpus(records: list[dict[str, object]]) -> str:
    identities = {str(item["id"]) for item in records}
    if len(identities) != len(records):
        raise SystemExit("frozen validation corpus contains duplicate identities")
    for item in records:
        parent = item["parent"]
        if parent is not None and str(parent) not in identities:
            raise SystemExit(f"frozen validation corpus has an unknown parent: {parent}")
        if item["lifecycle"] not in {"active", "working", "completed"}:
            raise SystemExit("frozen validation corpus has an invalid lifecycle")
    return corpus_digest(records)


def timed(callable_: object, records: list[dict[str, object]], iterations: int) -> float:
    started = time.perf_counter()
    for _ in range(iterations):
        callable_(records)
    return time.perf_counter() - started


def qualify_frozen_corpus(path: Path) -> dict[str, float | str]:
    fixture = json.loads(path.read_text(encoding="utf-8"))
    if fixture.get("kind") != "tool-shed-validation-performance-corpus":
        raise SystemExit("unsupported validation performance corpus")
    records = materialize_corpus(fixture)
    observed_digest = corpus_digest(records)
    if observed_digest != fixture.get("expected_digest"):
        raise SystemExit(
            "frozen validation performance corpus digest changed: " + observed_digest
        )
    samples = int(fixture["samples"])
    iterations = int(fixture["iterations"])
    ratios: list[float] = []
    for _ in range(samples):
        reference = timed(corpus_digest, records, iterations)
        candidate = timed(validate_corpus, records, iterations)
        ratios.append(candidate / reference)
    observed = statistics.median(ratios)
    baseline = float(fixture["baseline_candidate_ratio"])
    relative = observed / baseline
    maximum = float(fixture["max_relative_regression"])
    print(
        f"frozen corpus candidate/reference median: {observed:.4f}; "
        f"relative to baseline: {relative:.4f}"
    )
    if relative > maximum:
        raise SystemExit(
            f"frozen corpus performance regressed {relative:.3f}x from its checked-in "
            f"baseline; allowed {maximum:.3f}x"
        )
    return {
        "digest": observed_digest,
        "candidate_reference_ratio": observed,
        "relative_to_baseline": relative,
    }


def validator_command(args: argparse.Namespace) -> list[str]:
    return [
        sys.executable,
        "scripts/validate_tool_shed.py",
        "--profile",
        "release",
        "--warn-seconds",
        "60",
        "--max-seconds",
        "300",
        "--jobs",
        str(args.jobs),
        "--shard-index",
        str(args.shard_index),
        "--shard-count",
        str(args.shard_count),
    ]


def run_sample(command: list[str], sample: int, total: int) -> float:
    print(f"== validation performance sample {sample}/{total} ==", flush=True)
    started = time.monotonic()
    result = subprocess.run(command, cwd=ROOT, text=True, check=False)
    elapsed = time.monotonic() - started
    if result.returncode:
        raise SystemExit(
            f"validation performance sample {sample}/{total} failed functionally "
            f"after {elapsed:.3f}s"
        )
    print(f"sample {sample}/{total} completed in {elapsed:.3f}s", flush=True)
    return elapsed


def evaluate_median(elapsed: list[float], warning: float, maximum: float) -> float:
    median = statistics.median(elapsed)
    print(
        "validation performance samples: "
        + ", ".join(f"{value:.3f}s" for value in elapsed)
    )
    print(f"validation performance median: {median:.3f}s")
    if median > warning:
        print(
            f"WARNING: validation performance median exceeded its {warning:g}s "
            f"advisory threshold: {median:.3f}s",
            file=sys.stderr,
        )
    if median > maximum:
        raise SystemExit(
            f"validation performance median exceeded its {maximum:g}s budget: "
            f"{median:.3f}s"
        )
    return median


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    qualify_frozen_corpus(ROOT / args.corpus)
    if args.corpus_only:
        return 0
    command = validator_command(args)
    elapsed = [
        run_sample(command, sample, args.samples)
        for sample in range(1, args.samples + 1)
    ]
    evaluate_median(
        elapsed,
        args.warning_median_seconds,
        args.max_median_seconds,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
