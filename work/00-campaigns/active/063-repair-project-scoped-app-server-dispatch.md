# Repair project-scoped App Server dispatch

Status: working
Type: campaign
Updated: 2026-08-25
Next Action: execute the campaign completion gate
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
Completion Evidence: none
Disposition: none

## Request

Add detailed execution context here.

## Completion Check

A focused regression proves custom config and policy objects reach execution; a mismatched executable hash is rejected when a project qualification records one; the full Tool Shed validator passes; a patch release is published and synchronized before returning to Campaign 059.
