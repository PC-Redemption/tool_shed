# Tool Shed v0.27.x dirty Codex forward-compatibility qualification

Status: complete
Type: evidence
Updated: 2026-08-25
Next Action: none
Campaign: qualify-release-and-field-verify-dirty-codex-forward-compatibility
Parent: work/00-campaigns/completed/052-qualify-release-and-field-verify-dirty-codex-forward-compatibility.md

## Published release

- Latest stable version: `v0.27.1`
- Release URL: `https://github.com/PC-Redemption/tool_shed/releases/tag/v0.27.1`
- Content commit: `84d2b74780c59372325e9ae5c5d51a1f07fc98dd`
- Provenance commit: `010110197377b44157f518e0a38079d0520aade2`
- Annotated tag object: `9f29a5423e609985768257bda33f109aeb75bd98`
- Manifest release timestamp: `2026-08-25T10:57:11Z`
- GitHub Release publication timestamp: `2026-08-25T11:00:10Z`
- Manifest integrity: passed for all 139 shipped paths; canonical version comparison reports
  `current` with updater protocol 3.

The prior `v0.26.0` tag exposed a Windows-only test-fixture defect: the generated
schema unit test attempted to execute a POSIX shebang fixture directly. The shipped runtime behavior
was not implicated, but both main and tag Windows validation correctly failed. The fixture was made
platform-neutral with a mocked subprocess boundary, all local validation was repeated, and the fix
was published as `v0.26.1`. The already-published `v0.26.0` tag was not moved or reused.

## v0.27.0 Windows field failure and v0.27.1 remediation

The normal Windows `ts: fulltsupgrade` attempt against Bactron Core did not install `v0.27.0`.
Sanitized transaction `05be2fa74898ad3731f61410` reported `TSU-801`: the post-install stale-path
validator saw Markdown in the updater's temporary `.tool_shed.retired-*` directory. Rollback
restored the verified `v0.26.1` snapshot, preserved installed-skill parity and project identity,
removed temporary snapshot directories, and left the target worktree clean.

The `v0.27.1` patch removes the retired snapshot immediately after replacement and before any
post-install workspace scan; its already-verified archive remains the rollback authority. Failure
classification now uses the recorded release-validation or post-install-validation stage as a
safe fallback when validator text is opaque, producing `TSU-501` rather than `TSU-801`. Regression
coverage proves both that retired Markdown cannot contaminate a successful post-install scan and
that a forced opaque post-install failure restores the old snapshot without leaving a retirement
directory. Bactron Core was not modified while preparing this patch.

## Release validation

- The exact `v0.27.1` content and provenance candidates each passed the complete local canonical
  validator with 258 tests.
- The exact content commit passed Ubuntu Python 3.x/3.11 and Windows Python 3.x/3.11 qualification:
  `https://github.com/PC-Redemption/tool_shed/actions/runs/32839290767`.
- The `v0.27.1` tag workflow passed the same four matrices:
  `https://github.com/PC-Redemption/tool_shed/actions/runs/32839913524`.
- The matching main workflow passed the same four matrices:
  `https://github.com/PC-Redemption/tool_shed/actions/runs/32839913526`.
- Automated GitHub Release publication passed:
  `https://github.com/PC-Redemption/tool_shed/actions/runs/32839913485`.
- GitHub reports `v0.27.1` as the Latest, non-draft, non-prerelease release.

## Cross-platform qualification

The focused resolver, reporting, qualification-cache, App Server execution, and `next` forwarding
suite passed. The complete canonical validator passed 258 tests plus provider-adapter,
manifest, generated-index, stale-path, work-state, roadmap, disconnected-snapshot, and template
checks.

Covered behavior includes:

- below-minimum rejection and exact-reviewed fast paths;
- unseen stable and prerelease numeric-core acceptance with no upper cutoff, including `0.150.0`
  and later fixtures;
- same-version binary and policy fingerprint invalidation;
- older `PATH` plus newer extension selection and Windows extension-only discovery;
- generated-schema and sanitized runtime-probe fingerprints;
- named permission-profile negotiation and validated legacy fallback;
- transient retry without cache blacklisting and authoritative unsafe denials;
- truthful cache/status reporting and same-invocation read-only continuation;
- strict separation of dirty-read qualification from exact workspace-write qualification.

## Live Linux qualification

Two available Linux executables were exercised on 2026-08-24:

