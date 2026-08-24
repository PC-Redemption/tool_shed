# Snapshot upgrade performance and retry-safety qualification

Status: active
Type: evidence
Updated: 2026-08-24
Next Action: run the candidate on native Windows through an authorized branch/CI or workspace route and record cold plus warm-retry timing
Campaign: make-stable-snapshot-upgrades-fast-observable-and-retry-safe
Parent: work/00-campaigns/active/053-make-stable-snapshot-upgrades-fast-observable-and-retry-safe.md

## Baseline

The Bactron Core update from Tool Shed `0.25.2` to `0.26.1` exposed two verified updater archives
with the same prestate and different transaction IDs, consistent with one failed/rolled-back attempt
followed by a successful retry. The released client reran the complete developer validator on each
attempt, buffered subprocess output between phase boundaries, used a 300-second default validator
timeout, and retained no durable sanitized timing or failure report. Windows tag validation for
`v0.26.1` took 5m16s and 5m32s; its unit-test phase reported 319.570 seconds.

The installed Bactron snapshot ultimately remained integrity-clean: all 136 manifest hashes
matched, unrelated owner work and 26 dirty files were preserved, and the verified backup scope was
intact. This establishes the safety baseline but not the new performance gate.

## Candidate behavior

- Default release and post-install validation ceilings are 900 seconds.
- A 20-second background heartbeat keeps every long phase visible without mixing child output into
  JSON stdout.
- Every attempt writes a sanitized protected user-local transaction record with stage durations,
  validation mode/cache identity, bounded error class, and rollback outcome. It records no
  workspace path, prompt, response, command output, credential, or secret.
- A recoverable user-local per-workspace lock rejects concurrent duplicate upgrades.
- Successful validation is reusable only when release commit, validator SHA-256, operating system,
  architecture, Python implementation, and Python version all match exactly.
- Canonical stable releases may use the focused client smoke only when their provenance commit
  carries an exact qualification attestation binding the content commit, full validator, focused
  validator, and both comprehensive CI workflows. Overrides, missing attestations, and every
  changed identity fall back to full local validation.
- The Ubuntu/Windows and Python 3.11/current-Python full validation matrix remains unchanged.
- The unpublished candidate manifest is `0.27.0`; no tag, push, release, or client deployment has
  been performed by this campaign.

## Local verification

Focused command:

```text
python3 -m unittest -v tests.test_snapshot_upgrade_state \
  tests.test_scripts.ScriptTests.test_snapshot_updater_times_out_release_validation_before_mutation \
  tests.test_scripts.ScriptTests.test_snapshot_upgrade_warm_retry_reuses_validation_and_reaches_install_under_one_minute \
  tests.test_scripts.ScriptTests.test_snapshot_updater_installs_into_new_workspace \
  tests.test_scripts.ScriptTests.test_snapshot_updater_rolls_back_from_verified_archive \
  tests.test_scripts.ScriptTests.test_snapshot_upgrade_replaces_old_skill_and_refreshes_guidance_transactionally
```

Result: 12 tests passed in 3.026 seconds before the later dirty-work strengthening. The strengthened
warm-retry test then passed independently and printed:

```text
warm snapshot retry reached installation in 0.208s
```

That test injects a post-install failure after cold validation, verifies rollback, preserves both a
modified tracked owner file and an unrelated untracked source file, retries against the same exact
release identity, proves the validation cache hit, reaches successful installation in under one
minute, and verifies the durable transaction timing/rollback record.

Full command:

```text
python3 scripts/workspace_preflight.py --workspace .
python3 scripts/validate_tool_shed.py
```

Result: preflight passed; the final exact candidate passed all 250 tests in 62.814 seconds; provider conformance, generated
indexes, stale-path checks, work-state review, Program Roadmap validation, disposable all-provider
installation, and template sanity passed. The focused client smoke also passed in a disposable
release image.

## Remaining completion evidence

Native Windows has not executed this unpublished candidate. Campaign completion still requires a
Windows cold attempt plus warm retry to pass with visible heartbeat/timing evidence, dirty-work and
rollback preservation, exact cache identity, and warm progress to backup or installation in under
one minute. Running that candidate requires an authorized push/CI route or an explicitly authorized
Windows workspace mutation; `ts: next` alone grants neither.
