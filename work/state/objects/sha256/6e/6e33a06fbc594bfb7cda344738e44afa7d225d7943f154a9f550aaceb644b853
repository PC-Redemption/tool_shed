# Evidence: Hybrid SQLite Disconnected Production Canary

Status: passed
Type: evidence
Updated: 2026-08-28
Campaign: qualify-disconnected-hybrid-production-canary
Gate: G4-RELEASE-CANARY-PROVEN

## Qualification Boundary

Campaign 108 used one disposable Tool Shed-owned client in a secure temporary directory. The
client had local Git, zero remotes, an isolated `CODEX_HOME`, and an isolated `GH_CONFIG_DIR` whose
`gh auth status` reported no authenticated hosts. No unrelated project content was inspected or
copied. The only retained evidence is this sanitized summary.

## Released Upgrade Sequence

- Installed the published `v0.33.0` snapshot with the released updater (`3b96885fc056219aa2ab1c7c`).
- Proved the protocol-3 updater refused the protocol-4 `v0.34.0` release before mutation
  (`65590aecbb661bf7a77fb930`); the snapshot digest was unchanged.
- The first protocol-4 attempt intentionally reached post-install validation and rolled back after
  the synthetic fixture exposed uncommitted generated work. Transaction
  `25232178c8c4b68a8827cf4d` records `rollback_outcome: restored`, proving restoration from the
  updater-owned external archive. The fixture was committed and the normal retry succeeded
  (`3ed77b1fe08a7cfa8ff537c3`).
- Upgraded the live hybrid client from `v0.34.0` to `v0.34.1`
  (`573deaa790c51f1fd0b6f8e9`) and then to final `v0.34.2`
  (`39b136193a26c9e57da4aa0a`). Both protocol-4 transactions preserved work, checkpoint lineage,
  storage mode, project identity, and semantic state.
- Installed the matching Tool Shed Codex skill only inside the isolated canary home on the
  same-version `v0.34.2` transaction (`cb37cc5213700634e5ff9a55`). Its `SKILL.md` SHA-256 exactly
  matched the released snapshot.

## Canary Evidence-Response Repairs

The canary found two real release defects instead of waiving them:

1. Normal Python CLI imports could create `__pycache__` in an installed snapshot.
   `CHG-HYBRID-013` made every shipped Python entry point suppress import bytecode and added a
   regression over every CLI.
2. The focused and full validators explicitly invoked `py_compile`, which bypassed the import
   control. `CHG-HYBRID-014` moved compilation outputs to external temporary directories and made
   the tests remove inherited bytecode environment controls.

The final `v0.34.2` release identifies content commit
`c8e3f41c6f4587c047f10472074ede8d1522c693` and provenance commit
`aa4a9e3f07bdc3ee8fbdf5d5ccf6bdd641532910`. The exact content commit passed the complete
Ubuntu/Windows, Python 3.11/3.x Validate matrix in GitHub Actions run `33205642879`; the published
GitHub Release is non-draft and non-prerelease. Local release qualification passed 352/352 tests,
including validator nonmutation with `PYTHONDONTWRITEBYTECODE` and `PYTHONPYCACHEPREFIX` absent.

## Hybrid Closure And Recovery

- Promoted a synthetic Idea Brief into a Project Map, imported both under immutable UUIDv4 IDs,
  and recorded the typed `produces` relationship.
- Activated hybrid authority at revision 3. The live database, tracked checkpoint, updater backup,
  and independently rebuilt database all audited `CLEAN` with domain digest
  `0199516e7ea8cf913d3474ab0a6bbd9299a74efa0c62c06c03d26c2b61736e57` and checkpoint digest
  `0b2fd05e22ad35551fdf50d593159c0e254dfdcdf033256fff1cb4b71a57573b`.
- The final verified SQLite backup SHA-256 was
  `0faccc61f216069edf24b3cf947655ebb2571e566ef553726bfebb47cf7d82b6`.
- Completed and explicitly classified the bounded synthetic map. Final doctor state was `HEALTHY`,
  internally consistent, with zero findings, zero warnings, zero owner decisions, a clean Git
  worktree, and zero unclassified work.
- A downgrade attempt from `v0.34.2` to `v0.33.0` refused at release selection
  (`abe3486542ab1483dc028915`). Before/after hashes were identical for the snapshot
  (`6c2fb5533f42d87b0931c2984ccc64f3b393f7f0e04c601deb6f94c693fe9632`), live database
  (`e7cc3343dff8b518f6ebae833d0bd73f18d494707eb9075698771851b012615c`), and tracked checkpoint
  (`285b696ee9aec0bfcc1540b590ddda373927bde26150338e3056097113b4dc5b`).

## Integrity, Efficiency, And Soak

After normal updater, focused-smoke, strict-integrity, hybrid audit, rebuild, doctor, and profiling
execution, the final snapshot contained no `__pycache__`, `.pyc`, or `.pyo` artifact. Three soak
rounds from `2026-08-28T19:55:40Z` through `2026-08-28T19:55:47Z` each returned focused smoke
passed, hybrid audit `CLEAN`, unchanged revision and domain digest, doctor `HEALTHY`, and zero
findings. All seven performance probes returned `ok` with no warning. The two file-authoritative
cycle documents occupied 3,789 bytes; the compact managed audit was 547 bytes, an 85.56 percent
reduction for the bounded status query while preserving the governing files.

## Verdict

`EVID-G4-CANARY`: passed. The released protocol-4 path proved old-updater refusal, guarded install
and hybrid upgrade, exact reconstruction, closed-loop identity and relationship preservation,
external backup and restored rollback, verified SQLite backup, safe downgrade refusal, isolated
skill synchronization, no authenticated GitHub dependency, strict bytecode-free integrity, and a
zero-finding soak. Broad fleet rollout and retirement of retained source files remain outside this
campaign.
