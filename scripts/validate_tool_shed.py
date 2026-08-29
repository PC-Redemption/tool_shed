from __future__ import annotations

import sys as _runtime_sys

_runtime_sys.dont_write_bytecode = True

import argparse
import concurrent.futures
import hashlib
import json
import os
import py_compile
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROFILES = ("focused", "full", "release")
FOCUSED_TEST_MODULES = frozenset({"test_validation_profiles"})


@dataclass(frozen=True)
class TestResult:
    test_id: str
    returncode: int
    elapsed_seconds: float
    stdout: str
    stderr: str


@dataclass(frozen=True)
class EphemeralCanonicalState:
    database: Path
    views: Path
    created: bool


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


def nonnegative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be at least 0")
    return parsed


def default_jobs() -> int:
    return min(8, max(2, os.cpu_count() or 2))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--profile",
        choices=PROFILES,
        default="full",
        help="focused validator regression, full development validation, or release qualification",
    )
    parser.add_argument(
        "--jobs",
        type=positive_int,
        default=default_jobs(),
        help="maximum concurrent isolated unit-test processes",
    )
    parser.add_argument(
        "--warn-seconds",
        type=positive_float,
        help="warn when the complete selected profile exceeds this wall-clock threshold",
    )
    parser.add_argument(
        "--max-seconds",
        type=positive_float,
        help="fail when the complete selected profile exceeds this wall-clock budget",
    )
    parser.add_argument(
        "--shard-index",
        type=nonnegative_int,
        default=0,
        help="zero-based deterministic unit-test shard index",
    )
    parser.add_argument(
        "--shard-count",
        type=positive_int,
        default=1,
        help="number of deterministic unit-test shards",
    )
    args = parser.parse_args(argv)
    if args.shard_index >= args.shard_count:
        parser.error("--shard-index must be less than --shard-count")
    return args


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


def tree_fingerprint(root: Path) -> dict[str, str]:
    if not root.exists():
        return {}
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def canonical_state_fingerprint() -> dict[str, object]:
    """Capture every authoritative surface validation must leave unchanged."""
    import hybrid_state

    status = subprocess.run(
        ["git", "status", "--porcelain=v1", "-z"],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        check=True,
    ).stdout.hex()
    audit = hybrid_state.audit(ROOT)
    checkpoint = ROOT / "work/state/checkpoints/state-v2.json"
    return {
        "database_revision": audit["current_revision"],
        "database_domain_digest": audit["domain_digest"],
        "checkpoint_sha256": (
            hashlib.sha256(checkpoint.read_bytes()).hexdigest() if checkpoint.is_file() else None
        ),
        "views": tree_fingerprint(ROOT / ".tool-shed/views/work"),
        "git_status": status,
    }