1. Stable Codex `0.149.0` completed the exact-record smoke with ChatGPT authentication, Sol/high
   planning, Terra/low verification, new-thread isolation, fail-closed approvals, unchanged
   disposable workspace state, no mutation events, and safely reconciled cancellation. Outcome:
   `qualified_with_blockers` because interrupt acknowledgement raced with authoritative
   `interrupted` thread state.
2. The trusted Linux VS Code extension executable `0.149.0-alpha.4.3` was deliberately sent through
   the live dirty-read harness. It negotiated the allowed built-in `:read-only` permission profile,
   completed planning and verification in new threads, preserved the disposable workspace, emitted
   no mutation events, and safely reconciled cancellation. Outcome: `qualified_with_blockers` with
   only the same acknowledgement race.

Raw prompt-free telemetry remains in user-local Codex state and is not copied into this repository.
No prompts, responses, credentials, account identifiers, thread identifiers, or secrets are
recorded here.

## Bactron Core pre-upgrade state

- Target identity: `bactron-core` at `/mnt/w1-dev/bactron-core`
- Snapshot version: verified `v0.25.2`
- Snapshot provenance commit: `9dd212f946fedc4666dfd1c187051bbf0cd20ee8`
- Update binding was resolved for the exact target root.
- The project checkout contains unrelated owner changes. They have not been altered; the released
  transactional updater must preserve them and its rollback archive must cover its declared
  mutation surface.
- The share remains available through the approved read/write, no-execute mount route.

## Bactron Core Windows field verification

The owner ran the normal Windows `ts: fulltsupgrade` route from Bactron Core and then started a
fresh Codex session. Transaction `418f2206963949c1fb39ca37` completed successfully as `TSU-000`:

- the workspace snapshot and installed Codex skill became byte-exact `v0.27.1` matches;
- the release content commit was `84d2b74780c59372325e9ae5c5d51a1f07fc98dd`;
- convergence was committed as `06d2ad3`, and the worktree was clean;
- the verified immediate rollback archive was retained as
  `tool_shed.backup-20260825T111845Z.tar`;
- retention removed three older verified backups, reclaimed 5,004,141 bytes, and retained two
  workspace plus two skill backups.

The fresh-session App Server status selected Codex `0.149.0-alpha.4.3` through the normal Windows
resolver without a PATH preparation step. Its reviewed record was `exact-qualified` with blockers
for read-only planning (`gpt-5.6-sol` / high) and verification (`gpt-5.6-terra` / low). CAMP and
workspace writing remained unqualified, global and session defaults remained off, ordinary
execution remained GUI, and API fallback remained disabled.

A real verification turn then ran through App Server with `gpt-5.6-terra` / low. It reported Tool
Shed `v0.27.1`, the exact release content commit, branch `work/2026-05-26` at 27 commits ahead of
origin, and a clean worktree. Pre/post Git status and manifest hashes were identical, and no files
changed. The owner explicitly accepted this exact-qualified Windows execution as field evidence
because the installed alpha is now a reviewed record; cross-platform tests and live Linux evidence
continue to cover the unseen-version dirty-read path. This acceptance does not extend to CAMP or
any other workspace-writing role.

## Installed Codex skill synchronization

- Canonical source: `/home/jon/docker/tool_shed/skills/tool-shed`
- Installed target: `/home/jon/.codex/skills/tool-shed`
- Pre-synchronization drift was limited to `references/maintenance-routes.md`.
- The canonical source, staged replacement, and installed replacement each passed skill validation.
- Exact recursive comparison between canonical and installed skill is empty.
- Prior installed copy:
  `/home/jon/.codex/skills/tool-shed.backup-20260825T005119Z`
- A fresh Codex task is required to load the synchronized installed skill; this already-running task
  retains its originally loaded instructions.

The `v0.27.1` patch did not change `skills/tool-shed`. After publication, the canonical and
installed directories remained byte-for-byte identical and each passed `quick_validate.py`.
Synchronization was therefore a verified no-op: no installed files were replaced, no backup was
created, and no additional restart requirement was introduced.

## Field gate disposition

Publication, host-local installed-client synchronization, normal Windows Bactron Core upgrade, and
read-only Windows App Server field execution are complete. The owner accepted exact-qualified or
dirty-qualified read-only execution for this field gate when the installed executable is already a
reviewed record. Workspace-write qualification remains separately exact-version gated and was not
granted to `0.149.0-alpha.4.3`.
