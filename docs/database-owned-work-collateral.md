# Database-Owned Work Collateral

Tool Shed 0.36 adds a managed SQLite document interface for generated work collateral. The live
database is local and ignored; original files stay retained during conversion, and lifecycle views
under `.tool-shed/views/work/` are disposable.

The schema-2 interface is `scripts/document_store.py`. Every mutating command requires the same
project-bound `hybrid-state` binding used by the Hybrid substrate. Ordinary work should use these
commands, never direct SQL.

At cutover, legacy file-backed artifact, campaign, and Program Roadmap writers refuse generated
document operations. `new_artifact.py` automatically creates a managed database document when the
workspace is schema 2 and receives `--project-binding`; it does not add another file below `work/`.
Schema-1 and database-free workspaces retain the established file behavior.

## Compact reads

```bash
python3 scripts/document_store.py --workspace . list --lifecycle working --limit 50
python3 scripts/document_store.py --workspace . show IDEA-0001
python3 scripts/document_store.py --workspace . search "closed loop" --limit 20
python3 scripts/document_store.py --workspace . context IDEA-0001 --byte-budget 16384
python3 scripts/document_store.py --workspace . related IDEA-0001
python3 scripts/document_store.py --workspace . history IDEA-0001
python3 scripts/document_store.py --workspace . diff IDEA-0001 --from-revision 1 --to-revision 2
python3 scripts/document_store.py --workspace . resolve work/ideas/legacy-name.md
```

`context` always returns the requested document, then includes related records in stable ID order
while they fit. It names omitted IDs so an agent can expand deliberately. JSON output is the
portable default; rendered Markdown remains available through `show`, edit projections, and views.

## Guarded edits

```bash
python3 scripts/document_store.py --workspace . export-edit IDEA-0001 \
  --output .tool-shed/edits/IDEA-0001.md

# Patch the temporary Markdown file, then apply its exact revision.
python3 scripts/document_store.py --workspace . apply-edit \
  --project-binding <binding> --edit .tool-shed/edits/IDEA-0001.md \
  --actor codex --reason "Apply the accepted requirement change"
```

The apply step rejects a changed ID, stale revision, malformed metadata, or unknown header field.
It appends an immutable revision and updates the current document plus artifact state in one
transaction. Lifecycle changes and relationships use `set-lifecycle`, `relate`, and `unrelate`
with the same managed-operation fence.

New structured content can be supplied without shell quoting through `create --body-file`:

```bash
python3 scripts/document_store.py --workspace . create \
  --project-binding <binding> --type ticket --title "Example" \
  --body-file .tool-shed/edits/new-ticket.md --preferred-path work/tickets/ticket-example.md \
  --actor codex --reason "Create accepted work"
```

## Disposable views

```bash
python3 scripts/document_store.py --workspace . render-views
```

The command atomically rebuilds `active`, `working`, `blocked`, `parked`, `deferred`, `completed`,
`abandoned`, and `superseded` folders. Each file includes its immutable visible ID, artifact UUID,
document revision, and source database revision. Manual edits and extra files disappear on rebuild;
views are never relationship targets or writable authority.

## Safety

`audit` is read-only. A direct SQL change is structurally recorded as unmanaged and blocks the next
managed mutation. `checkpoint` writes a deterministic logical schema-2 checkpoint and immutable
SHA-256 content objects; `rebuild` verifies those objects before producing a fresh database. Reads
do not checkpoint, require Git, or require GitHub.

The exact authority, conversion, rollback, compatibility, and retirement rules are frozen in
[`database-owned-work-collateral-v1-contract.md`](database-owned-work-collateral-v1-contract.md).
