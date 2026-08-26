# Preserve File-Change Handoff and Robust Documentation Verification

Status: complete
Type: campaign
Updated: 2026-08-26
Next Action: none
Campaign ID: preserve-file-change-handoff-and-robust-doc-verification
Campaign Number: 088
Outcome: A completed first fileChange remains an immediate verification handoff even when its event reaches a no-further-request turn ceiling, and automatic documentation preparation requires whitespace-robust semantic assertions.
Primary Focus Areas: provider-portability
Supporting Focus Areas: campaign-lifecycle, workspace-safety
Depends On: none
Decision: none
Detour For: adopt-first-pass-app-server-preparation-in-core
Return To: adopt-first-pass-app-server-preparation-in-core
Completion Gate: Focused protocol tests prove same-event fileChange handoff wins over the model-turn ceiling without allowing another model request, ordinary pre-mutation budget breaches still fail closed, the automatic preparation prompt requires whitespace-normalized documentation assertions, a Core-shaped regression rejects or avoids formatting-fragile checks, and the focused App Server suites pass without publication, skill synchronization, Core mutation, or deployment.
Completion Evidence: work/evidence/evidence-file-change-handoff-and-robust-doc-verification.md
Completion Date: 2026-08-26
Completion Order: 73
Disposition: completed

## Request

Repair the two Tool Shed defects observed during Campaign 085's first Windows execution of Core
Campaign 022 through v0.29.11:

- Treat the first completed `fileChange` as the immediate deterministic-verification handoff when
  the same protocol boundary also reaches the configured model-turn ceiling. Do not permit another
  model request, and do not weaken input-token or tool-result ceilings.
- Require automatically prepared documentation verification to normalize whitespace before
  asserting multiword semantic phrases. Reject a Core-shaped raw-substring verifier before the
  capsule is persisted or a worker is launched.

Add focused protocol and dispatcher regressions, preserve ordinary pre-mutation budget failure,
and record the Windows evidence that motivated the correction. Keep this campaign local: do not
publish, synchronize the installed skill, mutate Core again, or deploy Bactron.

## App Server Preparation Contract

```json
{
  "campaign_id": "preserve-file-change-handoff-and-robust-doc-verification",
  "completion_evidence": "Focused protocol tests prove same-event fileChange handoff wins over the model-turn ceiling without allowing another model request, ordinary pre-mutation budget breaches still fail closed, the automatic preparation prompt requires whitespace-normalized documentation assertions, a Core-shaped regression rejects or avoids formatting-fragile checks, and the focused App Server suites pass without publication, skill synchronization, Core mutation, or deployment.",
  "exact_resolution": "dispatch-time",
  "execution_shape": "single-bounded-camp",
  "inline_assets": "metadata-only",
  "objective": "A completed first fileChange remains an immediate verification handoff even when its event reaches a no-further-request turn ceiling, and automatic documentation preparation requires whitespace-robust semantic assertions.",
  "schema_version": 1,
  "source_freshness": "required",
  "verification": "orchestrator-exactly-once"
}
```

## Completion Check

Focused protocol tests prove same-event fileChange handoff wins over the model-turn ceiling without allowing another model request, ordinary pre-mutation budget breaches still fail closed, the automatic preparation prompt requires whitespace-normalized documentation assertions, a Core-shaped regression rejects or avoids formatting-fragile checks, and the focused App Server suites pass without publication, skill synchronization, Core mutation, or deployment.
