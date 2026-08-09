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
    "/work/q&a/ask.txt",
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

SHIP_GUIDANCE_START = "<!-- BEGIN TOOL SHED SHIP GUIDANCE -->"
SHIP_GUIDANCE_END = "<!-- END TOOL SHED SHIP GUIDANCE -->"
SHIP_GUIDANCE = f"""{SHIP_GUIDANCE_START}
## Tool Shed ship route

- Treat `ts:ship <goal>` and `ts: ship <goal>` as authorization to plan, implement, validate, build, deploy, and verify the workspace goal end-to-end.
- Continue through every applicable lifecycle stage; do not stop merely because planning, coding, tests, or a build succeeded.
- Use the workspace's own tooling, environments, runbooks, and protected-environment controls.
- Keep changes scoped to the goal and preserve unrelated user work.
- Do not ask for repeated confirmation for reversible, in-scope steps already clearly authorized by the operator. One request may authorize multiple named operations. Ask again only when an action materially expands scope, targets a protected environment, is destructive or irreversible, uses an unknown deployment target, publishes externally, or otherwise requires new authority.
- Before an already-authorized consequential stage, identify at most three credible ways the plan could fail and add proportionate prevention, detection, verification, or rollback. Skip this check for routine reversible work.
- Verify the delivered result in its target environment before claiming completion.
- The route does not waive safety rules, required approvals, credential boundaries, or authorization limits.
- If a stage is inapplicable, explain why. If deployment is blocked, complete every safe preceding stage and report the exact blocker.
{SHIP_GUIDANCE_END}
"""

EXECUTION_GUIDANCE_START = "<!-- BEGIN TOOL SHED EVIDENCE RESPONSE GUIDANCE -->"
EXECUTION_GUIDANCE_END = "<!-- END TOOL SHED EVIDENCE RESPONSE GUIDANCE -->"
EXECUTION_GUIDANCE = f"""{EXECUTION_GUIDANCE_START}
## Tool Shed evidence-response loop

- Use the loop for nontrivial planning, implementation, debugging, research, validation, and deployment.
- Keep the desired outcome and the current condition limiting progress visible.
- After each material action or new observation, compare the actual state with the expected state. If they differ, update assumptions, the plan, and the next action before continuing; command success alone is not outcome success.
- Preserve the operator's scope, authority, and safety boundaries while adapting. A newly discovered action does not authorize itself.
- Skip explicit loop ceremony for simple answers and known single-step reversible work; execute and verify them directly.
{EXECUTION_GUIDANCE_END}
"""

CAMPAIGN_GUIDANCE_START = "<!-- BEGIN TOOL SHED CAMPAIGN GUIDANCE -->"
CAMPAIGN_GUIDANCE_END = "<!-- END TOOL SHED CAMPAIGN GUIDANCE -->"
CAMPAIGN_GUIDANCE = f"""{CAMPAIGN_GUIDANCE_START}
## Tool Shed campaign continuity

- Treat the requested outcome in the current chat as the campaign. Plans, checklists, workpackages, tests, builds, and deployments are possible stages or artifacts, not the campaign itself.
- Keep working while the next action is reversible, in scope, and already authorized. A progress summary, artifact update, phase boundary, or useful review point is not an approval gate.
- Do not stop because the operator might want to inspect completed work. Pause only for requested review, a material unresolved decision, contradictory evidence, new authority, or a protected, destructive, irreversible, or not-yet-authorized external action.
- If review is required, identify the exact file or result and relevant section, state the exact decision or approval needed, and say what happens after the response. Never use a vague "review this" or "let me know."
- End every final response for a Tool Shed campaign with exactly one verdict: `Campaign status: COMPLETE`, `Campaign status: CONTINUE`, or `Campaign status: BLOCKED`.
- `COMPLETE` means the whole requested outcome and applicable verification are finished, not merely an artifact or intermediate stage.
- `CONTINUE` means work remains but the current turn must end without needing operator input; name the next concrete action. Do not stop if that action can safely be performed now.
- `BLOCKED` means progress requires a named decision, dependency, permission, credential, external-state change, or required review; state the blocker and precise operator action.
{CAMPAIGN_GUIDANCE_END}
"""

ASK_GUIDANCE_START = "<!-- BEGIN TOOL SHED Q&A GUIDANCE -->"
ASK_GUIDANCE_END = "<!-- END TOOL SHED Q&A GUIDANCE -->"
ASK_GUIDANCE = f"""{ASK_GUIDANCE_START}
## Tool Shed Q&A inbox

- Treat `ts:ask` and `ts: ask` as requests to run `python3 <shed>/scripts/read_ask_inbox.py --workspace <workspace> --json`.
- The canonical inbox is `work/q&a/ask.txt`; also inspect `q&a/ask.txt` as a legacy or misplaced fallback.
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
        SHIP_GUIDANCE_START,
        SHIP_GUIDANCE_END,
        SHIP_GUIDANCE,
    )
    updated, _ = replace_managed_block(
        updated,
        EXECUTION_GUIDANCE_START,
        EXECUTION_GUIDANCE_END,
        EXECUTION_GUIDANCE,
    )
    updated, _ = replace_managed_block(
        updated,
        CAMPAIGN_GUIDANCE_START,
        CAMPAIGN_GUIDANCE_END,
        CAMPAIGN_GUIDANCE,
    )
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
    path = workspace / "work" / "q&a" / "ask.txt"
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# Put a question or direction below, then type ts:ask in Codex.\n",
        encoding="utf-8",
    )
    return True


def has_actionable_content(path: Path) -> bool:
    if not path.is_file():
        return False
    return any(
        line.strip() and not line.lstrip().startswith("#")
        for line in path.read_text(encoding="utf-8").splitlines()
    )


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
    canonical_ask = root / "work" / "q&a" / "ask.txt"
    if ask_created:
        print(f"Initialized Tool Shed Q&A inbox at {canonical_ask}")
    else:
        print(f"Preserved existing Tool Shed Q&A inbox at {canonical_ask}")
    fallback_ask = root / "q&a" / "ask.txt"
    if has_actionable_content(fallback_ask) and not has_actionable_content(canonical_ask):
        print(
            f"Q&A inbox warning: actionable content exists only in the noncanonical legacy "
            f"inbox at {fallback_ask}. The canonical inbox is {canonical_ask}. "
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
