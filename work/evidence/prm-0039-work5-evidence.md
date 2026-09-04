# PRM-0039 Work5 release and production evidence

- Content commit: `e9288eca37cd52ff9a65be03e67db41b662c255c`
- Provenance commit: `e490d6cf5c22d0051930e97fe9593bb6c46f4198`
- Release: `v0.46.0`, published non-draft and latest at
  `https://github.com/PC-Redemption/tool_shed/releases/tag/v0.46.0`
- Exact content-SHA GitHub Validate run: `33907816152`, successful across the Ubuntu/Windows and
  Python matrix.
- Publish GitHub Release run: `33908268456`, successful.
- Production web: `tool-shed-dashboard:v0.46.0`; Django production readiness, local health,
  public HTTPS health, and dashboard authentication redirect passed. The pre-v0.46 deployment is
  retained at `release-backups/pre-v0.46.0-20260904T1853Z`.
- Linux production client: official attested updater moved the exact disposable workspace from
  verified v0.45.0 to v0.46.0 while preserving Hybrid state and work; transaction
  `e41034fa709358d0109c25f1`.
- Windows production client: the protocol-4 guard first refused an uncheckpointed synthetic
  database, then the official attested updater moved the clean exact disposable workspace from
  verified v0.45.0 to v0.46.0 while preserving Hybrid state and work; transaction
  `a208a576020fb4c7e4288d0e`.
- Release-lane manifest `07e467d8-ffd8-45b7-9dbc-e70ac62112a3` reports all development and
  production lanes verified with no blockers.
