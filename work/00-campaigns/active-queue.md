# Active Campaign Queue

Updated: 2026-08-24

## Owner State

- Last completed: harden-dirty-qualification-cache-and-failure-semantics — Harden dirty-qualification cache and failure semantics
- Working now: qualify-release-and-field-verify-dirty-codex-forward-compatibility — Qualify, release, and field-verify dirty Codex forward compatibility
- Next: none
- Blocker or decision needed: none
- Detour and return point: none

## Ordered Queue

Queue positions are mutable; parenthesized campaign numbers and full `Campaign ID` values are stable.

1. (052) **[Qualify, release, and field-verify dirty Codex forward compatibility](active/052-qualify-release-and-field-verify-dirty-codex-forward-compatibility.md)**
   - 🆔 **CAMPAIGN ID:** `qualify-release-and-field-verify-dirty-codex-forward-compatibility`
   - 🚦 **STATE:** 🔵 **WORKING**
   - 🎯 **PRIMARY FOCUS AREAS:** Qualification and Release
   - 🧩 **SUPPORTING FOCUS AREAS:** Provider Portability; Snapshot Delivery
   - 🔗 **DEPENDS ON:** `make-codex-candidate-resolution-and-readiness-truthful` — ✅ **COMPLETE**
   - 🔗 **DEPENDS ON:** `harden-dirty-qualification-cache-and-failure-semantics` — ✅ **COMPLETE**
   - 🏁 **OUTCOME:** Prove the dirty-qualification system across Windows and Linux candidate layouts, publish it in the next integrity-verifiable Tool Shed release, and upgrade the Bactron Core Windows snapshot to confirm unseen newer Codex versions qualify and run without modifying snapshot machinery.
