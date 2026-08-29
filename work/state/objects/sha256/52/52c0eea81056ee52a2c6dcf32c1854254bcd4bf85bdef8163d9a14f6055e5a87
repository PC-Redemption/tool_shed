# Codex adapter compact routing and explicit Tool Shed activation

Status: complete
Type: campaign
Updated: 2026-08-18
Next Action: none
Campaign ID: codex-adapter-compact-routing-and-explicit-activation
Campaign Number: 034
Outcome: Resolve GitHub issue #41 by preventing implicit Tool Shed activation, replacing duplicated Codex root guidance with a compact conditional routing shim, and detecting global-skill/workspace-snapshot compatibility drift. Source: https://github.com/PC-Redemption/tool_shed/issues/41
Primary Focus Areas: provider-portability
Supporting Focus Areas: snapshot-delivery
Depends On: none
Decision: none
Detour For: none
Return To: none
Completion Gate: GitHub issue #41 acceptance criteria pass: unrelated unprefixed requests do not activate Tool Shed campaign behavior; explicit ts: routes retain their contracts; fresh and repeat installs are idempotent; upgrades remove legacy expanded Codex guidance while preserving owner-authored AGENTS.md content; root guidance remains compact; stale workspace snapshots paired with newer global skills produce an explicit compatibility diagnostic; focused regression tests and full Tool Shed validation pass.
Completion Evidence: Implemented explicit-only Tool Shed activation, a 1,045-byte single-block Codex AGENTS.md routing shim, idempotent legacy-block migration with owner-content preservation, and TOOL_SHED_SKILL_MISMATCH diagnostics. Focused migration, upgrade, idempotence, and stale/newer-or-unmanaged skill tests passed. Full validate_tool_shed.py qualification passed 157 tests plus manifest verification, five-provider conformance, index regeneration, stale-path and work-state review, roadmap validation, and disposable-workspace smoke.
Completion Date: 2026-08-18
Completion Order: 31
Disposition: completed

## Request

Add detailed execution context here.

## Completion Check

GitHub issue #41 acceptance criteria pass: unrelated unprefixed requests do not activate Tool Shed campaign behavior; explicit ts: routes retain their contracts; fresh and repeat installs are idempotent; upgrades remove legacy expanded Codex guidance while preserving owner-authored AGENTS.md content; root guidance remains compact; stale workspace snapshots paired with newer global skills produce an explicit compatibility diagnostic; focused regression tests and full Tool Shed validation pass.
