# Resolve Codex CLI and report App Server readiness

Status: complete
Type: campaign
Updated: 2026-08-21
Next Action: none
Campaign ID: resolve-codex-cli-and-report-app-server-readiness
Campaign Number: 045
Outcome: Make Tool Shed reliably resolve a usable Codex CLI/App Server executable, including trusted Windows VS Code bundles, and clearly distinguish unavailable, invalid, unsupported, unqualified, and qualified states across status, install, upgrade, smoke, startup, and qualification while preserving GUI fallback and no API fallback.
Primary Focus Areas: provider-portability
Supporting Focus Areas: snapshot-delivery, qualification-release
Depends On: app-server-explicit-command-opt-in
Decision: none
Detour For: none
Return To: none
Completion Gate: One centralized resolver handles an explicit override, PATH, trusted platform locations, and version-ordered OpenAI VS Code extension bundles; validates the executable version and App Server availability; is used by every Tool Shed Codex consumer; and makes install, upgrade, status, smoke, startup, and qualification report the selected source and distinct readiness states. The local host Codex CLI is updated and its installed version is requalified. Windows and Linux regression coverage and the full validator pass. The implementation does not auto-install Codex, modify permanent PATH, search arbitrary disk locations, persist user-specific paths in tracked files, automatically qualify a discovered version, or enable API fallback, and normal GUI operation remains available without Codex. Testing an installed or released Tool Shed build is optional follow-up evidence and is not required for campaign completion.
Completion Evidence: Central resolver implementation and Windows/Linux regression coverage complete; Codex CLI 0.149.0 live smoke, disposable write qualification, and GUI-triggered explicit planning route passed with recorded blockers; 49 focused tests and the full 218-test Tool Shed validator passed; installed or released-build field testing is explicitly optional follow-up.
Completion Date: 2026-08-21
Completion Order: 41
Disposition: completed

## Request

Implement GitHub issue [#45](https://github.com/PC-Redemption/tool_shed/issues/45), opened after
Tool Shed `v0.24.1` field testing on Windows showed that App Server compatibility checks could not
reach Codex when `codex` was absent from the host `PATH`, even though a usable `codex.exe` existed
inside the OpenAI VS Code extension.

Create one centralized executable resolver and route every Tool Shed Codex consumer through it.
Resolution must prefer an explicit supported override, then a valid executable on `PATH`, then
trusted platform-specific locations, including version-independent discovery under the OpenAI VS
Code extension directory. When several compatible extension versions exist, select the newest
valid candidate deterministically and report the chosen executable and discovery source. Validate
candidates with `--version` and separately determine whether the App Server command is available;
discovery must never imply qualification.

Use the resolver for install and upgrade readiness reporting, `ts: appserver status`, Codex version
detection, compatibility smoke, App Server startup and qualification, reasoning-catalog refresh,
and any other Tool Shed subprocess that launches Codex. Reports must distinguish at least:

- available and qualified;
- available but unqualified;
- available but App Server unavailable;
- not installed or not found; and
- invalid executable.

Missing Codex must leave normal GUI Tool Shed operation available and explain that only App Server
execution is unavailable. Installation and upgrade should surface this state proactively instead
of waiting for a CAMP failure.

Keep discovery bounded to trusted known locations. Do not search the whole disk, execute arbitrary
same-named files, persist user-specific paths in tracked files, install or copy Codex, modify
permanent `PATH`, enable API fallback, or automatically qualify a newly discovered version.

Add regression coverage for PATH resolution, Windows VS Code bundle discovery, multiple extension
versions, invalid and missing executables, absent App Server support, version/qualification states,
install and upgrade reporting, centralized smoke/startup use, unchanged Linux behavior, GUI
fallback, and the security boundaries above.

## Qualification and optional field testing

Update the Codex CLI on this Linux host to the chosen current stable version, verify the resolver
against it, and requalify that exact installed version for the applicable App Server roles.

An installed Windows or released-build field test remains useful optional evidence, especially for
the original no-`PATH` GUI environment, but it does not gate completion and does not require the
latest published Tool Shed version. If optional field testing exposes a defect, correct it through
the normal follow-up campaign or release process.

Local phase completed on 2026-08-21: the host was updated from Codex CLI 0.144.6 to 0.149.0, both
resolver-backed status routes first demonstrated the required unqualified-version state, and the
reviewed live smoke plus disposable write harness qualified 0.149.0 with the existing blockers.
The active GUI workflow then exercised the explicit planning selector/orchestrator path against the
same resolved executable and completed with Sol/high, one model turn, no tools, no mutations, and
no compatibility warning. Focused tests and the full 218-test validator passed. See
[`docs/codex-app-server-requalification-2026-08-21.md`](../../../docs/codex-app-server-requalification-2026-08-21.md).

## Completion Check

One centralized resolver handles an explicit override, PATH, trusted platform locations, and version-ordered OpenAI VS Code extension bundles; validates the executable version and App Server availability; is used by every Tool Shed Codex consumer; and makes install, upgrade, status, smoke, startup, and qualification report the selected source and distinct readiness states. Windows and Linux regression coverage and the full validator pass. The implementation does not auto-install Codex, modify permanent PATH, search arbitrary disk locations, persist user-specific paths in tracked files, automatically qualify a discovered version, or enable API fallback, and normal GUI operation remains available without Codex.

### Optional installed field validation

A future Windows field test may reproduce the original environment: a normally launched Codex GUI,
`Get-Command codex` not found, and Codex available only in the trusted OpenAI VS Code extension.
Useful observations include resolver source/path, detected version and compatibility, and whether
explicit App Server execution uses the same executable. This evidence may open follow-up work, but
its absence or the lack of an installed/released test build does not block this campaign.
