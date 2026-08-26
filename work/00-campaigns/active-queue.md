# Active Campaign Queue

Updated: 2026-08-26

## Owner State

- Last completed: establish-deterministic-app-server-worker-handoff — Establish deterministic App Server worker handoff
- Working now: none
- Next: prove-specified-command-free-first-pass-code-test-campaign-on-linux — Prove specified command-free provider path validation on Linux
- Blocker or decision needed: none
- Detour and return point: none

## Ordered Queue

Queue positions are mutable; parenthesized campaign numbers and full `Campaign ID` values are stable.

1. (080) **[Prove specified command-free provider path validation on Linux](active/080-prove-specified-command-free-first-pass-code-test-campaign-on-linux.md)**
   - 🆔 **CAMPAIGN ID:** `prove-specified-command-free-first-pass-code-test-campaign-on-linux`
   - 🚦 **STATE:** 🟢 **READY**
   - 🎯 **PRIMARY FOCUS AREAS:** Provider Portability
   - 🧩 **SUPPORTING FOCUS AREAS:** Campaign Lifecycle; Workspace Safety and Performance
   - 🔗 **DEPENDS ON:** `prove-first-pass-documentation-campaign-on-linux` — ✅ **COMPLETE**
   - 🔗 **DEPENDS ON:** `establish-deterministic-app-server-worker-handoff` — ✅ **COMPLETE**
   - 🗺️ **ROADMAP:** low-token-cross-platform-campaign-execution r6 / M11-LINUX-FIRST-PASS-PROOF
   - 🏁 **OUTCOME:** Provider adapter instruction paths are validated identically on Linux and Windows, and the fix completes through the command-free first-file-change handoff.
2. (081) **[Prove specified command-free documentation asset revision on Linux](active/081-prove-specified-command-free-first-pass-asset-aware-campaign-on-linux.md)**
   - 🆔 **CAMPAIGN ID:** `prove-specified-command-free-first-pass-asset-aware-campaign-on-linux`
   - 🚦 **STATE:** 🟡 **WAITING**
   - 🎯 **PRIMARY FOCUS AREAS:** Provider Portability
   - 🧩 **SUPPORTING FOCUS AREAS:** Workspace Safety and Performance; Campaign Lifecycle
   - 🔗 **DEPENDS ON:** `prove-specified-command-free-first-pass-code-test-campaign-on-linux` — 🟢 **READY**
   - 🗺️ **ROADMAP:** low-token-cross-platform-campaign-execution r6 / M11-LINUX-FIRST-PASS-PROOF / unlocks G11-LINUX-FIRST-PASS-RELIABLE
   - 🏁 **OUTCOME:** Documentation asset cache revisions cover every direct site asset deterministically, and the asset-aware fix completes through the command-free first-file-change handoff.
