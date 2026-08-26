# Publish and Synchronize Case-Normalized Verification

Status: queued
Type: campaign
Updated: 2026-08-26
Next Action: execute when selected from the active campaign queue
Campaign ID: publish-and-synchronize-case-normalized-verification
Campaign Number: 091
Outcome: A verified Tool Shed patch release publishes the case-normalized documentation verifier and the maintainer installed skill exactly matches it, allowing Campaign 085 to resume with a fresh Core replacement proof.
Primary Focus Areas: qualification-release
Supporting Focus Areas: provider-portability, snapshot-delivery
Depends On: require-case-normalized-documentation-verification
Decision: Owner authorization is required before publishing the patch release or replacing the installed maintainer skill.
Detour For: adopt-first-pass-app-server-preparation-in-core
Return To: adopt-first-pass-app-server-preparation-in-core
Completion Gate: The full Tool Shed validator passes twice around immutable release provenance; a patch version is committed, annotated, pushed, and verified as the latest non-draft GitHub release; the maintainer skill is backed up, quick-valid, and byte-identical to canonical source; Core and Bactron remain unchanged.
Completion Evidence: none
Disposition: none

## Request

After explicit owner authorization, publish the locally proven Campaign 090 correction as the next
Tool Shed patch release. Run the full validator before committing release content and again after
recording immutable provenance. Create the focused repair, release-content, and provenance commits;
create and push an annotated version tag; and verify a latest, non-draft, non-prerelease GitHub
Release through the documented release path.

Then follow the dual-role maintainer synchronization procedure: back up the installed Tool Shed
skill, stage and quick-validate the canonical source, replace the installed copy, quick-validate it,
and prove exact source-to-installed parity. Preserve rollback material and record durable evidence.
Do not change Core, run the replacement Windows proof, replay Core Campaign 023, deploy Bactron, or
expand the release beyond the case-normalized documentation-verifier correction and its campaign
lifecycle evidence.

## App Server Preparation Contract

```json
{
  "campaign_id": "publish-and-synchronize-case-normalized-verification",
  "completion_evidence": "The full Tool Shed validator passes twice around immutable release provenance; a patch version is committed, annotated, pushed, and verified as the latest non-draft GitHub release; the maintainer skill is backed up, quick-valid, and byte-identical to canonical source; Core and Bactron remain unchanged.",
  "exact_resolution": "dispatch-time",
  "execution_shape": "single-bounded-camp",
  "inline_assets": "metadata-only",
  "objective": "A verified Tool Shed patch release publishes the case-normalized documentation verifier and the maintainer installed skill exactly matches it, allowing Campaign 085 to resume with a fresh Core replacement proof.",
  "schema_version": 1,
  "source_freshness": "required",
  "verification": "orchestrator-exactly-once"
}
```

## Completion Check

The full Tool Shed validator passes twice around immutable release provenance; a patch version is committed, annotated, pushed, and verified as the latest non-draft GitHub release; the maintainer skill is backed up, quick-valid, and byte-identical to canonical source; Core and Bactron remain unchanged.
