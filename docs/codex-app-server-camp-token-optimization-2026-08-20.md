# Codex App Server CAMP Token Optimization

Date: 2026-08-20  
Campaign: 040, `app-server-camp-token-optimization`  
Implementation branch: `codex/tool-shed-app-server-camp-token-optimization`  
Qualification fixture branch: `codex/tool-shed-camp-token-qualification`  
Codex CLI: 0.144.6  
Model: `gpt-5.6-terra` / medium  
Result: economic target met; retain explicit opt-in

## Outcome

The same controller-regression edit used by the workspace-writing qualification completed with
61,516 input tokens, below the initial 120,000-token target and 74.53% below the 241,524-token
reference. The declared test file was the only changed path, the two requested regression
assertions were added, all 22 focused tests passed, the structured outcome remained
`step_complete`, and the Git journal remained safe. No Sol operation, retry, permission expansion,
network access, lifecycle mutation, or automatic rollback occurred.

The optimized path remains explicitly opt-in. This result does not change App Server's
experimental support status and is not approval for global enablement, deployment, additional
write roles, API execution, Luna, another provider, or another transport.

Implementation checkpoints are `22082bb` (baseline), `6f6c817` (bounded optimization), and
`ce0b05c` (trigger-neutral capsule). The final documentation/manifest commit is recorded in the
campaign completion state.

## Reference Anatomy

The prompt-free source anatomy is preserved in
`docs/codex-app-server-camp-token-baseline-2026-08-20.md`. Reasoning output is a subset of output
and is never added a second time.

| Turn | Purpose and classification | Input | Cached | Uncached | Output | Reasoning | Tool/result bytes | Elapsed |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | --- | ---: |
| 1 | Read the Tool Shed skill; deterministic orientation | 29,590 | 0 | 29,590 | 185 | 63 | command / 10,065 | 5.852s |
| 2 | Read campaign route and try the wrong identity path; avoidable loop | 31,743 | 29,440 | 2,303 | 214 | 53 | command / 17,661 | 4.937s |
| 3 | Search for the identity helper; avoidable loop | 35,546 | 31,488 | 4,058 | 206 | 112 | command / 458 | 5.239s |
| 4 | Run identity preflight; deterministic work | 35,796 | 34,560 | 1,236 | 77 | 9 | command / 679 | 2.582s |
| 5 | Apply the requested regression edit; required reasoning/action | 35,990 | 35,584 | 406 | 323 | 62 | file change / 373 | 6.862s |
| 6 | Run focused tests; verification/tool-result processing | 36,337 | 35,584 | 753 | 148 | 13 | command / 495 | 5.735s |
| 7 | Return `step_complete`; lifecycle decision | 36,522 | 35,584 | 938 | 156 | 78 | none | 3.753s |
| **Total** |  | **241,524** | **202,240** | **39,284** | **1,309** | **390** | **29,731** | **36.704s** |

The first four pre-edit turns consumed 132,675 input tokens and four of six model tools. The first
two orientation results contributed 27,726 bytes, or 93.25% of all model tool-result bytes. The
actual edit, test, and decision turns already totaled 108,849 input tokens. Fixed harness cost and
accumulated thread history therefore dominated; file context was not the primary avoidable cost.

## Changes

- App Server telemetry now records ordered per-model-turn token anatomy, elapsed time, the preceding
  tool type, and serialized tool-result bytes without retaining prompts or tool output.
- A focused ephemeral worker directory supplies a minimal execution contract. The real repository
  remains the exact workspace-write root, so isolation does not broaden filesystem authority.
- Repository orientation, Git state, exact writable scope, and pending verification are supplied as
  compact structured state. The worker does not rediscover project state or own lifecycle changes.
- Successful tests and checks run through App Server `command/exec` as shell-free argv arrays after
  the model edit. Success evidence retains exit status, byte counts, hashes, and an optional test
  count, not raw output. Failure stops the sequence and expands only to compact diagnostics.
- Verification state is authoritative: a failed deterministic verifier records
  `verification_failed`, exits nonzero, and selects workspace reconciliation. A mutation is never
  retried automatically.
- Generated execution text avoids unnecessarily naming project-management machinery. This removed
  the remaining skill-orientation turn without suppressing any applicable safety instruction.
- Fresh ephemeral threads remain the normal strategy. No resume/cache state or invalidation
  framework was added; the small and normal samples show that accumulated history costs more than
  it saves here.

The supplied file context grew from 46,332 to 52,888 bytes because the implementation and tests are
larger (+6,556, +14.15%). Prompt characters similarly grew from 47,296 to 54,345. Savings therefore
come from eliminating repeated reads, raw results, model-owned Git/test work, and carried history,
not from omitting required context or manipulating accounting.

## Weighted Usage Metric

`weighted_codex_usage` uses weights version `openai-relative-token-rates-2026-08-20-v1`. It
normalizes the current published API token-rate ratios to one Terra uncached input token:

