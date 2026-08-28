# Active Campaign Queue

Updated: 2026-08-28

## Owner State

- Last completed: rehearse-and-convert-maintainer-to-hybrid-state — Rehearse and convert the maintainer to hybrid state
- Working now: publish-hybrid-state-release-and-sync-maintainer-skill — Publish the hybrid-state release and synchronize the maintainer skill
- Next: none
- Blocker or decision needed: qualify-disconnected-hybrid-production-canary — Qualify a disconnected hybrid production canary
- Detour and return point: none

## Ordered Queue

Queue positions are mutable; parenthesized campaign numbers and full `Campaign ID` values are stable.

1. (107) **[Publish the hybrid-state release and synchronize the maintainer skill](active/107-publish-hybrid-state-release-and-sync-maintainer-skill.md)**
   - 🆔 **CAMPAIGN ID:** `publish-hybrid-state-release-and-sync-maintainer-skill`
   - 🚦 **STATE:** 🔵 **WORKING**
   - 🎯 **PRIMARY FOCUS AREAS:** Qualification and Release
   - 🧩 **SUPPORTING FOCUS AREAS:** Snapshot Delivery; Provider Portability
   - 🔗 **DEPENDS ON:** `rehearse-and-convert-maintainer-to-hybrid-state` — ✅ **COMPLETE**
   - 🗺️ **ROADMAP:** hybrid-sqlite-operational-state r3 / M4-RELEASE-CANARY-PROVEN
   - 🏁 **OUTCOME:** The unchanged maintainer-proven candidate is published with verified provenance and the separately installed Codex skill exactly matches the released canonical skill in a fresh session.
2. (108) **[Qualify a disconnected hybrid production canary](active/108-qualify-disconnected-hybrid-production-canary.md)**
   - 🆔 **CAMPAIGN ID:** `qualify-disconnected-hybrid-production-canary`
   - 🚦 **STATE:** 🔴 **BLOCKED**
   - 🎯 **PRIMARY FOCUS AREAS:** Snapshot Delivery
   - 🧩 **SUPPORTING FOCUS AREAS:** Qualification and Release; Workspace Safety and Performance; Artifact Workflows
   - 🔗 **DEPENDS ON:** `publish-hybrid-state-release-and-sync-maintainer-skill` — 🔵 **WORKING**
   - ⚠️ **DECISION NEEDED:** Separate owner authorization and an exact known client target are required before external workspace mutation.
   - 🗺️ **ROADMAP:** hybrid-sqlite-operational-state r3 / M4-RELEASE-CANARY-PROVEN / unlocks G4-RELEASE-CANARY-PROVEN
   - 🏁 **OUTCOME:** One production-shaped disconnected Tool Shed client with local Git but no project GitHub remote or authenticated gh proves install/upgrade, checkpoint, backup, restore, reconciliation, safe downgrade behavior, and rollback before broad rollout.
