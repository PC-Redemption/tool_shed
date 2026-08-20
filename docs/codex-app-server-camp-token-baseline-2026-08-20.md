# Codex App Server CAMP Token Baseline — 2026-08-20

## Scope

This is the pre-optimization anatomy of the representative App Server CAMP from the workspace-write
qualification. The source was the retained local Codex rollout for thread
`01a01ffb-74ea-7931-89db-58c6bf387bec` plus prompt-free Tool Shed telemetry. Extraction retained
only timestamps, token counters, sanitized tool classifications, and serialized tool-result byte
counts. Prompts, file contents, command output, and account data were not copied into this report.

The run used Codex CLI 0.144.6, App Server v2 over stdio, ChatGPT authentication, and
`gpt-5.6-terra` / medium. It returned `step_complete`, changed only the declared test file, and
passed 20 focused tests.

## Per-Turn Anatomy

Elapsed time is the interval from the preceding token update, or from the first user message for
turn 1. Tool-result bytes are the serialized local rollout item size, not model tokens. App Server
does not expose a byte-level decomposition of provider input into fixed harness, instructions,
files, and history; `context/history observation` therefore records the strongest local evidence
without presenting an estimate as protocol fact.

| Turn | Purpose and classification | Input | Cached | Uncached | Output | Reasoning* | Tool | Result bytes | Context/history observation | Elapsed |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | --- | ---: |
| 1 | Load Tool Shed skill; deterministic instruction operation | 29,590 | 0 | 29,590 | 185 | 63 | read skill | 10,065 | Initial request included 46,332 file bytes, a 47,296-character assembled prompt, user and repository instruction sources, plus the fixed Codex harness | 5.852 s |
| 2 | Read campaign route and try the wrong identity path; avoidable agent loop | 31,743 | 29,440 | 2,303 | 214 | 53 | read route + failed command | 17,661 | Prior turn and its 10,065-byte result were carried; the new result was the largest of the run | 4.937 s |
| 3 | Discover the identity script after the wrong path; avoidable agent loop | 35,546 | 31,488 | 4,058 | 206 | 112 | repository search | 458 | Accumulated thread now included both instruction reads and the failed command | 5.239 s |
| 4 | Run project identity; deterministic operation | 35,796 | 34,560 | 1,236 | 77 | 9 | identity command | 679 | Nearly the entire prior request was cached, but it still counted toward usage | 2.582 s |
| 5 | Apply the requested two-line test change; required execution | 35,990 | 35,584 | 406 | 323 | 62 | file change | 373 | First turn that mutated the declared target | 6.862 s |
| 6 | Run the focused suite; verification | 36,337 | 35,584 | 753 | 148 | 13 | test command | 495 | Successful test evidence was already compact | 5.735 s |
| 7 | Return `step_complete`; lifecycle/status transition | 36,522 | 35,584 | 938 | 156 | 78 | none | 0 | Final structured assessment carried the complete preceding thread | 3.753 s |
| **Total** |  | **241,524** | **202,240** | **39,284** | **1,309** | **390** | **6 calls** | **29,731** |  | **36.704 s** |

\* `reasoning_output_tokens` is a subset/annotation of output for this transcript: every cumulative
`total_tokens` equals input plus output. It must not be added to output again.

## Dominant Sources

1. Four turns occurred before the requested edit. They consumed 132,675 input tokens and four of
   six tool calls. Turns 2 and 3 were directly avoidable path/discovery loops.
2. The first two tool results were 27,726 bytes, 93.25% of all serialized tool-result bytes. Both
   were instruction/path orientation rather than CAMP evidence.
3. The actual edit, focused test, and structured completion were turns 5–7. Together they consumed
   108,849 input tokens, below the campaign's initial 120,000-input target.
4. Cached input reached 35,584 tokens by turn 5 and remained there. Caching lowered the relative
   weight of history but did not remove it from counted usage.
5. Successful edit and test outputs were already small. The largest opportunity is eliminating
   pre-edit model turns and preventing accumulated orientation history, not shaving a few hundred
   bytes from the final test result.

## Weighted Usage v1

`weighted_codex_usage` is a neutral comparison proxy, not dollars and not a claim about ChatGPT Pro
allowance accounting. Version `openai-relative-token-rates-2026-08-20-v1` normalizes the current
official model rates to one Terra uncached-input token:

| Model | Uncached input weight | Cached input weight | Output weight |
| --- | ---: | ---: | ---: |
| `gpt-5.6-terra` | 1.00 | 0.10 | 6.00 |
| `gpt-5.6-sol` | 2.50 | 0.25 | 15.00 |

The relative weights come from the official
[Terra model page](https://developers.openai.com/api/docs/models/gpt-5.6-terra) and
[Sol model page](https://developers.openai.com/api/docs/models/gpt-5.6-sol), which list separate
uncached-input, cached-input, and output rates. Those are API rates used only to construct a stable
relative proxy; Campaign execution continues to require ChatGPT authentication with no API path.

For one operation:

```text
weighted_codex_usage =
    uncached_input * model_uncached_weight
  + cached_input   * model_cached_weight
  + output         * model_output_weight
```

Reasoning output is reported separately but is not added again when it is already included in
output. The reference CAMP's weighted usage is:

```text
39,284 + (202,240 * 0.10) + (1,309 * 6.00) = 67,362.0 units
```

Per-turn baseline units are 30,700.0; 6,531.0; 8,442.8; 5,154.0; 5,902.4; 5,199.4; and 5,432.4.

## First Optimization Hypothesis

Preserve the workspace-write sandbox and Git journal, but move deterministic preflight and evidence
selection outside the model loop. Give Terra an already validated execution capsule with exact
paths, current safety state, focused source evidence, the requested edit, and one focused
verification command. The target shape is three reasoning boundaries: make the edit, process the
compact test result, and return the structured outcome. No implementation behavior has been changed
at the point represented by this report.
