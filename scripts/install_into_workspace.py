from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from repository_policy import POLICY_FILE, format_bytes, inspect_snapshot_ignore, inspect_work_ignore
from work_tree import ensure_work_tree
from workspace_preflight import inspect


IGNORE_ENTRIES = (
    "/tool_shed/",
    "/tool_shed.backup-*.tar",
    "/q&a/ask.txt",
    "/work/evidence/generated/",
)

GUIDANCE_START = "<!-- BEGIN TOOL SHED GENERATED EVIDENCE GUIDANCE -->"
GUIDANCE_END = "<!-- END TOOL SHED GENERATED EVIDENCE GUIDANCE -->"
GUIDANCE = f"""{GUIDANCE_START}
## Tool Shed generated evidence

- Never request or render per-file Git diffs for raw generated evidence.
- Use `git status --untracked-files=no` for routine source review when generated evidence is present.
- Summarize evidence through small versioned manifests instead of returning raw output.
- Avoid passing hundreds of literal paths to `git diff --no-index`.
- Before long automated campaigns, verify generated-output directories are ignored.
- Run Tool Shed workspace preflight and use its profile-specific mitigation before bulk output.
- Never run migration apply without an exact approved manifest and verified archive.
- Commit or checkpoint meaningful source and planning changes before large test runs.
- Start or fork a fresh Codex task after exceptionally large qualification campaigns.
{GUIDANCE_END}
"""

ASK_GUIDANCE_START = "<!-- BEGIN TOOL SHED Q&A GUIDANCE -->"
ASK_GUIDANCE_END = "<!-- END TOOL SHED Q&A GUIDANCE -->"
ASK_GUIDANCE = f"""{ASK_GUIDANCE_START}
## Tool Shed Q&A inbox

- Treat `ts:ask` and `ts: ask` as requests to run `python3 <shed>/scripts/read_ask_inbox.py --workspace <workspace> --json`.
- The canonical inbox is `q&a/ask.txt`; also inspect `work/q&a/ask.txt` as a legacy or misplaced fallback.
- Ignore blank lines and lines beginning with `#` in both files.
- Use canonical content when only it is actionable. If only fallback content is actionable, process it and clearly report its noncanonical location.
- If both files are actionable, do not merge or act on either; report the conflict and ask which request to use.
- Apply normal scope, authorization, safety, and routing rules to the selected request.
- Never move, clear, rewrite, or delete either inbox without explicit operator authorization.
- Summarize what was read and what was done in the final response.
{ASK_GUIDANCE_END}
"""


def ensure_root_gitignore(repository: Path) -> list[str]:
    path = repository / ".gitignore"
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    existing_lines = {line.strip() for line in existing.splitlines()}
    missing = [entry for entry in IGNORE_ENTRIES if entry not in existing_lines]
    if not missing:
        return []
    prefix = "" if not existing or existing.endswith("\n") else "\n"
    block = prefix + "\n# Tool Shed workspace-local and generated outputs\n" + "\n".join(missing) + "\n"
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(block)
    return missing


def replace_managed_block(existing: str, start: str, end: str, replacement: str) -> tuple[str, bool]:
    start_index = existing.find(start)
    end_index = existing.find(end, start_index + len(start)) if start_index >= 0 else -1
    if start_index >= 0 and end_index >= 0:
        end_index += len(end)
        updated = existing[:start_index] + replacement.rstrip("\n") + existing[end_index:]
        return updated, updated != existing
    if start_index >= 0:
        updated = existing[:start_index] + replacement
        return updated, updated != existing
    prefix = "" if not existing or existing.endswith("\n") else "\n"
    updated = existing + prefix + ("\n" if existing else "") + replacement
    return updated, True


def ensure_codex_guidance(repository: Path) -> bool:
    path = repository / "AGENTS.md"
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    updated = existing
    if GUIDANCE_START not in existing:
        prefix = "" if not updated or updated.endswith("\n") else "\n"
        updated += prefix + ("\n" if updated else "") + GUIDANCE
    updated, _ = replace_managed_block(
        updated,
        ASK_GUIDANCE_START,
        ASK_GUIDANCE_END,
        ASK_GUIDANCE,
    )
    if updated == existing:
        return False
    path.write_text(updated, encoding="utf-8", newline="\n")
    return True


