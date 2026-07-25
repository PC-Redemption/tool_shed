# Ticket: Field-verify generated evidence safeguards

Status: complete
Type: ticket
Updated: 2026-07-25
Next Action: none
Parent: work/maps/map-tool-shed-evolution.md

## Problem

Canonical Tool Shed now documents `work/evidence/generated/`, installs ignore
rules, and provides `workspace_preflight.py`. These safeguards need field
verification against the real failure recorded in
`work/incidents/incident-codex-desktop-crash-from-tracked-raw-evidence.md`.

The incident is a regression case, not a universal workspace definition. The
important product case is a workspace whose evidence volume, file families,
generated-output conventions, and repository state differ from other Tool Shed
installations, including an existing workspace that already has raw evidence
committed alongside dirty source work and human-readable evidence that must
remain tracked.

## Expected Behavior

Tool Shed should discover the workspace shape and explicit local policy, detect
unsafe layouts using both general safety limits and workspace-relative signals,
explain the durable/generated boundary clearly, select proportionate mitigations,
and prepare a reversible migration without deleting evidence, losing dirty
changes, overwriting repository policy, or mixing cleanup with
product-development commits.

## Acceptance Criteria

- [x] Installer idempotently adds `/tool_shed/`,
  `/tool_shed.backup-*.tar`, and `/work/evidence/generated/` without overwriting
  existing `.gitignore` content.
- [x] Preflight reports tracked and untracked evidence count and total bytes.
- [x] Preflight emits a versioned workspace profile covering repository scale,
  evidence paths, file composition, dirty state, ignore sources, generated-output
  conventions, and explicit local policy.
- [x] Every risk finding identifies whether it came from a hard safety limit,
  workspace-relative growth, repository composition, or declared policy.
- [x] An already unsafe baseline cannot normalize equivalent new risk, and local
  exceptions are explicit, reasoned, and visible in all output.
- [x] Mitigations scale from guidance through strict warnings and prepare-only
  migration to human-gated apply eligibility.
- [x] Preflight flags raw binary/device/log payloads anywhere under tracked
  `work/`, including files already committed before Tool Shed adoption.
- [x] Preflight reports large individual files, repository bundles, dumps, visible
  Tool Shed backups, and oversized tracked diffs.
- [x] General defaults retain conservative safety coverage, while adjustable
  thresholds and classification rules can be declared per workspace without
  silently disabling non-overridable gates.
- [x] Guidance distinguishes `.gitignore` from machine-local
  `.git/info/exclude`.
- [x] Guidance distinguishes removing the current snapshot from rewriting Git
  history.
- [x] A prepare-only migration mode inventories candidates, classifies
  keep/migrate/review, creates SHA-256 manifests, and performs no Git mutation.
- [x] Any apply mode requires an already verified archive and exact candidate
  manifest.
- [x] Migration preserves dirty source/build/script changes byte-for-byte.
- [x] Markdown, small JSON manifests, checksums, concise results, and deliberately
  curated documentation images can remain tracked.
- [x] Tool Shed index and stale-path/work-state checks pass after migration.
- [x] Codex-facing instructions prohibit bulk raw output and recommend blank
  handoffs for exceptionally renderer-heavy campaigns.
- [x] Tests cover Windows paths, spaces, mixed-case extensions, custom evidence
  paths, existing tracked evidence, and repositories with unrelated dirty
  changes.

## Verification

Build a profile matrix with:

- firmware/device captures, using the exact reported incident shape as a compact
  regression profile;
- application logs, traces, screenshots, and test recordings;
- data/science datasets, notebooks, generated tables, and model artifacts;
- media-heavy design or validation output;
- a documentation-first repository where most tracked evidence is legitimate;
- pre-existing policy files, custom generated paths, and unrelated dirty product
  files in each relevant profile.

Prove:

1. profiling is deterministic and non-mutating;
2. preflight identifies profile-appropriate risk and explains its reasoning;
3. mitigation severity changes appropriately across workspace profiles;
4. preparation produces workspace-specific manifests, readable archives, and
   matching hashes;
5. apply changes only approved raw evidence in the current snapshot;
6. retained evidence and dirty product work are unchanged;
7. repeat installer, profiling, and preflight runs are idempotent;
8. repository validation and Tool Shed reconciliation pass.

Reference cleanup outcome:

- repository cleanup commit `b6cbc665`
- Tool Shed closeout commit `bafc2661`
- tracked evidence reduced from 2,065 files to 121
- tracked raw extensions reduced to zero

## Outcome

Implemented workspace-adaptive profiling, explainable risk budgets, optional
reasoned evidence policy, and guarded prepare/apply migration. Firmware,
application, data, media, and documentation profiles pass focused tests. Full
repository validation is recorded in
`work/evidence/evidence-adaptive-generated-evidence-safeguards.md`.
