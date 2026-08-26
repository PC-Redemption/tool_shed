# Active Campaign Queue

Updated: 2026-08-26

## Owner State

- Last completed: publish-and-synchronize-first-pass-app-server-preparation — Publish and synchronize first-pass App Server preparation
- Working now: none
- Next: none
- Blocker or decision needed: adopt-first-pass-app-server-preparation-in-core — Adopt first-pass App Server preparation in Core
- Detour and return point: none

## Ordered Queue

Queue positions are mutable; parenthesized campaign numbers and full `Campaign ID` values are stable.

1. (085) **[Adopt first-pass App Server preparation in Core](active/085-adopt-first-pass-app-server-preparation-in-core.md)**
   - 🆔 **CAMPAIGN ID:** `adopt-first-pass-app-server-preparation-in-core`
   - 🚦 **STATE:** 🔴 **BLOCKED**
   - 🎯 **PRIMARY FOCUS AREAS:** Provider Portability
   - 🧩 **SUPPORTING FOCUS AREAS:** Snapshot Delivery; Workspace Safety and Performance; Campaign Lifecycle
   - 🔗 **DEPENDS ON:** `publish-and-synchronize-first-pass-app-server-preparation` — ✅ **COMPLETE**
   - ⚠️ **DECISION NEEDED:** separate owner Core upgrade and operator-assisted Windows authorization required
   - 🗺️ **ROADMAP:** low-token-cross-platform-campaign-execution r7 / M13-CORE-FIRST-PASS-ADOPTION / unlocks G13-CORE-FIRST-PASS-OWNER-READY
   - 🏁 **OUTCOME:** A fresh ordinary Core campaign completes on its first automatically prepared Windows App Server attempt.
