# Publish, Synchronize, and Upgrade the App Server Repair

Status: complete
Type: campaign
Updated: 2026-08-26
Next Action: none
Campaign ID: publish-synchronize-and-upgrade-app-server-repair
Campaign Number: 070
Outcome: Publish the verified Windows App Server preparation and verifier repair as Tool Shed v0.29.9, synchronize the maintainer skill, and upgrade Core's disconnected snapshot without application deployment.
Primary Focus Areas: qualification-release
Supporting Focus Areas: snapshot-delivery, provider-portability
Depends On: none
Decision: none
Detour For: none
Return To: none
Completion Gate: The unchanged candidate passes full validation; v0.29.9 content/provenance commits, annotated tag, canonical manifest, workflow, and GitHub Release agree; the Linux installed skill exact-diffs clean; Core uses a verified v0.29.9 snapshot and matching Windows skill with reconciled campaign/work state; no Campaign 013 replay or Bactron deployment occurs.
Completion Evidence: work/evidence/evidence-tool-shed-v0-29-9-release-sync-core-upgrade.md
Completion Date: 2026-08-26
Completion Order: 64
Disposition: completed

## Request

Publish the already verified Windows App Server preparation and deterministic-verifier repair as
Tool Shed v0.29.9. Follow the two-commit provenance procedure, run the full validator on the
unchanged content candidate and again after provenance, create and push the annotated tag, verify
the publication workflow and non-draft GitHub Release, and verify the live canonical manifest.

After publication is verified, synchronize the separately installed Linux Codex Tool Shed skill
from the canonical source using a unique backup and staged validation. Then use the current
released updater to upgrade `E:\dev\bactron-core` from v0.29.8 to v0.29.9 with bounded verified
backups and Windows skill synchronization. Preserve Core owner work and its Git history. Run only
the focused released updater checks and post-upgrade doctor/state verification; do not replay a
product campaign merely to test the transport again.

Do not deploy Bactron, replay Campaign 013, modify production, prune unknown backups, rewrite Git
history, force over a dirty target, enable API fallback, or expand App Server qualification.

## Completion Check

The unchanged candidate passes full validation; v0.29.9 content/provenance commits, annotated tag, canonical manifest, workflow, and GitHub Release agree; the Linux installed skill exact-diffs clean; Core uses a verified v0.29.9 snapshot and matching Windows skill with reconciled campaign/work state; no Campaign 013 replay or Bactron deployment occurs.
