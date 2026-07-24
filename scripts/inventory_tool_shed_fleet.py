#!/usr/bin/env python3
"""Inventory Tool Shed instruction snapshots locally and over SSH without writing."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
from typing import Any


INSTRUCTION_FILES = (
    "SHED_VERSION.json",
    "README.md",
    "selection.md",
    "conventions.md",
    "existing-projects.md",
    "skills/tool-shed/SKILL.md",
)
DEFAULT_ROOTS = ("/home", "/srv", "/opt", "/Users")


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def scan_roots(roots: list[str], files: tuple[str, ...] = INSTRUCTION_FILES) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    for root_text in roots:
        root = Path(os.path.expanduser(root_text))
        if not root.is_dir():
            continue
        for current, dirs, _names in os.walk(root, onerror=lambda _error: None):
            dirs[:] = [name for name in dirs if name not in {".git", ".cache", "node_modules", ".venv", "venv"}]
            if Path(current).name != "tool_shed":
                continue
            dirs[:] = []
            shed = Path(current)
            resolved = str(shed.resolve())
            if resolved in seen:
                continue
            seen.add(resolved)
            if not (shed / "selection.md").is_file() or not (shed / "conventions.md").is_file():
                continue
            hashes: dict[str, str | None] = {}
            for relative in files:
                candidate = shed / relative
                try:
                    hashes[relative] = hash_file(candidate) if candidate.is_file() else None
                except OSError:
                    hashes[relative] = None
            results.append(
                {
                    "path": resolved,
                    "kind": "checkout" if (shed / ".git").exists() else "snapshot",
                    "hashes": hashes,
                }
            )
    return sorted(results, key=lambda item: item["path"])


def ssh_hosts(config: Path) -> list[str]:
    hosts: list[str] = []
    if not config.is_file():
        return hosts
    for raw_line in config.read_text(encoding="utf-8").splitlines():
        parts = raw_line.split()
        if not parts or parts[0].lower() != "host":
            continue
        for host in parts[1:]:
            if not any(character in host for character in "*?!") and host != "github.com" and host not in hosts:
                hosts.append(host)
    return hosts


REMOTE_SCANNER = r'''
import hashlib, json, os, pathlib, sys
roots = json.loads(sys.argv[1]); files = json.loads(sys.argv[2]); results = []; seen = set()
def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""): value.update(chunk)
    return value.hexdigest()
for root_text in roots:
    root = pathlib.Path(os.path.expanduser(root_text))
    if not root.is_dir(): continue
    for current, dirs, names in os.walk(str(root), onerror=lambda error: None):
        dirs[:] = [name for name in dirs if name not in {".git", ".cache", "node_modules", ".venv", "venv"}]
        if pathlib.Path(current).name != "tool_shed": continue
        dirs[:] = []; shed = pathlib.Path(current); resolved = str(shed.resolve())
        if resolved in seen: continue
        seen.add(resolved)
        if not (shed / "selection.md").is_file() or not (shed / "conventions.md").is_file(): continue
        hashes = {}
        for relative in files:
            candidate = shed / relative
            try: hashes[relative] = digest(candidate) if candidate.is_file() else None
            except OSError: hashes[relative] = None
        results.append({"path": resolved, "kind": "checkout" if (shed / ".git").exists() else "snapshot", "hashes": hashes})
print(json.dumps(sorted(results, key=lambda item: item["path"])))
'''


def scan_host(host: str, roots: list[str], timeout: int) -> dict[str, Any]:
    command = " ".join(
        [
            "python3",
            "-c",
            shlex.quote(REMOTE_SCANNER),
            shlex.quote(json.dumps(roots)),
            shlex.quote(json.dumps(INSTRUCTION_FILES)),
        ]
    )
    try:
        completed = subprocess.run(
            ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", host, command],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {"host": host, "status": "unreachable", "detail": "scan timed out", "sheds": []}
    if completed.returncode != 0:
        detail = completed.stderr.strip().splitlines()[-1] if completed.stderr.strip() else f"ssh exited {completed.returncode}"
        return {"host": host, "status": "unreachable", "detail": detail, "sheds": []}
    try:
        sheds = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return {"host": host, "status": "error", "detail": "remote scanner returned invalid JSON", "sheds": []}
    return {"host": host, "status": "ok", "detail": "", "sheds": sheds}


def classify(report: dict[str, Any], canonical: dict[str, str]) -> None:
    for shed in report["sheds"]:
        missing = [name for name, value in shed["hashes"].items() if value is None]
        changed = [name for name, value in shed["hashes"].items() if value is not None and value != canonical[name]]
        if shed["kind"] == "checkout":
            state = "checkout"
        elif missing:
            state = "incomplete"
        elif changed:
            state = "stale"
        else:
            state = "current"
        shed.update({"state": state, "missing": missing, "changed": changed})


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--canonical", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--root", action="append", dest="roots", help="Search root; repeat as needed")
    parser.add_argument("--host", action="append", default=[], help="SSH host alias; repeat as needed")
    parser.add_argument("--all-ssh-hosts", action="store_true", help="Use literal aliases from the SSH config")
    parser.add_argument("--ssh-config", default="~/.ssh/config")
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    canonical_root = Path(args.canonical).expanduser().resolve()
    canonical = {name: hash_file(canonical_root / name) for name in INSTRUCTION_FILES}
    roots = args.roots or list(DEFAULT_ROOTS)
    hosts = list(args.host)
    if args.all_ssh_hosts:
        for host in ssh_hosts(Path(args.ssh_config).expanduser()):
            if host not in hosts:
                hosts.append(host)

    reports = [{"host": "local", "status": "ok", "detail": "", "sheds": scan_roots(roots)}]
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(12, max(1, len(hosts)))) as executor:
        reports.extend(executor.map(lambda host: scan_host(host, roots, args.timeout), hosts))
    for report in reports:
        classify(report, canonical)

    payload = {"canonical": str(canonical_root), "instruction_files": list(INSTRUCTION_FILES), "hosts": reports}
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        for report in reports:
            if report["status"] != "ok":
                print(f'{report["host"]}\t{report["status"]}\t{report["detail"]}')
                continue
            if not report["sheds"]:
                print(f'{report["host"]}\tno-snapshots')
            for shed in report["sheds"]:
                detail = ",".join(shed["missing"] + shed["changed"])
                print(f'{report["host"]}\t{shed["state"]}\t{shed["path"]}\t{detail}')
    return 0


if __name__ == "__main__":
    sys.exit(main())
