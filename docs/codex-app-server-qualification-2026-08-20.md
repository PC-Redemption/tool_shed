# Codex App Server Real-Campaign Qualification — 2026-08-20

## Decision

The read-only App Server route materially reduces avoidable Codex work without an observed loss of
planning usefulness, and it met the 10-planning/20-verification observation gate on Codex CLI
0.144.6. It is suitable for continued explicitly enabled trials, but **is not ready to become the
normal Tool Shed path**. Keep `codex_app_server_enabled = false` and retain the GUI fallback.

The blocking reliability evidence is a live cancellation race: `turn/interrupt` returned “no active
turn” while an immediate `thread/read` still showed that turn `inProgress`. The turn later became
`interrupted` and resumed successfully, but the intermediate state is not production-grade. OpenAI
also documents the App Server command and WebSocket transport as experimental and unsupported for
production workloads in the [official App Server documentation](https://developers.openai.com/codex/app-server).

## Scope and Method

- Qualification ID: `tool-shed-real-campaigns-2026-08-20`
- Raw prompt-free telemetry:
  `~/.codex/tool-shed/real-campaign-qualification-2026-08-20.jsonl`
- Core observation set: 10 real Sol/high planning operations and 20 real Terra/low verification
  operations, spanning small, medium, larger, multi-file, focused-summary, and resumed work.
- Extended set: 3 successful recovery model operations and 6 prompt-free control events, for 39
  telemetry records and 33 measured model operations in the final aggregate report.
- Sandbox: read-only. Workspace-writing roles remained disabled.
- Authentication: ChatGPT account. No API-key fallback exists.
- Fixed comparative baseline: 18,800 input tokens per measured operation.
- Model-turn metric: distinct `thread/tokenUsage/updated.last` payloads. It is an observed proxy,
  because the protocol does not expose a first-class provider model-request count.

The machine-readable comparison data is in
[`codex-app-server-qualification-comparison-2026-08-20.json`](codex-app-server-qualification-comparison-2026-08-20.json).
The existing GUI does not expose equivalent per-operation token telemetry in this workspace, so GUI
token and timing fields are `null`, not estimates. A bounded paired comparison instead measures the
old reference-file/tool-reading strategy against focused inline App Server delivery.

## Observed Operations and Tokens

All 30 core operations completed successfully at the App Server transport/execution layer. The
extended aggregate includes the three successful recovery model turns.

| Role | Core successes | Aggregate runs | Input | Cached input | Output | Reasoning | Estimated baseline | Avoidable input | Avg duration |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Planning / Sol high | 10 | 12 | 315,588 | 140,544 | 6,790 | 1,525 | 225,600 | 94,378 | 17.552 s |
| Verification / Terra low | 20 | 21 | 623,719 | 273,152 | 15,520 | 7,912 | 394,800 | 228,919 | 22.387 s |
| Total | 30 | 33 | 939,307 | 413,696 | 22,310 | 9,437 | 620,400 | 323,297 | — |

The 30-operation core alone used 886,883 input tokens: 282,176 planning and 604,707 verification.
Its estimated fixed baseline was 564,000 and its clamped per-operation avoidable total was 323,085.
Across the extended set, input averaged 28,463.848 tokens per useful operation, measured model turns
averaged 1.0 per measured operation, tool calls averaged 0.0, and inline context averaged 43,517.545
bytes per measured operation. The 18,800-token baseline is treated as Codex-owned harness overhead,
not a Tool Shed optimization target.

## Efficiency and Context Findings

The real-work paired comparison exceeded the earlier 67.47% benchmark result:

| Pair | Reference input | Focused inline input | Input reduction | Reference / inline duration |
| --- | ---: | ---: | ---: | ---: |
| Campaign 031 doctor planning | 186,244 | 25,666 | 86.22% | 100.853 / 21.972 s |
| Summary-routing verification | 135,797 | 30,550 | 77.50% | 38.262 / 19.330 s |
| Total | 322,041 | 56,216 | **82.54%** | 139.115 / 41.302 s |

The reference strategy used 12 observed model turns and 10 tool calls; focused inline delivery used
2 turns and no tool calls. Its total elapsed time was 70.31% lower. This shows that the earlier
improvement persists on representative real work, while avoiding a claim about unobservable GUI
tokens.

Across qualification, 80 files and 1,436,079 inline bytes were supplied. Two focused-summary uses
represented 787,970 source bytes with 10,834 summary bytes. Each use reduced a 393,985-byte source
set to 5,417 bytes. Planning needed no additional context. Verification correctly declined a strong
verdict without direct source evidence, demonstrating that a summary can preserve planning utility
without always being sufficient for verification. Summaries should remain ephemeral per operation;
the two observed uses do not justify campaign or Program/CAMP cache invalidation machinery.

## Planning and Verification Quality

Sol planning was materially useful in all ten core cases. It respected supplied constraints,
avoided repository-wide discovery, and produced plans suitable for downstream refinement. The
reference-file strategy was sometimes more detailed and raised additional possible risks, but that
increment did not justify its 6x model-turn and 5.7x input cost in the paired planning case. The
focused-summary planning operation used 19,400 input tokens and requested no further context.

Terra completed all twenty core verification turns. Its evidence verdicts were 5 PASS, 12
INCOMPLETE, and 3 FAIL; these are findings about the supplied campaign evidence, not App Server
execution failures. It was appropriately conservative when necessary evidence was omitted. It also
surfaced four integration defects that were reproduced and fixed during qualification:

- CLI version parsing and version participation in the observation gate;
- exact focused-summary provenance validation;
- enforcement of the configured new-thread policy;
- model-operation/context metric denominator and double-counting errors.

Manual adjudication was still necessary. Some findings were context-bound false positives—for
example, targeted batch execution belongs to the AI/skill route rather than the deterministic queue
script, and updater backups were visible but classified as unknown. Focused Terra verification is
therefore useful and cost-controlled, but should not turn an unsupported assertion directly into a
mutation.

## Thread Reuse

A planning new/resume pair used 32,351 then 32,950 input tokens; cached input rose from 9,984 to
31,488. A verification pair used 28,155 then 39,253 input tokens when the resumed turn added
cross-component context; cached input rose from 9,984 to 27,392. Continuity and cache reuse worked,
but total input did not fall and history grew.

Policy: start a fresh focused ephemeral thread for routine planning and verification. Resume only
when continuity materially matters or recovery must reconcile a known turn. A controlled resume
requires both the thread ID and the explicit retain-thread override under the default `new` policy.

## Recovery, Fallback, and Escalation

Controlled qualification produced bounded outcomes:

- cancellation: initial `user_intervention` due to the live interrupt/read race, later reconciled
  to `interrupted`, then successfully resumed;
- App Server termination: an idle server was killed, restarted, and the same thread resumed;
- RPC timeout: classified safe to resume, then reconciled after restart/read;
- stale thread ID: classified new-thread recovery, followed by a successful fresh verification;
- global feature disabled: selected the existing GUI fallback with
  `global_feature_disabled` and recorded one fallback event.

The final control classifications were 33 `none`, 3 `resume`, 1 `new_thread`, 1 `fallback`, and 1
`user_intervention`. There were no natural live failed-turn retries and no live Terra-to-Sol
escalations. The bounded one-retry/one-escalation behavior is covered by deterministic adapter tests;
no real campaign was deliberately failed merely to create a count. Normal production escalation
remains disabled.

## Protocol and Promotion Gates

- Codex CLI/App Server version remained 0.144.6; no version drift occurred.
- ChatGPT authentication, Sol/high planning, and Terra/low verification routing remained correct.
- The minimum observation count and version-compatibility gate passed.
- The GUI fallback remained available and was exercised once.
- `readOnly.access` remains inconsistent: the 0.144.6 runtime rejected it in favor of permission
  profiles while the generated schema/documentation exposed the former surface. The validated
  working read-only mechanism remains in use; no beta workaround was added.
- The cancellation state race remains a serious lifecycle reliability failure.
- Official App Server support status remains experimental/non-production.

Consequently, do not promote read-only planning and verification to the normal path yet. Continue
opt-in read-only observation with the current fail-closed behavior and rerun protocol,
authentication, routing, approval/read-only, recovery, and baseline smoke tests after any CLI or
official-interface change.

Workspace-writing CAMP execution remains blocked by four independent conditions: there is no bridge
to the initiating GUI approval panel; restricted-read protocol/schema behavior is inconsistent;
App Server is officially experimental and showed a cancellation race; and no workspace-writing
role has received an end-to-end qualification. CAMP execution, implementation, deployment,
workspace-writing debugging, testing, and all other writing roles remain on the GUI path.
