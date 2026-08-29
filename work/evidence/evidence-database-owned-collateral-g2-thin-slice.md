# Evidence: Database-Owned Collateral G2 Thin Slice

Status: passed
Type: evidence
Updated: 2026-08-28
Evidence ID: EVID-DBDOC-G2-THIN-SLICE
Gate: G2-THIN-SLICE-PROVEN
Campaign: 115

## Scope

This record verifies one complete database-authoritative document path in a disposable Hybrid
schema-2 shadow. The canonical maintainer database and retained source corpus were not converted.

## Results

- `scripts/document_store_schema.py` adds accounted document namespace, current document,
  immutable revision, path alias, and conversion-ledger tables with identity/history triggers.
- `scripts/document_store.py` performs a shadow schema-1-to-2 migration, managed import, stable
  visible-ID allocation, guarded reads and writes, revision-fenced Markdown export/apply, history,
  diff, ID relationship traversal, open outcome creation, logical checkpoint, content-object
  validation, and deterministic rebuild.
- The fixture imported `IDEA-0001` and `MAP-0001`, repeated import idempotently, revised the idea
  from revision 1 to 2, rejected the stale revision-1 edit, related the documents by artifact UUID,
  and kept the open lifecycle/verdict/reconciliation dimensions distinct.
- The schema-2 checkpoint stored immutable SHA-256 body objects and rebuilt a fresh database with
  the same semantic domain digest and current body.
- Both original Markdown files remained byte-identical after import, edit, relationship, outcome,
  checkpoint, and rebuild operations.
- A direct SQL title update was structurally accounted and classified `UNMANAGED_REVIEW`; the next
  managed mutation therefore refuses until exact disposition.
- `python3 -m unittest tests.test_document_store tests.test_document_contract` passed 5/5 tests.

## Verdict

`EVID-DBDOC-G2-THIN-SLICE`: passed. The representative vertical slice satisfies G2 without broad
corpus conversion or canonical maintainer cutover.
