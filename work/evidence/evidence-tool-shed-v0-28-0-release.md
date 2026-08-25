# Evidence: Tool Shed v0.28.0 release

Status: complete
Type: evidence
Updated: 2026-08-25
Next Action: use the synchronized release for the M3 native Linux installed-use proof
Campaign: publish-minimum-usable-tool-shed-v0-28-0

## Release identity

- Version: `0.28.0`
- Content commit: `b777c1a57a287df4dd4f5fd48f0d77bd46b7d25f`
- Provenance commit: `4c0d2f755137daa31969a3c24969bcfa06560d0b`
- Annotated tag: `v0.28.0`
- Released at: `2026-08-25T19:24:07Z`
- Minimum updater protocol: `3`

## Verification

- Frozen candidate full validator: `python3 scripts/validate_tool_shed.py`; 260 tests passed,
  including manifest integrity, provider conformance, generated indexes, stale paths, work state,
  Program Roadmaps, and disposable-workspace smoke.
- Manifest check after provenance population: `SHED_VERSION.json` matched all 139 tracked release
  files.
- Canonical version check: local `0.28.0 (verified)`, canonical `0.28.0`, relation `current`.
- GitHub release workflow: run `32889420426` succeeded against provenance commit `4c0d2f7`.
- GitHub Release: `v0.28.0`, published `2026-08-25T19:26:34Z`, non-draft,
  non-prerelease: https://github.com/PC-Redemption/tool_shed/releases/tag/v0.28.0

No installed skill or downstream workspace snapshot was changed during this release campaign.
