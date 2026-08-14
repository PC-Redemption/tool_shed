# Automate Dangler Resolution Reconciliation

Status: complete
Type: campaign
Updated: 2026-08-14
Next Action: none
Campaign ID: automate-dangler-resolution-reconciliation
Outcome: ts: reconcile campaigns deterministically creates or refreshes one Dangler Resolution campaign as the first queued campaign while preserving working work and requiring approval for ambiguous classifications
Depends On: none
Decision: none
Detour For: none
Return To: none
Completion Gate: single-command reconciliation creates or refreshes exactly one Dangler Resolution campaign at the required queue position; status and next expose it; focused and full validation pass; configured work environment is updated when available
Completion Evidence: 106-test full validator; real default reconcile created resolve-unclassified-work after working campaign; repeat run idempotent; installed Codex skill validated and exact-diff synchronized with backup tool-shed.backup-20260814T172336Z
Completion Date: 2026-08-14
Completion Order: 6
Disposition: completed

## Request

Change the `ts: reconcile campaigns` owner route so one command deterministically creates or
refreshes a single Dangler Resolution campaign whenever unclassified unresolved artifacts exist.

- Put the Dangler Resolution campaign first among queued work while preserving any campaign that
  is already working.
- Refresh its unresolved path list without creating duplicates.
- Keep artifact classification, lifecycle disposition, projection repair, and proposed execution
  order behind explicit owner approval when they are not the deterministic Dangler operation.
- Preserve a read-only CLI inspection mode for automation and diagnostics.
- Surface the resulting active campaign through `ts: status` and `ts: next`.
- Validate the canonical source, update the authorized local work client, and verify exact sync.

## Completion Check

single-command reconciliation creates or refreshes exactly one Dangler Resolution campaign at the required queue position; status and next expose it; focused and full validation pass; configured work environment is updated when available
