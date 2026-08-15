# Discover focus areas and render readiness cards

Status: working
Type: campaign
Updated: 2026-08-15
Next Action: execute the campaign completion gate
Campaign ID: discover-focus-areas-and-render-readiness-cards
Outcome: Tool Shed supports owner-approved, evidence-derived focus-area catalogs and renders deterministic, human-scannable campaign readiness cards using shared dependency-aware semantics.
Depends On: unify-dependency-aware-campaign-readiness
Decision: none
Detour For: none
Return To: none
Completion Gate: Issue #30 focus-area discovery, durable catalog, campaign fields, validation and migration, readiness-card rendering, tests, and operator documentation are complete; shared readiness semantics remain consistent and full validation passes.
Completion Evidence: none
Disposition: none

## Request

Deliver [GitHub issue #30](https://github.com/PC-Redemption/tool_shed/issues/30).

### Focus-area model

- Define an agent workflow that derives proposed focus areas from project documentation, code,
  runtime and hardware boundaries, tests, integrations, qualification, release, supply, and work
  history.
- Persist only owner-approved catalogs with stable IDs, names, purpose, inclusion and exclusion
  boundaries, evidence, and uncertainty; do not hard-code a universal taxonomy.
- Add first-class primary and supporting focus-area campaign fields, deterministic validation,
  reconciliation findings for unmapped work, and a previewed migration for focus areas embedded in
  outcome prose.

### Queue presentation

- Render ordered campaigns as deterministic, indented Markdown readiness cards.
- Show explicit, accessible text with portable emoji for working, ready, waiting, and blocked states.
- Render dependency state, primary and supporting focus areas, decisions, and outcomes while
  omitting empty optional rows.
- Consume the shared dependency-aware readiness semantics delivered by the prerequisite campaign;
  do not introduce another readiness interpretation.

### Verification and documentation

- Cover focus-area catalog validation, assignments, unknown IDs, migration preview, all readiness
  states, dependency and decision rendering, stale projections, and status/next consistency.
- Document focus-area derivation and approval, refresh triggers, campaign assignment rules, and
  visual state meanings.

## Completion Check

Issue #30 focus-area discovery, durable catalog, campaign fields, validation and migration, readiness-card rendering, tests, and operator documentation are complete; shared readiness semantics remain consistent and full validation passes.
