# Evidence: Windows realistic App Server budget on Tool Shed v0.29.8

Status: complete
Type: evidence
Updated: 2026-08-26
Next Action: publish the post-v0.29.8 verifier/preparation repair and upgrade clients only under separate owner authorization
Campaign: repair-and-reprove-windows-app-server-campaign-path
Campaign Reason: G8-WINDOWS-REALISTIC-BOUNDED completion evidence

## Result

Core's disconnected Tool Shed snapshot and installed Windows skill were upgraded from v0.29.7
to verified v0.29.8. Snapshot transaction `bb2f5d5a58097c940c768309` installed content
commit `038e2f4c624b1795932a30892edb12bd325c1bd9` from release provenance
`b2f59550fe63d4f59685792b36cfaa3cf118e1b3`. The update retained a bounded snapshot backup
and a bounded installed-skill backup; no backup pruning occurred.

Core Campaign 020 was a real, non-production owner-state repair. The one-command dispatcher
automatically prepared and persisted its capsule, started the queued campaign, and changed only
`work/maps/map-panel-forge.md` from the normal logged-in Windows session 1. It used no nested
Codex process and made no deployment, production, hardware, PID, or Campaign 013 change.

| Stage | Model | Model turns | Input tokens | Tool-result bytes |
| --- | --- | ---: | ---: | ---: |
| Automatic preparation | gpt-5.6-sol | 1 | 32,802 | 0 |
| CAMP execution | gpt-5.6-terra | 2 | 48,768 | 2,362 |
| Combined | mixed policy | 3 | 81,570 | 2,362 |

The combined run remained within every shared default: 3 of 4 model requests, 81,570 of
180,000 cumulative input tokens, 2,362 of 65,536 cumulative tool-result bytes, and a largest
single result of 2,362 of 16,384 bytes.

## Verification and repair

The first reserved verification stopped safely after mutation. Automatic preparation had chosen
the unavailable `py.exe` launcher and a broad clean-diff assertion that conflicted with the
dispatcher's own persisted capsule and lifecycle edits. The worker was not replayed. The capsule
was reconciled to the activated project interpreter and map-scoped checks, and the built-in
Windows deterministic verifier then passed all three commands through the logged-in console
sandbox. The old repeatable 5,403-byte stderr payload did not recur; final stderr byte counts were
0, 0, and 121, with the last being Git's line-ending warning.

The run also reproduced a CP-1252 decode traceback on non-ASCII sandbox output. Canonical Tool
Shed now forces UTF-8 decoding with replacement and enables Python UTF-8 mode for Windows
verification children. Automatic preparation now advertises and normalizes the current Python
executable and removes redundant broad worktree diff checks. The two focused test modules pass:
57 tests in 11.232 seconds.

Core Campaign 020 is complete at commit `8db9cda83f898dff28add5b6fa21ca239ceebed3`.
Its post-commit Tool Shed doctor reports internal consistency verified and only the two retained
pre-existing warning classes: tracked binary evidence and four legacy external-evidence
annotations. Snapshot integrity is verified, queue/work state is reconciled, and the Core
worktree is clean.

The canonical transport/preparation repair in this evidence is not published or synchronized to
clients. Publication, installed-skill synchronization, and another Core snapshot upgrade remain
separately authorized work.
