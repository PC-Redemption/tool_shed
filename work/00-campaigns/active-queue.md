# Active Campaign Queue

Updated: 2026-08-18

## Owner State

- Last completed: fail-closed-on-cross-workspace-routing — Fail closed on cross-workspace Tool Shed routing and mutations
- Working now: add-workspace-wide-ts-doctor-command — Add a workspace-wide ts: doctor integrity and consistency command
- Next: define-nested-cycles-and-owning-transitions — Define nested Tool Shed cycles and owning transitions
- Blocker or decision needed: none
- Detour and return point: none

## Ordered Queue

Queue positions are mutable; parenthesized campaign numbers and full `Campaign ID` values are stable.

1. (031) **[Add a workspace-wide ts: doctor integrity and consistency command](active/031-add-workspace-wide-ts-doctor-command.md)**
   - 🆔 **CAMPAIGN ID:** `add-workspace-wide-ts-doctor-command`
   - 🚦 **STATE:** 🔵 **WORKING**
   - 🎯 **PRIMARY FOCUS AREAS:** Workspace Safety and Performance
   - 🧩 **SUPPORTING FOCUS AREAS:** Artifact Workflows; Campaign Lifecycle; Provider Portability; Snapshot Delivery; Qualification and Release
   - 🏁 **OUTCOME:** Resolve GitHub issue #39 by adding one read-only-by-default workspace health command that composes existing checks, detects cross-surface inconsistencies, distinguishes internal consistency from external truth, and emits one unambiguous overall verdict with precise next actions.
2. (029) **[Define nested Tool Shed cycles and owning transitions](active/029-define-nested-cycles-and-owning-transitions.md)**
   - 🆔 **CAMPAIGN ID:** `define-nested-cycles-and-owning-transitions`
   - 🚦 **STATE:** 🟢 **READY**
   - 🎯 **PRIMARY FOCUS AREAS:** Campaign Lifecycle
   - 🧩 **SUPPORTING FOCUS AREAS:** Provider Portability; Qualification and Release
   - 🏁 **OUTCOME:** Resolve GitHub issue #37 by defining the five nested Tool Shed cycles and four computed work origins, exposing one consistent Cycle State Capsule in overview, status, and next, and making empty-queue next report the owning higher-level cycle and exact safe transition without bypassing approval or materialization boundaries.
3. (027) **[Publish and verify Tool Shed v0.22.0](active/027-publish-and-verify-tool-shed-v0-22-0.md)**
   - 🆔 **CAMPAIGN ID:** `publish-and-verify-tool-shed-v0-22-0`
   - 🚦 **STATE:** 🟢 **READY**
   - 🎯 **PRIMARY FOCUS AREAS:** Qualification and Release
   - 🧩 **SUPPORTING FOCUS AREAS:** Snapshot Delivery; Provider Portability
   - 🔗 **DEPENDS ON:** `compact-tool-shed-site-and-publish-guided-workflows` — ✅ **COMPLETE**
   - 🔗 **DEPENDS ON:** `harden-upgrade-campaign-number-convergence` — ✅ **COMPLETE**
   - 🔗 **DEPENDS ON:** `link-public-help-site-from-help-responses` — ✅ **COMPLETE**
   - 🏁 **OUTCOME:** Finish GitHub issue #34 and ship the verified fixes for issues #35 and #36 by freezing the complete v0.22.0 candidate, pushing it, publishing the traceable GitHub release, verifying canonical release and public documentation state, and closing each issue only when its acceptance evidence is satisfied.
