# Active Campaign Queue

Updated: 2026-08-26

## Owner State

- Last completed: establish-deterministic-app-server-worker-handoff — Establish deterministic App Server worker handoff
- Working now: none
- Next: prove-command-free-first-pass-code-test-campaign-on-linux — Prove command-free first-pass code and test preparation on Linux
- Blocker or decision needed: none
- Detour and return point: none

## Ordered Queue

Queue positions are mutable; parenthesized campaign numbers and full `Campaign ID` values are stable.

1. (078) **[Prove command-free first-pass code and test preparation on Linux](active/078-prove-command-free-first-pass-code-test-campaign-on-linux.md)**
   - 🆔 **CAMPAIGN ID:** `prove-command-free-first-pass-code-test-campaign-on-linux`
   - 🚦 **STATE:** 🟢 **READY**
   - 🎯 **PRIMARY FOCUS AREAS:** Provider Portability
   - 🧩 **SUPPORTING FOCUS AREAS:** Campaign Lifecycle; Workspace Safety and Performance
   - 🔗 **DEPENDS ON:** `prove-first-pass-documentation-campaign-on-linux` — ✅ **COMPLETE**
   - 🔗 **DEPENDS ON:** `establish-deterministic-app-server-worker-handoff` — ✅ **COMPLETE**
   - 🗺️ **ROADMAP:** low-token-cross-platform-campaign-execution r5 / M11-LINUX-FIRST-PASS-PROOF
   - 🏁 **OUTCOME:** A fresh bounded code-and-test campaign completes from one App Server command through the command-free first-file-change handoff.
2. (079) **[Prove command-free first-pass asset-aware preparation on Linux](active/079-prove-command-free-first-pass-asset-aware-campaign-on-linux.md)**
   - 🆔 **CAMPAIGN ID:** `prove-command-free-first-pass-asset-aware-campaign-on-linux`
   - 🚦 **STATE:** 🟡 **WAITING**
   - 🎯 **PRIMARY FOCUS AREAS:** Provider Portability
   - 🧩 **SUPPORTING FOCUS AREAS:** Workspace Safety and Performance; Campaign Lifecycle
   - 🔗 **DEPENDS ON:** `prove-command-free-first-pass-code-test-campaign-on-linux` — 🟢 **READY**
   - 🗺️ **ROADMAP:** low-token-cross-platform-campaign-execution r5 / M11-LINUX-FIRST-PASS-PROOF / unlocks G11-LINUX-FIRST-PASS-RELIABLE
   - 🏁 **OUTCOME:** A fresh asset-aware campaign completes or is reduced before worker launch using metadata-only asset context and the command-free first-file-change handoff.
