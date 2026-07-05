# Inventory: Example Existing Project Surfaces

Status: example
Type: inventory
Updated: 2026-07-05
Next Action: none
Parent: work/maps/map-example-existing-project.md

## Scope

Existing project surfaces discovered during Level 2 onboarding.

## Summary

- Project: example service
- Primary purpose: small web service with docs, source, tests, and deployment config
- Main entry points: `src/app.py`, `README.md`
- Validation commands: `pytest`
- Current ground action: decide whether stale deployment docs need a ticket or docs update

## Surfaces

| Surface | Location | Kind | Observed Role | Status | Follow-Up |
| --- | --- | --- | --- | --- | --- |
| README | `README.md` | docs | project front door and local setup | current | promote stable setup notes to docs if they grow |
| Source | `src/` | code | product implementation | current | map major modules if work expands |
| Tests | `tests/` | validation | regression checks | current | record command in map |
| Deployment notes | `docs/deploy.md` | docs | operational reference | unknown | verify before creating runbook |
| CI | `.github/workflows/ci.yml` | validation | automated test path | current | keep as validation surface |

## Existing Work Signals

| Signal | Location | What It Suggests | Confidence | Route |
| --- | --- | --- | --- | --- |
| TODO about deploy token | `docs/deploy.md` | possible stale operational doc | medium | ticket or docs |
| Missing architecture overview | no `docs/architecture.md` | documentation gap | low | spike before docs |

## Backfill Candidates

| Candidate | Artifact Type | Evidence | Reason |
| --- | --- | --- | --- |
| Verify deployment notes | ticket | TODO in `docs/deploy.md` | specific current uncertainty |
| Architecture overview | spike | missing docs plus unclear module roles | learn before writing docs |

## Observed Facts

- The project has a README, source tree, tests, deployment notes, and CI config.
- `pytest` is the documented validation command.

## Inferred Or Uncertain

- Deployment notes may be stale, but the inventory does not prove that by itself.
- Architecture docs may be useful if future work spans multiple modules.

## Recommendations

- Create one ticket to verify deployment notes if deployment work is active.
- Create a spike before writing architecture docs.
- Do not backfill historical ADRs without explicit evidence.

## Verification

- [x] Project map links to this inventory.
- [x] Inventory covers docs, code, tests, runtime/build, and existing planning surfaces where present.
- [x] Inferred items are marked separately from observed facts.
- [x] Follow-up artifacts are recommended only when supported by evidence.
