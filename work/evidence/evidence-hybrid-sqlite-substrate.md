# Hybrid SQLite Phase-One Substrate Evidence

Status: passed
Evidence ID: EVID-G2-SUBSTRATE
Gate: G2-SUBSTRATE-LOOP-PROVEN
Campaign: implement-minimum-sqlite-operational-substrate
Target: canonical Tool Shed worktree, local work3 candidate
Candidate version: 0.34.0
Date: 2026-08-28

## Qualified Boundary

This evidence qualifies only the minimum ignored, per-worktree, shadow-mode SQLite substrate. It
does not qualify the HPT2 closed-loop vertical slice, G2 efficiency thresholds, a live maintainer
conversion, updater protocol 4, release, installed-skill synchronization, or client mutation.
Campaigns, queues, Program Roadmaps, milestones, general Markdown bodies, imported source bytes,
and legacy retirement remain file-owned.

## Development-Change Reconciliation

Qualification found that rebuilding the current checkpoint could not reproduce the newest recovery
ledger exactly: it generated a different checkpoint-ledger identity and omitted the matching export
row. `CHG-HYBRID-003` records the approved correction. The digest-bound checkpoint envelope now
carries its canonical path and preallocated UUIDv4 checkpoint/export ledger identities. The live
checkpoint and a fresh rebuild therefore contain identical portable operation, event, migration,
export, and checkpoint rows. The change preserves schema version 1 authority and reruns the G1
contract and G2 substrate evidence.

## Focused Qualification

The strict focused command was:

```text
PYTHONPATH=scripts:. python3 -W error::ResourceWarning -m unittest -v \
  tests.test_hybrid_state \
  tests.test_scripts.ScriptTests.test_installer_preserves_gitignore_and_adds_generated_evidence_convention \
  tests.test_docs_site
```

Result: 21 of 21 tests passed. The seven substrate scenarios prove:

- schema version/application identity, the checksummed `0 -> 1` migration ledger, foreign keys,
  and the frozen set of 54 accounting/immutability triggers;
- managed import and typed relationships with UUIDv4 public IDs, complete write counts, one revision
  per managed operation, structural changes, events, and unchanged imported source bytes;
- direct-SQL accounting and classification, immutable identity/history refusal, unjournaled/schema
  bypass detection, and project/worktree lineage refusal;
- managed interruption rollback with no partial domain, operation, revision, or lock residue;
- digest-bound canonical checkpoint generation, exact portable-ledger reproduction, clean fresh
  rebuild, tamper refusal, and semantic parity;
- byte-preserving refusal of a corrupt database; and
- verified SQLite backup API behavior, newest-three retention, and hybrid legacy-writer refusal.

The installer test proves it preserves existing `.gitignore` content while adding exactly one
`/.tool-shed/` runtime boundary. The documentation tests prove the updated 23-page operator site
and command reference still build and validate.

## Repository Qualification

The first full-profile pass reached 333 of 333 passing tests, provider conformance, deterministic
index regeneration, reconciled work state, and valid Program Roadmaps. It then stopped at the
intentionally stale bootstrap evidence created by `CHG-HYBRID-003`; no product failure was hidden.
After guarded evidence refresh, the unchanged candidate is rerun through the complete full profile
before Campaign 104 completion.

No `.tool-shed/state.sqlite3` was created in this maintainer worktree. All database mutation and
recovery tests used disposable Git repositories. No deployment, publication, release, installed
skill synchronization, client upgrade, or live authority conversion occurred.

## Universal Closed-Loop G4 Requalification

The separately authorized Universal Closed-Loop initiative exposed one additional recovery case:
a detected direct-SQL mutation might be deliberately retained after exact operator review rather
than discarded. `CHG-HYBRID-016` adds that bounded route without weakening detection. Acceptance
requires the expected project binding, `UNMANAGED_REVIEW` classification, exact current revision,
exact semantic digest, non-empty authorization reference, and summary. It appends an
`unmanaged-reconciled` event, clears the unmanaged marker, leaves the database checkpoint-due, and
cannot return to `CLEAN` until a new deterministic tracked checkpoint is written.

On 2026-08-28 the focused Hybrid, maintainer-conversion, updater-protocol-4, and outcome suites
passed 33 of 33 tests. The direct-SQL test separately proved stale-digest refusal, authorized
acceptance, event provenance, checkpoint generation, and a fresh rebuild with the exact accepted
domain digest. A verified live backup and revision-44 checkpoint then rebuilt cleanly with domain
digest `92e9a708fcbb060ceee58078efbbb740582713aca79e20a627251b142b724ea6`.
