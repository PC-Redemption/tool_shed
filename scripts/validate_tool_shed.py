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


def validate_program_roadmaps() -> None:
    step("program roadmaps")
    run([sys.executable, "scripts/program_roadmap.py", "--workspace", ".", "validate"])


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
        ask_path = workspace / "work" / "01-q&a" / "ask.txt"
        if not ask_path.is_file():
            raise SystemExit("installer did not create the Tool Shed Q&A inbox")
        campaign_root = workspace / "work" / "00-campaigns"
        if not (campaign_root / "active-queue.md").is_file() or not (campaign_root / "completed-queue.md").is_file():
            raise SystemExit("installer did not create the owner campaign queue")
        if not (workspace / "work" / "tool-shed-project.json").is_file():
            raise SystemExit("installer did not create the stable project identity")
        if not (workspace / "work" / "roadmaps").is_dir():
            raise SystemExit("installer did not create the opt-in Program Roadmap directory")
        agents_text = (workspace / "AGENTS.md").read_text(encoding="utf-8")
        if agents_text.count("BEGIN TOOL SHED ROUTING GUIDANCE") != 1:
            raise SystemExit("installer did not create one compact Codex routing block")
        if any(
            marker in agents_text
            for marker in (
                "BEGIN TOOL SHED GENERATED EVIDENCE GUIDANCE",
                "BEGIN TOOL SHED WORKSPACE IDENTITY GUIDANCE",
                "BEGIN TOOL SHED OWNER CAMPAIGN GUIDANCE",
            )
        ):
            raise SystemExit("installer left expanded Tool Shed policy in Codex AGENTS.md")
        if any(
            fragment not in agents_text
            for fragment in (
                "Activate Tool Shed only",
                "Do not activate Tool Shed merely because",
                "TOOL_SHED_SKILL_MISMATCH",
                "skills/tool-shed/SKILL.md",
            )
        ) or len(agents_text.encode("utf-8")) > 4096:
            raise SystemExit("installer did not create compact conditional Codex routing")
        portable_text = " ".join(
            "\n".join(
                (
                    (ROOT / "skills" / "tool-shed" / "SKILL.md").read_text(encoding="utf-8"),
                    (
                        ROOT / "skills" / "tool-shed" / "references" / "campaign-routes.md"
                    ).read_text(encoding="utf-8"),
                )
            ).split()
        )
        for fragment, label in (
            ("ts:ship <goal>", "ship"),
            ("Do not ask for repeated confirmation for reversible, in-scope steps", "authority"),
            ("Command success alone is not outcome success", "evidence-response"),
            ("at most three credible failure modes", "prospective-failure"),
            ("ts: discuss <topic>", "discussion"),
            ("Direct, Guided, Coordinated, and Deep", "coordination"),
        ):
            if fragment not in portable_text:
                raise SystemExit(f"portable skill is missing the Tool Shed {label} contract")
        identity_contract = (
            "BEGIN TOOL SHED WORKSPACE IDENTITY GUIDANCE",
            "WORKSPACE_MISMATCH",
            "ts: use <project-alias-or-path>",
            "Generic edit and shell tools",
        )
        if any(fragment not in portable_text for fragment in identity_contract[1:]):
            raise SystemExit("portable skill did not retain the workspace identity boundary")
        doctor_contract = (
            "BEGIN TOOL SHED DOCTOR GUIDANCE",
            "ts: doctor",
            "scripts/doctor.py",
            "external or runtime truth",
            "doctor-repair",
        )
        if any(fragment not in portable_text for fragment in doctor_contract[1:]):
            raise SystemExit("portable skill did not retain the workspace doctor guidance")
        work_level_contract = (
            "ts:work1` through `ts:work5",
            "`ts:work` for `work2`",
            "work/tool-shed.yaml",
            "work_model: combined",
            "work_model: split",
            "work_level_config.py",
            "run_default: false",
            "stop on the first failure",
            "automatically deploys production",
        )
        if any(fragment not in portable_text for fragment in work_level_contract):
            raise SystemExit("portable skill did not retain the complete Tool Shed work-level contract")
        direct_contract = (
            "Resolve the named repository and target once",
            "Implement the focused change",
            "Campaign continuity keeps Direct work moving",
            "ts:ask` does not turn a bounded Direct request",
            "wording that merely appears near or discusses `ts:ship`",
        )
        if any(fragment not in portable_text for fragment in direct_contract):
            raise SystemExit("portable skill did not retain the complete Tool Shed Direct-route contract")
        campaign_contract = (
            "work/00-campaigns/",
            "work/01-q&a/ask.txt` as transient intake",
            "Cycle State Capsule",
            "cycles are Program → Milestone Wave → Queue → Campaign → Evidence",
            "Roadmap traceability is `roadmap-derived`",
            "`camp` is shorthand for `campaign`",
            "`que N` means the campaign",
            "`ts: unblock <campaign>`",
            "`ts: reconcile campaigns`",
            "current state token",
            "`--dry-run` never writes",
        )
        if any(fragment not in portable_text for fragment in campaign_contract):
            raise SystemExit("portable skill did not retain the complete owner campaign contract")
        roadmap_contract = (
            "`PRM` means **Plan → Roadmap → Milestone**",
            "`ts: prm <outcome>`",
            "ts: develop roadmap",
            "ts: approve roadmap <token>",
            "ts: approve campaign plan <token>",
            "fresh internal tokens",
            "without inventing a separate start approval",
            "never ingests existing work",
        )
        if any(fragment not in portable_text for fragment in roadmap_contract):
            raise SystemExit("portable skill did not retain the complete Program Roadmap contract")
        autonomy_contract = (
            "Persistent Autonomy And Authority Envelope",
            "ts: autonomy <0-5>",
            "exact numeric `ts: approve <0-5>`",
            "0 Observe",
            "5 Deliver",
            "state tokens internally",
            "impact, blast radius, rollback",
            "fails safely to level 0",
        )
        if any(fragment not in portable_text for fragment in autonomy_contract):
            raise SystemExit("portable skill did not retain the complete autonomy authority-envelope contract")
        kiss_contract = (
            "KISS: Minimum Sufficient Complexity",
            "smallest complete solution",
            "current requirement, concrete risk, or observed failure",
            "does not add a required field, form, checklist, or approval gate",
        )
        if any(fragment not in portable_text for fragment in kiss_contract):
            raise SystemExit("portable skill did not retain the complete KISS contract")
        brainstorm_contract = (
            "Brainstorm And Idea Brief Route",
            "`ts: brainstorm <idea>`",
            "`ts: bs <idea>`",
            "work/ideas/idea-*.md",
            "`ts: prm idea <idea-id-or-path>`",
            "outside campaign reconciliation",
            "Brainstorming is GUI-native",
        )
        if any(fragment not in portable_text for fragment in brainstorm_contract):
            raise SystemExit("portable skill did not retain the complete Brainstorm / Idea Brief contract")
        app_server_contract = (
            "ts: app-server on|off",
            "standalone `--gui`",
            "continues the same action immediately",
            "never replay the App Server step",
            "app-server-events.jsonl",
            "logging failure must never block GUI fallback",
        )
        if any(fragment not in portable_text for fragment in app_server_contract):
            raise SystemExit("portable skill did not retain the passive App Server contract")
        provider_paths = {
            "claude-code": "CLAUDE.md",
            "gemini-cli": "GEMINI.md",
            "github-copilot": ".github/copilot-instructions.md",
            "cursor": ".cursor/rules/tool-shed.mdc",
        }
        generated_work_level_contract = (
            "ts:work1` through `ts:work5",
            "`ts:work` = `work2`",
            "work/tool-shed.yaml",
            "run_default: false",
        )
        generated_direct_contract = (
            "single-repository bug fix or enhancement to Direct",
            "orient to the named target once",
            "campaign continuity does not upgrade Direct",
            "ts:ask` does not turn a bounded Direct request",
        )
        generated_prm_contract = (
            "`PRM` means Plan → Roadmap → Milestone",
            "`ts: prm <outcome>`",
            "PRM is not blanket authority",
        )
        generated_autonomy_contract = (
            "Tool Shed persistent autonomy and authority envelope",
            "ts: autonomy <0-5>",
            "ts: approve <0-5>",
            "internal concurrency controls",
            "impact, blast radius, rollback",
            "fails safely to level 0",
        )
        generated_kiss_contract = (
            "KISS as minimum sufficient complexity",
            "smallest complete solution",
            "current requirement, concrete risk, or observed failure",
            "does not create a required field, checklist, or approval gate",
        )
        generated_brainstorm_contract = (
            "Brainstorm / Idea Brief route",
            "`ts: brainstorm <idea>`",
            "`ts: bs <idea>`",
            "work/ideas/idea-*.md",
            "`ts: prm idea <idea-id-or-path>`",
            "excluded from campaign reconciliation",
            "Brainstorming is GUI-native",
        )
        generated_app_server_contract = (
            "ts: app-server on|off",
            "one-command `--gui`",
            "continue the same action immediately in GUI",
            "never replay the App Server step",
            "Logging failure never blocks fallback",
            "Explicit `--app-server` remains fail-closed",
        )
        for provider_id, relative in provider_paths.items():
            guidance = workspace / relative
            guidance_text = guidance.read_text(encoding="utf-8") if guidance.is_file() else ""
            if (
                "BEGIN TOOL SHED ROUTING GUIDANCE" not in guidance_text
                or any(fragment not in guidance_text for fragment in generated_direct_contract)
                or any(fragment not in guidance_text for fragment in generated_work_level_contract)
                or any(fragment not in guidance_text for fragment in generated_prm_contract)
                or any(fragment not in guidance_text for fragment in generated_autonomy_contract)
                or any(fragment not in guidance_text for fragment in generated_kiss_contract)
                or any(fragment not in guidance_text for fragment in generated_brainstorm_contract)
                or any(fragment not in guidance_text for fragment in generated_app_server_contract)
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
                "idea",
                "Validate Discovery",
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
            "work/ideas/idea-validate-discovery.md",
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
            validate_program_roadmaps()
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
