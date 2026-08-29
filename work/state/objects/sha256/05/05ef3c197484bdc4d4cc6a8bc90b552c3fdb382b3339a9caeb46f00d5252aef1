# Reconcile whole-work campaign coverage

Status: complete
Type: campaign
Updated: 2026-08-17
Next Action: none
Campaign ID: reconcile-whole-work-campaign-coverage
Campaign Number: 006
Outcome: Make campaign reconciliation discover and classify unresolved work across the complete work tree so a clean owner queue proves coverage instead of only projection consistency
Depends On: none
Decision: none
Detour For: none
Return To: none
Completion Gate: GitHub issue 26 remains linked; default reconciliation is read-only; all supported work artifacts and exclusions are counted; unresolved artifacts outside work/00-campaigns are reported; explicit campaign, standalone, and excluded associations reconcile deterministically; ambiguous candidates require owner decisions; approved CRUD operations require an exact manifest and whole-work stale-write token; lifecycle history is preserved; proposed order is never silently applied; focused cross-platform tests, operator documentation, and full validation pass
Completion Evidence: GitHub #26; unreleased 0.15.0 candidate; whole-work coverage and manifest-gated CRUD tests; full validator 104/104; installed skill exact with backup tool-shed.backup-20260814T164447Z
Completion Date: 2026-08-14
Completion Order: 5
Disposition: completed

## Request

GitHub issue: https://github.com/PC-Redemption/tool_shed/issues/26

Extend campaign reconciliation beyond projection consistency under `work/00-campaigns/`. Add a
read-only whole-`work/` discovery phase that inventories supported artifacts and documented
exclusions, detects unresolved work, builds relationships from artifact headers, and compares each
unresolved root or cluster with active, completed, deferred, and abandoned campaign coverage.

Report uncovered, unlinked, duplicate, mismatched, conflicting, stale-completion, and unstructured
candidates with coverage totals and explicit confidence. Add deterministic `Campaign:` association
semantics, including reasoned `standalone` and `excluded` alternatives. Any applied create or update
operation must use an exact approved manifest and a stale-write token covering the complete scanned
work surface. Preserve lifecycle history and leave semantic classification and queue priority to
the owner when evidence is ambiguous.

## Completion Check

GitHub issue 26 remains linked; default reconciliation is read-only; all supported work artifacts and exclusions are counted; unresolved artifacts outside work/00-campaigns are reported; explicit campaign, standalone, and excluded associations reconcile deterministically; ambiguous candidates require owner decisions; approved CRUD operations require an exact manifest and whole-work stale-write token; lifecycle history is preserved; proposed order is never silently applied; focused cross-platform tests, operator documentation, and full validation pass
