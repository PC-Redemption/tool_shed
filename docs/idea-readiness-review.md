# Adaptive Pre-PRM Idea Readiness Review Contract

Status: design-frozen
Contract version: 1
Hybrid database schema: 2
Roadmap: adaptive-pre-prm-idea-readiness-review
Gates: G1-FAILURE-CONCURRENCY-CONTRACT, G2-STRUCTURED-RESULT-AUTHORITY

This contract defines the quality boundary between an Idea Brief and PRM. It preserves free-form
brainstorming while making promotion readiness repeatable, revision-bound, and losslessly
transferable into planning.

## Exact Trigger Boundary

Semantic readiness review runs only from:

1. explicit `ts: bs review <idea-id-or-path>`; or
2. `ts: prm idea <idea-id-or-path>` when no current ready result exists.

Idea creation, editing, brainstorming, show/list/status/overview, generated-view rendering,
checkpointing, startup, background work, and elapsed time never run semantic review. Those surfaces
may perform only the bounded metadata comparison needed to report `ABSENT`, `STALE`,
`CURRENT-NOT-READY`, or `CURRENT-READY`.

## Semantic And Operational Outcomes

Semantic verdicts are `READY`, `READY-WITH-PRM-GATES`, and `NOT-READY`. `NOT-READY` is a successful
review whose material blocker prevents safe promotion. It is never used for runtime or storage
failure.

Operational failure is reported separately:

- `REVIEW-ERROR`: the review input, manifest, verdict, contract, token, or Idea concurrency fence
  is invalid;
- `REVIEW-UNAVAILABLE`: the managed Hybrid database, supported schema, or safe operation surface is
  unavailable.

Both operational states fail promotion closed. A generic override cannot reinterpret either state
or `NOT-READY` as ready.

## Structured Authority

Contract version 1 reuses the existing append-only managed `event` primitive. Each
`idea-readiness-review-v1` event contains one canonical JSON result and is bound to the Idea
artifact UUID, visible ID, document revision, body SHA-256, and contract version. Events are
immutable, revision-ledgered, checkpointed, and rebuilt with the Hybrid state. This is sufficient
for ordered history and exact freshness lookup, so version 1 adds no database table or schema.

The Idea Brief remains narrative authority. A review result is structured derived judgment, not a
second editable brief. Generated lifecycle views show only a compact latest-result projection and
explicitly state that rendering performed no semantic review.

## Managed Flow

1. The agent performs evidence-backed semantic judgment under one of the two triggers and writes a
   temporary structured input.
2. `idea_readiness.py prepare` validates the semantic shape and binds it to the current Idea and
   database state.
3. `validate` verifies the exact manifest without mutation.
4. `apply` requires the project binding and exact manifest token, rechecks the database and Idea
   revision/body hash inside the transaction, and appends one result event.
5. `status` performs only a read and metadata comparison. A changed Idea or contract makes the
   prior result stale without rerunning review.
6. `transfer-check` compares the current ready result with the target map or roadmap metadata. The
   review digest, Idea identity/revision/hash, and sorted gate IDs must match exactly. A missing,
   extra, renamed, or dropped gate fails promotion.

## Result Contract

Every result carries:

- review contract version, reviewer, timestamp, and result digest;
- exact Idea artifact ID, visible ID, document revision, and body hash;
- verdict and activated adaptive modules with reasons;
- material promotion blockers and decision owners;
- named PRM gates;
- deferred items, contradictions, complexity findings, and recommended updates; and
- an optional prior result digest when resuming interrupted review dialogue.

`READY` has no blockers or PRM gates. `READY-WITH-PRM-GATES` has no blockers and at least one gate.
`NOT-READY` has at least one blocker. Unknown verdicts and contract versions are rejected.

## Dialogue Resume

Review history is preserved. A later result may name `resumes_result_digest` only when that digest
exists for the same Idea. After the operator changes the brief, the earlier result becomes stale;
the agent uses its remaining blockers and the new brief to avoid repeating settled questions. A
return to ordinary brainstorming ends the triggered dialogue and does not rerun review.

## Portability And Upgrade

The deterministic surface uses Python's standard library and the existing embedded SQLite
contract. Semantic judgment stays provider-neutral and agent-supplied. Schema-2 clients that do not
know readiness events safely ignore them; readiness-aware clients reject unknown review contract
versions or verdicts and must not reuse them for promotion.

Existing Idea Briefs need no backfill. Their first manual review or later PRM promotion attempt
creates the first result. No Git, GitHub, network, daemon, scheduler, or server is required.

## Non-Goals

- Background, scheduled, startup, per-write, or per-brainstorm semantic review.
- An editable Markdown artifact per result.
- Review of non-Idea-Brief artifact classes in contract version 1.
- Bulk historical review backfill.
- A deterministic script pretending to make semantic readiness judgments.
