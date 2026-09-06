# IDEA-0023 Remaining Work Hierarchy — Work2 Evidence

Status: passed
Recorded: 2026-09-06
Campaign: `CAMP-0169`
Candidate commit: `f304e230881a9ad23342aa0338d4b2967df8b2fe`
Candidate version: `0.50.0` (unpublished development candidate)

## Result

The dashboard Work tab now defaults to a deterministic Remaining Tree. It excludes only work that
is terminal, reconciled, closed, and no longer in an active release stage; preserves required
ancestor context; orders complete root chains by reported planning position and readiness; marks
exactly one executable next Campaign; and routes malformed, missing, multiple, self, or cyclic
parentage to a fail-visible Needs placement group. The prior flat ledger remains available as the
explicit All/List audit view.

Every visible row has a compact command menu whose clipboard values come from an allowlist of
canonical Tool Shed entrypoints and stable IDs. Reported titles never become executable command
text.

## Verification

- 83 targeted dashboard, projection, and reporter tests passed.
- Focused Tool Shed validation passed, including the tracked-content manifest.
- Strict Doctor returned `HEALTHY` after the content commit.
- Isolated hosted development deployed image `tool-shed-dashboard:dev-f304e230881a` from the exact
  candidate. Development docs and dashboard health returned HTTP 200; the production regression
  health check also remained HTTP 200.
- An authenticated render inside the deployed image returned HTTP 200 for the default Tree and
  explicit All/List views. Tree/List switching, the Remaining default, and allowlisted `ts: status`
  row commands were present.
- The exact commit was registered with the open IDEA-0023 release cohort before CAMP-0169 was
  completed and reconciled.

## Work5 Boundary

CAMP-0170 owns release-profile validation, exact checkpoint replay on all development lanes,
exact-SHA CI, v0.50.0 publication, production promotion, immediate fresh-report convergence, issue
review, and recursive reconciliation through IDEA-0023.
