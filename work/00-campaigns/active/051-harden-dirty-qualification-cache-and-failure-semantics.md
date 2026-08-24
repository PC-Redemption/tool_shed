# Harden dirty-qualification cache and failure semantics

Status: queued
Type: campaign
Updated: 2026-08-24
Next Action: execute when selected from the active campaign queue
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
Completion Evidence: none
Disposition: none

## Request

Add detailed execution context here.

## Completion Check

Dirty qualification cache is stored outside canonical and installed Tool Shed trees with no prompts, responses, credentials, or secrets; cache identity includes executable hash, Codex version, generated protocol-schema hash when available or a documented runtime-probe fingerprint otherwise, Tool Shed qualification-policy hash, model-policy hash, and platform; writes are atomic, permission-restricted to 0600 where supported, and safe under concurrent processes; malformed, partial, foreign-platform, stale, or mismatched entries are ignored safely; executable or policy changes invalidate prior results, including same-version binary changes; transient network, authentication, service, or model-catalog failures fall back to GUI and remain retryable rather than becoming permanent blacklists; reviewed unsafe records remain authoritative until their relevant fingerprint changes or an explicit requalification route is used; sanitized status explains cache source and invalidation reason; focused security, corruption, concurrency, and retry tests pass.
