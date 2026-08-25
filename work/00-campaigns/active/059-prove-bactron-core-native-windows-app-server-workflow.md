# Prove the Bactron Core native Windows App Server workflow

Status: queued
Type: campaign
Updated: 2026-08-25
Next Action: execute when selected from the active campaign queue
Campaign ID: prove-bactron-core-native-windows-app-server-workflow
Campaign Number: 059
Outcome: Show that the released Tool Shed works through the normal Windows GUI environment for a fresh asset-aware Core campaign.
Primary Focus Areas: snapshot-delivery
Supporting Focus Areas: provider-portability, workspace-safety, qualification-release
Depends On: synchronize-maintainer-skill-and-smoke-v0-28-0
Decision: none
Detour For: none
Return To: none
Completion Gate: G4-WINDOWS-INSTALLED-WORKS passes with version, resolver, asset-aware execution, exactly-once verification, journal, and usage evidence.
Completion Evidence: none
Disposition: none
Roadmap: low-token-cross-platform-campaign-execution
Roadmap Revision: 1
Milestone: M4-WINDOWS-INSTALLED
Unlocks Gate: G4-WINDOWS-INSTALLED-WORKS

## Request

Using normal GUI execution on the work PC in E:\dev\bactron-core, upgrade the Tool Shed snapshot and Windows installed skill from the verified v0.28.0 release with bounded backups and rollback. Without PATH preparation, verify that all App Server consumers select the same exact GUI-provided Codex executable and readiness state. Create and execute one fresh bounded non-production asset-aware Core campaign through explicit App Server selection, capturing model/effort, context, tokens, turns, elapsed time, tool calls, changed paths, exactly-once declared verification, journal truth, and compact return. Repair ordinary setup defects inside this campaign with focused checks and one smoke. Do not replay Campaign 013, deploy Bactron, alter unrelated product scope, or run unrelated suites.

## Completion Check

G4-WINDOWS-INSTALLED-WORKS passes with version, resolver, asset-aware execution, exactly-once verification, journal, and usage evidence.
