# Evidence: Tool Shed v0.29.10 release and maintainer-skill synchronization

Status: verified
Type: evidence
Updated: 2026-08-26
Campaign: publish-and-synchronize-first-pass-app-server-preparation

## Verified release

- Version: `0.29.10`.
- Content commit: `4ca5b59f537a4d2bad0b95365f84c08d481f0e68`.
- Provenance commit: `e0b579e3c2877d451e1ad66906323da47d8eeaf6`.
- Annotated tag: `v0.29.10`.
- Released at: `2026-08-26T15:45:19Z`.
- GitHub Release: `https://github.com/PC-Redemption/tool_shed/releases/tag/v0.29.10`, verified
  non-draft, non-prerelease, and latest.
- The live canonical manifest byte-matched the local manifest and reported v0.29.10 with the exact
  content commit and tag. The local and canonical version relation was `current`.
- The release workflow did not register a v0.29.10 run after the branch and annotated tag were
  pushed. The documented release fallback validated the latest two-commit tag with
  `prepare_github_release.py` and created the missing GitHub Release explicitly with `gh release
  create --verify-tag --latest`; both public surfaces were then rechecked.

## Qualification

The first full validator exposed one ordinary focus-area migration defect: an approved migration
updated the campaign Outcome header but left the legacy focus phrase in its App Server Preparation
Contract objective. Campaign 084 repaired the migration to regenerate stable preparation intent
after an approved semantic header rewrite. The focused regression test passed.

After refreshing the unpublished manifest, the complete validator passed before the content commit
and again after provenance was populated. Each successful run passed 293 tests plus provider
conformance, generated-index refresh, stale-path checks, work-state review, Program Roadmap
validation, temporary-workspace smoke, and template/example sanity.

## Installed maintainer skill

- Released source: `/home/jon/docker/tool_shed/skills/tool-shed`.
- Installed target: `/home/jon/.codex/skills/tool-shed`.
- Rollback backup: `/home/jon/.codex/skills/tool-shed.backup-20260826T154825Z`.
- Source, prior installed target, backup, staged copy, and final installed target passed the system
  skill validator where applicable.
- Reviewed pre-deployment drift was exactly `references/campaign-routes.md`.
- Final `diff -qr` between released source and installed target was empty.
- The prior installed directory remained recoverable during replacement; the durable rollback copy
  above was not altered.

## Fresh-session first-pass smoke

A fresh ephemeral Codex task used `gpt-5.6-luna` with low reasoning in a read-only empty temporary
workspace. It loaded the installed Tool Shed skill, reported local Tool Shed v0.29.10 with verified
integrity, and confirmed that the installed contract:

- automatically prepares a ready campaign with no capsule at dispatch;
- supplies explicit expected-path starting states;
- forbids worker `commandExecution`; and
- hands verification to Tool Shed after the first completed `fileChange`.

The smoke changed no files, did not run a campaign, publish, synchronize, or browse, and consumed
36,458 tokens.

## Result and boundary

G12-FIRST-PASS-RELEASE-USABLE passes. The Linux-proven first-pass App Server preparation contract is
publicly released and available to fresh maintainer sessions. Bactron Core was not upgraded and no
application was deployed; Core adoption remains separately authorized work.
