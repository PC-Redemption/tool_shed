# IDEA-0023 v0.50.0 Work5 Evidence

Status: passed
Recorded: 2026-09-06
Release lane: `idea23-v0.50.0`
Work2 implementation: `f304e230881a9ad23342aa0338d4b2967df8b2fe`
Development candidate: `92cf9167848f7f3459690e76ccdb1c6c050d11c3`

## Development Qualification

- Canonical release profile: 620/620 isolated tests passed with eight workers; provider adapter,
  database-owned view, stale-path, work-state, roadmap, bootstrap-closure, fresh-install, template,
  and example checks all passed in 36.999 seconds.
- Web: exact candidate image `tool-shed-dashboard:dev-92cf9167848f`, image digest
  `sha256:9cbec160d0af1bb1ebf40a3b2820fde8ef7973bed9e7687ce1e1247792c932b3`.
  Development docs and dashboard health returned HTTP 200, an authenticated render exercised the
  new Work controls, and the production regression health endpoint remained HTTP 200.
- Linux: the disconnected candidate archive has SHA-256
  `cd4939586fdbbc73794e8b7da5ae0875bb94d04a8744ebd99eb7d91f4dd7a2a1`; 83 targeted tests,
  strict snapshot integrity, and strict Doctor passed in `/home/jon/dev/ts_linux_test_bed`.
- Windows: the identical archive passed the same 83 targeted tests, strict snapshot integrity, and
  strict Doctor under Python 3.14 in `E:\\dev\\ts_windows_test_bed` on `GOGETTER`.
- Both disposable parent repositories remained clean. Recoverable prior snapshots are retained as
  ignored `tool_shed.backup-idea23-92cf916.tar` directories.

## Release And Production Qualification

- Frozen content commit `880eb6bd705b632d6fd19d42b2c354c00620e7bf` passed exact-SHA
  GitHub Validate run `34053856250` across the complete Ubuntu and Windows matrix.
- Provenance-only commit `f4d5ad8d332306b4053983f86a579b1dabe7ece0` was tagged `v0.50.0`.
  Publish GitHub Release run `34054186989` passed and the non-draft, non-prerelease release became
  latest at `https://github.com/PC-Redemption/tool_shed/releases/tag/v0.50.0`.
- Web: a validated encrypted PostgreSQL backup and filesystem rollback snapshot preceded the
  deployment. Production runs `tool-shed-dashboard:v0.50.0` with image digest
  `sha256:8dac13d91e71e3bbef3616a34418a5ed5bf3da5ad8398ce5000b02d47800409b`;
  all containers are healthy, host-local health is HTTP 200, and public HTTPS health and docs are
  HTTP 200 through `X-Rookaro-Route: ts.rookaro.com`.
- Linux and Windows: the guarded updater independently selected the official `v0.50.0` release,
  verified its provenance and manifest, chose the attested focused-client smoke, preserved Hybrid
  state, installed content commit `880eb6bd705b632d6fd19d42b2c354c00620e7bf`, and returned strict
  Doctor `HEALTHY`. Both parent repositories remained clean.
- Immediate convergence: explicit enqueue sequence 10586 completed at
  `2026-09-06T19:16:54.779649Z` and the existing persistent worker delivered it at
  `2026-09-06T19:17:02.729986Z` with zero attempts. No manual worker, manual report drain, or safety
  pass ran. Subsequent automatically generated events also drained and pending count returned to
  zero.
- The authenticated production Work page rendered HTTP 200 from client v0.50.0 with the strict
  IDEA-0023 → MAP-0031 → PRM-0043 → CAMP-0169 / CAMP-0170 hierarchy, exactly one Next marker on
  CAMP-0170, no Needs placement group, and command menus on every displayed row. The hosted
  snapshot reported all 267 local artifacts without truncation.

## Final Reconciliation

- All six development and production lane records are verified in
  `work/evidence/release-lanes/idea23-v0.50.0.json`; structured production evidence is recorded in
  `work/evidence/release-v0.50.0-production.json`.
- CAMP-0170, PRM-0043, MAP-0031, and IDEA-0023 completed from the leaves upward with satisfied,
  terminal, recursively closed, and reconciled outcomes. CAMP-0169 was already reconciled by the
  Work2 checkpoint.
- Release cohort `0376b144-378b-4600-b9e9-c17737e01fb6` recorded `v0.50.0` against frozen content
  commit `880eb6bd705b632d6fd19d42b2c354c00620e7bf` and finalized with four registered candidates in
  `released-reconciled` disposition.
- The final reconciliation report, sequence 10600, auto-drained in 1.786 seconds with zero attempts
  and no manual worker or safety pass. Production reports the entire IDEA-0023 chain as
  completed/satisfied/reconciled; the default Remaining tree excludes it while All/List retains it
  for audit history.
- GitHub issue review found #57 directly related. A release note was added at
  `https://github.com/PC-Redemption/tool_shed/issues/57#issuecomment-5561559808`; the issue remains
  open because its broader type-specific semantic-projection scope extends beyond this release.