def materialize_ephemeral_canonical_state() -> EphemeralCanonicalState:
    """Rebuild ignored Hybrid runtime state for a clean canonical checkout."""
    import document_store
    import hybrid_state
    import project_identity

    database = hybrid_state.database_path(ROOT)
    views = ROOT / ".tool-shed/views/work"
    if database.is_file():
        return EphemeralCanonicalState(database=database, views=views, created=False)

    checkpoint = ROOT / "work/state/checkpoints/state-v2.json"
    if not checkpoint.is_file():
        return EphemeralCanonicalState(database=database, views=views, created=False)
    payload = json.loads(checkpoint.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 2 or payload.get("kind") != document_store.CHECKPOINT_KIND:
        return EphemeralCanonicalState(database=database, views=views, created=False)
    if views.exists():
        raise SystemExit(
            "canonical checkout has generated views but no live state database; "
            "remove or reconcile the incomplete ignored runtime state before validation"
        )

    database.parent.mkdir(parents=True, exist_ok=True)
    binding = project_identity.binding_token(ROOT, operation="hybrid-state")
    try:
        document_store.rebuild(
            ROOT,
            project_binding=binding,
            checkpoint=checkpoint,
            output=database,
        )
        document_store.render_views(ROOT)
    except BaseException:
        database.unlink(missing_ok=True)
        shutil.rmtree(views, ignore_errors=True)
        raise
    return EphemeralCanonicalState(database=database, views=views, created=True)


def cleanup_ephemeral_canonical_state(state: EphemeralCanonicalState) -> None:
    if not state.created:
        return
    state.database.unlink(missing_ok=True)
    shutil.rmtree(state.views, ignore_errors=True)
    for directory in (state.views.parent, state.database.parent):
        try:
            directory.rmdir()
        except OSError:
            pass


def compile_python() -> None:
    step("compile python")
    paths = sorted((ROOT / "scripts").glob("*.py")) + sorted((ROOT / "tests").glob("*.py"))
    with tempfile.TemporaryDirectory(prefix="tool-shed-compile-") as temporary:
        compile_root = Path(temporary)
        for index, path in enumerate(paths):
            py_compile.compile(
                str(path),
                cfile=str(compile_root / f"{index}.pyc"),
                doraise=True,
            )


def check_shed_manifest() -> None:
    step("shed version manifest")
    run([sys.executable, "scripts/update_shed_manifest.py", "--check"])


def _flatten_tests(suite: unittest.TestSuite) -> list[unittest.TestCase]:
    tests: list[unittest.TestCase] = []
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            tests.extend(_flatten_tests(item))
        else:
            tests.append(item)
    return tests


def discover_test_ids() -> list[str]:
    for path in (ROOT, ROOT / "scripts", ROOT / "tests"):
        value = str(path)
        if value not in sys.path:
            sys.path.insert(0, value)
    suite = unittest.defaultTestLoader.discover(
        str(ROOT / "tests"),
        top_level_dir=str(ROOT / "tests"),
    )
    return sorted(test.id() for test in _flatten_tests(suite))


def select_test_ids(profile: str, discovered: list[str]) -> list[str]:
    if profile != "focused":
        return list(discovered)
    selected = [
        test_id
        for test_id in discovered
        if test_id.split(".", 1)[0] in FOCUSED_TEST_MODULES
    ]
    # A disconnected snapshot may ship its own small smoke module instead of
    # the canonical validator tests. Run that module rather than silently
    # declaring an empty focused profile.
    return selected or list(discovered)


def shard_test_ids(test_ids: list[str], index: int, count: int) -> list[str]:
    return list(test_ids[index::count])


def _run_test_case(test_id: str, state_root: Path) -> TestResult:
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    python_paths = [str(ROOT / "tests"), str(ROOT / "scripts"), str(ROOT)]
    if environment.get("PYTHONPATH"):
        python_paths.append(environment["PYTHONPATH"])
    environment["PYTHONPATH"] = os.pathsep.join(python_paths)
    environment["TOOL_SHED_STATE_ROOT"] = str(
        state_root / hashlib.sha256(test_id.encode("utf-8")).hexdigest()[:16]
    )
    started = time.monotonic()
    result = subprocess.run(
        [sys.executable, "-m", "unittest", "-q", test_id],
        cwd=str(ROOT),
        env=environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return TestResult(
        test_id=test_id,
        returncode=result.returncode,
        elapsed_seconds=time.monotonic() - started,
        stdout=result.stdout,
        stderr=result.stderr,
    )


def execute_test_cases(test_ids: list[str], jobs: int, state_root: Path) -> list[TestResult]:
    results: list[TestResult] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as executor:
        futures = {
            executor.submit(_run_test_case, test_id, state_root): test_id
            for test_id in test_ids
        }
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())
    return sorted(results, key=lambda item: item.test_id)


def run_unit_tests(
    profile: str,
    jobs: int,
    *,
    shard_index: int = 0,
    shard_count: int = 1,
) -> None:
    step(f"unit tests ({profile})")
    discovered = discover_test_ids()
    all_selected = select_test_ids(profile, discovered)
    selected = shard_test_ids(all_selected, shard_index, shard_count)
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="tool-shed-test-state-") as temporary:
        results = execute_test_cases(selected, jobs, Path(temporary))
    failures = [item for item in results if item.returncode]
    if failures:
        for failure in failures:
            print(f"-- {failure.test_id} ({failure.elapsed_seconds:.3f}s) --", file=sys.stderr)
            if failure.stdout:
                print(failure.stdout.rstrip(), file=sys.stderr)
            if failure.stderr:
                print(failure.stderr.rstrip(), file=sys.stderr)
        raise SystemExit(f"{len(failures)} of {len(results)} isolated unit tests failed")
    elapsed = time.monotonic() - started
    shard = "" if shard_count == 1 else f" (shard {shard_index + 1}/{shard_count})"
    print(
        f"{len(results)} of {len(all_selected)} tests passed in {elapsed:.3f}s "
        f"with {jobs} workers{shard}."
    )


def check_provider_adapters() -> None:
    step("provider adapter conformance")
    run([sys.executable, "scripts/check_provider_adapters.py"])


def verify_database_views(document_store_module: object) -> None:
    current = ROOT / ".tool-shed/views/work"
    temp_parent = ROOT / ".tool-shed"
    temp_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="validation-views-", dir=temp_parent) as temporary:
        generated = Path(temporary) / "work"
        document_store_module.render_views(ROOT, output=generated)
        if tree_fingerprint(generated) != tree_fingerprint(current):
            raise SystemExit(
                "database-owned lifecycle views are stale; repair with: "
                "python3 scripts/document_store.py --workspace . render-views"
            )


def regenerate_indexes() -> None:
    import document_store

    if document_store.is_authoritative(ROOT):
        step("verify database-owned lifecycle views")
        verify_database_views(document_store)
    else:
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