| Model | Uncached input | Cached input | Output |
| --- | ---: | ---: | ---: |
| Terra | 1.00 | 0.10 | 6.00 |
| Sol | 2.50 | 0.25 | 15.00 |

The formula is `uncached_input * weight + cached_input * weight + output * weight`. Reasoning is
reported separately but not double-counted because it is included in output. This is a neutral
relative usage proxy, not dollars and not a claim about ChatGPT allowance consumption. Every
individual request remained below the documented long-context multiplier threshold.

## Same-Fixture Comparison

The first optimized rerun reached 96,329 input tokens but still performed one installed-skill read.
After the trigger-neutral capsule change, the final same-fixture result was:

| Metric | Reference | Optimized | Absolute change | Relative change |
| --- | ---: | ---: | ---: | ---: |
| Input | 241,524 | 61,516 | -180,008 | -74.53% |
| Cached input | 202,240 | 30,464 | -171,776 | -84.94% |
| Uncached input | 39,284 | 31,052 | -8,232 | -20.96% |
| Output | 1,309 | 395 | -914 | -69.82% |
| Reasoning output | 390 | 41 | -349 | -89.49% |
| Observed model turns | 7 | 2 | -5 | -71.43% |
| Model tools | 6 | 1 | -5 | -83.33% |
| Model tool-result bytes | 29,731 | 673 | -29,058 | -97.74% |
| Full elapsed | 36.704s | 12.458s | -24.246s | -66.06% |
| Weighted usage | 67,362.0 | 36,468.4 | -30,893.6 | -45.86% |
| Terra model requests | 7 | 2 | -5 | -71.43% |
| Sol model requests | 0 | 0 | 0 | 0% |
| Fixed orientation operations | 4 | 0 | -4 | -100% |

Optimized turn 1 used 30,590 input / 0 cached / 30,590 uncached / 315 output / 22 reasoning
tokens and performed the 673-byte file change. Turn 2 used 30,926 input / 30,464 cached / 462
uncached / 80 output / 19 reasoning tokens and returned the structured outcome. Tool Shed then ran
the 22-test verifier without another model request; its 121 output bytes were reduced to status,
byte counts, hashes, and test count.

## Generalization Samples

The reference fixture is the normal successful-test sample. Material improvement justified one
small sample, one larger-context sample, and one controlled diagnostic sample; no duplicate matrix
was run.

| Sample | Context | Input (cached / uncached) | Output / reasoning | Turns / tools | Full elapsed | Weighted | Result |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Small state edit | 13 B | 37,962 (28,160 / 9,802) | 172 / 25 | 2 / 1 | 7.456s | 13,650.0 | verified success |
| Normal controller regression + successful test | 52,888 B | 61,516 (30,464 / 31,052) | 395 / 41 | 2 / 1 | 12.458s | 36,468.4 | 22 tests; verified success |
| Larger documentation edit | 78,013 B | 67,496 (32,512 / 34,984) | 387 / 79 | 2 / 1 | 12.693s | 40,557.2 | verified success |
| Diagnostic evidence | 12 B | 37,973 (28,160 / 9,813) | 194 / 29 | 2 / 1 | 9.562s | 13,793.0 | expected verifier failure |

The diagnostic verifier exited 7 after emitting 25 stdout and 25 stderr bytes. Telemetry retained
only byte counts and SHA-256 digests, returned CLI status 2, selected
`reconcile_workspace_before_retry`, and issued no retry or Sol escalation. That sample exposed an
ambiguous journal label; the implementation now records `final_state=verification_failed` while
preserving the separate fact that the path journal itself was safe.

## Safety, Correctness, and Economics

The optimized run preserved ChatGPT authentication, Terra/medium, approval `never`, disabled
network, both temporary-directory exclusions, the exact writable root, exact path allowlist, Git
preflight, dirty-target refusal, unrelated-dirty preservation, no retry after mutation, and
Tool-Shed-owned lifecycle decisions. Deterministic commands use the same App Server workspace-write
sandbox. No reset, checkout, clean, rollback, permission expansion, deployment, or lifecycle write
was added.

The result demonstrates meaningful economic value for bounded small, normal, and larger successful
edits: two Terra requests are sufficient, successful verification costs no model turn, and weighted
usage fell 45.86% on the reference. The remaining fixed floor is material—about 38,000 input tokens
even for a 13-byte edit—and uncached reference input fell only 20.96%. App Server also remains
experimental, cancellation and restricted-read protocol mismatches remain, and failure recovery
after mutation intentionally requires reconciliation. These are reasons to retain explicit opt-in,
not to discard the bounded path.

Recommended next step: complete Campaign 040, keep App Server CAMP execution in maintenance/watch
with explicit opt-in, and reassess deferred Campaign 039 before reactivation because App Server may
replace part of the proposed watcher rather than complement it.
