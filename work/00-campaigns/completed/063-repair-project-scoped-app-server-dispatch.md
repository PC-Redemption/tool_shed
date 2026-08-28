# Repair project-scoped App Server dispatch

Status: complete
Type: campaign
Updated: 2026-08-25
Next Action: none
Campaign ID: repair-project-scoped-app-server-dispatch
Campaign Number: 063
Outcome: Make the direct dispatcher carry an explicitly selected project-scoped App Server configuration into the bounded execution it already authorized, while preserving exact executable identity and fail-closed defaults.
Primary Focus Areas: snapshot-delivery
Supporting Focus Areas: provider-portability
Depends On: none
Decision: none
Detour For: prove-bactron-core-native-windows-app-server-workflow
Return To: prove-bactron-core-native-windows-app-server-workflow
Completion Gate: A focused regression proves custom config and policy objects reach execution; a mismatched executable hash is rejected when a project qualification records one; the full Tool Shed validator passes; a patch release is published and synchronized before returning to Campaign 059.
Completion Evidence: Focused regression: 47 passed. Full release validation: 266 passed twice with all structural gates. Tool Shed v0.29.2 published by successful workflow 32900848161; Core transaction 539adb14dbac9a08767d1d60 installed it; exact GUI executable hash and all project-scoped consumers matched and enabled qualified CAMP execution. Historical claim audit: work/evidence/evidence-historical-campaign-external-claims-backfill.md
Completion Date: 2026-08-25
Completion Order: 56
Disposition: completed

## Request

Add detailed execution context here.

## Completion Check

A focused regression proves custom config and policy objects reach execution; a mismatched executable hash is rejected when a project qualification records one; the full Tool Shed validator passes; a patch release is published and synchronized before returning to Campaign 059.
