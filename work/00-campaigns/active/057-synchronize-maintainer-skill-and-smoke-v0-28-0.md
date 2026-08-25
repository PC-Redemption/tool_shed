# Synchronize the maintainer skill and smoke v0.28.0

Status: queued
Type: campaign
Updated: 2026-08-25
Next Action: execute when selected from the active campaign queue
Campaign ID: synchronize-maintainer-skill-and-smoke-v0-28-0
Campaign Number: 057
Outcome: Make the published low-token execution contract available to fresh Codex sessions on the maintainer host.
Primary Focus Areas: snapshot-delivery
Supporting Focus Areas: provider-portability, qualification-release
Depends On: publish-minimum-usable-tool-shed-v0-28-0
Decision: none
Detour For: none
Return To: none
Completion Gate: G2-RELEASE-USABLE passes with exact installed-skill parity and fresh-session evidence.
Completion Evidence: none
Disposition: none
Roadmap: low-token-cross-platform-campaign-execution
Roadmap Revision: 1
Milestone: M2-MINIMUM-RELEASE
Unlocks Gate: G2-RELEASE-USABLE

## Request

After public v0.28.0 verification, use the dual-role workspace procedure to quick-validate the released source skill, exact-diff source and installed copies, create one bounded timestamped backup, stage and replace the installed skill, verify exact parity, and perform one fresh-session routing/readiness smoke. Do not rerun the full repository validator or modify downstream project snapshots.

## Completion Check

G2-RELEASE-USABLE passes with exact installed-skill parity and fresh-session evidence.
