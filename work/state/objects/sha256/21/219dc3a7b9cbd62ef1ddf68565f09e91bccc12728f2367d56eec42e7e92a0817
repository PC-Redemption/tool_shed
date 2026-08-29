# Evidence: Case-normalized documentation verification

Status: verified
Type: evidence
Updated: 2026-08-26
Campaign: require-case-normalized-documentation-verification

## Field finding

The v0.29.12 Windows proof in Bactron Core Campaign 023 successfully exercised the repaired
first-file-change handoff. Automatic preparation and the worker each completed in one model turn,
the worker made exactly one expected documentation change without commands, and Tool Shed ran the
reserved deterministic verifier exactly once. The verifier then rejected valid sentence-initial
capitalization because it collapsed whitespace but compared semantic phrases case-sensitively.

## Repair

Automatic preparation now requires one shared normalizer for both the Markdown document and every
expected multiword phrase. The normalizer must collapse whitespace and normalize case. The capsule
parser recognizes this shared-normalizer shape before persistence and rejects both raw phrase checks
and the Core Campaign 023-shaped whitespace-only check.

The validation remains scoped to Markdown expected paths and inline Python verification. Existing
shell-free execution, path boundaries, worker command prohibition, and exactly-once orchestration
remain unchanged.

## Verification

- Python compilation passed for the dispatcher and its focused test module.
- All 21 dispatcher tests passed.
- All 71 Codex execution and dispatcher tests passed together.
- The regression rejects an unnormalized phrase check.
- The regression rejects a verifier that normalizes only document whitespace.
- The regression accepts a verifier that applies one whitespace-and-case normalizer to both the
  document and expected phrases.
- `git diff --check` passed.

The test run warned that the host's locally installed Codex build is newer than the qualified
versions. This campaign did not launch an App Server worker, so that compatibility warning does not
affect the parser-level result.

## Boundary

No release was published, no installed skill was synchronized, Core was not changed again, Core
Campaign 023 was not replayed, and Bactron was not deployed. Publication and maintainer skill
synchronization require the next explicit release authorization. Campaign 085's Core upgrade and
fresh replacement Windows proof remain covered by their existing authorization after that release.
