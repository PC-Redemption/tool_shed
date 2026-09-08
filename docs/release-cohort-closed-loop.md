# Persistent Work2-to-Work5 Release Cohorts

Tool Shed uses the existing Hybrid outcome tables to preserve which Work2 results are waiting for
production release. This lets a maintainer dogfood unpublished work immediately, batch compatible
changes, and pay the Work5 qualification cost once without losing Idea-to-production traceability.

## State model

One mutable `release-cohort` cycle owns zero or more candidate requirements. Each Work2 requirement
records the exact product commit, the owning outcome cycle, its origin artifact, and a passed Work2
checkpoint verification. `release-candidate-member` relationships connect every registered owner
to the cohort. Registration follows active `outcome-parent` relationships, so a PRM or campaign
entry retains its open Map and Idea ownership. Direct work creates one explicit open outcome rather
than becoming unowned release scope.

The lifecycle is:

```text
working -> frozen -> released-pending-reconciliation -> terminal/reconciled
```

- `working`: candidates may be registered and used in the configured work environment.
- `frozen`: the cohort is bound to the exact clean Work5 content commit; registration stops.
- `released-pending-reconciliation`: production publication evidence is attached to every owner.
  This state does not prevent a later Work2 result from starting a fresh working cohort while an
  intentionally continuing parent outcome remains open.
- `terminal`: every registered owner is terminal, reconciled, and has an accepted terminal verdict.

The live SQLite database remains the operational authority. Normal Hybrid checkpoints preserve the
cohort in tracked state and rebuild it exactly. The freeze mutation may occur after the final
content commit to avoid a commit-SHA self-reference; post-release reconciliation is checkpointed.

`status` derives one complete privacy-safe projection from all registrations before applying its
50-row display bound. Document-backed registrations retain their connected Idea/Map/PRM/Campaign
chain; valid document-free registrations aggregate as **Direct Work2 outcomes** per cohort and
stage. A final **Additional release obligations** row preserves totals when detail is bounded.
Registrations, globally unique commits, owning chains, and display groups are distinct counts.

## Guarded interface

Read current state and retain its project-bound token:

```bash
python3 scripts/release_cohort.py --workspace . --json status
```

After a Work2 product commit, register its nearest open owner. The command expands the full open
parent chain:

```bash
python3 scripts/release_cohort.py --workspace . register \
  --expect <state-token> --project-binding <hybrid-state-binding> \
  --commit <work2-commit> --origin-cycle <cycle-uuid>
```

For direct work without an existing owner, replace `--origin-cycle` with `--accepted-outcome` and
`--summary`. Exact repeated registration does not advance the database revision.

Release identity is project-configurable without modifying the installed Tool Shed snapshot. With
no `release_identity` configuration, the default accepts only stable canonical
`vMAJOR.MINOR.PATCH` tags; numeric segments with leading zeroes are not strict SemVer. A repository
that uses fixed-width dotted numeric tags declares the bounded alternative in its root
`.tool-shed-policy.json`:

```json
{
  "schema_version": 1,
  "release_identity": {
    "schema_version": 1,
    "policy": "fixed-width-dotted-numeric",
    "prefix": "v",
    "segment_widths": [2, 2, 2]
  }
}
```

That example accepts and preserves an exact tag such as `v00.05.00`. Prefixes are limited to 32
safe literal characters and each of the three widths must be from 1 through 12. Arbitrary regular
expressions, code hooks, and extra policy fields are rejected. A policy file used for unrelated
Tool Shed settings may omit `release_identity` and retain the strict default.

`status`, registration, freeze, publication recording, finalization, and base repair all evaluate
the same current project policy. Status reports the active policy, exact selected tag and commit,
selection source, and each visible tag rejected for formatting or reachability. The most recent
usable finalized-cohort tag wins to preserve release continuity. Otherwise, reachable eligible tag
commits are ranked by shortest parent-edge distance through the relevant commit's Git ancestry and
then commit SHA. This is a topology rule, not version-number ordering. Multiple eligible release
identities on the selected commit fail closed.

The active policy projection (including configured policy bytes) and complete Git tag-ref state
participate in the release-cohort state token. A relevant policy edit, tag creation, deletion, or
move therefore makes an earlier mutation token stale. Registration repeats the evaluator against
the exact candidate commit inside the guarded transaction, so a tag reachable only from a newer
`HEAD` cannot become that candidate's base.

If a working cohort recorded the wrong base, create a read-only state-bound plan and then apply
that exact manifest:

```bash
python3 scripts/release_cohort.py --workspace . --json preview-base-repair \
  --tag <existing-tag> [--cohort-id <cycle-uuid>]
python3 scripts/release_cohort.py --workspace . repair-base \
  --manifest <workspace-json-path> --expect <plan-token> \
  --project-binding <hybrid-state-binding>
```

The apply step revalidates the cohort revision, tag commit, policy, strict forward ancestry,
candidate membership, and selected-commit uniqueness, then appends correction evidence without
replacing the original base.
Frozen, released, and terminal cohorts cannot use this repair path.

When a pre-cohort Work2 result was already given a terminal local verdict, registration does not
reopen or rewrite it. The guarded command creates one open direct release extension related by
`release-extension-of`, preserves the original verdict as history, and makes only the missing
production-release obligation a cohort candidate. Repeating that backfill reuses the extension.

At Work5, freeze the clean combined candidate, publish it through the repository's ordinary
release route, and record the verified durable publication reference:

```bash
python3 scripts/release_cohort.py --workspace . freeze \
  --expect <state-token> --project-binding <hybrid-state-binding> \
  --content-commit <sha>
python3 scripts/release_cohort.py --workspace . record-release \
  --expect <fresh-token> --project-binding <hybrid-state-binding> \
  --tag <exact-project-release-tag> --evidence <durable-reference>
```

If exact-SHA CI rejects a frozen content commit, correct the candidate and run `freeze` again with
the new clean `HEAD` plus `--failure-evidence <failed-run-url>`. The guarded retry preserves the
rejected commit and failed-run reference, refuses a silent rebind, and keeps publication blocked
until the replacement content commit passes the ordinary exact-SHA gate.

Reconcile the registered outcome chains from their innermost result to their Idea roots using the
ordinary outcome-transition interface. Finalization fails closed while any registered owner is
open, failed, partial without approval, unreconciled, unpropagated, backed by a nonterminal managed
document, or not recursively closed at its cycle-role closure element. Direct non-document owners
retain the legacy outcome-only gate, and pre-closure schemas retain their compatibility behavior.
When multiple released
cohorts await parent reconciliation, select the exact cohort:

```bash
python3 scripts/release_cohort.py --workspace . finalize \
  --expect <fresh-token> --project-binding <hybrid-state-binding> \
  --authorization <reference> [--cohort-id <cycle-uuid>]
```

The mechanism never treats all open Ideas as release scope. An intentionally excluded candidate
must be resolved before freeze rather than silently stranded.
