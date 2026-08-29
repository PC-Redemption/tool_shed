# Evidence: Linux first-pass code proof interruption

Status: complete
Type: evidence
Updated: 2026-08-26
Next Action: replace the failed code/test and dependent asset-aware proofs in Roadmap Revision 4
Campaign: prove-first-pass-code-test-campaign-on-linux
Campaign Reason: truthful failed-proof evidence for G11-LINUX-FIRST-PASS-RELIABLE

## Result

Campaign 073 automatically prepared an atomic two-path code/test capsule and persisted a source
binding without manual editing. Preparation used 30,492 input tokens in one Sol/high turn and
estimated two worker turns plus an 8,192-byte largest tool result.

The Terra/medium worker started once and performed no mutation. Its first inspection produced a
19,301-byte serialized command result, exceeding the 16,384-byte live ceiling. The orchestrator
interrupted successfully, retained no raw output, ran no reserved verification, reported a safe
`safe_unverified` journal with no created, modified, deleted, or unexpected paths, and returned
`resume_bounded_camp`. Worker execution used 41,632 input tokens across two observed model turns.

This is a safe runtime result but a failed first-pass proof. Campaign 073 cannot truthfully satisfy
its first-worker completion gate and is preserved as abandoned history. Its not-yet-run dependent
asset proof is also abandoned. Neither campaign is replayed.

## Mitigation

The shared preparation path now injects every existing UTF-8 expected source file that fits the
64,000-byte context budget, blocking the preparation if an expected textual source cannot fit.
The worker contract now requires every inspection command to stay below 12,288 serialized bytes
using exact paths, symbol-scoped searches, and line ranges, and forbids broad listings, diffs, or
re-reading supplied files. A focused lifecycle repair permits abandoned historical dependents to
retain their original dependency without preventing truthful abandonment of the failed prerequisite.

Focused dispatcher, orchestration, and lifecycle checks passed 65 tests in 12.006 seconds. Fresh
code/test and asset-aware campaigns must prove the mitigation; this record does not pass G11.
