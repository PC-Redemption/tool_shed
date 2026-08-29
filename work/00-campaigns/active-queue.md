# Active Campaign Queue

Updated: 2026-08-28

## Owner State

- Last completed: upgrade-and-qualify-database-owned-collateral-maintainer — Upgrade and qualify the dual-role Tool Shed maintainer
- Working now: release-canary-and-reconcile-database-owned-collateral — Release, client-canary, and reconcile database-owned work collateral
- Next: none
- Blocker or decision needed: none
- Detour and return point: none

## Ordered Queue

Queue positions are mutable; parenthesized campaign numbers and full `Campaign ID` values are stable.

1. (119) **[Release, client-canary, and reconcile database-owned work collateral](active/119-release-canary-and-reconcile-database-owned-collateral.md)**
   - 🆔 **CAMPAIGN ID:** `release-canary-and-reconcile-database-owned-collateral`
   - 🚦 **STATE:** 🔵 **WORKING**
   - 🎯 **PRIMARY FOCUS AREAS:** Qualification and Release
   - 🧩 **SUPPORTING FOCUS AREAS:** Snapshot Delivery; Artifact Workflows; Provider Portability
   - 🔗 **DEPENDS ON:** `upgrade-and-qualify-database-owned-collateral-maintainer` — ✅ **COMPLETE**
   - 🗺️ **ROADMAP:** database-owned-work-collateral-and-lifecycle-views r3 / M6-RELEASE-CANARY-RECONCILED / unlocks G6-RELEASE-CANARY-RECONCILED
   - 🏁 **OUTCOME:** Publish a traceable release, prove clean and existing disconnected production-shaped installs, propagate all child results, and reconcile the source idea without deleting retained legacy collateral.
