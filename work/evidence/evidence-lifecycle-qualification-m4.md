# Evidence: IDEA-0020 M4 Development Fault Namespace

Status: passed
Recorded: 2026-09-03
Campaign: CAMP-0153
Program Roadmap: PRM-0038, M4-DEVELOPMENT-FAULT-NAMESPACE
Candidate commit: `3e3771d9d1c7a44afdd430278eb7de1a50a42850`
Candidate version: `0.43.0` (unpublished development cohort)
Environment: development only

## Result

The exact candidate implements a purpose-bound qualification-run root, manifest-owned synthetic
descendants, `qualification:write` credentials, application and database development-only guards,
operational-view exclusion, a separate authenticated Qualification Runs view, expiry without
lineage loss, preview-bound exact purge, stale-preview refusal, and retained tombstones.

After those controls passed, QH-009 and structurally faithful QH-010 were driven through the shared
hosted-development database from both disposable operating-system fixtures. All four independent
oracle results passed. No operational reporter credential was used, and no qualification project
appeared in the operational project list.

No source was pushed, no release was published, and no production service, database, fixture, or
installed client was changed.

## Exact Development Targets

| Target | Installed/served candidate | Result |
| --- | --- | --- |
| Linux fixture | `sup:/home/jon/dev/ts_linux_test_bed`; snapshot `3e3771d9d1c7`; 271-file manifest | PASS |
| Windows fixture | `GOGETTER:E:\dev\ts_windows_test_bed`; snapshot `3e3771d9d1c7`; 271-file manifest | PASS |
| Development web | compose project `tsrookarocom-dev`; image `tool-shed-dashboard:dev-3e3771d9d1c7` | healthy |

Rollback snapshots remain at `tool_shed.before-idea0020-3e3771d` in both disposable fixtures. The
installed personal Codex skill was not synchronized because this Work2 route owns only project
development lanes.

## Qualification Matrix

| Scenario / origin | Sealed run | Checks | Purged descendants | Result SHA-256 |
| --- | --- | ---: | ---: | --- |
| QH-009 Linux | `tsqh-22896e73c8bb9b11b39652db` | 16/16 | 12 | `5beeb8a182cc0808f2746da8b6cab18dbefe80bae5d854e335ffb52a7074d5df` |
| QH-010 Linux | `tsqh-5618a0194ca46fd0b2bb1982` | 17/17 | 11 | `bb7a46a1cdaf1a086bb9fda181f26449225f3c31142e369564521c087bda97e2` |
| QH-009 Windows | `tsqh-6816facebf67887bec6f905e` | 16/16 | 11 | `f5d98b49f96fa9896b7a178b178990f54debdcd407a8e903432487b5b2ad314e` |
| QH-010 Windows | `tsqh-4cc03448d58159e783d77cd6` | 17/17 | 11 | `0a40153422f895a2418664637f43111941f0a5b493d5eaded25e64094a81b0ca` |

The generated manifests, local observations, transport records, hosted exports, browser captures,
expiry records, purge previews, purge records, and compact results remain below
`work/evidence/generated/idea0020-m4/`. They contain no reporter or browser credential.

## Qualified Claims

- A strict manifest creates exactly one development-only qualification root and one scoped
  credential. Qualification credentials are refused by the operational endpoint, and operational
  credentials are refused by the qualification endpoint.
- Qualification projects and all of their aggregates are excluded from operational counts,
  searches, navigation, project pages, attention, versions, App Server, Work Efficiency, and live
  revision state. They are visible only to an authenticated user in the development Qualification
  Runs view.
- Both platforms preserved outage ordering, accepted the newest report on convergence, handled
  duplicate and stale delivery deterministically, and matched local identities, artifacts,
  closure fields, lineage fields, and receipt cardinality in hosted storage.
- Expiry revoked the write credential while retaining the root and descendants. Purge required an
  exact preview token and deleted only manifest-owned descendants.
- The Linux QH-009 run inserted one controlled receipt after preview. Applying the old token exited
  nonzero with `qualification purge preview is stale`; a new preview then purged all 12 exact
  descendants.
- Post-purge export retained all four roots as `purged` tombstones with their descendant counts and
  digests while each root's project set was empty.
- A final authenticated Chrome observation showed exactly `ts_linux_test_bed` and
  `ts_windows_test_bed` in the operational view, working links, and the requested purged tombstone
  in the separate Qualification Runs view. Its record SHA-256 is
  `0843de60cc3298cc286454b2e56a3e49e2b7c64639bb1daa953cac21150bcaf0`.

## Defect Found and Closed

The first live QH-009 handoff exposed a manifest-path mismatch: sealing correctly stored platform
under `fixture.platform`, while the qualification-root builder attempted to read
`target.platform`. The candidate now reads the sealed fixture field, and a regression test proves
both root and instance platform values. The failed attempt ingested no hosted data.

The first browser attempt also proved the interactive workstation's localhost tunnel was not
available to the SSH service account. The qualification used the already approved LAN-only
development endpoint `http://192.168.7.5:8443`; a direct Windows health check and every subsequent
browser run passed. This was an access-context distinction, not a product defect.

## Candidate Validation

The frozen candidate was validated from a clean detached worktree:

```text
python scripts/validate_tool_shed.py --profile release
SHED_VERSION.json matches 271 tracked files.
546 of 546 tests passed in 24.854s with 8 workers.
Provider adapter, database view, stale-path, work-state, Program Roadmap, bootstrap-closure,
temporary-workspace, template, and example checks passed.
tool_shed release validation passed in 32.680s.
```

The shared development health endpoint returned the expected healthy development payload after
the final image deployment. The source workspace's unrelated pre-existing edits were excluded from
the detached candidate and are not part of this evidence. Temporary reporter/browser credentials,
container token files, and run-owned credential state were removed after the tombstones were
captured.

## Boundary and Next Step

This completes `G4-DEVELOPMENT-ONLY-FAULT-NAMESPACE` and makes
`M5-EVIDENCE-SCALE-AND-ROUTE-SMOKE` ready. Work3 candidate freeze, push, publication, and Work5
production promotion remain separate explicit routes.
