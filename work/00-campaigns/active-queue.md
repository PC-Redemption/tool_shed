# Active Campaign Queue

Updated: 2026-08-25

## Owner State

- Last completed: dogfood-maintained-tool-shed-app-server-execution — Dogfood maintained Tool Shed App Server execution
- Working now: publish-minimum-usable-tool-shed-v0-28-0 — Publish the minimum usable Tool Shed v0.28.0 release
- Next: none
- Blocker or decision needed: none
- Detour and return point: none

## Ordered Queue

Queue positions are mutable; parenthesized campaign numbers and full `Campaign ID` values are stable.

1. (056) **[Publish the minimum usable Tool Shed v0.28.0 release](active/056-publish-minimum-usable-tool-shed-v0-28-0.md)**
   - 🆔 **CAMPAIGN ID:** `publish-minimum-usable-tool-shed-v0-28-0`
   - 🚦 **STATE:** 🔵 **WORKING**
   - 🎯 **PRIMARY FOCUS AREAS:** Qualification and Release
   - 🧩 **SUPPORTING FOCUS AREAS:** Provider Portability
   - 🔗 **DEPENDS ON:** `dogfood-maintained-tool-shed-app-server-execution` — ✅ **COMPLETE**
   - 🗺️ **ROADMAP:** low-token-cross-platform-campaign-execution r1 / M2-MINIMUM-RELEASE
   - 🏁 **OUTCOME:** Publish the dogfooded App Server candidate through the existing traceable release path without adding speculative qualification.
2. (057) **[Synchronize the maintainer skill and smoke v0.28.0](active/057-synchronize-maintainer-skill-and-smoke-v0-28-0.md)**
   - 🆔 **CAMPAIGN ID:** `synchronize-maintainer-skill-and-smoke-v0-28-0`
   - 🚦 **STATE:** 🟡 **WAITING**
   - 🎯 **PRIMARY FOCUS AREAS:** Snapshot Delivery
   - 🧩 **SUPPORTING FOCUS AREAS:** Provider Portability; Qualification and Release
   - 🔗 **DEPENDS ON:** `publish-minimum-usable-tool-shed-v0-28-0` — 🔵 **WORKING**
   - 🗺️ **ROADMAP:** low-token-cross-platform-campaign-execution r1 / M2-MINIMUM-RELEASE / unlocks G2-RELEASE-USABLE
   - 🏁 **OUTCOME:** Make the published low-token execution contract available to fresh Codex sessions on the maintainer host.
