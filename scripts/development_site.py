#!/usr/bin/env python3
"""Stage and operate the isolated LAN-only Tool Shed development site."""

from __future__ import annotations

import sys as _runtime_sys

_runtime_sys.dont_write_bytecode = True

import argparse
import json
import os
import shutil
import stat
import subprocess
import tarfile
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Sequence


ROOT = Path(__file__).resolve().parents[1]
DEVELOPMENT_ROOT = Path("/home/jon/docker/ts.rookaro.com-dev")
PRODUCTION_ROOT = Path("/home/jon/docker/ts.rookaro.com")
PROJECT = "tsrookarocom-dev"
PRODUCTION_PROJECT = "tsrookarocom"
LAN_ADDRESS = "192.168.7.5"
PORT = 8443
MARKER = ".tool-shed-development-site.json"


class DevelopmentSiteError(RuntimeError):
    pass


def run(arguments: Sequence[str], *, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        list(arguments),
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise DevelopmentSiteError(f"command failed ({result.returncode}): {' '.join(arguments)}: {detail}")
    return result


def target_contract(target: Path = DEVELOPMENT_ROOT) -> dict[str, Any]:
    resolved = target.expanduser().resolve()
    if resolved == PRODUCTION_ROOT.resolve():
        raise DevelopmentSiteError("development target must not be the production deployment root")
    return {
        "target": str(resolved),
        "production_target": str(PRODUCTION_ROOT),
        "compose_project": PROJECT,
        "production_compose_project": PRODUCTION_PROJECT,
        "endpoint": f"http://{LAN_ADDRESS}:{PORT}",
        "workpc_endpoint": f"http://127.0.0.1:{PORT}",
        "public_route": False,
        "tls": False,
        "data_source": "empty-database-plus-synthetic-seed-only",
    }


def _load_marker(target: Path) -> dict[str, Any]:
    marker_path = target / MARKER
    if not marker_path.is_file():
        raise DevelopmentSiteError(f"managed development marker is missing: {marker_path}")
    try:
        payload = json.loads(marker_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise DevelopmentSiteError("managed development marker is unreadable") from error
    if not isinstance(payload, dict) or payload.get("compose_project") != PROJECT:
        raise DevelopmentSiteError("managed development marker has the wrong project identity")
    return payload


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _replace_tree(source: Path, destination: Path) -> None:
    staged = destination.with_name(destination.name + ".staged")
    previous = destination.with_name(destination.name + ".previous")
    if staged.exists():
        shutil.rmtree(staged)
    shutil.copytree(source, staged)
    if previous.exists():
        shutil.rmtree(previous)
    if destination.exists():
        destination.rename(previous)
    staged.rename(destination)


def _export_commit(commit: str, destination: Path) -> str:
    resolved = run(("git", "rev-parse", "--verify", f"{commit}^{{commit}}"), cwd=ROOT).stdout.strip()
    archive = destination / "source.tar"
    run(("git", "archive", "--format=tar", "--output", str(archive), resolved), cwd=ROOT)
    source = destination / "source"
    source.mkdir()
    with tarfile.open(archive) as bundle:
        root = source.resolve()
        for member in bundle.getmembers():
            candidate = (source / member.name).resolve()
            try:
                candidate.relative_to(root)
            except ValueError as error:
                raise DevelopmentSiteError("source archive contains an unsafe path") from error
            if member.issym() or member.islnk():
                raise DevelopmentSiteError("source archive links are not permitted")
        bundle.extractall(source, filter="data")
    return resolved


def stage(commit: str, *, target: Path = DEVELOPMENT_ROOT) -> dict[str, Any]:
    contract = target_contract(target)
    resolved_target = Path(contract["target"])
    if resolved_target.exists():
        _load_marker(resolved_target)
    else:
        resolved_target.mkdir(parents=True, mode=0o750)

    with tempfile.TemporaryDirectory(prefix="tool-shed-development-stage-") as temporary_name:
        temporary = Path(temporary_name)
        source_commit = _export_commit(commit, temporary)
        exported = temporary / "source"
        short_commit = source_commit[:12]
        image_tag = f"dev-{short_commit}"
        image = f"tool-shed-dashboard:{image_tag}"
        bundle = temporary / "bundle"
        run((str(_runtime_sys.executable), "scripts/build_docs_site.py", "--output", str(bundle)), cwd=exported)
        run(("docker", "build", "-f", "dashboard/Dockerfile", "-t", image, "."), cwd=exported)
        _replace_tree(bundle / "public", resolved_target / "public")
        shutil.copy2(bundle / "docker-compose.yml", resolved_target / "docker-compose.yml")
        shutil.copy2(bundle / "nginx.conf", resolved_target / "nginx.conf")
        environment_example = (
            exported / "site" / "deploy" / ".env.development.example"
        ).read_text(encoding="utf-8")
        environment_example = environment_example.replace(
            "TOOL_SHED_DASHBOARD_IMAGE_TAG=development-candidate",
            f"TOOL_SHED_DASHBOARD_IMAGE_TAG={image_tag}",
        )
        (resolved_target / ".env.example").write_text(
            environment_example,
            encoding="utf-8",
        )

    marker = {
        "schema_version": 1,
        **contract,
        "source_commit": source_commit,
        "dashboard_image": image,
        "image_tag": image_tag,
    }
    _atomic_json(resolved_target / MARKER, marker)
    return {"operation": "stage", "state": "staged", **marker}


def _protected_environment(target: Path) -> Path:
    environment = target / ".env"
    if not environment.is_file():
        raise DevelopmentSiteError(
            f"protected development environment is missing: {environment}; create it from .env.example"
        )
    mode = stat.S_IMODE(environment.stat().st_mode)
    if mode & 0o077:
        raise DevelopmentSiteError(f"protected development environment must not be group/world accessible: {oct(mode)}")
    return environment


def _controlled_environment(target: Path, marker: dict[str, Any]) -> None:
    allowed = {
        "COMPOSE_PROJECT_NAME",
        "TOOL_SHED_DASHBOARD_ENVIRONMENT",
        "TOOL_SHED_DASHBOARD_ALLOW_INSECURE_HTTP",
        "TOOL_SHED_DASHBOARD_IMAGE_TAG",
        "TOOL_SHED_DOCS_CONTAINER_NAME",
        "TOOL_SHED_SITE_BIND_ADDRESS",
        "TOOL_SHED_SITE_PORT",
    }
    values: dict[str, str] = {}
    for raw_line in _protected_environment(target).read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key in allowed:
            values[key] = value
    expected = {
        "COMPOSE_PROJECT_NAME": PROJECT,
        "TOOL_SHED_DASHBOARD_ENVIRONMENT": "development",
        "TOOL_SHED_DASHBOARD_ALLOW_INSECURE_HTTP": "1",
        "TOOL_SHED_DASHBOARD_IMAGE_TAG": str(marker["image_tag"]),
        "TOOL_SHED_DOCS_CONTAINER_NAME": "ts-rookaro-com-dev",
        "TOOL_SHED_SITE_BIND_ADDRESS": LAN_ADDRESS,
        "TOOL_SHED_SITE_PORT": str(PORT),
    }
    mismatches = [key for key, value in expected.items() if values.get(key) != value]
    if mismatches:
        raise DevelopmentSiteError(
            "protected development environment does not match the isolated target: "
            + ", ".join(sorted(mismatches))
        )


def compose_arguments(target: Path, *arguments: str) -> tuple[str, ...]:
    environment = _protected_environment(target)
    return (
        "docker",
        "compose",
        "--project-name",
        PROJECT,
        "--project-directory",
        str(target),
        "--env-file",
        str(environment),
        "-f",
        str(target / "docker-compose.yml"),
        *arguments,
    )


def deploy(*, target: Path = DEVELOPMENT_ROOT) -> dict[str, Any]:
    contract = target_contract(target)
    resolved_target = Path(contract["target"])
    marker = _load_marker(resolved_target)
    _controlled_environment(resolved_target, marker)
    run(compose_arguments(resolved_target, "config", "--quiet"), cwd=resolved_target)
    run(compose_arguments(resolved_target, "up", "-d", "--no-build"), cwd=resolved_target)
    # Staging replaces public/ atomically. Recreate the docs container so its
    # bind mount follows the replacement directory instead of the old inode.
    run(
        compose_arguments(
            resolved_target,
            "up",
            "-d",
            "--no-build",
            "--force-recreate",
            "--no-deps",
            "docs",
        ),
        cwd=resolved_target,
    )
    return {"operation": "deploy", "state": "started", **marker, "status": status(target=resolved_target)}


def _health(url: str) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(url, timeout=4) as response:
            body = response.read(4096).decode("utf-8", errors="replace")
            return {"url": url, "status": response.status, "body": body.strip(), "healthy": response.status == 200}
    except (OSError, urllib.error.URLError) as error:
        return {"url": url, "status": None, "body": None, "healthy": False, "error": type(error).__name__}


def status(*, target: Path = DEVELOPMENT_ROOT) -> dict[str, Any]:
    contract = target_contract(target)
    resolved_target = Path(contract["target"])
    marker = _load_marker(resolved_target) if resolved_target.exists() else None
    compose: list[dict[str, Any]] = []
    if marker and (resolved_target / ".env").is_file():
        result = run(compose_arguments(resolved_target, "ps", "--format", "json"), cwd=resolved_target)
        for line in result.stdout.splitlines():
            if line.strip():
                compose.append(json.loads(line))
    return {
        "operation": "status",
        "contract": contract,
        "marker": marker,
        "containers": compose,
        "development_health": _health(f"http://{LAN_ADDRESS}:{PORT}/healthz"),
        "dashboard_health": _health(f"http://{LAN_ADDRESS}:{PORT}/dashboard/healthz"),
        "production_health": _health("http://127.0.0.1:8087/healthz"),
    }


def stop(*, target: Path = DEVELOPMENT_ROOT) -> dict[str, Any]:
    contract = target_contract(target)
    resolved_target = Path(contract["target"])
    _load_marker(resolved_target)
    run(compose_arguments(resolved_target, "stop"), cwd=resolved_target)
    return {"operation": "stop", "state": "stopped", **contract}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("plan")
    stage_parser = subparsers.add_parser("stage")
    stage_parser.add_argument("--commit", required=True)
    subparsers.add_parser("deploy")
    subparsers.add_parser("status")
    subparsers.add_parser("stop")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.command == "plan":
            result = {"operation": "plan", **target_contract()}
        elif args.command == "stage":
            result = stage(args.commit)
        elif args.command == "deploy":
            result = deploy()
        elif args.command == "status":
            result = status()
        else:
            result = stop()
    except DevelopmentSiteError as error:
        if args.json:
            print(json.dumps({"state": "failed", "error": str(error)}, sort_keys=True))
        else:
            print(f"Development site operation failed: {error}", file=_runtime_sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"Development site {result.get('operation')}: {result.get('state', result.get('endpoint'))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
