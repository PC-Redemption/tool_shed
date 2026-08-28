# Hybrid SQLite release-prerequisite qualification

Status: passed
Type: evidence
Updated: 2026-08-28
Next Action: publish and verify Tool Shed 0.34.0, then append release evidence without closing the client-canary gate
Campaign: publish-hybrid-state-release-and-sync-maintainer-skill

## Scope

This record qualifies the prerequisites discovered while executing Campaign 107. It does not claim
that Tool Shed 0.34.0 is published, that the installed maintainer skill is synchronized, that a
disconnected client was upgraded, or that G4 and the initiative are terminal.

## Candidate lineage

- `43da1fc`: implemented updater protocol 4 and staged bootstrap release-gate semantics.
- `b7d63f7`: reconciled `CHG-HYBRID-005` and assigned its HPT2 import identity.
- `d9fb8d7`: preassigned the import identities needed to close the append-only reconciliation
  recursion before `CHG-HYBRID-007` was recorded.

## Verified behavior

- Protocol 3 refusal of a protocol-4 manifest is tested independently of workspace mutation.
- Protocol 4 accepts a protocol-4 manifest and retains the protocol-3 transactional file/work
  convergence lifecycle.
- A file-authority workspace upgrades without creating `.tool-shed/state.sqlite3`.
- A CLEAN live hybrid database is WAL-checkpointed, copied through SQLite's backup API, audited,
  rebuilt from the tracked checkpoint in a disposable shadow, and re-audited with unchanged
  project, mode, revisions, domain digest, and schema/trigger digest.
- Post-install protocol-4 validation requires exact database parity, structural bootstrap
  verification, and a non-INVALID doctor verdict.
- The declared controlled-publication gate requires terminal G1-G3 scopes and completed M1-M3
  migration/upgrade obligations. G4 and the initiative remain open for release and client-canary
  evidence.
- A material change may retain `pending` rerun evidence only when that evidence is covered by the
  change and belongs to an explicitly nonterminal verdict scope. Stale, failed, uncovered, or
  pending evidence behind a terminal gate remains invalid.

## Evidence-response history

The first full rerun refused `CHG-HYBRID-005` because its HPT2 assigned ID was missing. The second
full rerun refused `CHG-HYBRID-006` for the same reason. The final repair preassigned IDs for both
the existing record and its closing reconciliation record before appending `CHG-HYBRID-007`.
This preserves the failed observations rather than rewriting history to imply a first-pass success.

## Results

- Focused bootstrap, hybrid-state, updater-protocol, validation-profile, and updater integration
  tests passed after implementation.
- HPT2 closed-loop parity: 6/6 tests passed after the preassigned-ID reconciliation.
- Focused bootstrap closure policy: 7/7 tests passed, including staged pending-evidence admission
  and terminal-gate refusal.
- Complete unit suite: 348/348 tests passed in 73.947 seconds.
- No tag, GitHub Release, installed-skill replacement, or disconnected-client mutation occurred
  during this prerequisite qualification.
