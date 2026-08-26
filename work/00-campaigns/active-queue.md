# Active Campaign Queue

Updated: 2026-08-26

## Owner State

- Last completed: publish-and-synchronize-bounded-app-server-release — Publish and synchronize the bounded App Server release
- Working now: none
- Next: none
- Blocker or decision needed: repair-and-reprove-windows-app-server-campaign-path — Repair and re-prove the Windows App Server campaign path
- Detour and return point: none

## Ordered Queue

Queue positions are mutable; parenthesized campaign numbers and full `Campaign ID` values are stable.

1. (068) **[Repair and re-prove the Windows App Server campaign path](active/068-repair-and-reprove-windows-app-server-campaign-path.md)**
   - 🆔 **CAMPAIGN ID:** `repair-and-reprove-windows-app-server-campaign-path`
   - 🚦 **STATE:** 🔴 **BLOCKED**
   - 🎯 **PRIMARY FOCUS AREAS:** Provider Portability
   - 🧩 **SUPPORTING FOCUS AREAS:** Snapshot Delivery; Workspace Safety and Performance; Qualification and Release
   - 🔗 **DEPENDS ON:** `publish-and-synchronize-bounded-app-server-release` — ✅ **COMPLETE**
   - ⚠️ **DECISION NEEDED:** separate owner Core snapshot and operator-assisted Windows authorization required
   - 🗺️ **ROADMAP:** low-token-cross-platform-campaign-execution r2 / M8-WINDOWS-REALISTIC-REPROOF / unlocks G8-WINDOWS-REALISTIC-BOUNDED
   - 🏁 **OUTCOME:** Make realistic Core App Server execution use the shared budget and reliable built-in deterministic verification transport.
