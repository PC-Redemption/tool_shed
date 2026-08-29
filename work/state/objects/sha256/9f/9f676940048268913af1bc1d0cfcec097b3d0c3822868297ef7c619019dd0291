# Evidence: Database-Owned Collateral G1 Contract

Status: passed
Type: evidence
Updated: 2026-08-28
Evidence ID: EVID-DBDOC-G1-CONTRACT
Gate: G1-CONTRACT-DESIGN-FROZEN
Campaign: 114

## Scope

This record verifies the authority, identity, schema, command, projection, checkpoint,
compatibility, conversion, rollback, retirement, and closed-loop boundary before document storage
or broad corpus conversion begins.

## Results

- `docs/database-owned-work-collateral-v1-contract.md` classifies generated documents,
  disposable projections, retained owner/product/evidence files, and recovery artifacts with one
  writable authority per field.
- The contract assigns 16 immutable visible-ID namespaces while retaining the Hybrid artifact UUID
  as relational identity. Existing campaign number 114 imports as `CAMP-0114`; collisions and
  ambiguous legacy numbering fail closed.
- The accepted ADR makes this an explicit Hybrid schema-2 extension. Schema-1 and newer clients
  refuse unsupported authority before mutation; schema-1 conversion uses a checksummed shadow
  migration.
- The complete managed command surface, revision-fenced Markdown edit protocol, bounded context,
  lifecycle view root, direct-SQL review behavior, content-addressed checkpoint, optional Git
  behavior, and no-GitHub production boundary are frozen.
- Conversion remains single-writer, shadow-first, resumable, idempotent, byte-retaining, and
  rollback-export qualified. This initiative cannot move or delete retained legacy collateral;
  retirement requires a separate owner decision after final reconciliation.
- Closed-loop reconciliation remains independent of storage success and must propagate every
  campaign result and authorized material change to the originating idea.
- `scripts/document_contract.py` accepted the canonical contract fixture and rejected the
  deliberately contradictory dual-authority/direct-SQL/tracked-live-database fixture.
- `python3 -m unittest tests.test_document_contract` passed 3/3 tests.

## Verdict

`EVID-DBDOC-G1-CONTRACT`: passed. The G1 contract is design-frozen and the representative thin
slice may implement schema 2 without broad corpus conversion.
