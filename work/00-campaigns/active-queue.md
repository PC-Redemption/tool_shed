# Active Campaign Queue

Updated: 2026-08-26

## Owner State

- Last completed: require-case-normalized-documentation-verification — Require Case-Normalized Documentation Verification
- Working now: none
- Next: none
- Blocker or decision needed: publish-and-synchronize-case-normalized-verification — Publish and Synchronize Case-Normalized Verification; adopt-first-pass-app-server-preparation-in-core — Adopt first-pass App Server preparation in Core
- Detour and return point: publish-and-synchronize-case-normalized-verification — Publish and Synchronize Case-Normalized Verification

## Ordered Queue

Queue positions are mutable; parenthesized campaign numbers and full `Campaign ID` values are stable.

1. (091) **[Publish and Synchronize Case-Normalized Verification](active/091-publish-and-synchronize-case-normalized-verification.md)**
   - 🆔 **CAMPAIGN ID:** `publish-and-synchronize-case-normalized-verification`
   - 🚦 **STATE:** 🔴 **BLOCKED**
   - 🎯 **PRIMARY FOCUS AREAS:** Qualification and Release
   - 🧩 **SUPPORTING FOCUS AREAS:** Provider Portability; Snapshot Delivery
   - 🔗 **DEPENDS ON:** `require-case-normalized-documentation-verification` — ✅ **COMPLETE**
   - ⚠️ **DECISION NEEDED:** Owner authorization is required before publishing the patch release or replacing the installed maintainer skill.
   - ↪️ **DETOUR FOR:** adopt-first-pass-app-server-preparation-in-core
   - ↩️ **RETURN TO:** adopt-first-pass-app-server-preparation-in-core
   - 🏁 **OUTCOME:** A verified Tool Shed patch release publishes the case-normalized documentation verifier and the maintainer installed skill exactly matches it, allowing Campaign 085 to resume with a fresh Core replacement proof.
2. (085) **[Adopt first-pass App Server preparation in Core](active/085-adopt-first-pass-app-server-preparation-in-core.md)**
   - 🆔 **CAMPAIGN ID:** `adopt-first-pass-app-server-preparation-in-core`
   - 🚦 **STATE:** 🔴 **BLOCKED**
   - 🎯 **PRIMARY FOCUS AREAS:** Provider Portability
   - 🧩 **SUPPORTING FOCUS AREAS:** Snapshot Delivery; Workspace Safety and Performance; Campaign Lifecycle
   - 🔗 **DEPENDS ON:** `publish-and-synchronize-case-normalized-verification` — 🔴 **BLOCKED**
   - ⚠️ **DECISION NEEDED:** Campaign 090 repaired and locally proved the case-normalization defect; Campaign 091 requires separate publication and maintainer-skill synchronization authorization before the existing Core authorization can resume.
   - 🗺️ **ROADMAP:** low-token-cross-platform-campaign-execution r7 / M13-CORE-FIRST-PASS-ADOPTION / unlocks G13-CORE-FIRST-PASS-OWNER-READY
   - 🏁 **OUTCOME:** A fresh ordinary Core campaign completes on its first automatically prepared Windows App Server attempt.
