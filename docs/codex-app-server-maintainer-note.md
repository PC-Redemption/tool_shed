# Codex App Server Maintainer Note

Status: maintenance/watch; experimental; global default disabled

App Server support exists, but the
[official App Server documentation](https://developers.openai.com/codex/app-server) currently
describes it as experimental and unsupported for production workloads. Do not enable it globally.
Normal Tool Shed and `ts: discuss` remain on the existing GUI path; Terra is the normal interactive
model unless the operator intentionally selects Sol for difficult direct GUI work.

## Daily owner contract

For one ready campaign in a Linux or Windows workspace, use the normal Codex GUI and send:

```text
ts: next --app-server
```

The dispatcher selects the ordinary next campaign, automatically prepares and persists a bounded
capsule when one is absent, runs routine CAMP work with Terra/medium, reserves deterministic
verification for the controller, and returns a compact journal. It never launches a nested
`codex exec` agent. Discussion, decisions, deployment, unsupported roles, and work that is not a
ready bounded campaign stay on their normal routes.

The enforced CAMP defaults are four observed model requests, 180,000 cumulative input tokens,
65,536 cumulative serialized tool-result bytes, and 16,384 bytes for one serialized result. When
a ceiling is reached, Tool Shed interrupts the turn and skips reserved verification. Before any
mutation, follow `resume_bounded_camp`. After an authorized path changes, follow
`reconcile_workspace_then_resume_bounded_camp`; inspect and preserve the mutation journal first,
and never replay the worker blindly. For an ordinary preflight or preparation failure before
mutation, repair the reported condition and rerun once, or omit `--app-server` to use the normal
GUI route.

Representative evidence now supersedes the earlier fixture-only efficiency conclusion:

| Measure | Native Linux realistic CAMP | Windows Core Campaign 020 |
| --- | ---: | ---: |
| Model requests / limit | 2 / 4 | 3 / 4, including preparation |
| Input tokens / limit | 40,016 / 180,000 | 81,570 / 180,000 |
| Weighted usage proxy | 26,600.0 | 168,501.6 combined |
| Tool-result bytes / limit | 1,820 / 65,536 | 2,362 / 65,536 |
| Largest tool result / limit | below 16,384 | 2,362 / 16,384 |
| Model/CAMP time | 16.851 / 17.350 seconds | 75.240 seconds model stages / 79.843 seconds dispatch |
| Mid-run owner prompts | 0 | 0 before the safe verification stop |
| Result | safe, verified | verified after one no-replay reconciliation |

The Linux proof completed two declared file changes and one reserved verification command without
intervention. The Windows one-command path prepared and performed the one declared map change
within every ceiling, then stopped safely because v0.29.8 preparation selected an unavailable
Python launcher and a verifier assertion that included dispatcher-owned lifecycle edits. The
worker was not replayed; one reconciliation corrected only the reserved checks, and the built-in
console verifier passed three commands. Canonical source now normalizes the current Python
executable, removes redundant broad diff assertions, and decodes Windows sandbox output as UTF-8.
That repair is not in v0.29.8: publication, skill synchronization, and client snapshot upgrades
remain separate owner-authorized work.

Linux execution is proven with the reviewed local Codex baseline. Windows execution and verification must run
in the logged-in GUI console; an SSH service session cannot reach the GUI sandbox runner pipe,
though it may trigger an interactive console task. API-key fallback, globally enabled App Server,
macOS, deployment, and production workloads are not supported by this contract. The outer GUI token
count is not exposed. Weighted usage is a comparative proxy,
not price or ChatGPT allowance.

Read-only planning (`gpt-5.6-sol` / high), verification (`gpt-5.6-terra` / low), and one explicitly
scoped `camp_execution` step (`gpt-5.6-terra` / medium) are supported. CAMP writing must
use `camp-run`, exact declared paths, the hardened workspace-write sandbox, and a Git mutation
journal. It remains opt-in. The representative CAMP used 241,524 input tokens and did not establish
savings in the original qualification; Campaign 040 subsequently reduced the same fixture to
61,516 input tokens and two model requests. Those results remain fixture history, not general
owner-efficiency evidence. The realistic Linux and Windows results above are authoritative for the
current operating conclusion. See
[the token optimization report](codex-app-server-camp-token-optimization-2026-08-20.md) for the
historical comparison. Broader writing, build, deployment, and permission expansion remain
blocked.

For CAMP, a protocol-level `turn/completed` event is not verification. The worker hands completed
edits back as `step_ready_for_verification` or `camp_ready_for_verification`, and the controller
runs every declared deterministic verification command exactly once. Compatibility outcomes
`step_complete` and `camp_complete` carry the same verification-pending meaning. Journals distinguish
`safe_unverified`, `verification_failed`, and `verified`; malformed, partial, `unknown`, interrupted,
unsafe, and unexpected-path results fail closed. Mutated failures are never replayed. A focused
context warning or oversized tool result is a compact, enforceable finding that prevents lifecycle
advance even when mutation and deterministic checks are otherwise safe.

Workspace-writing CAMP also has a live default ceiling: four observed model requests, 180,000
cumulative input tokens, 64 KiB cumulative serialized tool results, and 16 KiB for one result.
Reaching a ceiling interrupts the active turn, skips reserved verification, preserves the Git
journal, and returns either `resume_bounded_camp` or
`reconcile_workspace_then_resume_bounded_camp`. Telemetry retains no raw tool output.

The user-facing opt-ins are `ts: plan <request> --app-server`, `ts: verify <request>
--app-server`, `ts: camp run <camp> --app-server`, and `ts: next --app-server`; the last invokes
`app_server_dispatch.py` directly, with no nested `codex exec`, to perform normal next-action
selection, validate the campaign execution capsule and host preflight, and forward only to an
supported role rather than making `next` a role. `ts: app-server status` reports operator trust,
runtime readiness, observed safety, optional certification, and routing; `appserver` is an alias.
Eligible unflagged forms follow the protected user-local preference. Fresh schema-v2 `on` consent
trusts the resolved CLI for supported local roles, including bounded CAMP. `--gui` overrides it
once, while explicit `--app-server` stays strict. Missing positive qualification and executable-hash
certification do not block operator-runtime mode. An exact evidence-backed `unqualified` record is
the only version denial, and it does not block a fixed or newer version.

Persistent-mode failures before possible mutation hand the same action straight back to GUI. A
possible mutation requires mutation-journal and Git reconciliation before GUI continuation and is
never replayed. The append-only user-local operational log is sanitized and best-effort; logging
failure cannot block fallback.

Explicit preference changes refresh a protected recovery-only owner profile outside Codex home.
It is not a second authority and never enables App Server automatically; destructive replacement
requires `ts: app-server profile restore`. Validator subprocesses route default preference, profile,
and event paths through `TOOL_SHED_STATE_ROOT`. Schema-v2 events carry controlled source, event type,
role, and correlation identity, while schema-v1 history remains excluded legacy evidence.
`ts: app-server report` provides bounded local opportunity, selection, execution, completion,
fallback, reconciliation, failure-category, and skipped-opportunity counts without storing content.

All Codex consumers use one resolver. A supported explicit override remains authoritative.
Otherwise the resolver inventories `PATH`, bounded trusted platform locations, and OpenAI VS Code
extension bundles, then selects the highest semantically eligible CLI at or above `0.146.0`;
source priority breaks equal-version ties only. It reports every candidate plus the selected path,
source, App Server availability, trust/readiness/safety/certification dimensions, and supported roles.
The resolver also backs install/upgrade readiness, reasoning refresh, smoke, startup,
version detection, and qualification. It neither installs Codex nor changes permanent `PATH`,
persists user paths, searches arbitrary locations, or enables API fallback. Qualification and
dirty-read results remain diagnostic or optional strict-mode evidence in operator-runtime mode.
Missing Codex therefore leaves normal GUI Tool Shed work available.

Linux extension discovery is bounded to the desktop, Insiders, remote-server, and remote-server
Insiders extension roots under the user's home directory, with x86_64, aarch64, and arm64 Codex
payloads. This covers normally launched local and remote Linux GUI sessions without modifying
`PATH`.

Automated Windows and Linux regression coverage is not the Windows release gate. Before release,
collect external evidence from a fresh normally launched Codex GUI with `Get-Command codex` still
not found and no `PATH` preparation: status must discover the trusted VS Code bundle, and a
GUI-triggered `--app-server` operation, smoke, startup, version detection, and qualification must
use that same executable identity. Do not claim this gate has passed until those field results are
recorded.

For diagnostics or optional strict certification after a Codex update, run:

```bash
python3 scripts/codex_app_server_compatibility.py status
python3 scripts/codex_app_server_compatibility.py smoke --cwd .
python3 scripts/codex_app_server_write_qualification.py --help
```

Record durable reviewed results in `adapters/codex-app-server-qualifications.json`. Positive records
and executable hashes certify strict mode but do not gate normal operator-runtime access. To deny a
version, record its exact version with `status: unqualified` and a non-empty reviewed evidence
reference; remove or correct that record after a fix. The dirty-read cache remains advisory and its
writes remain locked, atomic, and permission-restricted. The disposable write harness remains for
release qualification and regression investigation, not every version update. Resume broader
engineering only for a concrete CLI, support-status, cancellation, restricted-read, approval,
token-efficiency, or production-contract change.

The current reviewed versions are Codex CLI 0.149.0 and 0.149.0-alpha.4.3. Stable 0.149.0 retains
explicit planning, verification, and CAMP roles with blockers after its smoke and disposable write
qualification; see
[`codex-app-server-requalification-2026-08-21.md`](codex-app-server-requalification-2026-08-21.md).
The extension-bundled alpha retains explicit read-only planning and verification and is also
qualified for explicit CAMP execution only when the resolved executable matches the reviewed
SHA-256 identity. See
[`codex-app-server-alpha-requalification-2026-08-24.md`](codex-app-server-alpha-requalification-2026-08-24.md)
and
[`codex-app-server-write-qualification-alpha-2026-08-25.md`](codex-app-server-write-qualification-alpha-2026-08-25.md).

Dirty qualification queries `permissionProfile/list`, selects the allowed built-in `:read-only`
profile, and sends `permissions` without the mutually exclusive `sandbox` or `sandboxPolicy`
fields. If that method is unavailable, it validates the legacy read-only sandbox. A runtime that
exposes profiles without an allowed read-only profile fails closed. The disposable qualification
tree is fingerprinted before and after the model turns, and protocol mutation events must remain
empty. Safe blockers such as a missing interrupt acknowledgement after authoritative interrupted
state are reported separately from fatal safety failures and unknown runtime outcomes.

A successful App Server selection banner reports API fallback: disabled so the no-fallback boundary is visible before execution.
