# Active Campaign Queue

Updated: 2026-08-25

## Owner State

- Last completed: repair-project-scoped-app-server-dispatch — Repair project-scoped App Server dispatch
- Working now: route-windows-verification-through-console-sandbox — Route Windows verification through console sandbox
- Next: none
- Blocker or decision needed: prove-bactron-core-native-windows-app-server-workflow — Prove the Bactron Core native Windows App Server workflow
- Detour and return point: route-windows-verification-through-console-sandbox — Route Windows verification through console sandbox

## Ordered Queue

Queue positions are mutable; parenthesized campaign numbers and full `Campaign ID` values are stable.

1. (064) **[Route Windows verification through console sandbox](active/064-route-windows-verification-through-console-sandbox.md)**
   - 🆔 **CAMPAIGN ID:** `route-windows-verification-through-console-sandbox`
   - 🚦 **STATE:** 🔵 **WORKING**
   - 🎯 **PRIMARY FOCUS AREAS:** Provider Portability
   - 🧩 **SUPPORTING FOCUS AREAS:** Workspace Safety and Performance
   - ↪️ **DETOUR FOR:** prove-bactron-core-native-windows-app-server-workflow
   - ↩️ **RETURN TO:** prove-bactron-core-native-windows-app-server-workflow
   - 🏁 **OUTCOME:** Make the one-command Windows App Server path execute declared deterministic verification reliably through the exact GUI Codex local sandbox after a successful worker turn, without a second model turn or post-mutation replay.
2. (059) **[Prove the Bactron Core native Windows App Server workflow](active/059-prove-bactron-core-native-windows-app-server-workflow.md)**
   - 🆔 **CAMPAIGN ID:** `prove-bactron-core-native-windows-app-server-workflow`
   - 🚦 **STATE:** 🔴 **BLOCKED**
   - 🎯 **PRIMARY FOCUS AREAS:** Snapshot Delivery
   - 🧩 **SUPPORTING FOCUS AREAS:** Provider Portability; Workspace Safety and Performance; Qualification and Release
   - 🔗 **DEPENDS ON:** `synchronize-maintainer-skill-and-smoke-v0-28-0` — ✅ **COMPLETE**
   - ⚠️ **DECISION NEEDED:** Detour Campaign 064 must replace the failing Windows post-turn command RPC before the final fresh proof.
   - 🗺️ **ROADMAP:** low-token-cross-platform-campaign-execution r1 / M4-WINDOWS-INSTALLED / unlocks G4-WINDOWS-INSTALLED-WORKS
   - 🏁 **OUTCOME:** Show that the released Tool Shed works through the normal Windows GUI environment for a fresh asset-aware Core campaign.
