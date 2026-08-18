# Add a workspace-wide ts: doctor integrity and consistency command

Status: working
Type: campaign
Updated: 2026-08-18
Next Action: execute the campaign completion gate
Campaign ID: add-workspace-wide-ts-doctor-command
Campaign Number: 031
Outcome: Resolve GitHub issue #39 by adding one read-only-by-default workspace health command that composes existing checks, detects cross-surface inconsistencies, distinguishes internal consistency from external truth, and emits one unambiguous overall verdict with precise next actions.
Primary Focus Areas: workspace-safety
Supporting Focus Areas: artifact-workflows, campaign-lifecycle, provider-portability, snapshot-delivery, qualification-release
Depends On: none
Decision: none
Detour For: none
Return To: none
Completion Gate: GitHub issue #39 acceptance criteria pass: the doctor command audits the full supported workspace surface; detects stale indexes and dirty campaign transitions; distinguishes structural consistency from unsupported runtime claims; emits compact human and stable JSON results with actionable verdicts; strict mode fails for unhealthy required states; repair remains explicit and guarded; focused regression tests pass; and command, operator, skill, and snapshot documentation are updated.
Completion Evidence: none
Disposition: none

## Request

Add detailed execution context here.

## Completion Check

GitHub issue #39 acceptance criteria pass: the doctor command audits the full supported workspace surface; detects stale indexes and dirty campaign transitions; distinguishes structural consistency from unsupported runtime claims; emits compact human and stable JSON results with actionable verdicts; strict mode fails for unhealthy required states; repair remains explicit and guarded; focused regression tests pass; and command, operator, skill, and snapshot documentation are updated.
