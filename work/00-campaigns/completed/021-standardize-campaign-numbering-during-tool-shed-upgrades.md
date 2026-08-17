# Standardize campaign numbering during Tool Shed upgrades

Status: complete
Type: campaign
Updated: 2026-08-17
Next Action: none
Campaign ID: standardize-campaign-numbering-during-tool-shed-upgrades
Campaign Number: 021
Outcome: Existing Tool Shed instances are reviewed during upgrade and safely converged to stable Campaign Number headers, numbered lifecycle filenames, and refreshed queue and index links when they do not already match, with owner content preserved and rollback on failure.
Primary Focus Areas: snapshot-delivery
Supporting Focus Areas: campaign-lifecycle, qualification-release
Depends On: test-campaign-id-heading-review
Decision: none
Detour For: none
Return To: none
Completion Gate: A legacy-upgrade fixture proves read-only mismatch reporting, exact-token guarded convergence, declared backup and mutation scope, collision refusal, semantic owner-content preservation, refreshed projections and indexes, rollback after injected failure, and the full repository validator passes.
Completion Evidence: Full validator passed 125 tests; legacy snapshot-upgrade fixture reported and converged numbering and filenames while preserving owner extensions; injected post-convergence failure restored the exact prior campaign tree; release manifest declares backed-up work/00-campaigns mutation scope; disposable installed-snapshot behavior verified.
Completion Date: 2026-08-17
Completion Order: 19
Disposition: completed

## Request

Add detailed execution context here.

## Completion Check

A legacy-upgrade fixture proves read-only mismatch reporting, exact-token guarded convergence, declared backup and mutation scope, collision refusal, semantic owner-content preservation, refreshed projections and indexes, rollback after injected failure, and the full repository validator passes.
