# Database-Owned Work Collateral v1 Contract

Status: design-frozen
Contract version: 1
Hybrid database schema: 2
Decision gate: G1-CONTRACT-DESIGN-FROZEN
Initiative: database-owned-work-collateral-and-lifecycle-views

This contract moves Tool Shed-generated work collateral from path-bound files to the existing
embedded SQLite authority. It extends, rather than replaces, the Hybrid SQLite v1 operational-state
and Universal Closed-Loop contracts. One field has one writable authority at a time. The live
database remains ignored local runtime state; deterministic checkpoints are the portable recovery
surface.

## Authority Classes

| Class | Examples | Writable authority after cutover | File behavior |
| --- | --- | --- | --- |
| Generated documents | ideas, maps, Program Roadmaps and revisions, campaigns, tickets, checklists, spikes, ADRs, decisions, inventories, runbooks, workpackages, incidents, Q&A, evidence summaries, focus-area records | SQLite document and revision rows | rendered views only |
| Generated collections | active/completed queues, indexes, lifecycle trees, status and history reports | SQLite query plus renderer | disposable projection |
| Imported owner material | owner-authored intake and explicitly imported source files | original file | hash/provenance reference only |
| Product truth | source, tests, `README.md`, `docs/`, schemas, templates, provider instructions and skills | file and Git | hash/reference only |
| Evidence payloads | raw/large/external evidence and command output | original target or file | hash/reference only; a generated evidence summary may be a DB document |
| Recovery truth | logical checkpoints, content objects, conversion manifests, release provenance and retained-source inventory | governed generated file | never imported as an editable document |

Classification is explicit in the conversion manifest. Ambiguous files are `unresolved` and stay
file-authoritative. A file pattern alone never transfers authority. Queue and index files are
projections, not documents. Files outside root `work/` are never document candidates unless a later
contract version names them.

## Identity And Numbering

Every document has two immutable identities:

- `artifact.id`: canonical lowercase UUID, used by foreign keys and internal relationships;
- `document.visible_id`: operator-facing `NAMESPACE-NNNN`, rendered in every title and projection.

Namespaces are `IDEA`, `MAP`, `PRM`, `CAMP`, `TKT`, `CHK`, `SPK`, `ADR`, `DEC`, `INV`, `RUN`,
`WP`, `INC`, `QNA`, `EVD`, and `FOC`. Width is at least four digits and expands without truncation.
Allocation is transactional, monotonically increasing per project and namespace, and numbers are
never reused. Existing campaign number 114 imports as `CAMP-0114`; other unambiguous legacy numbers
are preserved. Duplicate claims fail the import. Unnumbered legacy documents receive numbers once
in the reviewed assigned-ID manifest, which is reused across every rehearsal.

Titles, slugs, lifecycle, revision, and paths are mutable attributes and never relationship keys.
Aliases preserve every known historical path. A generated view path cannot be stored as a durable
relationship or outcome reference.

## Schema 2 Document Model

Hybrid schema 2 adds these portable, accounted tables to the v1 schema:

| Table | Purpose |
| --- | --- |
| `document_namespace` | namespace and next allocatable number; allocation never decrements |
| `document` | artifact UUID, visible ID, namespace/number, title, current revision, structured metadata, body hash and lifecycle |
| `document_revision` | immutable full title, metadata and Markdown body for every accepted revision |
| `document_path_alias` | immutable historical/source/view alias with nullable retirement revision |
| `document_conversion` | source hash, assigned identity, classification, parity and cutover disposition |

`document_revision` and completed conversion rows are append-only. Updating a document creates one
revision row and advances its current revision in the same managed transaction. The current row's
hashes must equal that revision. UTF-8, LF, lowercase SHA-256, canonical JSON, UTC whole-second RFC
3339 timestamps, and the Hybrid UUID rules apply. Markdown is preserved byte-for-byte after newline
normalization is explicitly selected; otherwise import retains the exact source bytes as a content
object and records a render distinction.

Schema 1 clients refuse schema 2 before mutation and name the required updater. Schema 2 can import
schema 1 checkpoints through a checksummed 1-to-2 shadow migration. A newer schema is always
refused. There is no in-place down migration.

## Managed Command Contract

Ordinary operation uses `scripts/document_store.py`; direct SQL is diagnostic bypass behavior.
Commands return a versioned JSON envelope by default and deterministic Markdown only when selected.

Read commands are `list`, `show`, `search`, `context`, `related`, `history`, `diff`, `resolve`, and
`render-views`. Mutating commands are `create`, `export-edit`, `apply-edit`, `set-lifecycle`,
`relate`, `unrelate`, `import-plan`, `import-apply`, and `checkpoint`. Maintenance commands are
`audit`, `migrate`, `rebuild`, `rollback-export`, and `qualify-conversion`.

Every mutation requires the project binding, immutable ID, expected current document revision,
actor, and reason. `export-edit` writes a temporary Markdown projection containing ID, revision,
editable structured metadata, and body. `apply-edit` rejects a stale revision, changed identity,
unknown field, malformed front matter, or edits outside the declared document. It validates in a
shadow transaction and atomically appends the revision. Temporary projections are ignored and are
not authority. Reads never change the database or create checkpoints.

