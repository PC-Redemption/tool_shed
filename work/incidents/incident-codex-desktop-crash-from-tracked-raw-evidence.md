# Incident: Codex Desktop crash from tracked raw evidence

Status: contained; repository trigger mitigated, desktop defect remains external
Type: incident
Updated: 2026-07-25
Next Action: file the external Codex Desktop robustness evidence separately if still needed
Parent: work/maps/map-tool-shed-evolution.md
Campaign: file-codex-desktop-robustness-issue

## Impact

A Tool Shed workspace for `7520553_SMI_FW` repeatedly terminated the complete
ChatGPT/Codex Desktop application while the owner attempted to open or continue a
long-running firmware qualification task.

Measured repository conditions before cleanup:

- 2,065 tracked files under `work/evidence/`
- 189,973,786 tracked working-tree bytes
- 1,488 `.SLG` files
- 340 `.bin` files
- nine `.bundle` files totaling 83,462,101 bytes
- approximately 603 MiB of loose Git objects
- 124 additional untracked files during the triggering campaign
- Codex review commands containing 111 explicit untracked artifact paths
- repeated review/diff responses around 1.5 MiB

The failures interrupted hardware qualification work and made both the original
task and a completed-history fork unsafe to open. Crashpad captured a 49 MiB
minidump during one occurrence.

## Timeline

- Raw target captures, debugger sessions, bundles, logs, and human-readable Tool
  Shed artifacts were all committed beneath `work/evidence/`.
- A hardware qualification campaign added another 124 untracked artifacts.
- Codex Desktop generated large `git diff --no-index` review operations over those
  paths and cached the resulting review state in the task.
- The app terminated while opening or rendering the affected task.
- A local `.git/info/exclude` rule reduced new Git status noise, but could not hide
  already tracked evidence or repair cached task history.
- Forking completed task history reproduced the instability.
- A blank task recovery was prepared instead.
- Before cleanup, two verified evidence archives and file-level SHA-256 manifests
  were created outside the repository.
- Commit `b6cbc665` removed 1,945 raw evidence files (163.35 MiB) from the current
  Git snapshot while retaining Markdown, compact manifests, checksums, results,
  CSV, and two curated PNGs.
- Commit `bafc2661` closed the Tool Shed cleanup workpackage.

## Cause

The repository-level trigger was an ambiguous evidence boundary: reviewable Tool
Shed records and bulk generated validation payloads shared the tracked
`work/evidence/` tree. Git and Codex therefore treated raw captures as normal
review state.

Codex Desktop also has an independent robustness defect: oversized or inconsistent
task/review state should degrade gracefully, but instead the renderer emitted
repeated `ResizeObserver` and item-state errors before the main process terminated.
Tool Shed can prevent the common workspace trigger but cannot fix that application
defect.

## Recovery

1. Installed a process-exit monitor that collects Windows events, app logs,
   Crashpad/Sentry data, and recent diagnostics.
2. Archived and hashed committed evidence, current evidence, and all dirty working
   files before mutation.
3. Added a shared evidence-retention policy and ignore rules.
4. Removed raw evidence from the current snapshot without rewriting Git history.
5. Verified Tool Shed indexes, work state, stale paths, and active firmware-file
   hashes.
6. Created a blank recovery task with a compact handoff and archived inherited
   history tasks.

Rollback archive:

`E:\dev\high_point\7520553_SMI_FW-cleanup-prep-20260725`

Crash bundle:

`C:\Users\jong.SHELDONMFG\AppData\Local\OpenAI\ChatGPTCrashMonitor\Bundles\ChatGPT-20260725-072703.zip`

## Prevention

- Define `work/evidence/generated/` as the ignored landing zone for raw payloads.
- Track narratives and selected compact manifests only.
- Run workspace preflight before long validation campaigns.
- Warn on excessive file count, bytes, binary evidence, visible backup archives,
  and large tracked diffs.
- Preserve existing `.gitignore`, `AGENTS.md`, dirty source, and evidence during
  adoption or cleanup.
- Treat current-snapshot cleanup and Git-history rewriting as separate operations.
- Use a blank handoff after renderer-heavy campaigns rather than assuming a fork
  removes hazardous completed history.

## Follow-Up

- [x] Complete `work/tickets/ticket-field-verify-generated-evidence-safeguards.md`.
- [x] Add this measured fixture to preflight and installer tests.
- [x] Verify existing-workspace migration reports tracked raw evidence, not only
  new untracked output.
- [ ] File the Crashpad bundle separately against Codex Desktop robustness.
