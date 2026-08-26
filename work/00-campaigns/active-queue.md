# Active Campaign Queue

Updated: 2026-08-26

## Owner State

- Last completed: establish-deterministic-app-server-worker-handoff — Establish deterministic App Server worker handoff
- Working now: none
- Next: prove-path-state-command-free-first-pass-code-test-campaign-on-linux — Prove path-state command-free provider validation on Linux
- Blocker or decision needed: none
- Detour and return point: none

## Ordered Queue

Queue positions are mutable; parenthesized campaign numbers and full `Campaign ID` values are stable.

1. (082) **[Prove path-state command-free provider validation on Linux](active/082-prove-path-state-command-free-first-pass-code-test-campaign-on-linux.md)**
   - 🆔 **CAMPAIGN ID:** `prove-path-state-command-free-first-pass-code-test-campaign-on-linux`
   - 🚦 **STATE:** 🟢 **READY**
   - 🎯 **PRIMARY FOCUS AREAS:** Provider Portability
   - 🧩 **SUPPORTING FOCUS AREAS:** Campaign Lifecycle; Workspace Safety and Performance
   - 🔗 **DEPENDS ON:** `prove-first-pass-documentation-campaign-on-linux` — ✅ **COMPLETE**
   - 🔗 **DEPENDS ON:** `establish-deterministic-app-server-worker-handoff` — ✅ **COMPLETE**
   - 🗺️ **ROADMAP:** low-token-cross-platform-campaign-execution r7 / M11-LINUX-FIRST-PASS-PROOF
   - 🏁 **OUTCOME:** Provider adapter instruction paths are validated identically on Linux and Windows through a command-free worker that receives explicit expected-path starting states.
2. (083) **[Prove path-state command-free asset revision on Linux](active/083-prove-path-state-command-free-first-pass-asset-aware-campaign-on-linux.md)**
   - 🆔 **CAMPAIGN ID:** `prove-path-state-command-free-first-pass-asset-aware-campaign-on-linux`
   - 🚦 **STATE:** 🟡 **WAITING**
   - 🎯 **PRIMARY FOCUS AREAS:** Provider Portability
   - 🧩 **SUPPORTING FOCUS AREAS:** Workspace Safety and Performance; Campaign Lifecycle
   - 🔗 **DEPENDS ON:** `prove-path-state-command-free-first-pass-code-test-campaign-on-linux` — 🟢 **READY**
   - 🗺️ **ROADMAP:** low-token-cross-platform-campaign-execution r7 / M11-LINUX-FIRST-PASS-PROOF / unlocks G11-LINUX-FIRST-PASS-RELIABLE
   - 🏁 **OUTCOME:** Documentation asset cache revisions cover every direct site asset deterministically through a command-free worker with explicit expected-path starting states.