def ensure_ask_inbox(workspace: Path) -> bool:
    path = workspace / "q&a" / "ask.txt"
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# Put a question or direction below, then type ts:ask in Codex.\n",
        encoding="utf-8",
    )
    return True


def existing_generated_outputs(repository: Path) -> tuple[int, int]:
    paths = [
        path
        for path in (repository / "work" / "evidence" / "generated").rglob("*")
        if path.is_file()
    ] if (repository / "work" / "evidence" / "generated").exists() else []
    paths.extend(path for path in repository.glob("tool_shed.backup-*.tar") if path.is_file())
    return len(paths), sum(path.stat().st_size for path in paths)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create the project work artifact tree.")
    parser.add_argument(
        "workspace",
        nargs="?",
        default=".",
        help="Project workspace root. Defaults to current directory.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.workspace).expanduser().resolve()
    ensure_work_tree(root)
    ask_created = ensure_ask_inbox(root)

    repository = inspect_work_ignore(root).repository
    if repository is not None:
        generated_count, generated_bytes = existing_generated_outputs(repository)
        added = ensure_root_gitignore(repository)
        if added:
            print("Repository policy: appended missing Tool Shed entries to root .gitignore: " + ", ".join(added))
            if generated_count:
                print(
                    "Adoption warning: the new generated-output rules cover "
                    f"{generated_count} existing file(s), {format_bytes(generated_bytes)}. "
                    "Files were not moved, deleted, or rewritten; review the rules and retain "
                    "small versioned summaries or manifests outside generated/."
                )
        if ensure_codex_guidance(repository):
            print(f"Codex guidance: updated Tool Shed rules in {repository / 'AGENTS.md'}.")

    index_script = Path(__file__).resolve().with_name("update_work_index.py")
    if index_script.exists():
        subprocess.run(
            [sys.executable, str(index_script), "--workspace", str(root), "--no-preflight"],
            check=True,
            stdout=subprocess.DEVNULL,
        )

    print(f"Initialized work tree under {root / 'work'}")
    if ask_created:
        print(f"Initialized Tool Shed Q&A inbox at {root / 'q&a' / 'ask.txt'}")
    else:
        print(f"Preserved existing Tool Shed Q&A inbox at {root / 'q&a' / 'ask.txt'}")
    fallback_ask = root / "work" / "q&a" / "ask.txt"
    if fallback_ask.is_file():
        print(
            f"Q&A inbox warning: found noncanonical inbox at {fallback_ask}. "
            f"The canonical inbox is {root / 'q&a' / 'ask.txt'}. "
            "Neither file was moved, cleared, rewritten, or deleted."
        )
    state = inspect_work_ignore(root)
    failed = False
    if state.match is None:
        if state.repository is not None:
            print("Repository policy: root work/ is trackable (Tool Shed default).")
    else:
        match = state.match
        print(
            f"Repository policy: root work/ is ignored by {match.source}:{match.line}: {match.rule!r} "
            f"(matched {match.path})."
        )
        print(
            f"Trackability preview: {state.file_count} file(s), {format_bytes(state.total_bytes)}, "
            "currently ignored under work/."
        )
        if state.exception_reason:
            print(f"Documented exception in {POLICY_FILE}: {state.exception_reason}")
        else:
            if state.exception_error:
                print(f"Invalid exception: {state.exception_error}")
            print(
                "Remove only the root /work/ ignore rule shown above, then rerun this command. "
                f"If ignoring work/ is intentional, document it in repository-root {POLICY_FILE}. "
                "No work/ files were deleted, replaced, relocated, or rewritten by this policy check."
            )
            failed = True

    repository, snapshot_match = inspect_snapshot_ignore(root)
    if repository is not None and (repository / "tool_shed").exists():
        if snapshot_match:
            print(
                f"Repository policy: /tool_shed/ is ignored by {snapshot_match.source}:"
                f"{snapshot_match.line}: {snapshot_match.rule!r}."
            )
        else:
            print("Repository policy: add /tool_shed/ to the repository-root .gitignore.")
            failed = True
    _, findings, _, _ = inspect(root)
    if findings:
        print("Workspace preflight warnings:")
        for finding in findings:
            print(f"- [{finding.code}] {finding.message}")
    else:
        print("Workspace preflight passed.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
