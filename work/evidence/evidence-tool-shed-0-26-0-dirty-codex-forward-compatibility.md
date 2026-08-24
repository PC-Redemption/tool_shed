# Tool Shed v0.26.0 dirty Codex forward-compatibility qualification

Status: active
Type: evidence
Updated: 2026-08-24
Next Action: obtain explicit publication authority, publish v0.26.0, upgrade Bactron Core, and record Windows field evidence
Parent: work/00-campaigns/active/052-qualify-release-and-field-verify-dirty-codex-forward-compatibility.md

## Candidate

- Version: `0.26.0` (unpublished candidate)
- Candidate content commits: `0ee2b04` and earlier attributable commits
- Campaign lifecycle commit: `f0e14c2`
- Published predecessor: `v0.25.2`
- Local branch relation after fetch: `main` is eight commits ahead of `origin/main` and zero behind
- Manifest integrity: passed for 136 shipped paths; release provenance remains intentionally null

## Cross-platform qualification

The focused resolver, reporting, qualification-cache, App Server execution, and `next` forwarding
suite passed 73 tests. The complete canonical validator passed 242 tests plus provider-adapter,
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

## Remaining release and field gates

Publication, installed-client synchronization, Bactron snapshot mutation, and Windows GUI field
execution have not been performed by this evidence revision. The Tool Shed `ts: next` route does
not itself grant release or other consequential external-mutation authority. After explicit
publication authority, follow `docs/releasing.md`, verify the live manifest and GitHub Release,
synchronize the host-local Codex skill from the validated canonical source, upgrade Bactron Core
through the published updater using its exact project binding, and collect sanitized Windows
extension-only dirty-qualified planning or verification evidence.
