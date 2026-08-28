# Hybrid SQLite Operational State

Status: maintainer-conversion candidate
Schema version: 1

Tool Shed's phase-one hybrid state is a guarded, local SQLite substrate. It does not replace
campaigns, Program Roadmaps, general Markdown bodies, imported source files, product documentation,
or existing queue/index authority. The canonical design boundary is
[`hybrid-sqlite-state-v1-contract.md`](hybrid-sqlite-state-v1-contract.md).

The live paths are:

```text
.tool-shed/state.sqlite3
.tool-shed/state.lock
.tool-shed/backups/
work/state/checkpoints/state-v1.json
```

The whole `.tool-shed/` directory is ignored. Each clone or worktree owns its database and lock.
The tracked checkpoint is the deterministic collaboration and rebuild surface; the SQLite binary,
WAL, SHM, lock, and rolling backups are never committed.

## Guarded Operations

Obtain the project binding immediately before a mutation:

```bash
python3 scripts/project_identity.py --workspace . identity \
  --operation hybrid-state --json
```

Then use the shared interface:

```bash
python3 scripts/hybrid_state.py --workspace . init \
  --project-binding <hybrid-state-binding>
python3 scripts/hybrid_state.py --workspace . audit
python3 scripts/hybrid_state.py --workspace . import \
  --project-binding <hybrid-state-binding> \
  --assigned-ids schemas/hybrid-state/v1/maintainer-assigned-ids.json \
  --path work/ideas/example.md
python3 scripts/hybrid_state.py --workspace . relate \
  --project-binding <hybrid-state-binding> \
  --from-artifact <uuid> --relation produces --to-artifact <uuid> \
  --provenance <reference>
python3 scripts/hybrid_state.py --workspace . backup \
  --project-binding <hybrid-state-binding>
python3 scripts/hybrid_state.py --workspace . checkpoint \
  --project-binding <hybrid-state-binding>
python3 scripts/hybrid_state.py --workspace . cutover \
  --project-binding <hybrid-state-binding> \
  --expect-checkpoint <verified-shadow-checkpoint-digest>
python3 scripts/hybrid_state.py --workspace . rebuild \
  --project-binding <hybrid-state-binding> \
  --checkpoint work/state/checkpoints/state-v1.json \
  --output .tool-shed/rebuilt.sqlite3
python3 scripts/hybrid_state.py --workspace . legacy-check --field artifact.id
```

`init` creates a shadow-mode database through `state.sqlite3.next`, validates it, checkpoints WAL,
and atomically promotes it. It refuses an existing database, a stale shadow, a foreign project
binding, or a workspace where `.tool-shed/` is not ignored. The canonical maintainer must not run
`init` as a live conversion until the separately planned rehearsal and cutover campaign.

`import` records stable artifact IDs, source hashes, Git state, provenance, parser status, and
unresolved details without rewriting the source file. `relate` adds a typed immutable-ID edge. Both
run inside one managed operation with one allocated revision and database-triggered structural and
event accounting. New public IDs are canonical UUIDv4 values. Database triggers also refuse changes
to accepted identity, source-hash, relationship-endpoint, and historical-revision fields.

The maintainer conversion uses
`schemas/hybrid-state/v1/maintainer-assigned-ids.json` so every selected retained source artifact
and its first import reuse the same UUIDv4 in both disposable rehearsals and the live conversion.
An assigned ID that conflicts with existing state fails the entire managed transaction.

## Entrance Audit

Every managed mutation audits before writing. `audit` is read-only and reports one classification:

- `CLEAN`: valid and checkpoint-current;
- `VALID_DIRTY`: valid managed changes exist below the checkpoint threshold;
- `CHECKPOINT_DUE`: a valid dirty database reached 100 revisions or 24 hours;
- `UNMANAGED_REVIEW`: direct SQL was accounted by triggers but needs explicit reconciliation;
- `INVALID`: identity, worktree lineage, integrity, foreign keys, schema, triggers, or revision
  invariants failed; or
- `UNJOURNALED`: semantic rows changed without complete accounting evidence.

