# Hybrid SQLite Operational State v1 Contract

Status: design-frozen
Contract version: 1
Decision gate: G1-DESIGN-FROZEN
Initiative: hybrid-sqlite-operational-state

This document is the phase-one authority and portability contract for Tool Shed's hybrid SQLite
operational-state work. It freezes the design inputs needed to implement the minimum substrate and
the HPT2 closed-loop vertical slice. It does not activate database authority, migrate the maintainer,
publish a release, synchronize an installed skill, or modify a client.

The independent bootstrap manifest is
`work/evidence/bootstrap-closure-hybrid-sqlite-operational-state.json`. Until the database-backed
closed-loop implementation imports that manifest and reproduces its result, the tracked manifest,
Git history, and `scripts/bootstrap_closure.py` remain the closure authority for this initiative.

## Authority Boundary

One field has one editable authority. Phase one does not create dual-write behavior.

| Surface | Phase-one authority | SQLite role | File role |
| --- | --- | --- | --- |
| Project identity | `work/tool-shed-project.json` | Store the verified UUID as a foreign lineage binding | Editable only through existing project-identity tooling |
| Imported owner/source files | Original files | Record path, bytes hash, provenance, parser outcome, and assigned immutable ID | Remain byte-authoritative and are never rewritten by import |
| README and `docs/` product truth | Files | Reference paths and hashes only | Remain editable canonical truth |
| Campaign, queue, roadmap, milestone, and gate lifecycle | Existing files/scripts | Out of phase-one authority | Existing Tool Shed mechanisms remain authoritative |
| General Markdown bodies and owner extensions | Files | Out of phase-one authority | Preserved without normalization |
| Stable phase-one entity IDs | SQLite after guarded cutover | Editable authority | Tracked checkpoints project the values read-only |
| Typed phase-one relationships | SQLite after guarded cutover | Editable authority | Imports are evidence; checkpoints are read-only projections |
| Revisions, operations, structural changes, and events | SQLite after guarded cutover | Editable authority | Deterministic checkpoints preserve portable history |
| Minimum requirements, material changes, evidence references, verdicts, and reconciliation | SQLite after guarded cutover | Editable authority for the HPT2 vertical slice | Bootstrap manifest remains independent authority until parity passes |
| Raw evidence | External target or existing files | Store references and hashes only | Existing evidence policy remains authoritative |
| Generated capsule, report, index, or checkpoint | SQLite revision plus generator | Source state | Read-only, digest-bound projection; manual edits fail closed |

Phase one explicitly excludes database authority for campaigns, Program Roadmaps, milestones,
general document bodies, broad index replacement, legacy-file retirement, credentials, and raw
evidence. Expanding that list requires a later accepted material change and new evidence.

## Stable Identity And Value Rules

- Public entity IDs are lowercase canonical UUIDv4 strings stored as `TEXT`. Existing Tool Shed
  project UUIDs and campaign numbers are preserved; paths and display numbers never become keys.
- Relationship endpoints always use immutable IDs. A current path is an attribute of an import or
  projection, not identity.
- Timestamps are UTC RFC 3339 values at whole-second precision ending in `Z`.
- Content digests are lowercase SHA-256 hex. Absolute host paths, secrets, credentials, raw prompts,
  and raw evidence payloads are forbidden in database rows and portable checkpoints.
- Enumerations are lowercase kebab-case. JSON payloads contain integers, strings, booleans, arrays,
  objects, or null; phase one stores no floating-point values.
- Unknown or malformed input is preserved as an unresolved import record. The importer never fills
  missing history with an inferred fact.

## Database And Worktree Contract

The live database path is `.tool-shed/state.sqlite3` at the verified Git workspace root. The whole
`.tool-shed/` directory is ignored local runtime state. Each clone and each Git worktree owns a
separate database, lock, and backup directory; a database is never shared across worktrees or copied
between branches as a merge mechanism.

The runtime paths are:

```text
.tool-shed/state.sqlite3
.tool-shed/state.lock
.tool-shed/backups/
work/state/checkpoints/state-v1.json
```

The tracked checkpoint path is a generated compatibility surface, not a second editable authority.
Git commits provide its historical versions. No GitHub remote, authenticated `gh`, MCP server, App
Server, database server, or cloud service is required. Local Git is required for lineage and the
tracked recovery surface.

