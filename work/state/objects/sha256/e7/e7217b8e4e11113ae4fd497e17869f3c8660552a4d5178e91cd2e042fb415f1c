# Publish Explicit-Reference Preparation Repair

Status: complete
Type: campaign
Updated: 2026-08-26
Next Action: none
Campaign ID: publish-explicit-reference-preparation-repair
Campaign Number: 087
Outcome: Publish the validated explicit-reference preparation bound in a verified Tool Shed patch release and synchronize the maintainer installed skill so the already-authorized Core adoption campaign can resume from a stable release.
Primary Focus Areas: qualification-release
Supporting Focus Areas: provider-portability, snapshot-delivery
Depends On: bound-explicit-reference-app-server-preparation
Decision: none
Detour For: adopt-first-pass-app-server-preparation-in-core
Return To: adopt-first-pass-app-server-preparation-in-core
Completion Gate: The unchanged candidate passes the full validator; content and provenance commits, annotated tag, live manifest, and non-draft latest GitHub Release agree; the maintainer installed skill is backed up, synchronized, exact-diff clean, and fresh-session verified; no Core snapshot or Bactron deployment changes.
Completion Evidence: work/evidence/evidence-tool-shed-v0-29-11-release-and-maintainer-sync.md
Completion Date: 2026-08-26
Completion Order: 72
Disposition: completed

## Request

After separate owner publication and installed-skill synchronization authorization, publish the
unchanged Campaign 086 repair as the next Tool Shed patch release. Run the full deterministic
validator once at this release boundary, make the scoped content and provenance commits, create and
push the annotated tag, and verify that the live manifest and latest non-draft GitHub Release agree
with the released source. Back up and synchronize the maintainer installed skill, verify exact path
and hash parity, and perform the documented fresh-session smoke. Preserve the already-installed Core
v0.29.10 snapshot during this campaign: Core adoption and the Windows worker proof remain in
Campaign 085 after this campaign returns control. Do not deploy Bactron or expand the candidate.

## App Server Preparation Contract

```json
{
  "campaign_id": "publish-explicit-reference-preparation-repair",
  "completion_evidence": "The unchanged candidate passes the full validator; content and provenance commits, annotated tag, live manifest, and non-draft latest GitHub Release agree; the maintainer installed skill is backed up, synchronized, exact-diff clean, and fresh-session verified; no Core snapshot or Bactron deployment changes.",
  "exact_resolution": "dispatch-time",
  "execution_shape": "single-bounded-camp",
  "inline_assets": "metadata-only",
  "objective": "Publish the validated explicit-reference preparation bound in a verified Tool Shed patch release and synchronize the maintainer installed skill so the already-authorized Core adoption campaign can resume from a stable release.",
  "schema_version": 1,
  "source_freshness": "required",
  "verification": "orchestrator-exactly-once"
}
```

## Completion Check

The unchanged candidate passes the full validator; content and provenance commits, annotated tag, live manifest, and non-draft latest GitHub Release agree; the maintainer installed skill is backed up, synchronized, exact-diff clean, and fresh-session verified; no Core snapshot or Bactron deployment changes.
