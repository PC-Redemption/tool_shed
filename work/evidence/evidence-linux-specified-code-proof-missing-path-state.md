# Evidence: Specified Linux code proof lacked expected-path starting state

Status: verified
Type: evidence
Updated: 2026-08-26
Campaign: prove-specified-command-free-first-pass-code-test-campaign-on-linux

## Result

Campaign 080 did not satisfy the code/test proof gate and must not be replayed.

Automatic preparation correctly resolved the confirmed provider-path defect to
`scripts/provider_adapters.py` plus a new `tests/test_provider_adapters.py`, supplied 11,110 bytes
of bounded context, selected one quiet unittest verifier, and estimated one model turn. The first
worker used 22,473 input tokens in one turn, issued zero commands and zero other tool calls, changed
no files, and returned `unknown`.

The worker's reason identified the exact collateral omission: Tool Shed declared the test path as
an expected mutation but did not explicitly state that the path was absent and authorized for
creation. With no command access, the worker conservatively treated the missing inline test content
as unknown existing content it could not overwrite.

## Repair

Every CAMP worker handoff now includes a deterministic map of each expected path to one starting
state: `existing-file`, `existing-directory`, `existing-other`, `symlink`, or
`absent-authorized-creation`. The prompt explicitly states that an absent authorized target has no
prior content to preserve and may be created. This state is computed after the Git mutation journal
begins and does not require worker filesystem inspection.

Focused dispatcher and execution tests passed 67 tests, including a direct check that an existing
file and an absent creation target receive distinct starting states.

## Boundary

No product mutation or verification occurred, and Campaign 080 was not replayed. Its dependent
asset proof is superseded without execution. Publication, synchronization, Core upgrade, Windows
execution, and deployment remain excluded.
