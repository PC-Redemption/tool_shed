from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from codex_skill_sync import inspect_codex_skill, load_release_skill_digests
from provider_adapters import provider_config, provider_ids
from repository_policy import POLICY_FILE, format_bytes, inspect_snapshot_ignore, inspect_work_ignore
from work_tree import ensure_work_tree
from workspace_preflight import inspect


IGNORE_ENTRIES = (
    "/tool_shed/",
    "/tool_shed.backup-*.tar",
    "/work/01-q&a/ask.txt",
    "/work/01-q&a/*.legacy-*",
    "/work/q&a/ask.txt",
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
- Start or fork a fresh agent session after exceptionally large qualification campaigns.
{GUIDANCE_END}
"""

ROUTING_GUIDANCE_START = "<!-- BEGIN TOOL SHED ROUTING GUIDANCE -->"
ROUTING_GUIDANCE_END = "<!-- END TOOL SHED ROUTING GUIDANCE -->"
ROUTING_GUIDANCE = f"""{ROUTING_GUIDANCE_START}
## Tool Shed request routing

- Treat a leading `ts:` as authoritative Tool Shed routing for the current request only.
- Locate the workspace-local shed, then read its `skills/tool-shed/SKILL.md` before acting.
- Keep project state in root `work/`; the workspace-local shed contains reusable machinery.
- Use only the provider capabilities actually available in the current product surface.
{ROUTING_GUIDANCE_END}
"""

DISCUSSION_GUIDANCE_START = "<!-- BEGIN TOOL SHED DISCUSSION GUIDANCE -->"
DISCUSSION_GUIDANCE_END = "<!-- END TOOL SHED DISCUSSION GUIDANCE -->"
DISCUSSION_GUIDANCE = f"""{DISCUSSION_GUIDANCE_START}
## Tool Shed discussion route

- Treat `ts: discuss <topic>` as the authoritative Tool Shed discovery route.
- Treat a leading `discussion:` as an informal, read-only campaign-entry signal.
- Explore the outcome, motivation, constraints, assumptions, unknowns, and smallest useful next route.
- Do not create or modify workspace artifacts unless the operator explicitly asks to capture or plan.
{DISCUSSION_GUIDANCE_END}
"""

COORDINATION_GUIDANCE_START = "<!-- BEGIN TOOL SHED COORDINATION GUIDANCE -->"
COORDINATION_GUIDANCE_END = "<!-- END TOOL SHED COORDINATION GUIDANCE -->"
COORDINATION_GUIDANCE = f"""{COORDINATION_GUIDANCE_START}
## Tool Shed minimum sufficient coordination

- Start at the lowest adequate level: Direct, Guided, Coordinated, or Deep.
- Default a clear, reversible, single-repository bug fix or enhancement to Direct, including when it arrives through `ts:ask`.
- For Direct work, orient to the named target once, implement the focused change, and run focused, proportionate verification.
- Do not create artifacts, branches, PRs, releases, deployments, broad qualification, or new worktrees for Direct work unless explicitly requested, mandated by repository policy, or justified by concrete risk, conflicting evidence, or observed failure.
- Escalate only when evidence shows ambiguity, consequence, irreversibility, repeated failure, coordination, or handoff cost.
- Load route-specific instructions and references only when the route needs them.
- Preserve a compact campaign state: outcome, current constraint, decisions, evidence, and next action.
{COORDINATION_GUIDANCE_END}
"""

WORK_LEVEL_GUIDANCE_START = "<!-- BEGIN TOOL SHED WORK LEVEL GUIDANCE -->"
WORK_LEVEL_GUIDANCE_END = "<!-- END TOOL SHED WORK LEVEL GUIDANCE -->"
WORK_LEVEL_GUIDANCE = f"""{WORK_LEVEL_GUIDANCE_START}
## Tool Shed numbered work levels

- Treat `ts:work1` through `ts:work5` as cumulative execution endpoints, independent of Direct, Guided, Coordinated, or Deep coordination.
- `work1`: implement, run the quickest meaningful check, checkpoint only requested changes in a local commit, leave the worktree clean when unrelated prior changes permit, and stop without deployment.
- `work2`: perform `work1`, deploy to the configured work environment, run focused browser and changed-behavior checks, checkpoint, and stop.
- `work3`: review the accumulated coded work and create, read, update, or delete project documentation as needed so it matches the candidate; then fully validate and build, update and verify the work environment when relevant, freeze it locally, and stop.
- `work4`: perform `work3`, then push without intentionally releasing or promoting production.
- `work5`: qualify, push, release or promote production, and verify the production target; this is equivalent to explicit `ts:ship`.
- Aliases are `ts:work` = `work2`, `ts:freeze` = `work3`, `ts:push` = `work4`, and `ts:ship` = `work5`. `ts:check <spot|focused|full|release>` validates only and does not mutate source, Git, or environments.
- Read optional tracked project state from `work/tool-shed.yaml`. `work_model: combined` means work and production share a target, so state that `work2` or `work3` may change the live site. `work_model: split` keeps `work2` and `work3` on development and reserves production promotion for `work5`.
- Reuse existing workspace tooling. The config is not a credential store, deployment framework, or authority grant. If absent, preserve existing behavior and ask one concise target question only when safe routing cannot be derived. Reject invalid schemas or modes rather than guessing.
- Preserve unrelated pre-existing changes. If they prevent a clean checkpoint, report it. If a `work4` push automatically deploys production, stop before pushing unless production release is explicitly authorized.
{WORK_LEVEL_GUIDANCE_END}
"""

SHIP_GUIDANCE_START = "<!-- BEGIN TOOL SHED SHIP GUIDANCE -->"
SHIP_GUIDANCE_END = "<!-- END TOOL SHED SHIP GUIDANCE -->"
SHIP_GUIDANCE = f"""{SHIP_GUIDANCE_START}
## Tool Shed ship route

- Treat `ts:ship <goal>` and `ts: ship <goal>` as authorization to plan, implement, validate, build, deploy, and verify the workspace goal end-to-end.
- Treat `ts: fulltsupgrade` and `ts:fulltsupgrade` as authorization to upgrade the current existing Tool Shed installation end-to-end from the latest verified published GitHub release, including guarded backup and update, provider convergence, full validation, installed Codex skill synchronization and exact verification when applicable, and rollback on failure.
- The full-upgrade route does not authorize publishing a release, rewriting history, overwriting a modified or unmanaged installation, deleting unknown recovery material, or changing other workspaces or fleet targets.
- Treat lifecycle stages as applicable only when the requested outcome includes them, repository policy mandates them, or concrete risk or observed failure justifies them. Wording that merely mentions or discusses `ts:ship` is not an end-to-end delivery request.
- State the concrete reason before expanding focused verification into broad qualification, deployment, or external publication.
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
- Preserve the selected coordination level while continuing; campaign continuity does not upgrade Direct work or make inapplicable lifecycle stages apply.
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
- The canonical inbox is `work/01-q&a/ask.txt`; inspect `work/q&a/ask.txt` only as a pre-migration legacy fallback.
- Ignore blank lines and lines beginning with `#` in both files.
- Use canonical content when only it is actionable. If only fallback content is actionable, process it and clearly report its noncanonical location.
- If both files are actionable, do not merge or act on either; report the conflict and ask which request to use.
- Apply normal scope, authorization, safety, and routing rules to the selected request.
- Dispatch the selected request under its natural coordination level; `ts:ask` does not turn a bounded Direct request into a heavyweight campaign.
- Never move, clear, rewrite, or delete either inbox without explicit operator authorization.
- Summarize what was read and what was done in the final response.
{ASK_GUIDANCE_END}
"""

CAMPAIGN_QUEUE_GUIDANCE_START = "<!-- BEGIN TOOL SHED OWNER CAMPAIGN GUIDANCE -->"
CAMPAIGN_QUEUE_GUIDANCE_END = "<!-- END TOOL SHED OWNER CAMPAIGN GUIDANCE -->"
CAMPAIGN_QUEUE_GUIDANCE = f"""{CAMPAIGN_QUEUE_GUIDANCE_START}
## Tool Shed owner campaign queue

- Keep durable owner-facing campaign state under first-sorted `work/00-campaigns/`; keep `work/01-q&a/ask.txt` as transient intake.
- Treat `ts: queue` and `ts: status` as requests to read the active owner capsule and validate lifecycle state.
- Treat `ts: next` as a request to select the first ready campaign, then execute only that campaign under its natural coordination and requested work level.
- In owner-queue requests, interpret `camp` as `campaign`. Interpret `que N` as the mutable 1-based queue position, resolved from a fresh status read; a heading such as `1. (004) Title` distinguishes queue position 1 from stable campaign number 004, and every card separately displays its full stable `Campaign ID`. Name lifecycle requests `<number>-<campaign-id>.md`, preserve matching numeric ID prefixes, use guarded `backfill-numbers` to rename legacy slug-only histories and refresh projections, and accept an exact zero-padded number or full Campaign ID for lifecycle commands. Never guess a missing or out-of-range position.
- Treat `ts: add`, `ts: unblock`, `ts: defer`, `ts: abandon`, and campaign completion as exact lifecycle mutations. `ts: unblock` returns blocked work to queued state, clears its decision, and does not start it. Read the current state token immediately before writing and reject stale state.
- Treat `ts: reconcile campaigns` as authorization for `reconcile_campaign_queue.py` to automatically create or refresh exactly one Dangler Resolution campaign as the first queued work while preserving any working campaign. Report whole-work coverage, exclusions, and queue drift. Use `--dry-run` for read-only inspection. Apply all other operations only from an exact approved manifest with the reported whole-work state token; never apply proposed execution order or ambiguous lifecycle decisions implicitly.
- Never silently reorder a campaign when priority or direction is ambiguous. Preserve blocked work as active; require a reason and reactivation condition for deferral and a disposition for abandonment.
- Complete a campaign only after its explicit completion gate and applicable verification pass. Then update active and completed queues as one recoverable operation and promote the next ready campaign.
- Treat `work/focus-areas.md` as an optional project-specific catalog. Onboarding creates it as proposed; owner approval is required before it governs campaign assignments or queue cards. Derive areas from project evidence rather than a built-in taxonomy.
- Treat `ts: build focus areas` as a two-stage route: inspect existing source, documentation, tests, integrations, runtime and delivery boundaries, and durable work; then present an exact evidence-backed catalog and active-campaign assignment proposal without writing. A build or refresh request is not approval.
- After explicit owner approval of the exact proposal, write the approved catalog, apply all active-campaign assignments, refresh indexes, and validate campaign, stale-path, and work state. Preserve stable IDs and accepted boundaries unless cited project evidence justifies a named change; never silently approve a taxonomy or leave approved active work unmapped.
- When an approved catalog exists, require known primary focus-area IDs for ordinary active campaigns, keep supporting IDs optional, and use the shared dependency/decision readiness states for status, selection, rendering, and reconciliation.
- Preview legacy outcome focus phrases without writing; apply only fully matched focus assignments through an exact approved reconciliation manifest.
- The workspace installer migrates legacy `work/q&a/` and root `q&a/` contents into `work/01-q&a/` without overwriting collisions, then removes the old folders. Campaign conversion remains preview-only until an exact manifest is explicitly approved.
{CAMPAIGN_QUEUE_GUIDANCE_END}
"""

ROADMAP_GUIDANCE_START = "<!-- BEGIN TOOL SHED PROGRAM ROADMAP GUIDANCE -->"
ROADMAP_GUIDANCE_END = "<!-- END TOOL SHED PROGRAM ROADMAP GUIDANCE -->"
ROADMAP_GUIDANCE = f"""{ROADMAP_GUIDANCE_START}
## Tool Shed Program Roadmaps

- Treat `ts: develop roadmap`, `ts: propose roadmap`, `ts: approve roadmap <token>`, `ts: derive campaigns for milestone <id>`, `ts: approve campaign plan <token>`, `ts: roadmap status`, `ts: review roadmap`, and `ts: overview` as the opt-in Program Roadmap lifecycle between project maps and campaigns.
- Keep development, review, campaign derivation, status, and overview read-only. A roadmap proposal may create only a proposed `work/roadmaps/` revision; it cannot approve intent or create campaigns.
- Require an approved initial project map for greenfield adoption. Existing or upgraded projects may use an active map and must preserve and classify all owner-authored work as completed, active, remaining, superseded, excluded, or uncertain from evidence.
- Roadmap approval and campaign-plan approval are separate exact-token mutations. Reject stale source, roadmap, or campaign state; preserve superseded approved revisions.
- Materialized campaigns must reference their Roadmap, Roadmap Revision, Milestone, and Unlocks Gate. Creating them does not authorize starting, deploying, releasing, or promoting them.
- Installation and upgrade create only the empty compatible topology. They never ingest work, propose or approve a roadmap, or materialize campaigns implicitly.
{ROADMAP_GUIDANCE_END}
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


def ensure_provider_guidance(repository: Path, provider_id: str) -> tuple[Path, bool]:
    config = provider_config(provider_id)
    path = repository / str(config["instruction_path"])
    current = path
    while current != repository:
        if current.is_symlink():
            raise ValueError(f"provider instruction path must not traverse a symlink: {current}")
        current = current.parent
    try:
        path.resolve(strict=False).relative_to(repository.resolve())
    except ValueError as error:
        raise ValueError(f"provider instruction path escapes the repository: {path}") from error
    if path.exists() and not path.is_file():
        raise ValueError(f"provider instruction target must be a regular file: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    if config["instruction_format"] == "mdc" and not existing:
        existing = "---\ndescription: Tool Shed workspace coordination\nalwaysApply: true\n---\n"
    updated = existing
    for start, end, guidance in (
        (ROUTING_GUIDANCE_START, ROUTING_GUIDANCE_END, ROUTING_GUIDANCE),
        (DISCUSSION_GUIDANCE_START, DISCUSSION_GUIDANCE_END, DISCUSSION_GUIDANCE),
        (COORDINATION_GUIDANCE_START, COORDINATION_GUIDANCE_END, COORDINATION_GUIDANCE),
        (GUIDANCE_START, GUIDANCE_END, GUIDANCE),
    ):
        updated, _ = replace_managed_block(updated, start, end, guidance)
    updated, _ = replace_managed_block(
        updated,
        WORK_LEVEL_GUIDANCE_START,
        WORK_LEVEL_GUIDANCE_END,
        WORK_LEVEL_GUIDANCE,
    )
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
    updated, _ = replace_managed_block(
        updated,
        CAMPAIGN_QUEUE_GUIDANCE_START,
        CAMPAIGN_QUEUE_GUIDANCE_END,
        CAMPAIGN_QUEUE_GUIDANCE,
    )
    updated, _ = replace_managed_block(
        updated,
        ROADMAP_GUIDANCE_START,
        ROADMAP_GUIDANCE_END,
        ROADMAP_GUIDANCE,
    )
    if updated == existing:
        return path, False
    path.write_text(updated, encoding="utf-8", newline="\n")
    return path, True


def ensure_ask_inbox(workspace: Path) -> bool:
    path = workspace / "work" / "01-q&a" / "ask.txt"
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# Put a question or direction below, then send ts:ask to your AI agent.\n",
        encoding="utf-8",
    )
    return True


def _collision_path(target: Path, label: str, content: bytes, claimed: dict[Path, bytes]) -> Path:
    if target not in claimed and not target.exists():
        return target
    existing = claimed.get(target)
    if existing is None and target.is_file():
        existing = target.read_bytes()
    if existing == content:
        return target
    candidate = target.with_name(f"{target.stem}.{label}{target.suffix}")
    counter = 2
    while candidate in claimed or candidate.exists():
        existing = claimed.get(candidate)
        if existing is None and candidate.is_file():
            existing = candidate.read_bytes()
        if existing == content:
            return candidate
        candidate = target.with_name(f"{target.stem}.{label}-{counter}{target.suffix}")
        counter += 1
    return candidate


def migrate_legacy_q_and_a(workspace: Path) -> list[tuple[Path, Path]]:
    target_root = workspace / "work" / "01-q&a"
    sources = (
        (workspace / "work" / "q&a", "legacy-work-q-and-a"),
        (workspace / "q&a", "legacy-root-q-and-a"),
    )
    mappings: list[tuple[Path, Path]] = []
    claimed: dict[Path, bytes] = {}
    for source_root, label in sources:
        if not source_root.exists():
            continue
        if source_root.is_symlink() or not source_root.is_dir():
            raise ValueError(f"legacy Q&A source must be a real directory: {source_root}")
        for path in sorted(source_root.rglob("*")):
            if path.is_symlink():
                raise ValueError(f"legacy Q&A migration refuses symlink: {path}")
            if path.is_dir():
                continue
            if not path.is_file():
                raise ValueError(f"legacy Q&A migration found unsupported entry: {path}")
            content = path.read_bytes()
            destination = _collision_path(target_root / path.relative_to(source_root), label, content, claimed)
            claimed[destination] = content
            mappings.append((path, destination))

    created: list[Path] = []
    try:
        for source, destination in mappings:
            content = source.read_bytes()
            destination.parent.mkdir(parents=True, exist_ok=True)
            if not destination.exists():
                shutil.copy2(source, destination)
                created.append(destination)
            if not destination.is_file() or destination.read_bytes() != content:
                raise ValueError(f"legacy Q&A copy verification failed: {source} -> {destination}")
    except Exception:
        for path in reversed(created):
            path.unlink(missing_ok=True)
        raise

    for source, _ in mappings:
        source.unlink()
    for source_root, _ in sources:
        if source_root.is_dir():
            for directory in sorted(
                (path for path in source_root.rglob("*") if path.is_dir()),
                key=lambda path: len(path.parts),
                reverse=True,
            ):
                directory.rmdir()
            source_root.rmdir()
    return mappings


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
    choices = (*provider_ids(), "all")
    parser.add_argument(
        "--provider",
        action="append",
        choices=choices,
        help=(
            "Install native guidance for a provider. Repeat for multiple providers or use 'all'. "
            "Defaults to codex for backward compatibility."
        ),
    )
    parser.add_argument(
        "--guidance-only",
        action="store_true",
        help="Refresh provider instruction blocks without changing work/, indexes, inboxes, or .gitignore.",
    )
    return parser.parse_args()


def selected_providers(values: list[str] | None) -> tuple[str, ...]:
    available = provider_ids()
    if not values:
        return ("codex",)
    if "all" in values:
        return available
    return tuple(dict.fromkeys(values))


def report_codex_skill_state() -> None:
    shed = Path(__file__).resolve().parents[1]
    source = shed / "skills" / "tool-shed"
    known_releases = load_release_skill_digests(
        shed / "adapters" / "codex-skill-releases.json"
    )
    state = inspect_codex_skill(source, known_releases)
    print(f"Codex skill: {state['state']} at {state['path']}.")
    if state["state"] in {"missing", "stale-released"}:
        print(
            "Safe Codex skill synchronization: "
            f"{state['sync_command']}."
        )
    elif state["state"] not in {"current"}:
        print("Codex skill synchronization refused: modified, unmanaged, or unsafe installation.")
    print("Codex skill changes require a fresh Codex session before they take effect.")


def main() -> int:
    args = parse_args()
    root = Path(args.workspace).expanduser().resolve()
    providers = selected_providers(args.provider)
    if args.guidance_only:
        repository = inspect_work_ignore(root).repository
        if repository is None or repository != root:
            print("Guidance-only installation requires the exact Git repository root.", file=sys.stderr)
            return 1
        try:
            for provider_id in providers:
                guidance_path, changed = ensure_provider_guidance(repository, provider_id)
                state = "updated" if changed else "current"
                print(f"Provider guidance ({provider_id}): {state} at {guidance_path}.")
        except ValueError as error:
            print(f"Provider guidance failed: {error}", file=sys.stderr)
            return 1
        if "codex" in providers:
            report_codex_skill_state()
        return 0
    ensure_work_tree(root)
    try:
        migrated_inboxes = migrate_legacy_q_and_a(root)
    except ValueError as error:
        print(f"Q&A inbox migration failed: {error}", file=sys.stderr)
        return 1
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
        try:
            for provider_id in providers:
                guidance_path, changed = ensure_provider_guidance(repository, provider_id)
                if changed:
                    print(
                        f"Provider guidance ({provider_id}): updated Tool Shed rules in {guidance_path}."
                    )
        except ValueError as error:
            print(f"Provider guidance failed: {error}", file=sys.stderr)
            return 1
        if "codex" in providers:
            report_codex_skill_state()

    index_script = Path(__file__).resolve().with_name("update_work_index.py")
    if index_script.exists():
        subprocess.run(
            [sys.executable, str(index_script), "--workspace", str(root), "--no-preflight"],
            check=True,
            stdout=subprocess.DEVNULL,
        )

    print(f"Initialized work tree under {root / 'work'}")
    canonical_ask = root / "work" / "01-q&a" / "ask.txt"
    if ask_created:
        print(f"Initialized Tool Shed Q&A inbox at {canonical_ask}")
    else:
        print(f"Preserved existing Tool Shed Q&A inbox at {canonical_ask}")
    if migrated_inboxes:
        print(
            f"Migrated {len(migrated_inboxes)} legacy Q&A file(s) into {canonical_ask.parent} "
            "and removed the old Q&A folders after byte verification."
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
