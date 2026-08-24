# Harden dirty-qualification cache and failure semantics

Status: complete
Type: campaign
Updated: 2026-08-24
Next Action: none
Campaign ID: harden-dirty-qualification-cache-and-failure-semantics
Campaign Number: 051
Outcome: Persist reusable dirty-qualification evidence in protected user-local state without modifying installed Tool Shed snapshots, while making cache identity, corruption recovery, concurrency, invalidation, transient retry, and authoritative unsafe-denial behavior explicit and fail-closed.
Primary Focus Areas: workspace-safety
Supporting Focus Areas: qualification-release, provider-portability
Depends On: implement-minimum-version-dirty-read-qualification, make-codex-candidate-resolution-and-readiness-truthful
Decision: none
Detour For: none
Return To: none
Completion Gate: Dirty qualification cache is stored outside canonical and installed Tool Shed trees with no prompts, responses, credentials, or secrets; cache identity includes executable hash, Codex version, generated protocol-schema hash when available or a documented runtime-probe fingerprint otherwise, Tool Shed qualification-policy hash, model-policy hash, and platform; writes are atomic, permission-restricted to 0600 where supported, and safe under concurrent processes; malformed, partial, foreign-platform, stale, or mismatched entries are ignored safely; executable or policy changes invalidate prior results, including same-version binary changes; transient network, authentication, service, or model-catalog failures fall back to GUI and remain retryable rather than becoming permanent blacklists; reviewed unsafe records remain authoritative until their relevant fingerprint changes or an explicit requalification route is used; sanitized status explains cache source and invalidation reason; focused security, corruption, concurrency, and retry tests pass.
Completion Evidence: Implemented protected user-local dirty-read cache keyed by executable, version, protocol, qualification policy, model policy, and platform; atomic 0600 concurrent writes, corruption/staleness/invalidation handling, retryable transient failures, persistent unsafe denials, explicit --requalify, and sanitized status. Full validate_tool_shed.py passed with 242 tests.
Completion Date: 2026-08-24
Completion Order: 46
Disposition: completed

## Request

Add detailed execution context here.

## Completion Check

Dirty qualification cache is stored outside canonical and installed Tool Shed trees with no prompts, responses, credentials, or secrets; cache identity includes executable hash, Codex version, generated protocol-schema hash when available or a documented runtime-probe fingerprint otherwise, Tool Shed qualification-policy hash, model-policy hash, and platform; writes are atomic, permission-restricted to 0600 where supported, and safe under concurrent processes; malformed, partial, foreign-platform, stale, or mismatched entries are ignored safely; executable or policy changes invalidate prior results, including same-version binary changes; transient network, authentication, service, or model-catalog failures fall back to GUI and remain retryable rather than becoming permanent blacklists; reviewed unsafe records remain authoritative until their relevant fingerprint changes or an explicit requalification route is used; sanitized status explains cache source and invalidation reason; focused security, corruption, concurrency, and retry tests pass.