Every connection sets and verifies:

```text
PRAGMA foreign_keys = ON
PRAGMA journal_mode = WAL
PRAGMA synchronous = FULL
PRAGMA busy_timeout = 5000
PRAGMA trusted_schema = OFF
```

Writers also hold `.tool-shed/state.lock`. One managed writer may run per worktree. Concurrent reads
are allowed. A writer that cannot acquire the lock within five seconds returns a bounded busy result
and performs no mutation. Network filesystems and a database path outside the verified worktree are
unsupported in phase one.

## Schema Version 1

SQLite `PRAGMA user_version` is `1`. Every table uses explicit columns, foreign keys, `CHECK`
constraints, and `WITHOUT ROWID` where the text primary key is sufficient. JSON columns contain
canonical UTF-8 JSON and are named with `_json`. The implementation may split an index or add a
non-authoritative generated view without changing the contract; changing a table, field, authority,
constraint, trigger invariant, or portable representation requires schema version 2 or an accepted
material change that proves version 1 semantics are unchanged.

### Metadata and accounting

| Table | Fields and authority |
| --- | --- |
| `state_meta` | Singleton `id=1`; `schema_version`; verified `project_id`; `workspace_id`; `storage_mode`; `current_revision`; `last_verified_revision`; `last_checkpoint_revision`; `dirty`; `checkpoint_pending`; `unmanaged_write_detected`; `source_digest`; `checkpoint_digest`; `schema_trigger_digest`. SQLite owns every field except imported `project_id`. |
| `managed_operation` | `id`; allocated `revision`; `command`; `actor`; `started_at`; `committed_at`; `expected_writes`; `actual_writes`; `status`. One active row is allowed while the workspace lock is held. |
| `structural_change` | `id`; `revision`; nullable `operation_id`; `table_name`; `row_id`; `operation`; `managed`; `payload_digest`; `recorded_at`. Append-only. |
| `event` | `id`; `revision`; nullable `operation_id`; `kind`; `entity_type`; `entity_id`; `payload_json`; `recorded_at`. Append-only and sufficient to explain semantic history without storing full Markdown. |

### Identity, import, and graph

| Table | Fields and authority |
| --- | --- |
| `workspace` | `id`; verified `project_id`; `name`; `created_at`. One row per local project identity. |
| `cycle` | `id`; `kind`; nullable `origin_artifact_id`; `accepted_outcome`; `lifecycle_state`; `opened_at`; nullable `closed_at`. Only the minimum closed-loop cycle is in phase one. |
| `artifact` | `id`; `type`; nullable `display_number`; `current_path`; `authority_mode`; `lifecycle_state`; `content_sha256`; `created_at`; `updated_at`. `current_path` is mutable metadata, never identity. |
| `import_record` | `id`; `artifact_id`; `source_path`; `source_sha256`; `tracked_state`; `provenance`; `parser_version`; `parse_status`; `unresolved_json`; `imported_at`. Source bytes remain file-authoritative. |
| `relationship` | `id`; `from_artifact_id`; `relation_type`; `to_artifact_id`; `provenance`; `created_revision`; nullable `retired_revision`. Endpoints are immutable IDs. |

### Minimum closed-loop vocabulary

| Table | Fields and authority |
| --- | --- |
| `requirement` | `id`; `cycle_id`; `origin_artifact_id`; `accepted_outcome`; `disposition`; `accepted_revision`; `milestone_key`; `evidence_gate_key`. |
| `material_change` | `id`; `cycle_id`; nullable `requirement_id`; nullable `decision_id`; `summary`; `rationale`; `authorization_ref`; nullable `supersedes_change_id`; `evidence_rerun_json`; `recorded_revision`. |
| `evidence_reference` | `id`; `cycle_id`; `kind`; `reference`; nullable `sha256`; `target_identity`; `collected_at`. Raw evidence is never absorbed. |
| `verification_result` | `id`; `evidence_id`; nullable `requirement_id`; `status`; `command_or_test_id`; `source_revision`; `verified_at`; nullable `details_json`. |
| `outcome_verdict` | `id`; `cycle_id`; `scope`; `disposition`; `summary`; `authorization_ref`; `decided_revision`; `decided_at`. |
| `reconciliation` | `id`; `cycle_id`; `origin_revision`; `product_truth_ref`; `verdict_id`; `state`; `compared_at`; `residual_work_json`. |

