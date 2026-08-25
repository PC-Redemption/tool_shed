# Publish the minimum usable Tool Shed v0.28.0 release

Status: working
Type: campaign
Updated: 2026-08-25
Next Action: execute the campaign completion gate
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
Completion Evidence: none
Disposition: none
Roadmap: low-token-cross-platform-campaign-execution
Roadmap Revision: 1
Milestone: M2-MINIMUM-RELEASE
Unlocks Gate: none

## Request

After maintained-workspace dogfood passes, freeze the intended release inputs and run the complete Tool Shed validator once. If unchanged inputs pass, follow the documented two-commit provenance flow for v0.28.0, create the annotated tag, push branch and tag, and verify the raw manifest plus non-draft GitHub Release. If code changes after a failure, run only the relevant focused check before one replacement full-validator run. Do not synchronize installed skills, upgrade downstream snapshots, add platform matrices, or deploy applications in this campaign.

## Completion Check

The release portion of G2-RELEASE-USABLE has one full-validator result and verified public provenance.
