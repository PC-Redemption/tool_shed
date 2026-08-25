# Tool Shed v0.27.0 dirty Codex forward-compatibility qualification

Status: active
Type: evidence
Updated: 2026-08-24
Next Action: upgrade Bactron Core through its normal Windows workspace process and record sanitized Windows field evidence
Campaign: qualify-release-and-field-verify-dirty-codex-forward-compatibility
Parent: work/00-campaigns/active/052-qualify-release-and-field-verify-dirty-codex-forward-compatibility.md

## Published release

- Latest stable version: `v0.27.0`
- Release URL: `https://github.com/PC-Redemption/tool_shed/releases/tag/v0.27.0`
- Content commit: `99f69eb4948f1838de6da40eabdb0a53c62cf0e3`
- Provenance commit: `d3e1259248bdb13eb377c3f14be28d75a876bcdf`
- Annotated tag object: `05c6a3b714a984212813ada86e70f8bd03efd9df`
- Manifest release timestamp: `2026-08-25T00:43:04Z`
- GitHub Release publication timestamp: `2026-08-25T00:46:12Z`
- Manifest integrity: passed for all 139 shipped paths; canonical version comparison reports
  `current` with updater protocol 3.

The prior `v0.26.0` tag exposed a Windows-only test-fixture defect: the generated
schema unit test attempted to execute a POSIX shebang fixture directly. The shipped runtime behavior
was not implicated, but both main and tag Windows validation correctly failed. The fixture was made
platform-neutral with a mocked subprocess boundary, all local validation was repeated, and the fix
was published as `v0.26.1`. The already-published `v0.26.0` tag was not moved or reused.

## Release validation

- The exact `v0.27.0` content and provenance candidates each passed the complete local canonical
  validator with 256 tests.
- The `v0.27.0` tag workflow passed Ubuntu Python 3.x/3.11 and Windows Python 3.x/3.11:
  `https://github.com/PC-Redemption/tool_shed/actions/runs/32794836239`.
- The matching main workflow passed the same four matrices:
  `https://github.com/PC-Redemption/tool_shed/actions/runs/32794836245`.
- Automated GitHub Release publication passed:
  `https://github.com/PC-Redemption/tool_shed/actions/runs/32794836244`.
- GitHub reports `v0.27.0` as the Latest, non-draft, non-prerelease release.

## Cross-platform qualification

The focused resolver, reporting, qualification-cache, App Server execution, and `next` forwarding
suite passed. The complete canonical validator passed 256 tests plus provider-adapter,
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

## Remaining field gate

Publication and host-local installed-client synchronization are complete. At the owner's request,
this task did not mutate Bactron Core. The remaining completion gate is owner-run through Bactron
Core's normal Windows workspace upgrade process: upgrade the dirty snapshot to the latest verified
published release while preserving unrelated files, verify snapshot integrity, confirm extension-
only Codex discovery without requiring `PATH`, and collect sanitized dirty-qualified read-only
planning or verification evidence. Workspace-write qualification remains separately exact-version
gated.
