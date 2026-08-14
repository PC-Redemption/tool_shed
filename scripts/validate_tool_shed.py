from __future__ import annotations

import hashlib
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


def is_canonical_checkout() -> bool:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=str(ROOT),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except OSError:
        return False
    return result.returncode == 0 and Path(result.stdout.strip()).resolve() == ROOT


def source_fingerprint() -> dict[str, str]:
    result: dict[str, str] = {}
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"}:
            continue
        result[path.relative_to(ROOT).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def compile_python() -> None:
    step("compile python")
    for path in sorted((ROOT / "scripts").glob("*.py")) + sorted((ROOT / "tests").glob("*.py")):
        py_compile.compile(str(path), doraise=True)


def check_shed_manifest() -> None:
    step("shed version manifest")
    run([sys.executable, "scripts/update_shed_manifest.py", "--check"])


def run_unit_tests() -> None:
    step("unit tests")
    run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"])


def check_provider_adapters() -> None:
    step("provider adapter conformance")
    run([sys.executable, "scripts/check_provider_adapters.py"])


def regenerate_indexes() -> None:
    step("regenerate indexes")
    run([sys.executable, "scripts/update_work_index.py", "--workspace", "."])
    run([sys.executable, "-m", "json.tool", "work/index.json"], quiet=True)


def check_stale_paths() -> None:
    step("stale paths")
    run([sys.executable, "scripts/check_stale_paths.py", "--workspace", "."])


def review_work_state() -> None:
    step("work state review")
    run([sys.executable, "scripts/review_work_state.py", "--workspace", "."])


def smoke_temp_workspace() -> None:
    step("temp workspace smoke")
    with tempfile.TemporaryDirectory(prefix="tool-shed-validate-") as temp:
        workspace = Path(temp)
        run(["git", "init", "--quiet"], cwd=workspace)
        run(
            [
                sys.executable,
                str(ROOT / "scripts" / "install_into_workspace.py"),
                str(workspace),
                "--provider",
                "all",
            ]
        )
        if not (workspace / "work" / "evidence" / "generated").is_dir():
            raise SystemExit("installer did not create the standard generated-evidence directory")
        ask_path = workspace / "work" / "q&a" / "ask.txt"
        if not ask_path.is_file():
            raise SystemExit("installer did not create the Tool Shed Q&A inbox")
        campaign_root = workspace / "work" / "00-campaigns"
        if not (campaign_root / "active-queue.md").is_file() or not (campaign_root / "completed-queue.md").is_file():
            raise SystemExit("installer did not create the owner campaign queue")
        agents_text = (workspace / "AGENTS.md").read_text(encoding="utf-8")
        if "ts:ship <goal>" not in agents_text or "plan, implement, validate, build, deploy, and verify" not in agents_text:
            raise SystemExit("installer did not create the Tool Shed ship guidance")
        if "Do not ask for repeated confirmation for reversible, in-scope steps" not in agents_text:
            raise SystemExit("installer did not create the Tool Shed authorization-discipline guidance")
        if "command success alone is not outcome success" not in agents_text:
            raise SystemExit("installer did not create the Tool Shed evidence-response guidance")
        if "at most three credible ways the plan could fail" not in agents_text:
            raise SystemExit("installer did not create the Tool Shed prospective-failure guidance")
        if "ts: discuss <topic>" not in agents_text or "Direct, Guided, Coordinated, or Deep" not in agents_text:
            raise SystemExit("installer did not create the Tool Shed discussion and coordination guidance")
        work_level_contract = (
            "ts:work1` through `ts:work5",
            "`ts:work` = `work2`",
            "work/tool-shed.yaml",
            "work_model: combined",
            "work_model: split",
            "automatically deploys production",
        )
        if any(fragment not in agents_text for fragment in work_level_contract):
            raise SystemExit("installer did not create the complete Tool Shed work-level contract")
        direct_contract = (
            "single-repository bug fix or enhancement to Direct",
            "orient to the named target once",
            "campaign continuity does not upgrade Direct",
            "ts:ask` does not turn a bounded Direct request",
            "merely mentions or discusses `ts:ship`",
        )
        if any(fragment not in agents_text for fragment in direct_contract):
            raise SystemExit("installer did not create the complete Tool Shed Direct-route contract")
        campaign_contract = (
            "work/00-campaigns/",
            "work/q&a/ask.txt` as transient intake",
            "current state token",
            "preview-only",
        )
        if any(fragment not in agents_text for fragment in campaign_contract):
            raise SystemExit("installer did not create the complete owner campaign contract")
        provider_paths = {
            "claude-code": "CLAUDE.md",
            "gemini-cli": "GEMINI.md",
            "github-copilot": ".github/copilot-instructions.md",
            "cursor": ".cursor/rules/tool-shed.mdc",
        }
        for provider_id, relative in provider_paths.items():
            guidance = workspace / relative
            guidance_text = guidance.read_text(encoding="utf-8") if guidance.is_file() else ""
            if (
                "BEGIN TOOL SHED ROUTING GUIDANCE" not in guidance_text
                or any(fragment not in guidance_text for fragment in direct_contract)
                or any(fragment not in guidance_text for fragment in work_level_contract)
            ):
                raise SystemExit(f"installer did not create {provider_id} adapter guidance")
        inbox_result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "read_ask_inbox.py"),
                "--workspace",
                str(workspace),
                "--json",
            ],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
        )
        if json.loads(inbox_result.stdout)["status"] != "empty":
            raise SystemExit("new Tool Shed Q&A inbox did not resolve as empty")
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
                "wp",
                "Finish Me",
                "--workspace",
                str(workspace),
                "--shed",
                str(ROOT),
            ]
        )
        run(
            [
                sys.executable,
                str(ROOT / "scripts" / "complete_workpackage.py"),
                "work/wp/active/wp-finish-me.md",
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
        checklist = workspace / "work" / "checklists" / "checklist-runtime-closeout.md"
        checklist.write_text(
            checklist.read_text(encoding="utf-8").replace(
                "Parent: work/...",
                "Parent: work/maps/map-validate-project.md",
            ),
            encoding="utf-8",
        )
        run([sys.executable, str(ROOT / "scripts" / "check_stale_paths.py"), "--workspace", str(workspace)])
        run(
            [
                sys.executable,
                str(ROOT / "scripts" / "review_work_state.py"),
                "--workspace",
                str(workspace),
                "--strict",
            ]
        )
        payload = json.loads((workspace / "work" / "index.json").read_text(encoding="utf-8"))
        paths = {item["path"] for item in payload["artifacts"]}
        required = {
            "work/maps/map-validate-project.md",
            "work/inventories/inventory-validate-project-surfaces.md",
            "work/wp/completed/wp-finish-me.md",
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
            if path.name in {"active-campaign-queue.md", "completed-campaign-queue.md"}:
                continue
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
    canonical = is_canonical_checkout()
    before = source_fingerprint() if not canonical else None
    if not canonical and ((ROOT / ".git").exists() or (ROOT / "work").exists()):
        raise SystemExit("disconnected snapshot contains forbidden .git or work content")
    try:
        compile_python()
        check_shed_manifest()
        run_unit_tests()
        check_provider_adapters()
        if canonical:
            regenerate_indexes()
            check_stale_paths()
            review_work_state()
        else:
            step("canonical workspace state")
            print("Skipped for disconnected snapshot; no snapshot-local work/ was created.")
        smoke_temp_workspace()
        sanity_check_markdown()
    finally:
        cleanup_caches()
    if before is not None and source_fingerprint() != before:
        raise SystemExit("disconnected snapshot changed during validation")
    print("tool_shed validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
