# Evidence: Bounded App Server Planning Retrieval — M1

Status: completed
Type: evidence
Updated: 2026-09-06
Campaign: CAMP-0167
Roadmap: PRM-0042 / M1-BOUNDED-RETRIEVAL-CORE
Candidate: `c745b684ee3c847755ef78ffda2f245fdd825874`

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
- `.venv/bin/python scripts/validate_tool_shed.py --profile full --jobs 8`: 615 tests passed and
  every full development check passed after current Hybrid views were rendered.
- Snapshot/client slice: 238 tests passed, including disconnected snapshot validation and warm
  upgrade installation.
- `git diff --check`: passed.
- Linux (`sup`, `/home/jon/dev/ts_linux_test_bed`): 615/615 tests, verified snapshot integrity,
  strict Doctor `HEALTHY`, and a clean committed qualification fixture.
- Windows (`gogetter`, `E:\dev\ts_windows_test_bed`): 615/615 tests under Python 3.14, verified
  snapshot integrity, strict Doctor `HEALTHY`, and a clean committed qualification fixture.
- Windows exposed and now covers CRLF normalization before line-range and returned-byte-budget
  accounting; exact source bytes remain digest-bound for tamper detection.
- Development web staged and deployed exact commit `c745b684ee3c847755ef78ffda2f245fdd825874`;
  documentation, dashboard, and production-isolation health checks passed.

## Live App Server Protocol Proof

Installed Codex App Servers completed real read-only preparation turns against `README.md`:

- Canonical/Linux Codex 0.149.0 and Windows Codex 0.153.0 each returned `completed` with exactly one
  `dynamicToolCall`.
- Linux returned `README.md` lines 1–19 (874 bytes); Windows returned lines 1–19 (869 bytes).
- Both runs recorded zero refused calls and `content_retained: false`.
- Linux manifest: `fa0c78ad036845459917fd0f8498526b1dc1a02e8e8925c5c19b91091f03e2c7`.
- Windows manifest: `a8d9f53ce7c5d705aaec708148f800dfde07fdbac343c1030f35858f44bf1df8`.

The prompt-free local smoke telemetry is retained under the ignored operator evidence path
`.tool-shed/idea-0021-retrieval-smoke.jsonl`; it contains no retrieved source text.

## Remaining Work5 Boundary

M2 owns the final frozen-candidate repetition, exact-SHA CI, release provenance, all production
lanes, immediate dashboard convergence, and recursive reconciliation.

## Work3 Exact-Candidate Replay

The tracked Work3 candidate `de7a6cd9f57edfdc1df654f8fd6fd74cc3ea5b06` adds only this
evidence, the CAMP-0167 Hybrid checkpoint, and the initial release-lane record to the qualified
source commit. Its exported Tool Shed snapshot has archive SHA-256
`f4b64116b2f083437c82a16667e2da961d79d2908c5e1d5ab17df8b7302367d4`.

- Web: staged exact `de7a6cd9f57edfdc1df654f8fd6fd74cc3ea5b06`; documentation and
  dashboard endpoints were healthy, all isolated development containers were healthy, and the
  production health endpoint remained healthy.
- Linux: exact exported snapshot verified as 0.49.0, the focused retrieval suite passed 8/8, the
  Git fixture remained clean, and strict Doctor returned `HEALTHY`.
- Windows: the same exact exported snapshot verified as 0.49.0, the focused retrieval suite passed
  8/8 under Python 3.14, the Git fixture remained clean, and strict Doctor returned `HEALTHY`.
- Release-lane Work3 verification passed with web, Windows, and Linux development lanes recorded
  `verified` against the exact candidate.
