# Qualify, release, and field-verify dirty Codex forward compatibility

Status: working
Type: campaign
Updated: 2026-08-24
Next Action: execute the campaign completion gate
Campaign ID: qualify-release-and-field-verify-dirty-codex-forward-compatibility
Campaign Number: 052
Outcome: Prove the dirty-qualification system across Windows and Linux candidate layouts, publish it in the next integrity-verifiable Tool Shed release, and upgrade the Bactron Core Windows snapshot to confirm unseen newer Codex versions qualify and run without modifying snapshot machinery.
Primary Focus Areas: qualification-release
Supporting Focus Areas: provider-portability, snapshot-delivery
Depends On: make-codex-candidate-resolution-and-readiness-truthful, harden-dirty-qualification-cache-and-failure-semantics
Decision: none
Detour For: none
Return To: none
Completion Gate: Cross-platform tests cover below-minimum rejection, exact-reviewed fast path, unseen stable and prerelease versions, versions 0.150.0 and later, same-version different binaries, PATH plus newer extension selection, Windows extension-only discovery, absent schema generation, permission-profile and validated legacy fallback, transient retry, unsafe denial, truthful status, cache invalidation, and same-invocation read-only execution; live Linux qualification passes for available representative exact and unseen executables; the Windows Bactron Core snapshot is upgraded through the approved snapshot updater, remains integrity-clean, resolves its installed Codex without requiring PATH, and demonstrates dirty-qualified read-only planning or verification with sanitized evidence; canonical focused tests and full validation pass; Tool Shed is version-bumped above 0.25.2, its manifest hashes and release provenance are valid, the matching commit, tag, and release are published, and installation/update documentation reflects the new behavior; workspace-write remains separately exact-qualified.
Completion Evidence: none
Disposition: none

## Request

Add detailed execution context here.

## Completion Check

Cross-platform tests cover below-minimum rejection, exact-reviewed fast path, unseen stable and prerelease versions, versions 0.150.0 and later, same-version different binaries, PATH plus newer extension selection, Windows extension-only discovery, absent schema generation, permission-profile and validated legacy fallback, transient retry, unsafe denial, truthful status, cache invalidation, and same-invocation read-only execution; live Linux qualification passes for available representative exact and unseen executables; the Windows Bactron Core snapshot is upgraded through the approved snapshot updater, remains integrity-clean, resolves its installed Codex without requiring PATH, and demonstrates dirty-qualified read-only planning or verification with sanitized evidence; canonical focused tests and full validation pass; Tool Shed is version-bumped above 0.25.2, its manifest hashes and release provenance are valid, the matching commit, tag, and release are published, and installation/update documentation reflects the new behavior; workspace-write remains separately exact-qualified.
