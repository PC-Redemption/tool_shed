# Publish the minimum usable Tool Shed v0.28.0 release

Status: complete
Type: campaign
Updated: 2026-08-25
Next Action: none
Campaign ID: publish-minimum-usable-tool-shed-v0-28-0
Campaign Number: 056
Outcome: Publish the dogfooded App Server candidate through the existing traceable release path without adding speculative qualification.
Primary Focus Areas: qualification-release
Supporting Focus Areas: provider-portability
Depends On: dogfood-maintained-tool-shed-app-server-execution
Decision: none
Detour For: none
Return To: none
Completion Gate: The release portion of G2-RELEASE-USABLE has one full-validator result and verified public provenance.
Completion Evidence: work/evidence/evidence-tool-shed-v0-28-0-release.md; frozen candidate full validator passed 260 tests; content commit b777c1a57a287df4dd4f5fd48f0d77bd46b7d25f; provenance commit 4c0d2f755137daa31969a3c24969bcfa06560d0b; annotated v0.28.0 tag pushed; release workflow 32889420426 passed; canonical manifest reports current 0.28.0; GitHub Release is verified non-draft and non-prerelease.
Completion Date: 2026-08-25
Completion Order: 51
Disposition: completed
Roadmap: low-token-cross-platform-campaign-execution
Roadmap Revision: 1
Milestone: M2-MINIMUM-RELEASE
Unlocks Gate: none

## Request

After maintained-workspace dogfood passes, freeze the intended release inputs and run the complete Tool Shed validator once. If unchanged inputs pass, follow the documented two-commit provenance flow for v0.28.0, create the annotated tag, push branch and tag, and verify the raw manifest plus non-draft GitHub Release. If code changes after a failure, run only the relevant focused check before one replacement full-validator run. Do not synchronize installed skills, upgrade downstream snapshots, add platform matrices, or deploy applications in this campaign.

## Completion Check

The release portion of G2-RELEASE-USABLE has one full-validator result and verified public provenance.
