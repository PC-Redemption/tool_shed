# Evidence: Tool Shed v0.29.13 release and maintainer synchronization

Status: verified
Type: evidence
Updated: 2026-08-26
Campaign: publish-and-synchronize-case-normalized-verification

## Release result

Tool Shed v0.29.13 publishes the Campaign 090 correction requiring automatic Markdown semantic
verification to apply one shared whitespace-and-case normalizer to both the document and every
expected phrase.

- Repair and lifecycle commit: `0b51b66fd780ff0be60c488b46858fc5bee91f6d`
- Content commit: `eae28bee58b3f282b28862bb3e45e7d43e092594`
- Provenance commit and annotated-tag target: `1940cddc3b70bb64c5f12289151cc94e09c69802`
- Annotated tag: `v0.29.13`
- Manifest release timestamp: `2026-08-26T17:47:51Z`
- GitHub Release publication: `2026-08-26T17:51:21Z`
- GitHub Release: `https://github.com/PC-Redemption/tool_shed/releases/tag/v0.29.13`

The branch and tag were pushed. The `Publish GitHub Release` workflow completed successfully and
verified the Release object. Independent version and GitHub checks reported v0.29.13 as current and
latest, non-draft, and non-prerelease with matching provenance.

## Validation

The full validator passed before the content commit and again after provenance was populated. Each
pass ran 297 unit tests and also passed Python compilation, manifest integrity, provider adapter
conformance, index regeneration, stale-path checks, work-state review, Program Roadmap validation,
temporary-workspace installation smoke, and template/example sanity.

## Maintainer skill synchronization

- Canonical source: `/home/jon/docker/tool_shed/skills/tool-shed`
- Installed target: `/home/jon/.codex/skills/tool-shed`
- Rollback backup: `/home/jon/.codex/skills/tool-shed.backup-20260826T175145Z`
- Source quick validation: passed
- Staged quick validation: passed
- Installed quick validation: passed
- Source-to-staged and source-to-installed `diff -qr`: empty
- Normalized source, backup, and installed tree hash:
  `8e77678cb10350c0d56c8a3bb0affbe0f9df846bbf2679e6a75045b06ae40814`

The portable skill bytes are unchanged from v0.29.12. The replacement still followed the complete
backup, staging, validation, and exact-parity procedure; retained skill context requires a fresh
Codex task to reload, while the already-authorized Core snapshot upgrade installs the released
dispatcher independently.

## Boundary

This campaign did not mutate Core or deploy Bactron. Campaign 085 retains explicit authorization
for the bounded Core snapshot/skill upgrade and fresh operator-assisted Windows proof, which may
resume immediately from this verified release.
