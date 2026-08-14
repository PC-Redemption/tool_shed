# Restore blocked campaign lifecycle

Status: working
Type: campaign
Updated: 2026-08-14
Next Action: execute the campaign completion gate
Campaign ID: restore-blocked-campaign-lifecycle
Outcome: Provide a deterministic supported transition that returns blocked campaigns to schedulable execution without weakening start invariants
Depends On: none
Decision: none
Detour For: none
Return To: none
Completion Gate: A GitHub repository issue documents the defect, reproduction, expected behavior, and acceptance criteria; blocked campaigns can be unblocked through a token-protected command; blocker metadata and queue projections clear; next and start behave correctly; focused lifecycle tests and operator documentation pass; completion evidence references the GitHub issue
Completion Evidence: none
Disposition: none

## Request

Tool Shed's deterministic campaign queue can transition a queued or working campaign to blocked,
but it has no supported transition back to schedulable execution. `start` correctly accepts only a
queued campaign, while `next` excludes blocked campaigns, leaving blocked active work unable to
resume without manual state edits or a terminal lifecycle action.

As part of this campaign, create or update an issue in the GitHub repository that records:

- the `start -> block -> start` reproduction and observed errors;
- the expected supported transition from blocked work back to schedulable execution;
- the proposed token-protected lifecycle semantics and blocker-metadata cleanup;
- acceptance criteria covering queue projections, `next`, `start`, stale-token handling, tests,
  and operator documentation.

Reference that GitHub issue in the campaign's completion evidence.

## Completion Check

A GitHub repository issue documents the defect, reproduction, expected behavior, and acceptance
criteria. Blocked campaigns can be unblocked through a token-protected command; blocker metadata
and queue projections clear; `next` and `start` behave correctly; focused lifecycle tests and
operator documentation pass; completion evidence references the GitHub issue.
