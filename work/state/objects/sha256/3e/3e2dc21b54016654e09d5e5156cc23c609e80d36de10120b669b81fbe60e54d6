# App Server CAMP Token Optimization

Status: complete
Type: campaign
Updated: 2026-08-20
Next Action: none
Campaign ID: app-server-camp-token-optimization
Campaign Number: 040
Outcome: Reduce weighted Codex usage per completed App Server Terra CAMP while preserving Campaign 036 safety, correctness, structured outcomes, focused tests, and explicit opt-in routing.
Primary Focus Areas: provider-portability
Supporting Focus Areas: workspace-safety, qualification-release
Depends On: none
Decision: none
Detour For: none
Return To: none
Completion Gate: Per-turn baseline anatomy identifies the dominant sources of the 241,524-input reference CAMP; incremental optimizations compact deterministic evidence, reduce avoidable model turns and repeated context, and preserve the exact qualified safety policy; the same representative CAMP is rerun with complete before/after input, cached, uncached, output, reasoning, turns, tools, elapsed, and weighted-usage metrics plus correctness and safety comparison; additional representative CAMPs are sampled only if the fixture improves materially; all focused and full validation passes; economic usefulness, remaining blockers, and the next recommendation are documented without enabling App Server globally or broadening roles, permissions, network, deployment, providers, or transport.
Completion Evidence: Branch codex/tool-shed-app-server-camp-token-optimization commits 22082bb, 6f6c817, ce0b05c, 9f72e2c; same-fixture Terra CAMP reduced input 241524 to 61516 and weighted usage 67362.0 to 36468.4 with 22 focused tests, safe Git journal, additional small/larger/diagnostic samples, and full 180-test Tool Shed validation; report docs/codex-app-server-camp-token-optimization-2026-08-20.md.
Completion Date: 2026-08-20
Completion Order: 36
Disposition: completed

## Request

Optimize App Server CAMP execution for weighted Codex usage per completed CAMP. The unit of
comparison is a complete CAMP from start through verified `COMPLETE`, not an individual turn.
Preserve correctness, the structured lifecycle contract, focused tests, and the qualified
Terra/medium execution policy.

The App Server safety baseline comes from the isolated qualification branch
`codex/tool-shed-app-server-write-qualification` (`8b12c6a`, `69a27d8`). The current workspace's
Campaign 036 is unrelated completion-watcher history, so this campaign has no queue dependency on
that numeric record. Preserve the following reference observation for before/after comparison:

| Metric | Campaign 036 App Server reference |
| --- | ---: |
| Model | `gpt-5.6-terra` / medium |
| Input tokens | 241,524 |
| Cached input | 202,240 |
| Uncached input | 39,284 |
| Output tokens | 1,309 |
| Reasoning output | 390 |
| Observed model turns | 7 |
| Tool calls | 6 |
| Elapsed | 36.704 seconds |
| Result | `step_complete` |
| Correctness | only the declared test file changed; 20 focused tests passed |

The initial engineering target is less than approximately 120,000 total input tokens for equivalent
behavior. This is an optimization target, not permission to omit necessary context or manipulate
accounting. If another metric better represents actual Codex consumption, document the evidence and
prioritize the versioned `weighted_codex_usage` comparison.

## Immutable Safety And Scope Boundary

Do not weaken the qualified boundary to save tokens. Preserve ChatGPT-only authentication,
Terra/medium CAMP execution, `workspaceWrite`, the exact writable root and path allowlist, disabled
network, both temporary-directory exclusions, approval policy `never`, required Git state, refusal
of dirty declared targets, preservation of unrelated dirty work, no retry after mutation, no
permission expansion, and no reset, checkout, clean, or automatic destructive rollback.

Do not add deployment, additional write roles, global App Server enablement, API execution, Luna,
remote daemons, WebSockets, blanket approvals, broader filesystem or network permissions, or new
App Server lifecycle roles. `app_server_camp_execution` remains explicit opt-in even if the economic
gate passes; promotion is a separate decision.

