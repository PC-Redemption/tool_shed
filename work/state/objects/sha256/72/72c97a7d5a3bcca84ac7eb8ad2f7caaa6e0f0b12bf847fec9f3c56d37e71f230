# Evidence: Database-Owned Collateral G3 Interface And Views

Status: passed
Type: evidence
Updated: 2026-08-28
Evidence ID: EVID-DBDOC-G3-INTERFACE-VIEWS
Gate: G3-INTERFACE-VIEWS-PROVEN
Campaign: 116

## Scope

This record verifies the normal Codex/operator document surface and disposable lifecycle views in
a provider-neutral Python/SQLite fixture. Corpus conversion and maintainer cutover remain gated.

## Results

- Managed reads cover list, show, search, bounded context, related, history, diff, resolve, and
  lifecycle view rendering. Normal writes cover create, export/apply edit, lifecycle change,
  relate/unrelate, import apply, and checkpoint.
- The context fixture always returned the requested `TKT-0001` and explicitly omitted related
  `CHK-0001` at a 512-byte budget instead of silently truncating either document.
- Revision-fenced edits and lifecycle transitions reject stale document revisions. Relationships
  resolve immutable artifact IDs while operator output uses immutable visible IDs.
- The renderer produced all eight portable lifecycle folders and deterministic ID-prefixed files.
  After injected manual noise, rebuild removed the noise and reproduced the exact document bytes.
- Search uses a dependency-free deterministic bounded fallback; SQLite FTS remains an optional
  optimization and does not affect semantics.
- The interface uses only Python 3.11+ and SQLite. It requires no provider API, direct SQL, symlink,
  daemon, Git, GitHub, network, server, credential, or shell-specific feature.
- `python3 -m unittest tests.test_document_store` passed 3/3 tests, including the prior thin-slice,
  direct-SQL, stale-edit, checkpoint/rebuild, bounded-context, and deterministic-view cases.

## Verdict

`EVID-DBDOC-G3-INTERFACE-VIEWS`: passed. The normal managed command and disposable projection
surface satisfies G3; inventory, rollback export, and broad conversion remain M4 work.
