# Active Campaign Queue

Updated: 2026-08-25

## Owner State

- Last completed: eliminate-nested-codex-wrapper-and-prove-linux-dispatch — Eliminate the nested Codex wrapper and prove one-call Linux App Server dispatch
- Working now: publish-and-synchronize-direct-app-server-dispatch-v0-29-1 — Publish and synchronize direct App Server dispatch v0.29.1
- Next: none
- Blocker or decision needed: prove-bactron-core-native-windows-app-server-workflow — Prove the Bactron Core native Windows App Server workflow
- Detour and return point: publish-and-synchronize-direct-app-server-dispatch-v0-29-1 — Publish and synchronize direct App Server dispatch v0.29.1

## Ordered Queue

Queue positions are mutable; parenthesized campaign numbers and full `Campaign ID` values are stable.

1. (062) **[Publish and synchronize direct App Server dispatch v0.29.1](active/062-publish-and-synchronize-direct-app-server-dispatch-v0-29-1.md)**
   - 🆔 **CAMPAIGN ID:** `publish-and-synchronize-direct-app-server-dispatch-v0-29-1`
   - 🚦 **STATE:** 🔵 **WORKING**
   - 🎯 **PRIMARY FOCUS AREAS:** Qualification and Release
   - 🧩 **SUPPORTING FOCUS AREAS:** Provider Portability; Snapshot Delivery
   - 🔗 **DEPENDS ON:** `eliminate-nested-codex-wrapper-and-prove-linux-dispatch` — ✅ **COMPLETE**
   - ↪️ **DETOUR FOR:** prove-bactron-core-native-windows-app-server-workflow
   - ↩️ **RETURN TO:** prove-bactron-core-native-windows-app-server-workflow
   - 🏁 **OUTCOME:** Release Tool Shed 0.29.1 with the clean-runner import repair, verified two-commit provenance, and exact installed-skill parity before Windows adoption.
2. (059) **[Prove the Bactron Core native Windows App Server workflow](active/059-prove-bactron-core-native-windows-app-server-workflow.md)**
   - 🆔 **CAMPAIGN ID:** `prove-bactron-core-native-windows-app-server-workflow`
   - 🚦 **STATE:** 🔴 **BLOCKED**
   - 🎯 **PRIMARY FOCUS AREAS:** Snapshot Delivery
   - 🧩 **SUPPORTING FOCUS AREAS:** Provider Portability; Workspace Safety and Performance; Qualification and Release
   - 🔗 **DEPENDS ON:** `synchronize-maintainer-skill-and-smoke-v0-28-0` — ✅ **COMPLETE**
   - ⚠️ **DECISION NEEDED:** Owner consent is required before any Bactron Core snapshot change or Windows App Server proof.
   - 🗺️ **ROADMAP:** low-token-cross-platform-campaign-execution r1 / M4-WINDOWS-INSTALLED / unlocks G4-WINDOWS-INSTALLED-WORKS
   - 🏁 **OUTCOME:** Show that the released Tool Shed works through the normal Windows GUI environment for a fresh asset-aware Core campaign.
