# Database-Owned Work Collateral Conversion

Conversion is additive, resumable, and reversible. Run it against a disposable copy before the
canonical maintainer. Original files remain unchanged and an external retained-source archive is
mandatory before authority cutover.

## Sequence

1. Rebuild or initialize the Hybrid database and migrate a shadow to schema 2.
2. Generate a conversion inventory with `scripts/document_conversion.py inventory`.
3. Review every `generated`, `file-owned`, `projection`, and `unresolved` classification plus its
   assigned UUID and visible number. Do not apply a manifest with unexplained ambiguity.
4. Copy every inventory entry to an external archive with `archive`; the controller rehashes both
   sides and writes an archive manifest.
5. Run `apply` against the schema-2 shadow. Each source hash and assigned identity is fenced.
6. Run `qualify`, checkpoint, rebuild, repeat `apply`, and generate `rollback-export`.
7. Only after identical rehearsals pass may the maintainer use the guarded cutover procedure.

The inventory includes every regular file below `work/`, including file-owned and unresolved
material. Generated Markdown requires a recognized `Type:` header. Ambiguity never defaults to
database authority. Campaign numbers are preserved; other visible numbers are assigned
deterministically and frozen in the reviewed manifest.

Interruption is safe at document boundaries. Completed imports are identified by source path/hash,
artifact UUID, and visible ID; a resumed pass reports them as idempotent. A changed source, ID
collision, or schema mismatch fails before that document mutates.

Qualification proves retained-source hashes, revision-1 bytes, visible IDs, artifact/path bindings,
pre-conversion relationships, and pre-conversion operation/event/ledger history. The logical
checkpoint plus immutable body objects must rebuild to the same database digest. A repeat apply
must import zero documents. Rollback export writes the newest database bodies to a separate tree;
it never overwrites retained originals.

Schema-1 document operations and schema 3+ databases are refused. There is no in-place downgrade.
Retiring the original corpus remains a separate owner decision after final reconciliation.
