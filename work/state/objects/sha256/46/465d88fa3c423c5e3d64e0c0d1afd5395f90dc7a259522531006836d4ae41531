# Evidence: Tool Shed v0.30.0 release and maintainer synchronization

Status: complete
Type: evidence
Updated: 2026-08-27
Next Action: none
Project Map: work/maps/map-passive-app-server-dogfooding.md
Campaign: publish-and-synchronize-passive-app-server-dogfooding

## Release result

Tool Shed v0.30.0 publishes passive App Server dogfooding with one protected user-local
preference, deterministic route precedence, same-action GUI fallback before mutation,
mutation-aware reconciliation without replay, and sanitized best-effort event records.

- Content commit: `a13de638837415002ee0741cae8ffffe7e22b3b2`
- Provenance commit and annotated-tag target: `257f6578b7f3778be78c2cc3f7e5aa829e78eb03`
- Annotated tag: `v0.30.0`
- Manifest release timestamp: `2026-08-27T12:08:37Z`
- Release workflow: `33070626608`, successful
- GitHub Release publication: `2026-08-27T12:11:53Z`
- GitHub Release: `https://github.com/PC-Redemption/tool_shed/releases/tag/v0.30.0`

The branch and tag were pushed. The raw canonical manifest reports v0.30.0 with the exact content
commit and tag above. The GitHub Release is latest, non-draft, and non-prerelease.

## Validation

The full Tool Shed validator passed immediately before the content commit and again after immutable
provenance was populated. Each pass ran 310 unit tests and also passed Python compilation, manifest
integrity for 143 shipped files, provider adapter conformance, index regeneration, stale-path and
work-state checks, Program Roadmap validation, disposable all-provider installation smoke, and
template/example sanity.

## Maintainer skill synchronization

- Canonical source: `/home/jon/docker/tool_shed/skills/tool-shed`
- Installed target: `/home/jon/.codex/skills/tool-shed`
- Rollback backup: `/home/jon/.codex/skills/tool-shed.backup-20260827T121301Z`
- Canonical source quick validation: passed
- Staged copy quick validation: passed
- Installed target quick validation: passed
- Canonical-to-staged and canonical-to-installed `diff -qr`: empty
- Pre-replacement target was copied to the rollback backup; the redundant retired copy was moved
  to recoverable desktop trash only after backup parity and installed validation passed.

## Status smoke and remaining gate

A new CLI process reported Codex 0.149.0 App Server available and exact-qualified, with qualified
planning (`gpt-5.6-sol`/high), verification (`gpt-5.6-terra`/low), and CAMP execution
(`gpt-5.6-terra`/medium). API fallback remains disabled. The new user-local preference is absent,
so its fail-safe effective state is OFF and the current execution default is GUI.

The planned fresh-session v0.30.0 smoke was retired when the operator-trust runtime program
superseded the qualification-era contract. The completed release and synchronization facts above
remain historical evidence; they are not evidence for the current unpublished v0.33.0 candidate.

## Boundary

No product project source or snapshot was changed. Field dogfooding remains dependent on Campaign
096 completion and on explicit authorization for each named product workspace mutation.
