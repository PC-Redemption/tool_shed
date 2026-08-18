# Define nested Tool Shed cycles and owning transitions

Status: working
Type: campaign
Updated: 2026-08-18
Next Action: execute the campaign completion gate
Campaign ID: define-nested-cycles-and-owning-transitions
Campaign Number: 029
Outcome: Resolve GitHub issue #37 by defining the five nested Tool Shed cycles and four computed work origins, exposing one consistent Cycle State Capsule in overview, status, and next, and making empty-queue next report the owning higher-level cycle and exact safe transition without bypassing approval or materialization boundaries.
Primary Focus Areas: campaign-lifecycle
Supporting Focus Areas: provider-portability, qualification-release
Depends On: none
Decision: none
Detour For: none
Return To: none
Completion Gate: GitHub issue #37 acceptance criteria pass: operator and command docs define five nested cycles, four computed work origins, cycle completion and return control, and independent origin, coordination, work-level, and cycle-state dimensions; overview, status, and next use one human and JSON Cycle State Capsule calculation; empty-queue next reports pending plan approval, a derivable next milestone, a fully completed roadmap, or no higher-level driver with an exact safe transition; existing approval, protected-environment, and materialization boundaries remain unchanged; direct, owner-originated, roadmap-derived, detour-return, pending-plan, derivable-milestone, and completed-roadmap tests pass; the full validator passes; and issue #37 is updated with verified evidence.
Completion Evidence: none
Disposition: none

## Request

Deliver [GitHub issue #37](https://github.com/PC-Redemption/tool_shed/issues/37). Define and teach
one nested control model—Program Cycle, Milestone Wave Cycle, Queue Cycle, Campaign Cycle, and
Evidence Loop—while keeping work origin, coordination level, execution endpoint, and cycle state
as independent dimensions. Compute work origin from existing state as direct, owner-originated,
roadmap-derived, or detour without introducing a conflicting use of `standalone` or unnecessary
required headers.

Add one shared Cycle State Capsule calculation to human-readable and JSON output for `overview`,
`status`, and `next`. When the queue has no ready campaign, inspect higher-level state and report
which cycle owns the next transition: pending Dangler Resolution work, exact campaign-plan
approval, an incomplete materialized milestone or gate, a derivable next milestone, roadmap drift
requiring review, a completed roadmap, or no higher-level driver. Report the exact safe command or
owner choice without approving, materializing, starting, revising, or bypassing an existing token,
authority, or protected-environment boundary.

Keep human and JSON state consistent, document where control returns when each cycle completes,
and cover the issue's empty-queue, milestone progression, completed-program, origin, and detour
scenarios with focused regression tests before full qualification.

## Completion Check

GitHub issue #37 acceptance criteria pass: operator and command docs define five nested cycles, four computed work origins, cycle completion and return control, and independent origin, coordination, work-level, and cycle-state dimensions; overview, status, and next use one human and JSON Cycle State Capsule calculation; empty-queue next reports pending plan approval, a derivable next milestone, a fully completed roadmap, or no higher-level driver with an exact safe transition; existing approval, protected-environment, and materialization boundaries remain unchanged; direct, owner-originated, roadmap-derived, detour-return, pending-plan, derivable-milestone, and completed-roadmap tests pass; the full validator passes; and issue #37 is updated with verified evidence.
