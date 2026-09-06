# Evidence: Bounded App Server Planning Retrieval — M1

Status: candidate-ready
Type: evidence
Updated: 2026-09-06
Campaign: CAMP-0167
Roadmap: PRM-0042 / M1-BOUNDED-RETRIEVAL-CORE
Candidate: the Work2 content commit containing this evidence

## Result

The bounded retrieval core satisfies `G-RETRIEVAL-CONTRACT` and the implementation portion of
`G-CORRECTNESS-BUDGETS`:

- App Server `thread/start` registers one dynamic function, `read_context`.
- The function serves only manifest-declared UTF-8 regular files from a private immutable snapshot
  outside the model sandbox.
- Every request requires the exact manifest SHA-256, POSIX path, one-based start line, and bounded
  line count.
- Leaf and parent symlinks, traversal, absolute/drive paths, undeclared files, stale live sources,
  changed snapshots, invalid ranges, per-read excess, and cumulative excess fail closed.
- Planning interrupts command, file-change, MCP, web, image, or any other non-dynamic tool request.
- Durable evidence contains manifest/source digests, paths, ranges, byte totals, and refusal codes;
  retrieved content is never retained.
- `needs_more_context` is a controlled empty-capsule pre-mutation result and never advances the
  campaign.

## Focused Verification

- `python3 -m unittest tests.test_context_retrieval tests.test_app_server_dispatch
  tests.test_codex_execution`: 95 tests passed.
- `.venv/bin/python scripts/validate_tool_shed.py --profile full --jobs 8`: 613 tests passed and
  every full development check passed in 35.212 seconds after current Hybrid views were rendered.
- Snapshot/client slice: 238 tests passed, including disconnected snapshot validation and warm
  upgrade installation.
- `git diff --check`: passed.

## Live App Server Protocol Proof

The installed Codex App Server completed a real read-only preparation turn against `README.md`:

- route: `app-server`
- status: `completed`
- tool calls: 1
- tool type: `dynamicToolCall`
- manifest digest: `3f99acb08747864f135fb157c1d1b387231d61c78763254daf2cc192387e9d9a`
- returned range: `README.md` lines 1–8, 514 bytes
- refused calls: 0
- content retained: false
- structured answer: first heading `tool_shed`, `used_read_context: true`

The prompt-free local smoke telemetry is retained under the ignored operator evidence path
`.tool-shed/idea-0021-retrieval-smoke.jsonl`; it contains no retrieved source text.

## Remaining Work5 Boundary

M2 owns exact-candidate release validation, fresh and upgraded disposable Linux and Windows
qualification, hosted-development verification, exact-SHA CI, release provenance, all production
lanes, immediate dashboard convergence, and recursive reconciliation.