`context` accepts a byte budget and returns the requested document first, then relationships in a
stable priority and ID order; it reports omitted IDs rather than silently truncating a document.
Search uses SQLite FTS when available and a deterministic bounded fallback otherwise.

## Lifecycle Views

The portable view root is `.tool-shed/views/work/`, with children `active`, `working`, `blocked`,
`parked`, `deferred`, `completed`, `abandoned`, and `superseded`. Each rendered filename is
`VISIBLE-ID--slug.md`; its header carries artifact UUID, visible ID, database revision, document
revision, lifecycle, and a generated/do-not-edit marker. An `_index.md` in each child lists IDs,
titles, types, and current status. The whole tree is ignored and atomically replaceable.

Views contain no writable state, symlinks are not required, and deletion or manual edits are healed
by `render-views`. A view build reads one verified database revision and refuses to publish a mixed
revision. Retained legacy paths are registered aliases but are never regenerated in place during
this initiative.

## Checkpoint And Git Policy

Schema 2 writes `work/state/checkpoints/state-v2.json` plus immutable content objects under
`work/state/objects/sha256/aa/<digest>`. The checkpoint contains all portable logical rows but
replaces revision bodies with validated content-object references. Objects are UTF-8 bytes named by
their SHA-256; existing objects are never rewritten. The checkpoint manifest is canonical JSON and
binds the project, database schema/revision, source lineage when Git exists, previous digest,
complete object inventory, table digests, and its own digest.

A checkpoint is created only for an explicit operator request, completed reconciliation,
milestone/cycle closure, schema migration, conversion/cutover, release qualification, accepted
unmanaged-write disposition, or the existing 100-revision/24-hour dirty threshold. Git and GitHub
are optional: without Git, checkpoints still write locally with `source_commit: null`; snapshot
commit/push is skipped and reported. The live database, WAL, locks, backups, edit projections, and
lifecycle views are never tracked.

## Direct SQL And Closed-Loop Rules

All document tables use the Hybrid accounting and immutable-history triggers. Direct SQL therefore
sets unmanaged review exactly as v1 does. The next managed entrance audits schema, revisions,
hashes, current/revision parity, visible-ID uniqueness, aliases, relationships, and content
objects. It may read and report the state but refuses further mutation until exact disposition.
No automatic checkpoint blesses an unmanaged change.

A database transaction, completed campaign, empty queue, rendered view, migration, or release is
not outcome closure. Every originated idea, map, roadmap, campaign, and material development change
keeps its outcome-cycle identity. Child results propagate by immutable artifact/cycle IDs. Terminal
reconciliation requires accepted requirements, current product truth, target evidence, authorized
changes, residual work, and a verdict. Unknown historical evidence stays unknown.

## No-Loss Conversion And Rollback

Conversion is fixed and resumable:

```text
inventory -> external archive -> reviewed classification/ID manifest -> schema-2 shadow
-> import -> byte/render/semantic/identity/relationship/history parity -> checkpoint/rebuild
-> repeated idempotence -> dual-read/single-write rehearsal -> guarded cutover
-> rollback export proof -> maintainer soak -> client canaries
```

Inventory includes tracked, untracked, and ignored files, exact paths, sizes, hashes, Git state when
available, detected type/status/number, owner extensions, inbound/outbound references, assigned IDs,
classification, and warnings. Interrupted import resumes from immutable source hashes and performs
no duplicate allocation or revision. A changed source fails until reinventory.

Before cutover, files remain the only writer. At cutover, imported generated fields become SQLite
authority and legacy writers refuse them. Every original remains byte-identical at its original
path and in a verified external archive through this release and soak. `rollback-export` must render
all post-cutover database changes into a separate recovery tree and prove semantic parity before an
older file-authority tool may resume. Database backup and checkpoint rebuild are both qualified.
The database-aware artifact creator switches to managed document creation and accepts the exact
project binding; campaign and Program Roadmap file commands fail closed until invoked through the
managed document route. This prevents a retained source from silently becoming a second writer.

This initiative does not delete, move, rewrite, or mark retained originals disposable. Retirement
requires a separate owner decision after final reconciliation, with retention duration, inbound-link
handling, archive location, recovery test, and explicit deletion scope. Until then, retention is an
accepted residual obligation, not incomplete conversion.

## Compatibility And Rollout

The dual-role canonical maintainer is the first real conversion target and uses its dedicated
upgrade/synchronization procedure; it never snapshot-installs over itself. Qualification order is:
disposable fixtures, disposable maintainer-shaped copies, canonical maintainer, separately installed
Codex skill, clean disconnected client, existing disconnected client, then optional production
publication. Production needs Python 3.11+, SQLite with FTS optional, local writable storage, and
the Tool Shed files; Git, GitHub, network access, a server, and credentials are not required.

Release publication does not authorize retained-file retirement. An older updater encountering
schema 2 refuses before backup or mutation. The current updater separately protects the live
database, WAL state, checkpoints/objects, retained originals, provider files, and installed skill,
and restores the complete declared surface on failure.

## Frozen Decisions

The authority classes, namespaces, dual immutable IDs, schema-2 boundary, command set, edit fence,
view root/format, checkpoint/object format, direct-SQL disposition, conversion order, maintainer-first
rollout, disconnected operation, closed-loop propagation, and separate retirement authority are
settled. Changing one is a material development change: record authorization, supersession,
affected requirements, and evidence reruns before implementation continues.
