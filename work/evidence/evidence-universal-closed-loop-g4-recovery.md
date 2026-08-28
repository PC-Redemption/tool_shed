# Universal Closed-Loop G4 Recovery And Backfill Evidence

Status: passed (local candidate); gate remains open for exact-candidate CI
Evidence ID: EVID-CLOSED-G4-RECOVERY
Gate: G4-RECOVERY-BACKFILL-PROVEN
Campaign: qualify-universal-reconciliation-backfill-and-recovery
Target: canonical Tool Shed maintainer and disposable recovery workspaces
Candidate version: 0.35.0
Date: 2026-08-28

## Qualified Boundary

G4 qualifies historical backfill, ambiguity refusal, exact direct-SQL reconciliation, backup,
rollback, deterministic rebuild, compact query behavior, read-only soak, and release-matrix
portability. It does not publish 0.35.0, synchronize the installed maintainer skill, run the
released disconnected-client canary, or close the initiative; those remain G5 work.

## Recovery And Direct-SQL Reconciliation

`CHG-CLOSED-003` and the substrate overlay `CHG-HYBRID-016` record the only qualification-driven
behavioral addition. Direct SQL still enters `UNMANAGED_REVIEW`. Retaining it now requires the exact
project binding, review classification, current revision, semantic SHA-256 digest, authorization
reference, and summary. The operation journals `unmanaged-reconciled`, leaves the database
`VALID_DIRTY`, and requires a deterministic checkpoint before returning to `CLEAN`. Stale-digest
acceptance is refused.

The focused Hybrid, maintainer-conversion, updater-protocol-4, and outcome suites passed 33 of 33
tests. They cover direct-SQL detection and acceptance, interruption rollback, deterministic
checkpoint rebuild, ambiguous historical match refusal, explicit historical overlays, backfill
idempotency, foreign-project and stale-plan refusal, evidence-digest refusal, as-of reconstruction,
and direct-work and campaign result propagation.

The maintainer backup API produced the verified clean backup
`.tool-shed/backups/state-v1-20260828T212224Z.sqlite3` with SHA-256
`d81f4e9b5bcdea5ae7abde26a5ae1b97ef7df31473f32a0eaf1a1e27c513be49`.
Revision 44 checkpoint digest
`28549e74ddd9de575cd8f7f97a4f752973fb17a16da86e2336ff14e6adfb8764`
rebuilt a fresh database with the exact live domain digest
`92e9a708fcbb060ceee58078efbbb740582713aca79e20a627251b142b724ea6`.
After Hybrid historical-overlay reconciliation, the canonical revision-48 checkpoint digest is
`76e20eee17240e4580c0c9ac8af0eb0390a5818bec345cabc03b996d9af8b23f`.

## Historical Truth And Context Efficiency

The generic audit reports only the intentionally open universal root, with no invalid,
terminal-unreconciled, or unpropagated cycles. Historical reports reproduce the completed Campaign
109-111 overlays independently of the current owning root. HPT2 remains explicitly partial and
reconciled because its unavailable source history is never invented; after synchronization it
again passed bootstrap and all eight operation-parity checks.

The deterministic efficiency benchmark passed semantic and evidence parity on small, maintainer,
and 2,500-file fixtures. Median estimated context reduction was 99.98%, with zero fallback queries.
A 100-iteration read-only soak repeatedly ran outcome audit/report and roadmap status/overview.
Before and after SHA-256 values were identical for both the live database
(`3857872a44197c8cb0fc97ece1a8cf0ad842f798b479bc8c72822f0f2212e5d3`) and tracked checkpoint
(`0dede4448f8471bcfd168eaf1d2a49aa0f68883b10e84c84f95826cc9c185d1e`).

## Remaining G4 Completion Work

The complete 367-test suite and repository validators must pass after the final release-manifest
refresh. The exact candidate must then be committed and pushed, a fresh source-complete external
archive must pass two disposable maintainer rehearsals, and the exact GitHub CI matrix must pass.
Only then may this evidence become `passed` and G4 receive a satisfied verdict.
