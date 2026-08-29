# Evidence: Database-Owned Collateral G4 Conversion And Recovery

Status: passed
Type: evidence
Updated: 2026-08-28
Evidence ID: EVID-DBDOC-G4-CONVERSION-RECOVERY
Gate: G4-CONVERSION-RECOVERY-PROVEN
Campaign: 117

## Scope

This record verifies a no-loss conversion and recovery rehearsal against a disposable copy of the
canonical maintainer. The canonical live database and retained files were not converted.

## Maintainer-Shaped Result

- Rehearsal root: `/tmp/tool-shed-doc-rehearsal-UDTCij`
- Exact inventory: 274 files; 239 generated, 15 file-owned, 3 projections, and 17 unresolved.
- External retained-source archive: 274/274 files copied and SHA-256 verified outside the workspace.
- Frozen baseline: 53 artifact/path bindings, 50 typed relationship rows, and 2,387 immutable
  operation/change/event/migration/export/checkpoint history rows.
- Simulated interruption: five documents committed; resume recognized those five and imported the
  remaining 234 without reallocating identity.
- Idempotence: the third complete pass imported zero and recognized all 239 documents.
- Body/recovery: 239 revision bodies became immutable content objects; checkpoint rebuild reproduced
  the exact semantic database digest; rollback export produced 239 documents.
- Qualification findings: none. Retained-source, initial revision, UUID, visible ID, relationship,
  history, and archive parity all passed.

## Focused Qualification

- `schemas/document-store/v1/conversion-manifest.schema.json` defines the portable reviewed plan.
- `scripts/document_conversion.py` implements inventory, external archive, resumable apply, exact
  qualification, and separate rollback export.
- The fixture preserves campaign number 7, classifies queues as projections, raw evidence as
  file-owned, and unknown Markdown as unresolved. It proves interrupted resume, repeated apply,
  checkpoint rebuild, rollback byte parity, and older/newer schema refusal.
- `python3 -m unittest tests.test_document_conversion tests.test_document_store
  tests.test_document_contract` passed 7/7 tests.

## Verdict

`EVID-DBDOC-G4-CONVERSION-RECOVERY`: passed. The conversion is no-loss, idempotent, recoverable,
and schema-fenced in maintainer-shaped disposable rehearsal. Canonical cutover remains M5.
