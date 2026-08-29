# Implement minimum-version dirty read qualification

Status: complete
Type: campaign
Updated: 2026-08-24
Next Action: none
Campaign ID: implement-minimum-version-dirty-read-qualification
Campaign Number: 049
Outcome: Replace exact-only read qualification with a minimum Codex version of 0.146.0 and no upper cutoff, automatically dirty-qualify every unseen eligible executable, and continue the same explicit planning or verification request immediately when its bounded read-only qualification passes.
Primary Focus Areas: qualification-release
Supporting Focus Areas: provider-portability, workspace-safety
Depends On: none
Decision: none
Detour For: none
Return To: none
Completion Gate: Canonical Tool Shed independently evaluates an unseen Codex version without requiring a pre-existing registry record; versions below 0.146.0 fail closed; every version at or above 0.146.0, including prereleases and 0.150.0 or later, can run dirty qualification; the runner negotiates experimental permission profiles when supported and validated legacy read-only behavior otherwise, proves ChatGPT authentication, required models and reasoning, isolated read-only turns, fail-closed approvals, no unexpected writes, and cancellation against a deliberately active turn; safe blockers are distinct from fatal or unknown states; passing dirty qualification continues the original read-only request in the same invocation; workspace-write remains exact-record and separate-harness qualified; focused tests and current operator documentation pass.
Completion Evidence: Commit 46418a8 implements the 0.146.0 numeric-core floor with no upper cutoff, automatic non-persistent dirty read qualification, experimental :read-only permission-profile negotiation with legacy fallback, classified fail-closed outcomes, unchanged-workspace checks, and exact-only CAMP writing. The real Codex 0.149.0-alpha.4.3 live run qualified with only the safely reconciled interrupt-acknowledgement blocker; all 225 repository tests and full Tool Shed validation passed.
Completion Date: 2026-08-24
Completion Order: 44
Disposition: completed

## Request

Add detailed execution context here.

## Completion Check

Canonical Tool Shed independently evaluates an unseen Codex version without requiring a pre-existing registry record; versions below 0.146.0 fail closed; every version at or above 0.146.0, including prereleases and 0.150.0 or later, can run dirty qualification; the runner negotiates experimental permission profiles when supported and validated legacy read-only behavior otherwise, proves ChatGPT authentication, required models and reasoning, isolated read-only turns, fail-closed approvals, no unexpected writes, and cancellation against a deliberately active turn; safe blockers are distinct from fatal or unknown states; passing dirty qualification continues the original read-only request in the same invocation; workspace-write remains exact-record and separate-harness qualified; focused tests and current operator documentation pass.
