# Evidence: Linux first-pass code proof turn-limit interruption

Status: complete
Type: evidence
Updated: 2026-08-26
Next Action: replace Campaign 075 after enforcing mutation-first worker execution
Campaign: prove-repaired-first-pass-code-test-campaign-on-linux
Campaign Reason: truthful failed-proof evidence for G11-LINUX-FIRST-PASS-RELIABLE

## Result

Campaign 075 automatically prepared and persisted a source-bound atomic capsule without manual
editing. Existing expected source was injected inline, and all observed command results stayed
below the single and cumulative byte ceilings. Preparation used 30,659 input tokens in one Sol/high
turn, selected two expected paths and two context files totaling 6,629 bytes, and estimated two
worker turns plus an 8,192-byte largest tool result.

The first Terra/medium worker changed only the two authorized paths and produced no unexpected-path
finding. It nevertheless reached the fourth observed model-request ceiling before returning the
required verification handoff. The orchestrator interrupted successfully, skipped reserved
verification, retained a safe `safe_unverified` journal, and returned
`reconcile_workspace_then_resume_bounded_camp`. Execution used 95,296 input tokens; the largest tool
result was 10,275 bytes and cumulative tool results were 14,453 bytes.

The reserved verifier was run exactly once during GUI reconciliation and failed because the new
test module could not import the script's sibling `provider_adapters` module from repository-root
test discovery. Campaign 075 therefore cannot satisfy either correctness or first-worker evidence
and is not replayed. The two worker-owned source changes were inspected and removed after this
evidence was recorded; they were not retained as product work.

## Mitigation

The bounded worker contract now treats the capsule prompt and inline context as complete for the
first mutation. It forbids command execution for repository orientation or inspection before the
first file-change operation and requires an `unknown` pre-mutation return when the supplied boundary
is insufficient. Any later inspection remains capped below 12,288 serialized bytes. This targets
the two exploratory command turns that consumed Campaign 075's handoff budget without weakening the
four-request runtime ceiling.

A fresh campaign—not a continuation or replay of Campaign 075—must prove this mitigation before
G11 can pass.
