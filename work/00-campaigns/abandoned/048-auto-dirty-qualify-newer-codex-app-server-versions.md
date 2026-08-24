# Automatically dirty-qualify newer Codex App Server versions

Status: abandoned
Type: campaign
Updated: 2026-08-24
Next Action: none
Campaign ID: auto-dirty-qualify-newer-codex-app-server-versions
Campaign Number: 048
Outcome: Make Codex App Server qualification fail-forward across CLI churn: accept versions at or above 0.146.0, automatically dirty-qualify every unseen newer version without an upper version cutoff, and immediately use passing versions for explicit read-only planning and verification while preserving fail-closed GUI fallback and exact reviewed qualification for workspace-write CAMP execution.
Primary Focus Areas: qualification-release
Supporting Focus Areas: provider-portability, workspace-safety
Depends On: none
Decision: none
Detour For: none
Return To: none
Completion Gate: Canonical Tool Shed implements and documents a minimum-only Codex version policy of >=0.146.0; exact reviewed records remain the fast path; unseen versions including 0.150.0 and later automatically run a bounded dirty qualification and continue the same requested read-only operation when it passes; dirty qualification negotiates supported permission profiles or validated legacy read-only policy, checks ChatGPT auth, required models and reasoning, isolated read-only turns, fail-closed approvals, unexpected writes, and deterministic active-turn cancellation; safe blockers are distinguished from fatal or unknown states; transient failures fall back to GUI without permanent blacklisting; cached results invalidate on executable, protocol-schema, Tool Shed policy, or model-policy changes; workspace-write remains exact-version and separate-harness qualified; focused tests, full validation, release documentation, manifest provenance, and the next Tool Shed release verify the behavior.
Completion Evidence: none
Disposition: superseded by a dependency-ordered mitigation sequence with non-overlapping completion gates; replacement: implement-minimum-version-dirty-read-qualification

## Request

Add detailed execution context here.

## Completion Check

Canonical Tool Shed implements and documents a minimum-only Codex version policy of >=0.146.0; exact reviewed records remain the fast path; unseen versions including 0.150.0 and later automatically run a bounded dirty qualification and continue the same requested read-only operation when it passes; dirty qualification negotiates supported permission profiles or validated legacy read-only policy, checks ChatGPT auth, required models and reasoning, isolated read-only turns, fail-closed approvals, unexpected writes, and deterministic active-turn cancellation; safe blockers are distinguished from fatal or unknown states; transient failures fall back to GUI without permanent blacklisting; cached results invalidate on executable, protocol-schema, Tool Shed policy, or model-policy changes; workspace-write remains exact-version and separate-harness qualified; focused tests, full validation, release documentation, manifest provenance, and the next Tool Shed release verify the behavior.
