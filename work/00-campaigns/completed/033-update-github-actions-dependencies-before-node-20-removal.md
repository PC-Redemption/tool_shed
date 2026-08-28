# Update GitHub Actions dependencies before Node 20 removal

Status: complete
Type: campaign
Updated: 2026-08-18
Next Action: none
Campaign ID: update-github-actions-dependencies-before-node-20-removal
Campaign Number: 033
Outcome: Resolve GitHub issue #40 by updating the workflow action majors away from the retiring Node 20 runtime while preserving Ubuntu and Windows coverage for Python 3.11 and the current supported Python version. Source: https://github.com/PC-Redemption/tool_shed/issues/40
Primary Focus Areas: qualification-release
Supporting Focus Areas: none
Depends On: none
Decision: none
Detour For: none
Return To: none
Completion Gate: Supported replacement action majors are used; Ubuntu and Windows coverage for Python 3.11 and the current supported Python version is preserved; and both validate and release workflows complete without the Node 20 deprecation annotation.
Completion Evidence: Tool Shed v0.23.0 published at https://github.com/PC-Redemption/tool_shed/releases/tag/v0.23.0; Validate passed on main (https://github.com/PC-Redemption/tool_shed/actions/runs/32179421159) and tag (https://github.com/PC-Redemption/tool_shed/actions/runs/32179423039); Publish GitHub Release passed (https://github.com/PC-Redemption/tool_shed/actions/runs/32179423109); all check annotation queries returned zero Node 20 annotations; local release qualification passed 157 tests, provider conformance, work-state and smoke validation; issue #40 closed with evidence. Historical claim audit: work/evidence/evidence-historical-campaign-external-claims-backfill.md
Completion Date: 2026-08-18
Completion Order: 32
Disposition: completed

## Request

Add detailed execution context here.

## Completion Check

Supported replacement action majors are used; Ubuntu and Windows coverage for Python 3.11 and the current supported Python version is preserved; and both validate and release workflows complete without the Node 20 deprecation annotation.