def validate_bootstrap_closures(*, require_final: bool = False) -> None:
    step("bootstrap outcome closure")
    manifests = sorted((ROOT / "work" / "evidence").glob("bootstrap-closure-*.json"))
    commands: list[list[str]] = []
    for manifest in manifests:
        arguments = [
            sys.executable,
            "scripts/bootstrap_closure.py",
            "--workspace",
            ".",
            "verify",
            "--manifest",
            manifest.relative_to(ROOT).as_posix(),
        ]
        if require_final:
            arguments.append("--require-final")
        commands.append(arguments)
    if len(commands) == 1:
        run(commands[0])
        return
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(4, len(commands))) as executor:
        futures = [executor.submit(run, arguments) for arguments in commands]
        for future in futures:
            future.result()


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
    for path in (
        ROOT / "__pycache__",
        ROOT / "scripts" / "__pycache__",
        ROOT / "tests" / "__pycache__",
    ):
        shutil.rmtree(path, ignore_errors=True)


def profile_step_names(
    profile: str,
    *,
    canonical: bool,
    primary_shard: bool = True,
) -> tuple[str, ...]:
    if not primary_shard:
        return ("run_unit_tests",)
    names = ["compile_python", "check_shed_manifest", "run_unit_tests"]
    if profile in {"full", "release"}:
        names.append("check_provider_adapters")
        if canonical:
            names.extend(
                (
                    "regenerate_indexes",
                    "check_stale_paths",
                    "review_work_state",
                    "validate_program_roadmaps",
                    "validate_bootstrap_closures",
                )
            )
        if profile == "release":
            names.append("smoke_temp_workspace")
        names.append("sanity_check_markdown")
    return tuple(names)


def enforce_time_budget(profile: str, elapsed: float, maximum: float | None) -> None:
    if maximum is not None and elapsed > maximum:
        raise SystemExit(
            f"tool_shed {profile} validation exceeded its {maximum:g}s budget: "
            f"{elapsed:.3f}s"
        )


def report_time_budget(
    profile: str,
    elapsed: float,
    warning: float | None,
    maximum: float | None,
) -> None:
    if warning is not None and elapsed > warning:
        print(
            f"WARNING: tool_shed {profile} validation exceeded its {warning:g}s "
            f"advisory threshold: {elapsed:.3f}s",
            file=sys.stderr,
        )
    enforce_time_budget(profile, elapsed, maximum)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    started = time.monotonic()
    canonical = is_canonical_checkout()
    ephemeral = (
        materialize_ephemeral_canonical_state()
        if canonical
        else EphemeralCanonicalState(Path(), Path(), False)
    )
    before = source_fingerprint() if not canonical else canonical_state_fingerprint()
    if not canonical and ((ROOT / ".git").exists() or (ROOT / "work").exists()):
        raise SystemExit("disconnected snapshot contains forbidden .git or work content")
    try:
        actions = {
            "compile_python": compile_python,
            "check_shed_manifest": check_shed_manifest,
            "check_provider_adapters": check_provider_adapters,
            "regenerate_indexes": regenerate_indexes,
            "check_stale_paths": check_stale_paths,
            "review_work_state": review_work_state,
            "validate_program_roadmaps": validate_program_roadmaps,
            "validate_bootstrap_closures": lambda: validate_bootstrap_closures(
                require_final=args.profile == "release"
            ),
            "smoke_temp_workspace": smoke_temp_workspace,
            "sanity_check_markdown": sanity_check_markdown,
        }
        for name in profile_step_names(
            args.profile,
            canonical=canonical,
            primary_shard=args.shard_index == 0,
        ):
            phase_started = time.monotonic()
            if name == "run_unit_tests":
                run_unit_tests(
                    args.profile,
                    args.jobs,
                    shard_index=args.shard_index,
                    shard_count=args.shard_count,
                )
            else:
                actions[name]()
            print(
                f"phase {name} completed in {time.monotonic() - phase_started:.3f}s",
                flush=True,
            )
        if not canonical:
            step("canonical workspace state")
            print("Skipped for disconnected snapshot; no snapshot-local work/ was created.")
    finally:
        cleanup_caches()
        after = canonical_state_fingerprint() if canonical else source_fingerprint()
        cleanup_ephemeral_canonical_state(ephemeral)
    if before != after:
        label = "canonical authoritative state" if canonical else "disconnected snapshot"
        raise SystemExit(f"{label} changed during validation")
    elapsed = time.monotonic() - started
    report_time_budget(
        args.profile,
        elapsed,
        args.warn_seconds,
        args.max_seconds,
    )
    print(
        f"tool_shed {args.profile} validation passed in "
        f"{elapsed:.3f}s"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
