# Active Campaign Queue

Updated: 2026-08-24

## Owner State

- Last completed: implement-minimum-version-dirty-read-qualification — Implement minimum-version dirty read qualification
- Working now: make-codex-candidate-resolution-and-readiness-truthful — Make Codex candidate resolution and readiness truthful
- Next: none
- Blocker or decision needed: none
- Detour and return point: none

## Ordered Queue

Queue positions are mutable; parenthesized campaign numbers and full `Campaign ID` values are stable.

1. (050) **[Make Codex candidate resolution and readiness truthful](active/050-make-codex-candidate-resolution-and-readiness-truthful.md)**
   - 🆔 **CAMPAIGN ID:** `make-codex-candidate-resolution-and-readiness-truthful`
   - 🚦 **STATE:** 🔵 **WORKING**
   - 🎯 **PRIMARY FOCUS AREAS:** Provider Portability
   - 🧩 **SUPPORTING FOCUS AREAS:** Qualification and Release
   - 🔗 **DEPENDS ON:** `implement-minimum-version-dirty-read-qualification` — ✅ **COMPLETE**
   - 🏁 **OUTCOME:** Discover and report every trusted Codex executable, deliberately select the highest eligible version when no explicit override is supplied, and make status and command routing advertise only roles that are actually exact-qualified or dirty-qualified for the selected executable.
2. (051) **[Harden dirty-qualification cache and failure semantics](active/051-harden-dirty-qualification-cache-and-failure-semantics.md)**
   - 🆔 **CAMPAIGN ID:** `harden-dirty-qualification-cache-and-failure-semantics`
   - 🚦 **STATE:** 🟡 **WAITING**
   - 🎯 **PRIMARY FOCUS AREAS:** Workspace Safety and Performance
   - 🧩 **SUPPORTING FOCUS AREAS:** Qualification and Release; Provider Portability
   - 🔗 **DEPENDS ON:** `implement-minimum-version-dirty-read-qualification` — ✅ **COMPLETE**
   - 🔗 **DEPENDS ON:** `make-codex-candidate-resolution-and-readiness-truthful` — 🔵 **WORKING**
   - 🏁 **OUTCOME:** Persist reusable dirty-qualification evidence in protected user-local state without modifying installed Tool Shed snapshots, while making cache identity, corruption recovery, concurrency, invalidation, transient retry, and authoritative unsafe-denial behavior explicit and fail-closed.
3. (052) **[Qualify, release, and field-verify dirty Codex forward compatibility](active/052-qualify-release-and-field-verify-dirty-codex-forward-compatibility.md)**
   - 🆔 **CAMPAIGN ID:** `qualify-release-and-field-verify-dirty-codex-forward-compatibility`
   - 🚦 **STATE:** 🟡 **WAITING**
   - 🎯 **PRIMARY FOCUS AREAS:** Qualification and Release
   - 🧩 **SUPPORTING FOCUS AREAS:** Provider Portability; Snapshot Delivery
   - 🔗 **DEPENDS ON:** `make-codex-candidate-resolution-and-readiness-truthful` — 🔵 **WORKING**
   - 🔗 **DEPENDS ON:** `harden-dirty-qualification-cache-and-failure-semantics` — 🟡 **WAITING**
   - 🏁 **OUTCOME:** Prove the dirty-qualification system across Windows and Linux candidate layouts, publish it in the next integrity-verifiable Tool Shed release, and upgrade the Bactron Core Windows snapshot to confirm unseen newer Codex versions qualify and run without modifying snapshot machinery.
