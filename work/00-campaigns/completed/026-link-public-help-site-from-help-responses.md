# Link the public help site from Tool Shed help responses

Status: complete
Type: campaign
Updated: 2026-08-18
Next Action: none
Campaign ID: link-public-help-site-from-help-responses
Campaign Number: 026
Outcome: Resolve GitHub issue #36 by making every ts: help-family response visibly offer https://ts.rookaro.com/ and making ts: commands offer the public reference while preserving complete offline, workspace-local help behavior.
Primary Focus Areas: provider-portability
Supporting Focus Areas: qualification-release
Depends On: none
Decision: none
Detour For: none
Return To: none
Completion Gate: Portable Help Route guidance, generated provider instructions, operator documentation, and packaged skill surfaces consistently require the public help link for ts: help, ts: help all, and focused ts: help responses, plus the public reference or root help link for ts: commands; rendering help performs no request-time network check; stable topic links are used only where defined; focused packaging tests prevent drift; the full Tool Shed validator passes; and GitHub issue #36 is updated with verified evidence.
Completion Evidence: Implemented offline-first public help and reference links across portable routing, generated five-provider guidance, operator docs, README, packaging tests, and the v0.22.0 manifest; focused checks and the full 147-test validator passed; GitHub issue #36 updated at https://github.com/PC-Redemption/tool_shed/issues/36#issuecomment-5328769028.
Completion Date: 2026-08-18
Completion Order: 25
Disposition: completed

## Request

Address [GitHub issue #36](https://github.com/PC-Redemption/tool_shed/issues/36). The public site is
available, but the portable agent-facing Help Route does not currently require responses to expose
it. Add a short visible link to `https://ts.rookaro.com/` for `ts: help`, `ts: help all`, and
`ts: help <topic-or-command>`. Allow `ts: commands` to point directly to
`https://ts.rookaro.com/ref/`.

The public links supplement local help; they must not replace local source reads or introduce a
request-time availability check. Keep the portable skill, campaign-route reference, generated
provider guidance, operator documentation, packaging manifest, and focused regression tests in
sync. Use stable topic URLs only when the site defines them and always retain the root help link.

## Completion Check

Portable Help Route guidance, generated provider instructions, operator documentation, and packaged skill surfaces consistently require the public help link for ts: help, ts: help all, and focused ts: help responses, plus the public reference or root help link for ts: commands; rendering help performs no request-time network check; stable topic links are used only where defined; focused packaging tests prevent drift; the full Tool Shed validator passes; and GitHub issue #36 is updated with verified evidence.
