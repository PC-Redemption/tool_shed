# Active Campaign Queue

Updated: 2026-08-24

## Owner State

- Last completed: establish-secure-smb-access-to-bactron-workspace — Establish read/write SMB access to the complete w1-dev Windows share
- Working now: none
- Next: implement-minimum-version-dirty-read-qualification — Implement minimum-version dirty read qualification
- Blocker or decision needed: none
- Detour and return point: none

## Ordered Queue

Queue positions are mutable; parenthesized campaign numbers and full `Campaign ID` values are stable.

1. (049) **[Implement minimum-version dirty read qualification](active/049-implement-minimum-version-dirty-read-qualification.md)**
   - 🆔 **CAMPAIGN ID:** `implement-minimum-version-dirty-read-qualification`
   - 🚦 **STATE:** 🟢 **READY**
   - 🎯 **PRIMARY FOCUS AREAS:** Qualification and Release
   - 🧩 **SUPPORTING FOCUS AREAS:** Provider Portability; Workspace Safety and Performance
   - 🏁 **OUTCOME:** Replace exact-only read qualification with a minimum Codex version of 0.146.0 and no upper cutoff, automatically dirty-qualify every unseen eligible executable, and continue the same explicit planning or verification request immediately when its bounded read-only qualification passes.
2. (050) **[Make Codex candidate resolution and readiness truthful](active/050-make-codex-candidate-resolution-and-readiness-truthful.md)**
   - 🆔 **CAMPAIGN ID:** `make-codex-candidate-resolution-and-readiness-truthful`
   - 🚦 **STATE:** 🟡 **WAITING**
   - 🎯 **PRIMARY FOCUS AREAS:** Provider Portability
   - 🧩 **SUPPORTING FOCUS AREAS:** Qualification and Release
   - 🔗 **DEPENDS ON:** `implement-minimum-version-dirty-read-qualification` — 🟢 **READY**
   - 🏁 **OUTCOME:** Discover and report every trusted Codex executable, deliberately select the highest eligible version when no explicit override is supplied, and make status and command routing advertise only roles that are actually exact-qualified or dirty-qualified for the selected executable.
3. (051) **[Harden dirty-qualification cache and failure semantics](active/051-harden-dirty-qualification-cache-and-failure-semantics.md)**
   - 🆔 **CAMPAIGN ID:** `harden-dirty-qualification-cache-and-failure-semantics`
   - 🚦 **STATE:** 🟡 **WAITING**
   - 🎯 **PRIMARY FOCUS AREAS:** Workspace Safety and Performance
   - 🧩 **SUPPORTING FOCUS AREAS:** Qualification and Release; Provider Portability
   - 🔗 **DEPENDS ON:** `implement-minimum-version-dirty-read-qualification` — 🟢 **READY**
   - 🔗 **DEPENDS ON:** `make-codex-candidate-resolution-and-readiness-truthful` — 🟡 **WAITING**
   - 🏁 **OUTCOME:** Persist reusable dirty-qualification evidence in protected user-local state without modifying installed Tool Shed snapshots, while making cache identity, corruption recovery, concurrency, invalidation, transient retry, and authoritative unsafe-denial behavior explicit and fail-closed.
4. (052) **[Qualify, release, and field-verify dirty Codex forward compatibility](active/052-qualify-release-and-field-verify-dirty-codex-forward-compatibility.md)**
   - 🆔 **CAMPAIGN ID:** `qualify-release-and-field-verify-dirty-codex-forward-compatibility`
   - 🚦 **STATE:** 🟡 **WAITING**
   - 🎯 **PRIMARY FOCUS AREAS:** Qualification and Release
   - 🧩 **SUPPORTING FOCUS AREAS:** Provider Portability; Snapshot Delivery
   - 🔗 **DEPENDS ON:** `make-codex-candidate-resolution-and-readiness-truthful` — 🟡 **WAITING**
   - 🔗 **DEPENDS ON:** `harden-dirty-qualification-cache-and-failure-semantics` — 🟡 **WAITING**
   - 🏁 **OUTCOME:** Prove the dirty-qualification system across Windows and Linux candidate layouts, publish it in the next integrity-verifiable Tool Shed release, and upgrade the Bactron Core Windows snapshot to confirm unseen newer Codex versions qualify and run without modifying snapshot machinery.
