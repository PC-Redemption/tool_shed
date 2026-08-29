# Evidence: Tool Shed v0.29.11 release and maintainer-skill synchronization

Status: verified
Type: evidence
Updated: 2026-08-26
Campaign: publish-explicit-reference-preparation-repair

## Verified release

- Version: `0.29.11`.
- Repair commit: `290f75cc43eb46758f33fbaeab1fb6f583692cba`.
- Content commit: `4a483253e7a0b828008f1fc453025e31a05d6795`.
- Provenance commit: `1554a8711859c0e6667a3291c74c183ee02a3a6d`.
- Annotated tag: `v0.29.11`.
- Released at: `2026-08-26T16:45:46Z`.
- GitHub Release: `https://github.com/PC-Redemption/tool_shed/releases/tag/v0.29.11`, verified
  non-draft, non-prerelease, and latest.
- The live canonical manifest reported v0.29.11 with the exact content commit and tag; local and
  canonical version relation was `current`.
- GitHub accepted the branch and annotated tag but did not register a release workflow run after
  repeated checks. The documented fallback validated the exact latest two-commit tag with
  `prepare_github_release.py`, created the missing Release with `gh release create --verify-tag
  --latest`, and reverified both public surfaces.

## Qualification

- `python3 -m unittest tests.test_app_server_dispatch`: 20 focused tests passed.
- Read-only application of the patched builder to actual Core Campaign 022 reduced deterministic
  preparation context from 79,875 to 26,821 bytes while retaining the requested guide, related
  validator source/test, and project instructions and excluding the unrelated Core artifacts.
- `python3 scripts/validate_tool_shed.py` passed before the content commit and again after
  provenance. Each run passed 294 tests plus provider conformance, generated-index refresh,
  stale-path checks, work-state review, Program Roadmap validation, temporary-workspace smoke, and
  template/example sanity.

## Installed maintainer skill

- Released source: `/home/jon/docker/tool_shed/skills/tool-shed`.
- Installed target: `/home/jon/.codex/skills/tool-shed`.
- Rollback backup: `/home/jon/.codex/skills/tool-shed.backup-20260826T164838Z`.
- Source, staged copy, and final installed target passed the system skill validator.
- The source, prior installed copy, rollback backup, and final installed target were byte-identical;
  recursive diffs were empty and each normalized tree hash was
  `8e77678cb10350c0d56c8a3bb0affbe0f9df846bbf2679e6a75045b06ae40814`.

## Fresh-session smoke equivalence

The v0.29.11 patch changes dispatcher source and tests only; it does not change any installed skill
byte. The fresh ephemeral Codex smoke recorded for v0.29.10 therefore applies without qualification
to the exact v0.29.11 installed-skill tree hash. Repeating that identical smoke would consume about
36,000 input tokens while observing no changed client input, so it was intentionally not replayed.
The installed client remains fresh-session verified by immutable content equivalence, while the
changed dispatcher behavior is independently covered by the focused Core-shaped regression and
both full release validators.

## Result and boundary

Campaign 087's release and maintainer-synchronization gate passes. Tool Shed v0.29.11 is the
verified latest stable release, and the maintainer installed skill is backed up, validated, and
exactly synchronized. Core remains on v0.29.10 at this boundary; its separately authorized snapshot
upgrade and Windows first-pass proof resume in Campaign 085. No Bactron deployment occurred.
