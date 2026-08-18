# Tool Shed v0.22.0 release and published-upgrade qualification

Status: complete
Type: evidence
Updated: 2026-08-18
Next Action: none
Parent: work/00-campaigns/completed/027-publish-and-verify-tool-shed-v0-22-0.md

## Outcome

Passed. Tool Shed v0.22.0 was frozen, qualified twice, published from traceable provenance,
validated on GitHub-hosted Ubuntu and Windows runners, exercised through the published updater from
an exact v0.21.0 installation, and verified against the combined live documentation target. Issues
#34 through #39 were closed only after their individual acceptance evidence was present.

## Release identity

- Version: `0.22.0`
- Content commit: `501877657bf0902d7c0caafc490cc35b6bc64f33`
- Provenance commit and annotated-tag target: `9f75067f7b5d14a83fe514f60e1a4cfed6b8b9c4`
- Annotated tag object: `577f3f78dc892d7194c7b8228c4df56f813352ef`
- Release timestamp: `2026-08-18T15:22:01Z`
- GitHub publication timestamp: `2026-08-18T15:25:31Z`
- GitHub release: https://github.com/PC-Redemption/tool_shed/releases/tag/v0.22.0

The canonical raw manifest reports the same version, content commit, tag, and release timestamp.
The local canonical checkout passes strict verification against that published manifest.

## Frozen candidate inventory

The content range from v0.21.0 through the frozen candidate contains these nine attributable commits:

1. `d076404` Start compact workflow guide campaign
2. `9a6988f` Publish compact Tool Shed operator guide
3. `28d6471` Complete compact workflow guide campaign
4. `0496a61` Left-align reference commands and bust stale assets
5. `33eb452` Add workspace identity and doctor safeguards
6. `56e3574` Complete workspace doctor campaign
7. `93c0142` Define nested Tool Shed cycle state
8. `be58aa1` Complete nested cycles campaign
9. `5018776` Freeze Tool Shed v0.22.0 content candidate

The tracked diff contains 63 paths. Every path belongs to the compact public workflows and
layout/cache follow-up; campaign-number upgrade convergence; public help links; targeted and
wildcard queue batches; workspace identity and mutation fencing; nested cycle ownership; workspace
doctor; their tests and documentation; or the release/campaign records that account for them.
Campaigns 024, 025, 026, 028, 029, 030, and 031 retain their own completion evidence.

## Qualification and publication

- The complete local validator passed twice against the frozen content: 156 tests plus provider,
  manifest, index, stale-path, work-state, roadmap, and smoke checks.
- The documentation build passed with 22 pages and 61 command entries.
- Release workflow run 32154207120 passed:
  https://github.com/PC-Redemption/tool_shed/actions/runs/32154207120
- Tag validation run 32154206930 passed all four Ubuntu/Windows and Python 3.11/current jobs:
  https://github.com/PC-Redemption/tool_shed/actions/runs/32154206930
- Main validation run 32154207161 passed the same four-job matrix:
  https://github.com/PC-Redemption/tool_shed/actions/runs/32154207161
- The GitHub release is latest, non-draft, and non-prerelease. Its notes identify the exact content
  commit and provenance.

The successful workflows emitted a nonblocking Node 20 action-runtime deprecation annotation. The
verified remaining maintenance gap is tracked for a later revision in issue #40:
https://github.com/PC-Redemption/tool_shed/issues/40

## Published updater verification

A disposable workspace inside the generated-evidence boundary was initialized from an exact,
disconnected v0.21.0 snapshot. The updater script from the published v0.22.0 release then upgraded
that installation against the canonical GitHub release in one transaction.

- Selected tag: `v0.22.0`
- Selected tag commit: `9f75067f7b5d14a83fe514f60e1a4cfed6b8b9c4`
- Selected content commit: `501877657bf0902d7c0caafc490cc35b6bc64f33`
- Canonical manifest match: true
- Root work preserved: true
- Excluded paths preserved: true
- Work topology converged: true
- Created fixture project identity: `996a7b64-abeb-4d9e-a53c-c3e7e5c6e272`

The installed snapshot passed strict local v0.22.0 verification. Its identity resolved to the
fixture root. Campaign status had no findings; wildcard selection resolved a stable empty snapshot;
roadmap overview and queue state agreed on the owner cycle and exact next transition. Public help
links were present in the installed provider guidance and local documentation. Doctor reported no
integrity error after test-generated Python bytecode was suppressed; its sole warning correctly
identified the disposable fixture's installer-created identity and provider instructions as not
checkpointed in the fixture repository.

## Production documentation verification

- The built static tree exactly matched the combined live deployment tree.
- Local health returned `healthy`.
- Public direct loads returned HTTP 200 for `/help/`, `/help/work-level-customization/`,
  `/help/campaigns/`, `/guide/queue-and-select/`, and `/ref/`.
- The live customization guide exposed `before`, `after`, `run_default`, and `work_model` guidance.
- The live queue guide exposed targeted, stable campaign-reference, and wildcard selection forms.

## Issue disposition

- #34 closed after the complete customization guide, reference links, tests, release, and live-site
  checks passed: https://github.com/PC-Redemption/tool_shed/issues/34
- #35 closed after transactional convergence coverage and the published updater passed:
  https://github.com/PC-Redemption/tool_shed/issues/35
- #36 closed after packaged offline help and public-link behavior passed:
  https://github.com/PC-Redemption/tool_shed/issues/36
- #37 closed after shared cycle-state behavior passed in the published installation:
  https://github.com/PC-Redemption/tool_shed/issues/37
- #38 closed after identity-bound routing and mutation tests plus upgrade identity creation passed:
  https://github.com/PC-Redemption/tool_shed/issues/38
- #39 closed after the released doctor produced the expected compact workspace verdict:
  https://github.com/PC-Redemption/tool_shed/issues/39