## Execution Workstreams

1. Capture per-model-turn anatomy for the 241,524-input reference: turn number and purpose; input,
   cached, uncached, output, and reasoning tokens; requested tool; tool-result size; CAMP, Program,
   file, and total context bytes; carried thread history; and elapsed time. Classify each of the
   seven turns as required reasoning, response to new evidence, deterministic work, avoidable loop,
   tool-result processing, verification, lifecycle transition, or other.
2. Identify the dominant costs across fixed harness, CAMP/Program instructions, file context,
   previous model output, tool calls/results, and accumulated history. Do not assume a resumed
   thread is cheaper than focused fresh turns with explicit state.
3. Compact successful deterministic evidence for tests, builds, lint, listings, searches, Git,
   diffs, commands, and validation. Provide structured summaries on success; expand progressively
   from concise failure to focused diagnostics only when Terra needs them.
4. Move deterministic orchestration out of model turns where practical. Evaluate Tool Shed-owned
   structured CAMP state containing the current step, completed actions, workspace/test/safety
   state, and pending action. Tool Shed remains authoritative for lifecycle transitions.
5. Reduce repeated unchanged CAMP and Program context, completed steps, irrelevant history, broad
   discovery, full-file context, repeated file reads, raw Git output, and full successful test
   output. Supply focused ranges and incremental evidence without omitting applicable constraints.
6. Create a neutral, versioned `weighted_codex_usage` metric based on current documented relative
   Codex model rates. Account separately for uncached input, cached input, output, model, and
   reasoning tokens when exposed distinctly. Do not call the metric dollars or ignore cached input.
7. Optimize one category at a time—tool-result compaction, deterministic turns, thread history,
   repeated CAMP/Program context, file evidence, test/build evidence, then fresh-versus-resumed
   strategy—and measure after every material change.
8. Re-run the same representative CAMP and compare full-CAMP input, cached/uncached input, output,
   reasoning output, model turns, tool calls, fixed-overhead operations, Terra/Sol operations,
   elapsed time, and weighted usage. Verify equivalent diff correctness, tests, safety, and
   structured outcome.
9. Only if the reference improves materially, sample a small, normal, larger, successful-test, and
   diagnostic-evidence CAMP without duplicating expensive work unnecessarily. Determine whether the
   result generalizes and whether Terra App Server CAMP execution has meaningful economic value.

Likely high-value targets are model-turn count, accumulated thread history, raw tool-result size,
and repeated context. Do not build a large orchestration framework for marginal savings.

## Verification And Reporting

Add focused coverage for every new compaction, structured-state, deterministic-orchestration,
context-selection, conditional-failure-detail, token/weighted-usage, thread-strategy, and CAMP
completion behavior. Keep every existing App Server write-safety test and the full Tool Shed suite
passing.

The completion report must identify the assigned campaign number and branch/commits; original
per-turn anatomy and primary costs; turns eliminated or combined; tool-result, thread-history,
CAMP/Program, file, test, and Git evidence changes; before/after input, cached input, uncached input,
output, model turns, tool calls, elapsed time, and weighted usage with absolute and percentage
change; correctness/test/safety equivalence; additional real-CAMP results and generalization; the
economic-value conclusion; remaining blockers; full validation; and the recommended next Tool Shed
step.

## Completion Check

Per-turn baseline anatomy identifies the dominant sources of the 241,524-input reference CAMP; incremental optimizations compact deterministic evidence, reduce avoidable model turns and repeated context, and preserve the exact qualified safety policy; the same representative CAMP is rerun with complete before/after input, cached, uncached, output, reasoning, turns, tools, elapsed, and weighted-usage metrics plus correctness and safety comparison; additional representative CAMPs are sampled only if the fixture improves materially; all focused and full validation passes; economic usefulness, remaining blockers, and the next recommendation are documented without enabling App Server globally or broadening roles, permissions, network, deployment, providers, or transport.
