# Active Campaign Queue

Updated: 2026-08-27

## Owner State

- Last completed: qualify-and-document-operator-trust-camp-boundaries — Qualify and document operator-trust CAMP boundaries
- Working now: none
- Next: none
- Blocker or decision needed: publish-and-synchronize-passive-app-server-dogfooding — Publish and synchronize passive App Server dogfooding; field-dogfood-passive-app-server-mode — Field-dogfood passive App Server mode in product work
- Detour and return point: none

## Ordered Queue

Queue positions are mutable; parenthesized campaign numbers and full `Campaign ID` values are stable.

1. (096) **[Publish and synchronize passive App Server dogfooding](active/096-publish-and-synchronize-passive-app-server-dogfooding.md)**
   - 🆔 **CAMPAIGN ID:** `publish-and-synchronize-passive-app-server-dogfooding`
   - 🚦 **STATE:** 🔴 **BLOCKED**
   - 🎯 **PRIMARY FOCUS AREAS:** Qualification and Release
   - 🧩 **SUPPORTING FOCUS AREAS:** Snapshot Delivery; Provider Portability
   - 🔗 **DEPENDS ON:** `qualify-passive-app-server-dogfooding-core` — ✅ **COMPLETE**
   - ⚠️ **DECISION NEEDED:** fresh Codex task must load synchronized v0.30.0 skill and run ts: app-server status
   - 🗺️ **ROADMAP:** passive-app-server-dogfooding r1 / M2-FIELD-ADOPTION
   - 🏁 **OUTCOME:** A traceable Tool Shed release and synchronized maintainer/client skill make the M1 behavior available for real work.
2. (097) **[Field-dogfood passive App Server mode in product work](active/097-field-dogfood-passive-app-server-mode.md)**
   - 🆔 **CAMPAIGN ID:** `field-dogfood-passive-app-server-mode`
   - 🚦 **STATE:** 🔴 **BLOCKED**
   - 🎯 **PRIMARY FOCUS AREAS:** Provider Portability
   - 🧩 **SUPPORTING FOCUS AREAS:** Qualification and Release; Workspace Safety and Performance
   - 🔗 **DEPENDS ON:** `publish-and-synchronize-passive-app-server-dogfooding` — 🔴 **BLOCKED**
   - ⚠️ **DECISION NEEDED:** separate authority for each product workspace mutation remains required
   - 🗺️ **ROADMAP:** passive-app-server-dogfooding r1 / M2-FIELD-ADOPTION / unlocks G2-FIELD-DOGFOOD-WORKS
   - 🏁 **OUTCOME:** Representative normal product work proves that passive mode keeps work moving and produces useful sanitized evidence without repetitive owner interaction.
