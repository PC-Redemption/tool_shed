# Close out Codex App Server integration

Status: complete
Type: campaign
Updated: 2026-08-20
Next Action: none
Campaign ID: close-out-codex-app-server-integration
Campaign Number: 035
Outcome: Preserve the validated opt-in App Server capability in maintenance/watch mode without starting further speculative development.
Primary Focus Areas: provider-portability
Supporting Focus Areas: qualification-release
Depends On: none
Decision: none
Detour For: none
Return To: none
Completion Gate: Maintainer note and version-triggered requalification workflow are durable; runtime remains default-off and read-only; full validation passes; campaign is recorded complete with production qualification blocked.
Completion Evidence: docs/codex-app-server-maintainer-note.md; docs/codex-app-server-execution.md; adapters/codex-app-server-qualifications.json; full Tool Shed validation (174 tests)
Completion Date: 2026-08-20
Completion Order: 33
Disposition: completed

## Request

Close the implementation campaign with the following durable decision:

- Architecture, read-only planning, read-only verification, token savings, and compatibility
  hardening are validated.
- Default execution remains disabled.
- Workspace writing remains disabled.
- Production qualification remains blocked.
- Normal GUI execution, including `ts: discuss`, remains the production path.

App Server is now maintenance/watch work. Reopen engineering only after a Codex CLI/App Server
version change, OpenAI support-status change, cancellation or restricted-read behavior change,
supported GUI approval integration, or a stable production contract. Do not create speculative
follow-on work for unsupported capabilities.

## Completion Check

Maintainer note and version-triggered requalification workflow are durable; runtime remains default-off and read-only; full validation passes; campaign is recorded complete with production qualification blocked.
