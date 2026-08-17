# Show campaign IDs on ordered Active Campaign Queue entries

Status: queued
Type: campaign
Updated: 2026-08-17
Next Action: execute when selected from the active campaign queue
Campaign ID: show-campaign-ids-on-ordered-active-campaign-queue-entries
Outcome: Deliver GitHub issue #32 by rendering every active queue card with its exact stable Campaign ID, clearly distinguished from the mutable 1-based queue position used by que N.
Primary Focus Areas: campaign-lifecycle
Supporting Focus Areas: snapshot-delivery, provider-portability, qualification-release
Depends On: discover-focus-areas-and-render-readiness-cards
Decision: none
Detour For: none
Return To: none
Completion Gate: GitHub issue #32 acceptance criteria pass: every generated active queue card displays its exact Campaign ID; rendering and validation tests cover the field; initialization, templates, installation and update remain consistent; operator documentation explains stable IDs versus queue positions; deterministic regeneration preserves order and lifecycle state; full Tool Shed validation passes.
Completion Evidence: none
Disposition: none

## Request

Deliver [GitHub issue #32](https://github.com/PC-Redemption/tool_shed/issues/32).

- Show the exact stable Campaign ID on every generated active-queue card.
- Keep that identifier visually and semantically distinct from the mutable 1-based `que N` position.
- Preserve the accessible icon-plus-text card format and deterministic queue order/lifecycle state.
- Align rendering, validation, initialization/templates, workspace install/update behavior,
  operator documentation, and tests.

## Completion Check

GitHub issue #32 acceptance criteria pass: every generated active queue card displays its exact Campaign ID; rendering and validation tests cover the field; initialization, templates, installation and update remain consistent; operator documentation explains stable IDs versus queue positions; deterministic regeneration preserves order and lifecycle state; full Tool Shed validation passes.