The minimum verdict vocabulary is `open`, `satisfied`, `satisfied-with-approved-change`, `partial`,
`failed`, `rejected`, `superseded`, `parked`, and `not-applicable`. Reconciliation state is `open`,
`reconciliation-required`, or `reconciled`. Lifecycle, verdict, and reconciliation remain separate.

### Migration, export, and recovery ledgers

| Table | Fields and authority |
| --- | --- |
| `migration_ledger` | `id`; `from_schema`; `to_schema`; `migration_digest`; `source_digest`; `backup_ref`; `status`; `started_at`; nullable `completed_at`. Append-only. |
| `export_ledger` | `id`; `revision`; `format_version`; `path`; `digest`; `status`; `created_at`. Append-only. |
| `checkpoint_ledger` | `id`; `revision`; `path`; `digest`; `source_commit`; `status`; `created_at`. Append-only. |

Foreign keys use `RESTRICT` for identity and historical rows. Phase one does not cascade-delete
history. Retirement uses nullable retired revisions or an explicit terminal disposition.

## Trigger And Direct-SQL Contract

Every mutable domain table has insert, update, and delete accounting triggers. Identity columns,
append-only ledgers, historical revision fields, and accepted source hashes have separate immutable
field triggers. A managed operation allocates one revision before its domain writes; its triggers
reuse that revision and increment `actual_writes`.

When a write occurs without the active managed-operation context, the trigger allocates an implicit
revision, records `managed=false`, appends a structural-change row and event, and sets
`dirty=1`, `checkpoint_pending=1`, and `unmanaged_write_detected=1`. This is accidental-bypass
diagnosis, not a security boundary: a caller with arbitrary SQL access can imitate context, so the
entrance audit also verifies content and schema continuity.

At every managed entrance, before reading state for a lifecycle mutation, the shared access layer:

1. verifies project identity, worktree lineage, and the workspace lock;
2. runs `PRAGMA integrity_check` and `PRAGMA foreign_key_check`;
3. hashes normalized tables, indexes, and triggers from `sqlite_schema` and compares the frozen
   schema/trigger digest;
4. checks revision continuity, operation write counts, append-only ledgers, and checkpoint/export
   revisions;
5. recomputes the canonical phase-one domain digest and detects data changes without revision
   evidence; and
6. validates domain invariants and classifies the database.

The only entrance results are:

- `CLEAN`: verified and checkpoint-current;
- `VALID_DIRTY`: verified changes exist but no checkpoint boundary is due;
- `CHECKPOINT_DUE`: verified changes reached a mandatory checkpoint boundary;
- `UNMANAGED_REVIEW`: structurally valid bypass writes need exact disposition;
- `INVALID`: integrity, foreign keys, schema, or domain invariants fail; or
- `UNJOURNALED`: the domain digest changed without complete revision-ledger evidence.

Only the first three permit a covered managed mutation. The audit never silently blesses direct SQL.
Accepting an unmanaged change requires an exact material-change record, authority, passing rerun
evidence, and a tracked checkpoint. Invalid or unjournaled state is restored or rebuilt before
mutation.

## Checkpoint And Event Format

`work/state/checkpoints/state-v1.json` is the single tracked phase-one checkpoint. It contains an
envelope and the complete phase-one logical rows required to rebuild the ignored database. It does
not include raw evidence, credentials, absolute paths, SQLite pages, WAL bytes, or general Markdown
bodies.

Canonical serialization is UTF-8, LF, two-space indented JSON with lexicographically sorted object
keys. Entity arrays sort by entity type and immutable ID; event and ledger arrays sort by revision
then ID. Timestamps use the value rules above. The envelope records format version, project ID,
schema version, database revision, source commit, source-tree digest, previous checkpoint digest,
and a SHA-256 digest calculated over the document with only the digest field omitted.

The generator writes a temporary file, reparses it, rebuilds a shadow database, runs integrity and
foreign-key checks, compares the semantic digest, and atomically replaces the tracked checkpoint.
Manual edits fail digest, lineage, or ledger validation and block mutation until discarded or
explicitly imported as an authorized material change.

A checkpoint is required at completed reconciliation, milestone or cycle closure, schema migration,
maintainer/client conversion, release qualification, accepted unmanaged-write disposition, an
explicit operator request, or when valid dirty state reaches 100 revisions or 24 hours since the
last checkpoint. Merely opening, querying, or validating the database never creates a checkpoint.

