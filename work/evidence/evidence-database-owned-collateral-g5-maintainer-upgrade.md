# Evidence: Database-Owned Collateral G5 Maintainer Upgrade

Status: passed
Type: evidence
Updated: 2026-08-28
Evidence ID: EVID-DBDOC-G5-MAINTAINER-UPGRADE
Gate: G5-MAINTAINER-UPGRADE-PROVEN
Campaign: 118

## Scope

This record qualifies the dual-role canonical maintainer conversion, recovery, managed-operation
fence, and unpublished installed-skill staging. The installed client is deliberately not replaced
until the v0.36 publication is verified in M6.

## Canonical Conversion And Recovery

- Clean schema-1 entrance: revision 66.
- Verified pre-conversion backup:
  `.tool-shed/backups/state-v1-20260829T010408Z.sqlite3`, SHA-256
  `fef7ce1d841804d41cfa4a0f3531076c62a082f13e1c6e8e761710bb24b5e7f8`.
- Reviewed assignment manifest token: `ce4b21d0bad4db34`; 276 files, comprising 256 generated,
  16 file-owned, four projections, and zero unresolved.
- Verified external retained-source archive:
  `/home/jon/docker/tool_shed-retained-source-v0.36.0-20260829T010401Z-r2` with all 276 files.
- Canonical schema-2 rehearsal imported all 256 generated documents and preserved 56 artifact/path
  bindings, 54 typed relationships, and 2,415 immutable history rows with zero findings. Its
  semantic digest was `62a2dd74d3cbe4979c1bf2613a5ad2efe8b323918cb5b7129190640eb23e24c0`.
- Checkpoint/rebuild and rollback export passed. Lifecycle views rendered 264 files across all eight
  states.
- An idempotent replay defect was detected because a no-op callback still advanced the database
  revision. The import entrance now returns read-only success for an exact prior conversion;
  focused tests prove the revision remains unchanged.
- A verified schema-2 recovery backup was retained, then the guarded restore command checked the
  exact backup digest and expected live revision, copied through the SQLite backup API, audited the
  staging database, atomically promoted it, and reproduced clean schema-1 revision 66 with domain
  digest `7e67cffa3e0b8846bc6687cb4223fe97d93ed46c4b25e078d5834ff01d123eed`.

## Authority And Maintainer Route

- `new_artifact.py` creates managed database documents after schema-2 cutover and leaves no new
  generated source file in `work/`.
- Legacy campaign and Program Roadmap file commands fail closed after cutover; schema-1 and
  database-free clients retain their prior behavior.
- The workspace-local Tool Shed skill validates and routes schema-2 reads/writes through the
  managed document interface. Its exact staged copy validates at
  `/home/jon/.codex/skills/.tool-shed-v0.36.0-stage-N7JOxyWP` with an empty canonical diff.
- The currently installed published skill differs in exactly the three expected unpublished route
  files. Per the maintainer upgrade contract, deployment, exact post-install diff, and fresh-task
  smoke remain mandatory M6 work after publication.

## Qualification

- Focused document, conversion, and Hybrid recovery suites passed 14/14.
- The full isolated unit profile passed 375/375 in 15.3 seconds; manifest and provider-conformance
  checks passed.
- Full-profile orchestration proceeded through work-state and roadmap validation, then stopped only
  because the independently governed Universal Closed-Loop release/canary evidence is intentionally
  stale for the unpublished v0.36 consumer change. That evidence is a required M6 publication and
  canary result, not a waived M5 defect.

## Verdict

`EVID-DBDOC-G5-MAINTAINER-UPGRADE`: passed. The canonical maintainer conversion and exact restore
are proven, managed authority is fenced, and the unpublished skill is staged without violating the
post-publication deployment rule. Final cutover follows campaign closure; publication, client
deployment, and fresh-task smoke remain explicitly owned by M6.
