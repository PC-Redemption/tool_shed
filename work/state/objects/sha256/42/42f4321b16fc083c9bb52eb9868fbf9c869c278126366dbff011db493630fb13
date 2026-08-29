# Evidence: Tool Shed v0.29.12 release and maintainer synchronization

Status: verified
Type: evidence
Updated: 2026-08-26
Campaign: publish-and-synchronize-file-change-handoff-repair

## Release result

Tool Shed v0.29.12 publishes the locally proven correction that preserves deterministic
verification when the first completed `fileChange` coincides with the model-turn ceiling and
requires whitespace-robust automatic documentation verification.

- Repair commit: `72959cea7c5c36b0e5f51823c07c92dc5b3f6fda`
- Content commit: `dfacc4459ad9e63b753086897ae267f2d7c153a3`
- Provenance commit and annotated-tag target: `2f941c742d4d71a41d659d02c207199fa1e99dfa`
- Annotated tag: `v0.29.12`
- Release timestamp: `2026-08-26T17:17:13Z`
- GitHub Release: `https://github.com/PC-Redemption/tool_shed/releases/tag/v0.29.12`

The branch and tag were pushed. The automated release workflow did not register the new tag, so
the documented `prepare_github_release.py` and `gh release create --verify-tag --latest` fallback
created the missing Release object. Independent API verification reported v0.29.12 as the latest,
non-draft, non-prerelease release, and the live canonical manifest reported version relation
`current` with the expected content commit and provenance.

## Validation

The full validator passed before the content commit and again after provenance was populated.
Each pass ran 297 unit tests and also passed Python compilation, manifest integrity, provider
adapter conformance, index regeneration, stale-path checks, work-state review, Program Roadmap
validation, temporary-workspace installation smoke, and template/example sanity.

## Maintainer skill synchronization

- Canonical source: `/home/jon/docker/tool_shed/skills/tool-shed`
- Installed target: `/home/jon/.codex/skills/tool-shed`
- Rollback backup: `/home/jon/.codex/skills/tool-shed.backup-20260826T171933Z`
- Source quick validation: passed
- Staged quick validation: passed
- Installed quick validation: passed
- Source-to-installed `diff -qr`: empty
- Normalized source, backup, and installed tree hash:
  `8e77678cb10350c0d56c8a3bb0affbe0f9df846bbf2679e6a75045b06ae40814`

The portable skill bytes did not change between v0.29.11 and v0.29.12. The prior fresh-session
smoke therefore remains applicable by exact immutable tree identity; repeating the same model run
would spend tokens without testing changed behavior.

## Boundary

This campaign did not change Core or deploy Bactron. Campaign 085 retains the earlier explicit
authorization for the Core snapshot/skill re-upgrade and operator-assisted Windows first-pass
proof, which resumes after this release boundary.