## Branch, Merge, Rebuild, And Clone Behavior

At entrance, the local database must name the same project ID and tracked checkpoint digest as the
checked-out worktree. A missing database rebuilds from retained imports and the checkpoint. A stale
or foreign lineage is never reused automatically; it is backed up, then rebuilt or explicitly
reconciled.

Checkpoint merge uses Git's base, ours, and theirs documents plus immutable IDs. It may merge
disjoint new IDs, identical edits, and changes to different explicitly independent fields.
Same-field differences, delete/edit pairs, competing accepted outcomes, different verdicts,
relationship endpoint changes, and overlapping material-change dispositions are semantic conflicts.
They require an exact reconciliation record. Timestamp-only last-write-wins and path-order choices
are forbidden.

A fresh clone verifies project identity, imports retained files by recorded hash, loads the tracked
checkpoint into a new shadow database, and requires the same schema, logical row, event, ledger, and
semantic digests before promotion.

## Backup, Migration, Rollback, And Downgrade

Rolling database backups live under `.tool-shed/backups/` and are ignored. They use SQLite's backup
API, never a raw main-file copy. A backup is verified with integrity and foreign-key checks plus its
project, schema, revision, and digest. The newest three verified rolling backups are retained. A
backup is mandatory before schema migration, cutover, restore, accepted unmanaged-write repair, and
the first managed write after either 24 hours or 100 revisions since the last verified backup.

Migrations are ordered, checksummed Python/SQL resources whose number matches `PRAGMA user_version`.
They run only against `state.sqlite3.next` after an external file/archive backup and a SQLite backup
exist. The shadow database must rebuild and compare semantically before an atomic promotion. A
failure discards the shadow database and leaves the current authority unchanged.

Tool Shed updater protocol 4 is the minimum database-aware protocol. Protocol 3 and older must read
the release manifest, refuse before backup or workspace mutation, and direct the operator to a
current released updater outside the stale client. Protocol 4 separately inventories and protects:

- the existing file-authority surface and ignored/untracked intake;
- `state.sqlite3` through the backup API plus WAL/SHM checkpoint handling;
- tracked checkpoint/export surfaces;
- provider instruction files; and
- the separately installed Codex skill when explicitly selected.

The updater acquires the workspace lock, checkpoints WAL with `TRUNCATE`, builds and validates a
shadow database, promotes atomically, regenerates projections, runs bootstrap/database closure and
doctor checks, and restores the declared surface on failure.

Before writers reopen, rollback restores the verified file archive and database backup and proves
their fingerprints. After any database-authoritative write, downgrade or rollback is allowed only
through a verified reverse export that reproduces the older file-authority contract including all
post-cutover changes. Otherwise the operation refuses and names the blocking schema/state. There is
no in-place down migration in phase one.

The canonical maintainer checkout never runs `update_snapshot.py` against itself. It is rehearsed in
a disposable clone and converted by the dedicated migration path. The installed Codex skill is a
separate post-publication target. A disconnected client is upgraded only from a verified release.

## No-Data-Loss Conversion Contract

The conversion sequence is fixed:

```text
inventory -> external archive -> assigned-ID manifest -> shadow import
          -> byte and semantic parity -> fresh-clone rebuild -> dual-read/single-write
          -> guarded cutover -> rollback proof -> soak
```

The inventory records every relevant file, size, SHA-256, Git state, current path, existing number
or ID, owner extension, proposed disposition, unknown field, and warning. IDs are assigned once and
reused across rehearsals. Every source byte and every semantic field is accounted for separately.
Unknown content becomes an unresolved import record. All original files remain unchanged through
the first hybrid release and soak; retirement is a later independently reviewed migration.

Legacy file-authority writers read the storage-mode marker before mutation and refuse a field whose
authority moved to SQLite. During shadow qualification, files remain the only writer and SQLite is
reimported for comparison. Two writable authorities for one field are forbidden.

## HPT2 Evidence Inventory

HPT2 is the selected historical vertical slice, but this repository currently contains no artifact
whose title or stable ID is HPT2 and no exact original HPT2 campaign, requirement ledger, or target
evidence bundle. The preserved evidence available at G1 is:

