# Active Campaign Queue

Updated: 2026-08-18

## Owner State

- Last completed: define-nested-cycles-and-owning-transitions — Define nested Tool Shed cycles and owning transitions
- Working now: publish-and-verify-tool-shed-v0-22-0 — Publish and verify Tool Shed v0.22.0
- Next: none
- Blocker or decision needed: none
- Detour and return point: none

## Ordered Queue

Queue positions are mutable; parenthesized campaign numbers and full `Campaign ID` values are stable.

1. (027) **[Publish and verify Tool Shed v0.22.0](active/027-publish-and-verify-tool-shed-v0-22-0.md)**
   - 🆔 **CAMPAIGN ID:** `publish-and-verify-tool-shed-v0-22-0`
   - 🚦 **STATE:** 🔵 **WORKING**
   - 🎯 **PRIMARY FOCUS AREAS:** Qualification and Release
   - 🧩 **SUPPORTING FOCUS AREAS:** Snapshot Delivery; Provider Portability
   - 🔗 **DEPENDS ON:** `compact-tool-shed-site-and-publish-guided-workflows` — ✅ **COMPLETE**
   - 🔗 **DEPENDS ON:** `harden-upgrade-campaign-number-convergence` — ✅ **COMPLETE**
   - 🔗 **DEPENDS ON:** `link-public-help-site-from-help-responses` — ✅ **COMPLETE**
   - 🔗 **DEPENDS ON:** `extend-next-with-targeted-and-wildcard-batches` — ✅ **COMPLETE**
   - 🔗 **DEPENDS ON:** `define-nested-cycles-and-owning-transitions` — ✅ **COMPLETE**
   - 🔗 **DEPENDS ON:** `fail-closed-on-cross-workspace-routing` — ✅ **COMPLETE**
   - 🔗 **DEPENDS ON:** `add-workspace-wide-ts-doctor-command` — ✅ **COMPLETE**
   - 🏁 **OUTCOME:** Ship one verified Tool Shed v0.22.0 release that contains and accounts for every repository update since v0.21.0: the compact public operator workflows and follow-up layout/cache fix, upgrade campaign-number convergence, public help links, targeted and wildcard queue batches, fail-closed workspace identity and routing, nested cycle ownership, and the workspace doctor; freeze the exact candidate, push and publish it traceably, verify canonical release, updater, and public documentation state, and close issues #34 through #39 only when each issue's acceptance evidence is satisfied.
