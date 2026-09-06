# Dashboard Reporter v0.48.1 Work3 Qualification

Status: passed
Recorded: 2026-09-06
Release lane: `99ded537-9287-4724-a42e-9846b6995327`
Candidate commit: `2538636e6101d3be5723ebfb3b7dbf93f39ffecf`
Candidate version: `0.48.1` (unpublished development candidate)

## Result

The exact candidate passed repository and disconnected-snapshot validation on Linux and Windows.
It corrects the production lock/claim race by constructing report payloads before the short outbox
write transaction, retaining and retrying the persistent worker after transient SQLite contention,
releasing the per-delivery lease on every exit, and replacing a still-live claim when its recorded
process no longer exists. Existing outboxes add the nullable process identifier in place.

The regression drives the observed sequence directly: the persistent worker owns its process
claim, the first drain attempt raises `database is locked`, no event, manual report, or safety pass
is introduced, and the same worker delivers on its next cycle before releasing the claim. Separate
coverage proves that report construction can acquire an outbox write lock, delivery contention
releases the worker lease, a dead-process claim is replaced before expiry, and the legacy outbox
schema migrates without losing its claim row.

## Exact Development Targets

| Lane | Target and artifact | Result |
| --- | --- | --- |
| Web | `tsrookarocom-dev@sup.local:/home/jon/docker/ts.rookaro.com-dev`; `tool-shed-dashboard:dev-2538636e6101`; image `sha256:ee46c6666c790b4d7bbbce0aa079a9788a2aba07d6095dfeb0e8104b9a912ab1` | Development site and dashboard health HTTP 200; production regression health HTTP 200 |
| Linux | `sup:/home/jon/dev/ts_linux_test_bed`; archive `sha256:ee26d1d5cfe70081e38ae5f9f8a20510c6444962f55fbd7b8d9c8e2f4529a549` | Strict disconnected snapshot verified; 32 reporter tests and 602/602 full tests passed |
| Windows | `GOGETTER:E:\dev\ts_windows_test_bed`; same archive | Strict disconnected snapshot verified; 32 reporter tests and 602/602 full tests passed |

The archive contains neither Git metadata nor a project `work/` tree. Its digest matched on both
platforms. The prior client snapshots remain recoverable as
`tool_shed.before-v0481-2538636` in each disposable test bed. Windows full validation ran from an
isolated environment populated only from `requirements-dashboard.txt`; the initial system-Python
run was incomplete because Django was not installed and is not counted as product evidence.

## Boundary

No production deployment, tag, GitHub Release, stable-client update, or user-level skill
synchronization occurred during Work3 qualification. The published v0.48.0 clients remain
authoritative until Work5 completes every production lane.
