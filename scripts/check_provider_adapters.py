#!/usr/bin/env python3
"""Run static conformance checks for every Tool Shed provider adapter."""

from __future__ import annotations

import sys as _runtime_sys

_runtime_sys.dont_write_bytecode = True

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from provider_adapters import CAPABILITY_LEVELS, load_manifest
from project_identity import IDENTITY_RELATIVE_PATH, binding_token


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts" / "install_into_workspace.py"
ROUTING_MARKER = "BEGIN TOOL SHED ROUTING GUIDANCE"
DISCUSSION_MARKER = "BEGIN TOOL SHED DISCUSSION GUIDANCE"
COORDINATION_MARKER = "BEGIN TOOL SHED COORDINATION GUIDANCE"
IDENTITY_MARKER = "BEGIN TOOL SHED WORKSPACE IDENTITY GUIDANCE"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Emit a JSON conformance summary.")
    return parser.parse_args()


def run_installer(workspace: Path) -> None:
    arguments = [sys.executable, str(INSTALLER), str(workspace), "--provider", "all"]
    if (workspace / IDENTITY_RELATIVE_PATH).is_file():
        arguments.extend(
            ("--project-binding", binding_token(workspace, operation="workspace-install"))
        )
    subprocess.run(
        arguments,
        cwd=str(ROOT),
        check=True,
        stdout=subprocess.DEVNULL,
    )


def main() -> int:
    args = parse_args()
    manifest = load_manifest()
    providers = manifest["providers"]
    results: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory(prefix="tool-shed-adapters-") as temp:
        workspace = Path(temp)
        subprocess.run(["git", "init", "--quiet", str(workspace)], check=True)
        owner_text: dict[str, str] = {}
        for provider_id, config in providers.items():
            relative = str(config["instruction_path"])
            if relative.endswith("tool-shed.mdc"):
                continue
            content = f"# Owner guidance for {provider_id}\n"
            path = workspace / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            owner_text[relative] = content

        run_installer(workspace)
        after_first: dict[str, str] = {}
        for provider_id, config in providers.items():
            relative = str(config["instruction_path"])
            path = workspace / relative
            if not path.is_file():
                raise SystemExit(f"{provider_id}: missing instruction file {relative}")
            text = path.read_text(encoding="utf-8")
            after_first[relative] = text
            if text.count(ROUTING_MARKER) != 1:
                raise SystemExit(f"{provider_id}: expected one {ROUTING_MARKER!r}")
            if provider_id == "codex":
                for marker in (DISCUSSION_MARKER, COORDINATION_MARKER, IDENTITY_MARKER):
                    if marker in text:
                        raise SystemExit(f"{provider_id}: legacy expanded marker remains: {marker!r}")
                for fragment in (
                    "Activate Tool Shed only",
                    "Do not activate Tool Shed merely because",
                    "TOOL_SHED_SKILL_MISMATCH",
                    "skills/tool-shed/SKILL.md",
                ):
                    if fragment not in text:
                        raise SystemExit(f"{provider_id}: compact routing is missing {fragment!r}")
            else:
                for marker in (DISCUSSION_MARKER, COORDINATION_MARKER, IDENTITY_MARKER):
                    if text.count(marker) != 1:
                        raise SystemExit(f"{provider_id}: expected one {marker!r}")
            if owner_text.get(relative) and not text.startswith(owner_text[relative]):
                raise SystemExit(f"{provider_id}: owner content was not preserved")
            if config["instruction_format"] == "mdc" and not text.startswith("---\n"):
                raise SystemExit(f"{provider_id}: MDC frontmatter is missing")
            level = int(config["qualified_level"])
            results.append(
                {
                    "provider": provider_id,
                    "instruction_path": relative,
                    "qualified_level": level,
                    "qualified_capability": CAPABILITY_LEVELS[level],
                    "qualification_basis": config["qualification_basis"],
                    "owner_content_preserved": True,
                    "routing_present": True,
                    "compact_routing": provider_id == "codex",
                }
            )

        run_installer(workspace)
        for relative, first_text in after_first.items():
            second_text = (workspace / relative).read_text(encoding="utf-8")
            if second_text != first_text:
                raise SystemExit(f"adapter is not idempotent: {relative}")

    payload = {"schema_version": 1, "providers": sorted(results, key=lambda item: str(item["provider"]))}
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        for result in payload["providers"]:
            print(
                f"{result['provider']}: level {result['qualified_level']} "
                f"({result['qualified_capability']}), {result['instruction_path']}"
            )
        print("Provider adapter conformance passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
