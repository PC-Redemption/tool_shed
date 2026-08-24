# Make Codex candidate resolution and readiness truthful

Status: queued
Type: campaign
Updated: 2026-08-24
Next Action: execute when selected from the active campaign queue
Campaign ID: make-codex-candidate-resolution-and-readiness-truthful
Campaign Number: 050
Outcome: Discover and report every trusted Codex executable, deliberately select the highest eligible version when no explicit override is supplied, and make status and command routing advertise only roles that are actually exact-qualified or dirty-qualified for the selected executable.
Primary Focus Areas: provider-portability
Supporting Focus Areas: qualification-release
Depends On: implement-minimum-version-dirty-read-qualification
Decision: none
Detour For: none
Return To: none
Completion Gate: Resolver inventory includes explicit override, PATH, bounded trusted locations, and OpenAI VS Code extension bundles with executable path, source, version, App Server availability, and qualification state; explicit override remains authoritative; without an override, the highest semantically eligible version at or above 0.146.0 is selected and source priority only resolves equal-version ties; an older PATH executable cannot silently hide a newer eligible extension executable; user-facing status distinguishes exact-qualified, dirty-qualifying, dirty-qualified, transient-fallback, unsafe-blocked, below-minimum, and write-not-qualified states; enabled roles contain only routes actually usable for the selected executable; GUI fallback and App Server selection messages identify the concrete executable and reason; Windows and Linux resolver/reporting regression tests pass.
Completion Evidence: none
Disposition: none

## Request

Add detailed execution context here.

## Completion Check

Resolver inventory includes explicit override, PATH, bounded trusted locations, and OpenAI VS Code extension bundles with executable path, source, version, App Server availability, and qualification state; explicit override remains authoritative; without an override, the highest semantically eligible version at or above 0.146.0 is selected and source priority only resolves equal-version ties; an older PATH executable cannot silently hide a newer eligible extension executable; user-facing status distinguishes exact-qualified, dirty-qualifying, dirty-qualified, transient-fallback, unsafe-blocked, below-minimum, and write-not-qualified states; enabled roles contain only routes actually usable for the selected executable; GUI fallback and App Server selection messages identify the concrete executable and reason; Windows and Linux resolver/reporting regression tests pass.
