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

## Exact-Candidate Disposable Maintainer Rehearsal

Commit `010b626b7fc609b1179506f9ac73743583486e91` was checked out into a detached,
database-free worktree. The controller archived all 451 tracked files with zero ignored or
untracked files. The external archive has SHA-256
`972cd2d80f4f150f7a0754171e3aa3fde6cffa4121216ecad6bd93f626041372` and inventory digest
`b156a08d1facad20c1fc9e05465f3598d927cb4f0bf98063a489edadeaefe368`.

Two isolated restores produced deterministic source fingerprint
`6df5d9d432de673dd56ed12714c99ee688f7d2a447cd7da048ce541d8804302d`, semantic digest
`0ea4f0f5b5571aa09cfe91be5d141d2f84dc98219c9428f6a4deb48cb790b113`, and rehearsal token
`3a202d878fb3e0895fe008f699fc976ab5293f0d7da70077327ba87ed46a7f09`.
Each run restored all 451 files, passed file/SQLite and eight-operation HPT2 parity, created and
rebuilt both shadow and hybrid checkpoints, verified its backup, rejected foreign lineage,
classified direct SQL as `UNMANAGED_REVIEW`, reconciled it to `VALID_DIRTY`, rebuilt the clean
checkpoint, and rolled a simulated interrupted transaction back to `CLEAN`.

## Remaining G4 Completion Work

The complete 367-test suite and full repository profile passed after the final release-manifest
refresh. The fresh source-complete external archive and two disposable maintainer rehearsals also
passed. GitHub run `33213018163` then exercised commit `150ef1670ab9c0df81f3029cac072e7434e9ed43`
across the 28-job Windows/POSIX matrix. Twenty-four jobs passed. The three shard-zero jobs reached
the release-profile bootstrap check and correctly refused the intentionally open G4/migration
state; one Windows shard passed its 52 behavioral tests but exceeded the 60-second aggregate budget
at 71.032 seconds. `CHG-CLOSED-004` records the now-complete migration boundary and terminal G4
state so the exact reconciliation rerun can prove the release profile. A clean rerun, including the
slow Windows shard, remains mandatory before publication.

The reconciled run `33213400441` cleared every staged-release gate and 27 of 28 jobs. Its sole
failure was again Windows/Python 3.11 shard 7/7: all selected tests completed successfully, but the
41-entrypoint bytecode smoke serialized Windows process startup and pushed aggregate validation to
94 seconds. `CHG-CLOSED-005` retains every `--help` exit-code and nonmutation assertion while using
a bounded eight-worker pool for those independent probes. Locally, the focused smoke fell from
2.152 to 0.539 seconds and the entire 52-test shard passed in 4.099 seconds against the unchanged
60-second release budget. The exact cross-platform rerun remains mandatory.
