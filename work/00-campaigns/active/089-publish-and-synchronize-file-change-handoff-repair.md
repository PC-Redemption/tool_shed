# Publish and Synchronize File-Change Handoff Repair

Status: working
Type: campaign
Updated: 2026-08-26
Next Action: execute the campaign completion gate
Campaign ID: publish-and-synchronize-file-change-handoff-repair
Campaign Number: 089
Outcome: Publish the locally proven file-change handoff and whitespace-robust documentation-verifier correction as a verified Tool Shed patch release and synchronize the maintainer installed skill so Campaign 085 can resume under its existing Core authorization.
Primary Focus Areas: qualification-release
Supporting Focus Areas: provider-portability, snapshot-delivery
Depends On: preserve-file-change-handoff-and-robust-doc-verification
Decision: none
Detour For: adopt-first-pass-app-server-preparation-in-core
Return To: adopt-first-pass-app-server-preparation-in-core
Completion Gate: The unchanged Campaign 088 candidate passes the full validator; content and provenance commits, annotated tag, live manifest, and non-draft latest GitHub Release agree; the maintainer installed skill is backed up, synchronized, exact-diff clean, and fresh-session verified; Core and Bactron remain unchanged.
Completion Evidence: none
Disposition: none

## Request

After separate owner publication and installed-skill synchronization authorization, publish the
unchanged Campaign 088 candidate as the next Tool Shed patch release. Run the full deterministic
validator once at the release boundary, create the scoped content and provenance commits, create
and push the annotated tag, and verify that the live manifest and latest non-draft GitHub Release
agree with the released source. Back up and synchronize the maintainer installed skill, prove exact
source parity, and use an immutable-byte-equivalent fresh-session result only when the skill bytes
are unchanged from an already-proven smoke. Leave Core unchanged during this campaign; its already-
authorized snapshot re-upgrade and Windows proof resume through Campaign 085 after this campaign
returns control. Do not replay Core Campaign 022 or 013, and do not deploy Bactron.

## App Server Preparation Contract

```json
{
  "campaign_id": "publish-and-synchronize-file-change-handoff-repair",
  "completion_evidence": "The unchanged Campaign 088 candidate passes the full validator; content and provenance commits, annotated tag, live manifest, and non-draft latest GitHub Release agree; the maintainer installed skill is backed up, synchronized, exact-diff clean, and fresh-session verified; Core and Bactron remain unchanged.",
  "exact_resolution": "dispatch-time",
  "execution_shape": "single-bounded-camp",
  "inline_assets": "metadata-only",
  "objective": "Publish the locally proven file-change handoff and whitespace-robust documentation-verifier correction as a verified Tool Shed patch release and synchronize the maintainer installed skill so Campaign 085 can resume under its existing Core authorization.",
  "schema_version": 1,
  "source_freshness": "required",
  "verification": "orchestrator-exactly-once"
}
```

## Completion Check

The unchanged Campaign 088 candidate passes the full validator; content and provenance commits, annotated tag, live manifest, and non-draft latest GitHub Release agree; the maintainer installed skill is backed up, synchronized, exact-diff clean, and fresh-session verified; Core and Bactron remain unchanged.
