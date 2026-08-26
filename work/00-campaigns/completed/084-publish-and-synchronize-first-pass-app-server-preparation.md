# Publish and synchronize first-pass App Server preparation

Status: complete
Type: campaign
Updated: 2026-08-26
Next Action: none
Campaign ID: publish-and-synchronize-first-pass-app-server-preparation
Campaign Number: 084
Outcome: Make the Linux-proven first-pass preparation contract available to new maintainer sessions through a verified release.
Primary Focus Areas: qualification-release
Supporting Focus Areas: provider-portability, snapshot-delivery
Depends On: prove-path-state-command-free-first-pass-asset-aware-campaign-on-linux
Decision: none
Detour For: none
Return To: none
Completion Gate: G12-FIRST-PASS-RELEASE-USABLE passes with one full validator, verified provenance, exact installed-skill parity, and a fresh-session smoke.
Completion Evidence: work/evidence/evidence-tool-shed-v0-29-10-release-and-maintainer-sync.md
Completion Date: 2026-08-26
Completion Order: 70
Disposition: completed
Roadmap: low-token-cross-platform-campaign-execution
Roadmap Revision: 7
Milestone: M12-FIRST-PASS-DISTRIBUTION
Unlocks Gate: G12-FIRST-PASS-RELEASE-USABLE

## Request

After separate owner publication authorization, freeze unchanged Linux-proven inputs, run the complete Tool Shed validator once, publish the next semantic release through the documented provenance flow, verify the public release, synchronize the maintainer installed skill with one bounded backup and exact diff, and run one fresh-session first-pass preparation smoke. Do not upgrade Core or deploy applications.

## App Server Preparation Contract

```json
{
  "campaign_id": "publish-and-synchronize-first-pass-app-server-preparation",
  "completion_evidence": "G12-FIRST-PASS-RELEASE-USABLE passes with one full validator, verified provenance, exact installed-skill parity, and a fresh-session smoke.",
  "exact_resolution": "dispatch-time",
  "execution_shape": "single-bounded-camp",
  "inline_assets": "metadata-only",
  "objective": "Make the Linux-proven first-pass preparation contract available to new maintainer sessions through a verified release.",
  "schema_version": 1,
  "source_freshness": "required",
  "verification": "orchestrator-exactly-once"
}
```

## Completion Check

G12-FIRST-PASS-RELEASE-USABLE passes with one full validator, verified provenance, exact installed-skill parity, and a fresh-session smoke.
