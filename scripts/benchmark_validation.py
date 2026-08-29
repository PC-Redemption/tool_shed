#!/usr/bin/env python3
"""Measure repeated Tool Shed validation without making routine CI timing-sensitive."""

from __future__ import annotations

import sys as _runtime_sys

_runtime_sys.dont_write_bytecode = True

import argparse
import statistics
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


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
    args = parser.parse_args(argv)
    if args.shard_index < 0 or args.shard_index >= args.shard_count:
        parser.error("--shard-index must be between 0 and --shard-count - 1")
    if args.warning_median_seconds >= args.max_median_seconds:
        parser.error("--warning-median-seconds must be less than --max-median-seconds")
    return args


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
