# Active Campaign Queue

Updated: 2026-08-24

## Owner State

- Last completed: harden-dirty-qualification-cache-and-failure-semantics — Harden dirty-qualification cache and failure semantics
- Working now: none
- Next: none
- Blocker or decision needed: qualify-release-and-field-verify-dirty-codex-forward-compatibility — Qualify, release, and field-verify dirty Codex forward compatibility; make-stable-snapshot-upgrades-fast-observable-and-retry-safe — Make stable snapshot upgrades fast, observable, and retry-safe
- Detour and return point: none

## Ordered Queue

Queue positions are mutable; parenthesized campaign numbers and full `Campaign ID` values are stable.

1. (052) **[Qualify, release, and field-verify dirty Codex forward compatibility](active/052-qualify-release-and-field-verify-dirty-codex-forward-compatibility.md)**
   - 🆔 **CAMPAIGN ID:** `qualify-release-and-field-verify-dirty-codex-forward-compatibility`
   - 🚦 **STATE:** 🔴 **BLOCKED**
   - 🎯 **PRIMARY FOCUS AREAS:** Qualification and Release
   - 🧩 **SUPPORTING FOCUS AREAS:** Provider Portability; Snapshot Delivery
   - 🔗 **DEPENDS ON:** `make-codex-candidate-resolution-and-readiness-truthful` — ✅ **COMPLETE**
   - 🔗 **DEPENDS ON:** `harden-dirty-qualification-cache-and-failure-semantics` — ✅ **COMPLETE**
   - ⚠️ **DECISION NEEDED:** Owner reserved the Bactron Core snapshot upgrade for the normal Windows workspace process. Completion requires upgrading the dirty snapshot to the latest verified published release with unrelated files preserved, verifying integrity and extension-only Codex resolution without PATH, and recording sanitized dirty-qualified read-only planning or verification evidence.
   - 🏁 **OUTCOME:** Prove the dirty-qualification system across Windows and Linux candidate layouts, publish it in the next integrity-verifiable Tool Shed release, and upgrade the Bactron Core Windows snapshot to confirm unseen newer Codex versions qualify and run without modifying snapshot machinery.
2. (053) **[Make stable snapshot upgrades fast, observable, and retry-safe](active/053-make-stable-snapshot-upgrades-fast-observable-and-retry-safe.md)**
   - 🆔 **CAMPAIGN ID:** `make-stable-snapshot-upgrades-fast-observable-and-retry-safe`
   - 🚦 **STATE:** 🔴 **BLOCKED**
   - 🎯 **PRIMARY FOCUS AREAS:** Snapshot Delivery
   - 🧩 **SUPPORTING FOCUS AREAS:** Qualification and Release; Workspace Safety and Performance
   - ⚠️ **DECISION NEEDED:** Native Windows cold and warm-retry qualification of the unpublished 0.27.0 candidate requires either authorization to push the candidate for Windows CI or explicit authorization to mutate and execute it in a Windows workspace; ts: next grants neither.
   - 🏁 **OUTCOME:** Reduce normal stable-release snapshot upgrade latency and eliminate opaque or repeated validation delays while preserving exact release provenance, content integrity, dirty-work protection, verified backup and rollback, provider convergence, Codex skill synchronization, and fail-closed post-install checks.
