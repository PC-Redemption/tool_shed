# Active Campaign Queue

Updated: 2026-08-18

## Owner State

- Last completed: add-workspace-wide-ts-doctor-command — Add a workspace-wide ts: doctor integrity and consistency command
- Working now: define-nested-cycles-and-owning-transitions — Define nested Tool Shed cycles and owning transitions
- Next: publish-and-verify-tool-shed-v0-22-0 — Publish and verify Tool Shed v0.22.0
- Blocker or decision needed: none
- Detour and return point: none

## Ordered Queue

Queue positions are mutable; parenthesized campaign numbers and full `Campaign ID` values are stable.

1. (029) **[Define nested Tool Shed cycles and owning transitions](active/029-define-nested-cycles-and-owning-transitions.md)**
   - 🆔 **CAMPAIGN ID:** `define-nested-cycles-and-owning-transitions`
   - 🚦 **STATE:** 🔵 **WORKING**
   - 🎯 **PRIMARY FOCUS AREAS:** Campaign Lifecycle
   - 🧩 **SUPPORTING FOCUS AREAS:** Provider Portability; Qualification and Release
   - 🏁 **OUTCOME:** Resolve GitHub issue #37 by defining the five nested Tool Shed cycles and four computed work origins, exposing one consistent Cycle State Capsule in overview, status, and next, and making empty-queue next report the owning higher-level cycle and exact safe transition without bypassing approval or materialization boundaries.
2. (027) **[Publish and verify Tool Shed v0.22.0](active/027-publish-and-verify-tool-shed-v0-22-0.md)**
   - 🆔 **CAMPAIGN ID:** `publish-and-verify-tool-shed-v0-22-0`
   - 🚦 **STATE:** 🟢 **READY**
   - 🎯 **PRIMARY FOCUS AREAS:** Qualification and Release
   - 🧩 **SUPPORTING FOCUS AREAS:** Snapshot Delivery; Provider Portability
   - 🔗 **DEPENDS ON:** `compact-tool-shed-site-and-publish-guided-workflows` — ✅ **COMPLETE**
   - 🔗 **DEPENDS ON:** `harden-upgrade-campaign-number-convergence` — ✅ **COMPLETE**
   - 🔗 **DEPENDS ON:** `link-public-help-site-from-help-responses` — ✅ **COMPLETE**
   - 🏁 **OUTCOME:** Finish GitHub issue #34 and ship the verified fixes for issues #35 and #36 by freezing the complete v0.22.0 candidate, pushing it, publishing the traceable GitHub release, verifying canonical release and public documentation state, and closing each issue only when its acceptance evidence is satisfied.
