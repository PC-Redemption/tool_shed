# ADR: Use schema-2 SQLite authority for generated work collateral

Status: accepted
Type: adr
Updated: 2026-08-28
Next Action: implement the representative thin slice against the frozen v1 document contract
Campaign: 114
Parent: work/maps/map-database-owned-work-collateral-and-lifecycle-views.md
Supersedes: none
Superseded By: none

## Context

Path-authoritative work documents mix active and historical material, make lifecycle moves costly,
and force agents to rediscover relationships from filenames and Markdown. Generated views alone
improve navigation but retain the underlying path identity and maintenance pressure.

The existing Hybrid SQLite substrate already supplies project-bound identity, managed revisions,
ID relationships, direct-write detection, checkpoints, backups, and rebuild. Hiding document tables
inside schema 1 would let older clients misinterpret a database whose authority had materially
changed.

## Decision

Extend the embedded database to Hybrid schema 2 and make Tool Shed-generated work collateral
SQLite-authoritative after guarded cutover. Preserve the existing artifact UUID as the relational
identity and add an immutable namespaced visible ID. Store current document state and immutable full
revisions transactionally. Ordinary tools use deterministic commands and revision-fenced Markdown
edit projections; generated lifecycle trees are ignored disposable views.

Use content-addressed tracked objects plus a deterministic logical checkpoint for portable recovery.
Keep imported owner material, code, tests, canonical product documentation, provider instructions,
raw evidence, and recovery artifacts file-owned. Retain every original converted file unchanged
through rollout. Retirement is a later owner decision, not part of conversion.

## Consequences

- Paths, titles, and lifecycle can change without rewriting durable relationships.
- Older clients can safely refuse schema 2 instead of silently producing dual authority.
- Codex retains bounded Markdown reads and patch-shaped edits without direct SQL.
- Checkpoint commits occur at governed boundaries rather than on database access.
- Migration and updater logic must protect both schema generations and prove rollback export.
- The retained legacy corpus remains visible noise during the qualified soak; lifecycle views are
  the preferred operating tree until a separate retirement decision.

## Alternatives Considered

- File authority plus generated views: rejected as the endpoint because path coupling remains.
- A schema-1 sidecar table set: rejected because it conceals an authority and portability break.
- MongoDB or another service: rejected because it adds server, credential, backup, and disconnected
  operation burdens without a product need.
- Automatic legacy deletion after import: rejected because import parity is not sufficient evidence
  for retention or link retirement.
