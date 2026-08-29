# Evidence: Realistic Linux App Server CAMP usage budget

Status: complete
Type: evidence
Updated: 2026-08-26
Next Action: publish and synchronize the corrective release only after separate owner authorization
Campaign: bound-realistic-app-server-campaign-growth
Gate: G6-LINUX-REALISTIC-BOUNDED
Result: passed

## Enforced defaults

The existing App Server notification loop now requests `turn/interrupt` when any live CAMP ceiling
is reached:

| Measure | Default |
| --- | ---: |
| Observed model requests | 4 |
| Cumulative input tokens | 180,000 |
| Cumulative serialized tool results | 65,536 bytes |
| One serialized tool result | 16,384 bytes |

The compact finding contains only the reached limit, observed count, configured limits, and
interrupt acknowledgement. Reserved deterministic verification is skipped after interruption. The
Git journal returns `resume_bounded_camp` before mutation or
`reconcile_workspace_then_resume_bounded_camp` after an authorized path changed; mutated work is
never replayed automatically.

Focused execution and dispatcher tests passed 56/56 in 11.934 seconds. They include live
interruption with a real fake-App-Server protocol stream, truthful authorized-path mutation
journaling, verifier suppression, all four ceiling classifiers, compact-output assertions, the
ordinary two-turn verified path, automatic preparation, and direct dispatch.

## Representative native Linux proof

A fresh Git fixture at `/tmp/tool-shed-camp066-linux-final-BULMIZKo` supplied a behavioral spec, an
incomplete Python module, and two unit tests. One direct App Server `camp-run` invocation used
`/home/jon/.local/bin/codex` 0.149.0 with `gpt-5.6-terra` / medium, no nested `codex exec`, and an
external telemetry path. The worker implemented the Python behavior and added operator
documentation in one `fileChange`; Tool Shed then ran the reserved unittest command exactly once.

| Measure | Result | Ceiling |
| --- | ---: | ---: |
| Model requests | 2 | 4 |
| Input tokens | 40,016 | 180,000 |
| Cached input | 19,200 | reported separately |
| Output tokens | 644 | reported separately |
| Reasoning output | 48 | included in output |
| Weighted usage proxy | 26,600.0 | informational |
| Serialized tool-result bytes | 1,820 | 65,536 total / 16,384 single |
| Model duration | 16.851 seconds | informational |
| CAMP duration | 17.350 seconds | informational |
| Deterministic verification | 2/2 tests passed, one command | exactly once |

The journal ended `verified`, safe true, with only `src/budget_report.py` modified and
`docs/usage-budget.md` created. There were no deleted or unexpected paths, and pre-existing state
was preserved. The 40,016 input tokens are 92.6% below the 540,741-token Core foundation worker and
93.6% below the 625,383-token Core runtime worker.

The external telemetry SHA-256 was
`e21025cbe5163d9b17198e33b1b8a3207126aa7d6650892ce44a5c646e444b12`. Result file hashes were
`cad364e17cbb8fd98b512923619cfbe553986b629c4ed449f4e026964b0a88d7` for the Python module and
`a713cdc6c0dc81293b93fad8c9516196a459451668068e0580c1f52bc554c428` for the operator document.

An earlier fresh fixture also completed the same change in two turns with 40,916 input tokens and
passing tests, but its journal correctly stopped because the proof harness placed telemetry inside
the repository as an undeclared path. That mutated step was not replayed; the authoritative proof
used a new repository and external telemetry.
