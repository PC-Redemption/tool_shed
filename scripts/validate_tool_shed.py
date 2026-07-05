from __future__ import annotations

import json
import py_compile
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def step(name: str) -> None:
    print(f"== {name} ==", flush=True)


def run(args: list[str], *, cwd: Path = ROOT, quiet: bool = False) -> None:
    subprocess.run(args, cwd=str(cwd), check=True, stdout=subprocess.DEVNULL if quiet else None)


def compile_python() -> None:
    step("compile python")
    for path in sorted((ROOT / "scripts").glob("*.py")) + sorted((ROOT / "tests").glob("*.py")):
        py_compile.compile(str(path), doraise=True)


def run_unit_tests() -> None:
    step("unit tests")
    run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"])


def regenerate_indexes() -> None:
    step("regenerate indexes")
    run([sys.executable, "scripts/update_work_index.py", "--workspace", "."])
    run([sys.executable, "-m", "json.tool", "work/index.json"], quiet=True)


def check_stale_paths() -> None:
    step("stale paths")
    run([sys.executable, "scripts/check_stale_paths.py", "--workspace", "."])


def smoke_temp_workspace() -> None:
    step("temp workspace smoke")
    with tempfile.TemporaryDirectory(prefix="tool-shed-validate-") as temp:
        workspace = Path(temp)
        run([sys.executable, str(ROOT / "scripts" / "install_into_workspace.py"), str(workspace)])
        run(
            [
                sys.executable,
                str(ROOT / "scripts" / "onboard_existing_project.py"),
                "Validate Project",
                "--workspace",
                str(workspace),
                "--shed",
                str(ROOT),
            ]
        )
        run(
            [
                sys.executable,
                str(ROOT / "scripts" / "new_artifact.py"),
                "checklist",
                "Runtime Closeout",
                "--workspace",
                str(workspace),
                "--shed",
                str(ROOT),
            ]
        )
        run([sys.executable, str(ROOT / "scripts" / "check_stale_paths.py"), "--workspace", str(workspace)])
        payload = json.loads((workspace / "work" / "index.json").read_text(encoding="utf-8"))
        paths = {item["path"] for item in payload["artifacts"]}
        required = {
            "work/maps/map-validate-project.md",
            "work/inventories/inventory-validate-project-surfaces.md",
            "work/checklists/checklist-runtime-closeout.md",
        }
        missing = sorted(required - paths)
        if missing:
            raise SystemExit(f"index missing expected artifacts: {missing}")


def header_fields(path: Path) -> dict[str, str]:
    fields: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines()[:20]:
        if ":" not in raw_line:
            continue
        key, value = raw_line.split(":", 1)
        fields[key.strip()] = value.strip()
    return fields


def sanity_check_markdown() -> None:
    step("template and example sanity")
    required = {"Status", "Type", "Updated", "Next Action"}
    for directory in [ROOT / "templates", ROOT / "examples"]:
        for path in sorted(directory.glob("*.md")):
            text = path.read_text(encoding="utf-8")
            if "{{ title }}" in text:
                text = text.replace("{{ title }}", "Example").replace("{{ date }}", "2026-07-05")
                with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
                    temp_path = Path(handle.name)
                    handle.write(text)
                try:
                    fields = header_fields(temp_path)
                finally:
                    temp_path.unlink(missing_ok=True)
            else:
                fields = header_fields(path)
            missing = sorted(required - set(fields))
            if missing:
                raise SystemExit(f"{path.relative_to(ROOT)} missing header fields: {missing}")


def cleanup_caches() -> None:
    for path in ROOT.rglob("__pycache__"):
        shutil.rmtree(path)


def main() -> int:
    try:
        compile_python()
        run_unit_tests()
        regenerate_indexes()
        check_stale_paths()
        smoke_temp_workspace()
        sanity_check_markdown()
    finally:
        cleanup_caches()
    print("tool_shed validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
