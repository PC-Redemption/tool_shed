# Bound updater backup scope and prune obsolete verified archives

Status: complete
Type: campaign
Updated: 2026-08-17
Next Action: none
Campaign ID: bound-updater-backup-scope-and-prune-archives
Campaign Number: 014
Outcome: Tool Shed updater backups cover only the declared transaction mutation surface and safely retain or prune verified updater-owned workspace and user-skill archives after complete success.
Primary Focus Areas: none
Supporting Focus Areas: none
Depends On: complete-portable-verified-installer
Decision: none
Detour For: none
Return To: none
Completion Gate: GitHub issue #31 backup-scope, manifest, rollback, retention, pruning, preview, safety, JSON reporting, documentation, and cross-platform test acceptance criteria pass; full Tool Shed validation succeeds.
Completion Evidence: Implemented verified mutation-surface manifests and scoped rollback, generated-output exclusion with declared expansion, verified workspace and Codex-skill retention/pruning controls, safe preview and unknown preservation, JSON reporting, documentation, and regression coverage; python3 scripts/validate_tool_shed.py passed 116 tests plus provider conformance and workspace smoke validation.
Completion Date: 2026-08-15
Completion Order: 13
Disposition: completed

## Request

Deliver [GitHub issue #31](https://github.com/PC-Redemption/tool_shed/issues/31).

### Bound the backup mutation surface

- Declare the exact installer mutation surface before creating an archive and back up everything
  required for exact rollback: the existing snapshot, mutable repository/provider files, selected
  work/Q&A migration paths, user-skill state when synchronization is requested, and absence
  markers for paths that did not exist.
- Record included and explicitly excluded paths, hashes, source/target versions, updater protocol,
  transaction identity, and timestamp in the verified backup manifest.
- Exclude untouched generated-output paths such as `work/evidence/generated/` when the selected
  protocol guarantees they cannot be mutated. Expand scope only when a migration requires it, and
  report the reason and estimated size before archive creation.
- Prove exact rollback after injected failures at every post-replacement stage, including with
  large generated trees and supported hard-link cases, without following unsafe filesystem links.

### Add verified retention and pruning

- After complete installation, convergence, optional skill synchronization, and validation
  success, inventory and cryptographically verify canonical updater-owned workspace and user-skill
  backups before classifying them.
- Protect the current immediate rollback archive, retain the newest two verified archives by
  default, prune only older verified updater-owned archives, and report retained/removed paths and
  reclaimed bytes.
- Preserve unknown, manually named, malformed, unsupported, or unverifiable archives. Never prune
  before success or after an interrupted, failed, or rolled-back update.
- Add `--backup-retention`, `--no-prune-backups`, and read-only `--prune-preview` controls, with
  project-policy overrides for stronger recovery, regulatory, or audit retention.
- Ensure no-op and duplicate-version checks do not create redundant backups.

### Safety, output, and verification

- Resolve every cleanup target within the intended workspace or configured backup directory;
  reject symlinks, junctions, hard links, or archive members that escape the allowed root, and
  never classify ownership from filenames alone.
- Extend JSON output with declared backup scope, protected/retained/pruned/unknown archives, and
  reclaimed bytes. Document scope, rollback guarantees, defaults, overrides, previews, and the
  irreversibility of deletion.
- Test generated-output exclusion and byte preservation, supported NTFS/POSIX hard-link behavior,
  filesystem-link rejection, injected failures, unknown archives, retention overrides, preview,
  user-skill retention, and repeated same-version runs.

## Completion Check

GitHub issue #31 backup-scope, manifest, rollback, retention, pruning, preview, safety, JSON reporting, documentation, and cross-platform test acceptance criteria pass; full Tool Shed validation succeeds.
