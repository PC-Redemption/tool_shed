# Forward next App Server selection to qualified CAMP execution

Status: complete
Type: campaign
Updated: 2026-08-21
Next Action: none
Campaign ID: forward-next-app-server-to-qualified-camp-execution
Campaign Number: 046
Outcome: Allow ts: next --app-server to perform unchanged next-action selection and forward the invocation-scoped selector only when the selected action is an already-qualified executable role, primarily CAMP execution, while preserving unflagged GUI behavior, compatibility gates, safety boundaries, and no API fallback.
Primary Focus Areas: campaign-lifecycle
Supporting Focus Areas: provider-portability, qualification-release
Depends On: app-server-explicit-command-opt-in
Decision: none
Detour For: none
Return To: none
Completion Gate: ts: next --app-server is accepted; normal ts: next remains unchanged; both select the same next CAMP; eligible CAMP work executes through the existing centralized App Server camp_execution path using gpt-5.6-terra with medium reasoning without a second command; non-CAMP, GUI-native, blocked, decision, external, and unqualified actions are reported without being forced through CAMP execution; explicit per-command selection, global default OFF, centralized executable/version/role qualification, ChatGPT-only authentication, no API fallback, CAMP safety controls, and existing ts: camp run behavior are preserved; focused and full validation pass; and user documentation is updated.
Completion Evidence: ts: next --app-server forwarding uses unchanged next selection and the centralized qualified CAMP path; GUI/default and fail-closed behavior, global default OFF, no API fallback, safety controls, and existing camp-run behavior are covered; user documentation is updated; 49 focused tests and the full 218-test Tool Shed validator passed; installed or released-build field testing is explicitly optional follow-up.
Completion Date: 2026-08-21
Completion Order: 42
Disposition: completed

## Request

Support `ts: next --app-server` as an execution-path forwarding command. Keep normal `ts: next`
navigation and selection authoritative: the option does not make `next` a new App Server role.
After selection, forward the invocation-scoped App Server preference only when the selected next
action maps to an already-qualified executable role.

The primary required path is:

```text
ts: next --app-server
-> normal next-action selection
-> next action is CAMP execution
-> existing App Server qualification checks
-> existing camp_execution runner
-> gpt-5.6-terra / medium
```

This must select the same CAMP as unflagged `ts: next` and execute it without requiring the user to
enter a second `ts: camp run <id> --app-server` command. Do not create a second CAMP runner or
duplicate role/model policy.

Preserve unflagged behavior:

```text
ts: next
-> existing GUI/default execution path
```

The selector is explicit and applies only to the current invocation. Do not persist session state,
change `codex_app_server_enabled`, globally enable App Server, introduce implicit App Server use, or
add API fallback. `ts: discuss` and discussion or user-interaction actions selected by `next` remain
GUI-native.

When normal navigation selects a non-CAMP action—such as discussion, roadmap review, planning,
user decision, blocked work, a qualification gate, external action, or unsupported lifecycle
role—report the selected action and the appropriate next route. Never silently force it through
CAMP execution. If the architecture already supports generic selector forwarding cleanly,
investigate forwarding to the existing qualified planning (`gpt-5.6-sol` / `high`) or verification
(`gpt-5.6-terra` / `low`) roles, but do not expand scope or redesign `next` merely to do so.

Forwarding must use the centralized App Server executable discovery, installed-version detection,
version qualification, role qualification, ChatGPT-only authentication, and no-API-fallback
policy. Missing Codex, an unqualified version, an unavailable App Server command, or another failed
compatibility gate must fail closed for App Server execution while leaving the ordinary GUI route
available.

Successful forwarding must visibly report the selected campaign, App Server execution, CAMP role,
centralized model/reasoning choice, and explicit opt-in. Preserve the existing exact workspace and
write boundaries, Git safety journal, disabled network, no retry after mutation, focused context,
Tool Shed-owned CAMP state, compact evidence, and optimized CAMP execution where applicable.

Add focused regression coverage proving:

- unflagged `ts: next` remains GUI/default;
- flagged and unflagged navigation select the same next CAMP;
- the explicit selector reaches the existing CAMP execution path and Terra/medium policy;
- the global default remains off and the selector does not persist;
- missing or unqualified Codex fails closed without removing GUI availability;
- non-CAMP, discussion, blocked, and user-decision actions are surfaced without CAMP execution;
- API fallback remains disabled; and
- existing `ts: camp run <id> --app-server` behavior remains unchanged.

Update the user command reference and run focused tests plus the full Tool Shed validator. Keep the
campaign limited to command routing: do not add roles, session toggles, Luna, API execution,
deployment qualification, sandbox changes, watcher work, or changes to Campaign 039.

Campaign 046 may be implemented and qualified against the Campaign 045 resolver candidate.
Installed or released-build testing of the two changes together is optional follow-up evidence,
not a completion gate. Any defect found during later field testing should enter the normal
follow-up campaign or release process.

## Completion Check

ts: next --app-server is accepted; normal ts: next remains unchanged; both select the same next CAMP; eligible CAMP work executes through the existing centralized App Server camp_execution path using gpt-5.6-terra with medium reasoning without a second command; non-CAMP, GUI-native, blocked, decision, external, and unqualified actions are reported without being forced through CAMP execution; explicit per-command selection, global default OFF, centralized executable/version/role qualification, ChatGPT-only authentication, no API fallback, CAMP safety controls, and existing ts: camp run behavior are preserved; focused and full validation pass; and user documentation is updated.
