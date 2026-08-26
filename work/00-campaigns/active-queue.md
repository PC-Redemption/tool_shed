# Active Campaign Queue

Updated: 2026-08-26

## Owner State

- Last completed: preserve-file-change-handoff-and-robust-doc-verification — Preserve File-Change Handoff and Robust Documentation Verification
- Working now: publish-and-synchronize-file-change-handoff-repair — Publish and Synchronize File-Change Handoff Repair
- Next: none
- Blocker or decision needed: adopt-first-pass-app-server-preparation-in-core — Adopt first-pass App Server preparation in Core
- Detour and return point: publish-and-synchronize-file-change-handoff-repair — Publish and Synchronize File-Change Handoff Repair

## Ordered Queue

Queue positions are mutable; parenthesized campaign numbers and full `Campaign ID` values are stable.

1. (089) **[Publish and Synchronize File-Change Handoff Repair](active/089-publish-and-synchronize-file-change-handoff-repair.md)**
   - 🆔 **CAMPAIGN ID:** `publish-and-synchronize-file-change-handoff-repair`
   - 🚦 **STATE:** 🔵 **WORKING**
   - 🎯 **PRIMARY FOCUS AREAS:** Qualification and Release
   - 🧩 **SUPPORTING FOCUS AREAS:** Provider Portability; Snapshot Delivery
   - 🔗 **DEPENDS ON:** `preserve-file-change-handoff-and-robust-doc-verification` — ✅ **COMPLETE**
   - ↪️ **DETOUR FOR:** adopt-first-pass-app-server-preparation-in-core
   - ↩️ **RETURN TO:** adopt-first-pass-app-server-preparation-in-core
   - 🏁 **OUTCOME:** Publish the locally proven file-change handoff and whitespace-robust documentation-verifier correction as a verified Tool Shed patch release and synchronize the maintainer installed skill so Campaign 085 can resume under its existing Core authorization.
2. (085) **[Adopt first-pass App Server preparation in Core](active/085-adopt-first-pass-app-server-preparation-in-core.md)**
   - 🆔 **CAMPAIGN ID:** `adopt-first-pass-app-server-preparation-in-core`
   - 🚦 **STATE:** 🔴 **BLOCKED**
   - 🎯 **PRIMARY FOCUS AREAS:** Provider Portability
   - 🧩 **SUPPORTING FOCUS AREAS:** Snapshot Delivery; Workspace Safety and Performance; Campaign Lifecycle
   - 🔗 **DEPENDS ON:** `publish-and-synchronize-file-change-handoff-repair` — 🔵 **WORKING**
   - ⚠️ **DECISION NEEDED:** Campaign 088 repaired and focused-tested the two defects exposed by Core Campaign 022; publishing that new correction and synchronizing the maintainer skill require separate owner authorization before the already-authorized Core proof resumes
   - 🗺️ **ROADMAP:** low-token-cross-platform-campaign-execution r7 / M13-CORE-FIRST-PASS-ADOPTION / unlocks G13-CORE-FIRST-PASS-OWNER-READY
   - 🏁 **OUTCOME:** A fresh ordinary Core campaign completes on its first automatically prepared Windows App Server attempt.
