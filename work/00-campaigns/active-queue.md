# Active Campaign Queue

Updated: 2026-08-25

## Owner State

- Last completed: publish-and-synchronize-direct-app-server-dispatch-v0-29-1 — Publish and synchronize direct App Server dispatch v0.29.1
- Working now: repair-project-scoped-app-server-dispatch — Repair project-scoped App Server dispatch
- Next: none
- Blocker or decision needed: prove-bactron-core-native-windows-app-server-workflow — Prove the Bactron Core native Windows App Server workflow
- Detour and return point: repair-project-scoped-app-server-dispatch — Repair project-scoped App Server dispatch

## Ordered Queue

Queue positions are mutable; parenthesized campaign numbers and full `Campaign ID` values are stable.

1. (063) **[Repair project-scoped App Server dispatch](active/063-repair-project-scoped-app-server-dispatch.md)**
   - 🆔 **CAMPAIGN ID:** `repair-project-scoped-app-server-dispatch`
   - 🚦 **STATE:** 🔵 **WORKING**
   - 🎯 **PRIMARY FOCUS AREAS:** Snapshot Delivery
   - 🧩 **SUPPORTING FOCUS AREAS:** Provider Portability
   - ↪️ **DETOUR FOR:** prove-bactron-core-native-windows-app-server-workflow
   - ↩️ **RETURN TO:** prove-bactron-core-native-windows-app-server-workflow
   - 🏁 **OUTCOME:** Make the direct dispatcher carry an explicitly selected project-scoped App Server configuration into the bounded execution it already authorized, while preserving exact executable identity and fail-closed defaults.
2. (059) **[Prove the Bactron Core native Windows App Server workflow](active/059-prove-bactron-core-native-windows-app-server-workflow.md)**
   - 🆔 **CAMPAIGN ID:** `prove-bactron-core-native-windows-app-server-workflow`
   - 🚦 **STATE:** 🔴 **BLOCKED**
   - 🎯 **PRIMARY FOCUS AREAS:** Snapshot Delivery
   - 🧩 **SUPPORTING FOCUS AREAS:** Provider Portability; Workspace Safety and Performance; Qualification and Release
   - 🔗 **DEPENDS ON:** `synchronize-maintainer-skill-and-smoke-v0-28-0` — ✅ **COMPLETE**
   - ⚠️ **DECISION NEEDED:** Detour Campaign 063 must repair and release project-scoped direct dispatch before the Windows proof can continue.
   - 🗺️ **ROADMAP:** low-token-cross-platform-campaign-execution r1 / M4-WINDOWS-INSTALLED / unlocks G4-WINDOWS-INSTALLED-WORKS
   - 🏁 **OUTCOME:** Show that the released Tool Shed works through the normal Windows GUI environment for a fresh asset-aware Core campaign.
