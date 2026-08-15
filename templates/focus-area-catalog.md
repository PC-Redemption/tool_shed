# {{ title }} Focus Areas

Status: proposed
Type: focus-area-catalog
Updated: {{ date }}
Next Action: inspect the complete project surface, propose evidence-backed areas, and request owner approval

This catalog is project-specific durable state. Ordinary queue rendering consumes it only after
`Status: approved`; agents must not silently rediscover, rename, or hard-code focus areas.

## Discovery Evidence

Review README and architecture documentation, source modules and build targets, external
applications and repositories, runtime/service/hardware boundaries, tests and fixtures,
qualification infrastructure, deployment/release/regulatory/supply workflows, and active,
deferred, and completed work.

Test the proposed catalog for coverage, overlap, excessive breadth, temporary categories, weak
evidence, and unmapped enduring responsibilities. Record uncertainties for owner review.

## Proposed Focus Areas

Add one block per proposed area using stable lowercase kebab-case IDs:

<!-- Focus Area ID: example-area -->
<!-- Name: Example Area -->
<!-- Purpose: Enduring project responsibility this area owns -->
<!-- Includes: Components, workflows, and boundaries included in the area -->
<!-- Excludes: Adjacent responsibilities intentionally outside the area -->
<!-- Evidence: Multiple project paths, tests, runtime boundaries, or lifecycle workflows -->
<!-- Uncertainty: Open boundary questions or none -->

## Approval

Owner decision: pending

Change `Status` to `approved` only after the owner accepts the catalog. Assign focus areas to all
active campaigns in the same exact reconciliation manifest so approved state never silently leaves
active work unmapped.
