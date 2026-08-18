<!-- BEGIN TOOL SHED ROUTING GUIDANCE -->
## Tool Shed request routing

- Activate Tool Shed only when the request begins with `ts:`, explicitly names Tool Shed, or explicitly asks to create or manage Tool Shed artifacts or campaign state.
- Do not activate Tool Shed merely because `tool_shed/`, `work/`, or canonical Tool Shed repository files exist in the workspace.
- For an activated request, locate the workspace-local shed, then read its `skills/tool-shed/SKILL.md` before acting; load only the route reference that skill selects.
- If a separately installed or already-loaded Tool Shed skill differs from the workspace-local copy, report `TOOL_SHED_SKILL_MISMATCH`, use the workspace-local contract for this workspace, and recommend the documented update or synchronization route instead of combining both contracts.
- Keep project state in root `work/`; the workspace-local shed contains reusable machinery.
- Use only the provider capabilities actually available in the current product surface.
<!-- END TOOL SHED ROUTING GUIDANCE -->