| Evidence | Location | Interpretation |
| --- | --- | --- |
| Operator-reported missing closure | `work/ideas/idea-universal-closed-loop-outcome-reconciliation.md` exploration log | Establishes why HPT2 was selected; not proof of original intent or delivery |
| Accepted Hybrid DB sequencing | `work/ideas/idea-sqlite-backed-tool-shed-operational-state.md` | Requires HPT2 as the first database-backed reconciliation case |
| Approved gate and campaign outcome | `work/roadmaps/roadmap-hybrid-sqlite-operational-state.md` | Defines the required M2 parity result |
| Current Tool Shed product truth | `README.md`, `docs/`, `scripts/`, and tests at the future M2 source commit | Candidate delivered-product evidence; must be narrowed to actual HPT2 claims |

M2 must obtain or explicitly disposition the original HPT2 Idea Brief/source request, accepted
changes, campaign and milestone history, product commits, tests, qualification evidence, and current
truth. Missing records remain `unknown`; they are never reconstructed as facts from plausible
history. This evidence gap does not alter schema version 1 or the no-data-loss contract, but it
blocks a satisfied HPT2 verdict until resolved.

## Context-Efficiency Fixtures

M2 uses identical requests and expected semantic answers in file-first and hybrid modes:

- `small`: a freshly installed deterministic workspace with 25 mixed active/completed artifacts;
- `maintainer`: this canonical repository's exact pre-cutover commit and work-state inventory; and
- `large`: a deterministic synthetic 2,500-record graph derived from the public fixture schema,
  with no invented historical claims.

Each fixture runs orientation, status, next, overview, dependency/gate lookup, historical
change/decision reporting, closed-loop audit, and one bounded mutation plus checkpoint evaluation.
It records supplied context bytes, estimated tokens using the documented four-bytes-per-token
fallback when provider usage is unavailable, queries/rows/files read, projection bytes, round trips,
duration, fallback reason, and semantic/provenance/evidence parity.

The acceptance gate is at least 70% median reduction in supplied context bytes or estimated input
tokens, zero incorrect transitions or semantic/evidence differences, and no more than 5% explained
full-tree fallback in clean steady-state runs. Migration, recovery, and corruption diagnosis are
reported separately and do not dilute the steady-state denominator.

## Bootstrap Closure Operations

Create an authored manifest from `templates/bootstrap-closure.json`, then bind it once:

```bash
python3 scripts/project_identity.py --workspace . identity --operation bootstrap-closure --json
python3 scripts/bootstrap_closure.py --workspace . baseline \
  --manifest work/evidence/bootstrap-closure-example.json \
  --project-binding <bootstrap-closure-binding>
```

All later semantic writes use the current manifest token and the same project binding:

```bash
python3 scripts/bootstrap_closure.py --workspace . record-change ...
python3 scripts/bootstrap_closure.py --workspace . record-evidence ...
python3 scripts/bootstrap_closure.py --workspace . record-verdict ...
```

`verify` and `report` are read-only. `verify --gate G1-DESIGN-FROZEN` checks a specific evidence
gate. `verify --require-final` enforces release readiness and fails while an accepted requirement,
migration item, upgrade target, required verdict, material-change evidence rerun, binding, or
evidence reference is missing, pending, failed, stale, or unsupported.

The full development validator invokes structural bootstrap verification. The release profile
invokes final verification. A database-aware updater must invoke final verification before
promotion. The database-backed HPT2 implementation must import the exact manifest token, records,
and ordering and reproduce the same report before bootstrap authority can retire.

## Settled Decisions And Deferred Implementation

All decisions that can change schema version 1 or the no-data-loss promise are settled above:
authority, identifiers, paths, concurrency, schema fields, trigger accounting, direct-SQL handling,
checkpoint serialization and cadence, merge/rebuild behavior, backup retention, migration,
protocol 4 refusal, rollback/downgrade, rollout order, HPT2 uncertainty handling, and efficiency
fixtures.

Implementation details may still be refined when they preserve this contract—for example index
selection, SQL statement layout, function names, and diagnostic wording. A discovered need to alter
an authority, field, invariant, portable representation, loss promise, or acceptance threshold is a
material change: record it in the bootstrap ledger, identify the superseded decision, rerun named
evidence, and revise the roadmap if the milestone or risk boundary changes.
