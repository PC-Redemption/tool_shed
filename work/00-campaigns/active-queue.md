# Active Campaign Queue

Updated: 2026-08-26

## Owner State

- Last completed: bound-explicit-reference-app-server-preparation — Bound Explicit-Reference App Server Preparation
- Working now: none
- Next: none
- Blocker or decision needed: publish-explicit-reference-preparation-repair — Publish Explicit-Reference Preparation Repair; adopt-first-pass-app-server-preparation-in-core — Adopt first-pass App Server preparation in Core
- Detour and return point: publish-explicit-reference-preparation-repair — Publish Explicit-Reference Preparation Repair

## Ordered Queue

Queue positions are mutable; parenthesized campaign numbers and full `Campaign ID` values are stable.

1. (087) **[Publish Explicit-Reference Preparation Repair](active/087-publish-explicit-reference-preparation-repair.md)**
   - 🆔 **CAMPAIGN ID:** `publish-explicit-reference-preparation-repair`
   - 🚦 **STATE:** 🔴 **BLOCKED**
   - 🎯 **PRIMARY FOCUS AREAS:** Qualification and Release
   - 🧩 **SUPPORTING FOCUS AREAS:** Provider Portability; Snapshot Delivery
   - 🔗 **DEPENDS ON:** `bound-explicit-reference-app-server-preparation` — ✅ **COMPLETE**
   - ⚠️ **DECISION NEEDED:** separate owner authorization required for patch release publication and maintainer installed-skill synchronization
   - ↪️ **DETOUR FOR:** adopt-first-pass-app-server-preparation-in-core
   - ↩️ **RETURN TO:** adopt-first-pass-app-server-preparation-in-core
   - 🏁 **OUTCOME:** Publish the validated explicit-reference preparation bound in a verified Tool Shed patch release and synchronize the maintainer installed skill so the already-authorized Core adoption campaign can resume from a stable release.
2. (085) **[Adopt first-pass App Server preparation in Core](active/085-adopt-first-pass-app-server-preparation-in-core.md)**
   - 🆔 **CAMPAIGN ID:** `adopt-first-pass-app-server-preparation-in-core`
   - 🚦 **STATE:** 🔴 **BLOCKED**
   - 🎯 **PRIMARY FOCUS AREAS:** Provider Portability
   - 🧩 **SUPPORTING FOCUS AREAS:** Snapshot Delivery; Workspace Safety and Performance; Campaign Lifecycle
   - 🔗 **DEPENDS ON:** `publish-and-synchronize-first-pass-app-server-preparation` — ✅ **COMPLETE**
   - ⚠️ **DECISION NEEDED:** Campaign 086 repaired the v0.29.10 context-padding defect locally; Campaign 087 must publish and synchronize the corrective patch before the already-authorized Core re-upgrade and Windows proof resume
   - 🗺️ **ROADMAP:** low-token-cross-platform-campaign-execution r7 / M13-CORE-FIRST-PASS-ADOPTION / unlocks G13-CORE-FIRST-PASS-OWNER-READY
   - 🏁 **OUTCOME:** A fresh ordinary Core campaign completes on its first automatically prepared Windows App Server attempt.