Only the first three permit a managed mutation. Direct SQL is therefore survivable but never
silently accepted. Removing or changing an accounting trigger changes the frozen schema digest and
fails closed. The triggers are an accounting mechanism, not a security boundary against a caller
with arbitrary database access.

## Checkpoint, Rebuild, And Backup

Checkpoint JSON uses canonical ordering, two-space indentation, a complete portable table set, an
exact project/source envelope, previous-checkpoint linkage, and a SHA-256 digest calculated with
only the envelope digest omitted. Stable checkpoint/export ledger IDs and the original checkpoint
path are included in that envelope. Generation reparses the temporary document before promotion
and records the matching ledger entries.

Rebuild validates the checkpoint digest and project, creates a new shadow database without firing
accounting triggers during load, restores portable rows, establishes local worktree lineage,
recreates the frozen triggers, checks foreign keys and integrity, compares the semantic digest, and
compares every portable ledger row. Only then does it promote the requested new database. It never
overwrites an existing database.

Rolling backups use SQLite's backup API and reproduce the live audit classification. The newest
three verified backups are retained. Raw main-file copying is not an accepted backup operation.

## Authority And Rollout Boundary

This substrate remains `shadow` until a later guarded campaign proves HPT2 reconciliation and the
maintainer conversion. Existing file writers remain authoritative. `legacy-check` demonstrates the
future refusal boundary: when a database is explicitly converted to `hybrid`, fields such as stable
artifact IDs, relationships, revisions, evidence references, verdicts, and reconciliation are no
longer writable through legacy file routes.

Current updater protocol 3 preserves but does not migrate ignored hybrid runtime state. The first
database-aware release requires protocol 4, complete bootstrap closure, maintainer rehearsal and
conversion evidence, supported-platform release qualification, and separate client-canary
authorization.

The HPT2 shadow qualification and its explicit `partial`/`reconciled` historical disposition are
documented in [`outcome-reconciliation.md`](outcome-reconciliation.md). Passing that vertical slice
does not itself authorize the later live maintainer conversion.

## Dedicated Maintainer Conversion

The canonical maintainer never runs the disconnected-snapshot updater against itself. Its dedicated
controller is `scripts/maintainer_hybrid_conversion.py`. The controller requires a clean exact
source commit, inventories tracked, untracked, and ignored files, writes a byte-verified archive
outside the repository, and refuses to raw-copy an existing SQLite database. SQLite backups use
the substrate backup API.

The guarded sequence is:

```bash
python3 scripts/maintainer_hybrid_conversion.py --workspace . archive \
  --output <external>/maintainer-pre-cutover.tar.gz
python3 scripts/maintainer_hybrid_conversion.py --workspace . rehearse \
  --archive <external>/maintainer-pre-cutover.tar.gz --runs 2 \
  --report <external>/maintainer-rehearsal.json
python3 scripts/project_identity.py --workspace . identity \
  --operation hybrid-state --json
python3 scripts/maintainer_hybrid_conversion.py --workspace . cutover \
  --archive <external>/maintainer-pre-cutover.tar.gz \
  --rehearsal-report <external>/maintainer-rehearsal.json \
  --project-binding <hybrid-state-binding> \
  --report <external>/maintainer-cutover.json
python3 scripts/maintainer_hybrid_conversion.py --workspace . soak \
  --minimum-seconds 5 --report <external>/maintainer-soak.json
```

Each rehearsal restores the exact external archive into independent clones, imports the fixed IDs,
reproduces HPT2 parity, checkpoints and rebuilds both shadow and hybrid modes, verifies the SQLite
backup, simulates interruption and direct SQL, restores the external archive, and proves that a
database copied into a foreign clone fails worktree-lineage audit. Live cutover is allowed only
when both rehearsal semantic digests match the same archive and source commit. It preserves the
assigned retained-source fingerprint across the no-write window, creates and verifies a pre-cutover
SQLite backup, activates hybrid authority from the exact clean shadow checkpoint, writes the tracked
portable checkpoint, rebuilds it, and verifies legacy-writer refusal. Publication, installed-skill
synchronization, disconnected-client mutation, and legacy-file retirement remain outside this step.
