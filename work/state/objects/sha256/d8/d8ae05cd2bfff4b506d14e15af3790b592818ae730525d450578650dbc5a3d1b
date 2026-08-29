# Require Case-Normalized Documentation Verification

Status: complete
Type: campaign
Updated: 2026-08-26
Next Action: none
Campaign ID: require-case-normalized-documentation-verification
Campaign Number: 090
Outcome: Automatic documentation preparation generates and accepts only semantic phrase verification that normalizes both whitespace and case for the document and expected phrases.
Primary Focus Areas: provider-portability
Supporting Focus Areas: campaign-lifecycle, workspace-safety
Depends On: none
Decision: none
Detour For: adopt-first-pass-app-server-preparation-in-core
Return To: adopt-first-pass-app-server-preparation-in-core
Completion Gate: The preparation prompt requires shared whitespace-and-case normalization; a Core Campaign 023-shaped case-sensitive verifier is rejected before persistence; an equivalent verifier that normalizes both document and expected phrases is accepted; focused dispatcher tests pass; no publication, skill synchronization, Core mutation, or deployment occurs.
Completion Evidence: work/evidence/evidence-case-normalized-documentation-verification.md
Completion Date: 2026-08-26
Completion Order: 75
Disposition: completed

## Request

Repair the automatic-verification defect observed in Core Campaign 023 after v0.29.12. The
preparer correctly collapsed Markdown whitespace, but its case-sensitive semantic phrases rejected
valid sentence-initial capitalization after a one-turn, one-file worker completed safely.

Require one shared normalizer that collapses whitespace and normalizes case for both the document
text and every expected semantic phrase. Reject the Core-shaped whitespace-only verifier before
capsule persistence or worker launch, accept the equivalent shared-normalizer form, and add focused
prompt and parser regressions. Preserve the existing shell-free, path-scoped, bounded verification
rules. Do not publish, synchronize an installed skill, mutate Core again, replay Core Campaign 023,
or deploy Bactron.

## App Server Preparation Contract

```json
{
  "campaign_id": "require-case-normalized-documentation-verification",
  "completion_evidence": "The preparation prompt requires shared whitespace-and-case normalization; a Core Campaign 023-shaped case-sensitive verifier is rejected before persistence; an equivalent verifier that normalizes both document and expected phrases is accepted; focused dispatcher tests pass; no publication, skill synchronization, Core mutation, or deployment occurs.",
  "exact_resolution": "dispatch-time",
  "execution_shape": "single-bounded-camp",
  "inline_assets": "metadata-only",
  "objective": "Automatic documentation preparation generates and accepts only semantic phrase verification that normalizes both whitespace and case for the document and expected phrases.",
  "schema_version": 1,
  "source_freshness": "required",
  "verification": "orchestrator-exactly-once"
}
```

## Completion Check

The preparation prompt requires shared whitespace-and-case normalization; a Core Campaign 023-shaped case-sensitive verifier is rejected before persistence; an equivalent verifier that normalizes both document and expected phrases is accepted; focused dispatcher tests pass; no publication, skill synchronization, Core mutation, or deployment occurs.
