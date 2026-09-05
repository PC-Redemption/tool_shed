<!-- BEGIN TOOL SHED ROUTING GUIDANCE -->
## Tool Shed request routing

- Activate Tool Shed only when the request begins with `ts:`, explicitly names Tool Shed, or explicitly asks to create or manage Tool Shed artifacts or campaign state.
- Do not activate Tool Shed merely because `tool_shed/`, `work/`, or canonical Tool Shed repository files exist in the workspace.
- For an activated request, locate the workspace-local shed, then read its `skills/tool-shed/SKILL.md` before acting; load only the route reference that skill selects.
- If a separately installed or already-loaded Tool Shed skill differs from the workspace-local copy, report `TOOL_SHED_SKILL_MISMATCH`, use the workspace-local contract for this workspace, and recommend the documented update or synchronization route instead of combining both contracts.
- Keep project state in root `work/`; the workspace-local shed contains reusable machinery.
- Use only the provider capabilities actually available in the current product surface.
<!-- END TOOL SHED ROUTING GUIDANCE -->

## Tool Shed platform test beds

- Use SSH host `gogetter.local` and workspace `E:\dev\ts_windows_test_bed` as the default target
  for Tool Shed Windows installation, update, upgrade, recovery, scheduler, background-process,
  and runtime qualification.
- The exact workspace and its Git repository are disposable maintainer test infrastructure. The
  maintainer may replace them completely and may create, mutate, or delete synthetic Tool Shed
  Ideas, PRMs, campaigns, outcomes, configuration, and failure fixtures there.
- Prefer this test bed over live project workspaces. Use a live project only when the operator
  explicitly requests field verification that the test bed cannot supply.
- Before destructive work, verify the remote host is `GOGETTER` and the resolved Windows path is
  exactly `E:\dev\ts_windows_test_bed`. This authority does not extend to other paths, projects,
  credentials, accounts, unrelated scheduled tasks, or external infrastructure.
- The parent repository is `PC-Redemption/ts_windows_test_bed`; its local `AGENTS.md` and `README.md`
  contain the complete disposable-workspace authority and repository-boundary contract.
- Use local workspace `/home/jon/dev/ts_linux_test_bed` on `sup.local` as the equivalent default
  target for Tool Shed Linux installation, update, upgrade, recovery, scheduler,
  background-process, and runtime qualification.
- The Linux workspace and its Git repository are equally disposable and may contain synthetic Tool
  Shed Ideas, PRMs, campaigns, outcomes, configuration, and failure fixtures. Before destructive
  work, verify the host is `sup` and the resolved path is exactly
  `/home/jon/dev/ts_linux_test_bed`.
- The Linux parent repository is `PC-Redemption/ts_linux_test_bed`; its local `AGENTS.md` and
  `README.md` contain the complete disposable-workspace authority and repository-boundary contract.
