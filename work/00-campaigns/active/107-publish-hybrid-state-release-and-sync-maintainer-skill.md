# Publish the hybrid-state release and synchronize the maintainer skill

Status: working
Type: campaign
Updated: 2026-08-28
Next Action: execute the campaign completion gate
Campaign ID: publish-hybrid-state-release-and-sync-maintainer-skill
Campaign Number: 107
Outcome: The unchanged maintainer-proven candidate is published with verified provenance and the separately installed Codex skill exactly matches the released canonical skill in a fresh session.
Primary Focus Areas: qualification-release
Supporting Focus Areas: snapshot-delivery, provider-portability
Depends On: rehearse-and-convert-maintainer-to-hybrid-state
Decision: none
Detour For: none
Return To: none
Completion Gate: The exact content commit passes the release profile on Windows and POSIX; the new minimum updater protocol and old-updater refusal are qualified; the two-commit provenance, tag, and GitHub Release are verified; the installed maintainer skill is backed up, replaced, validated, exact-diff equal, and smoke-tested.
Completion Evidence: none
Disposition: none
Roadmap: hybrid-sqlite-operational-state
Roadmap Revision: 3
Milestone: M4-RELEASE-CANARY-PROVEN
Unlocks Gate: none

## Request

After G3 passes and only under separate explicit release authority, freeze the unchanged candidate, qualify and publish through the documented two-commit process, then synchronize the installed maintainer skill through its special host-local procedure. Requested endpoint: work5 release; stop before any downstream client upgrade.

## App Server Preparation Contract

```json
{
  "campaign_id": "publish-hybrid-state-release-and-sync-maintainer-skill",
  "completion_evidence": "The exact content commit passes the release profile on Windows and POSIX; the new minimum updater protocol and old-updater refusal are qualified; the two-commit provenance, tag, and GitHub Release are verified; the installed maintainer skill is backed up, replaced, validated, exact-diff equal, and smoke-tested.",
  "exact_resolution": "dispatch-time",
  "execution_shape": "single-bounded-camp",
  "inline_assets": "metadata-only",
  "objective": "The unchanged maintainer-proven candidate is published with verified provenance and the separately installed Codex skill exactly matches the released canonical skill in a fresh session.",
  "schema_version": 1,
  "source_freshness": "required",
  "verification": "orchestrator-exactly-once"
}
```

## Completion Check

The exact content commit passes the release profile on Windows and POSIX; the new minimum updater protocol and old-updater refusal are qualified; the two-commit provenance, tag, and GitHub Release are verified; the installed maintainer skill is backed up, replaced, validated, exact-diff equal, and smoke-tested.
