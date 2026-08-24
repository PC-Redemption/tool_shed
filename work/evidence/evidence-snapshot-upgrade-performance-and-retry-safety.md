# Snapshot upgrade performance and retry-safety qualification

Status: active
Type: evidence
Updated: 2026-08-24
Next Action: obtain authorization to push the frozen 0.27.0 candidate to a qualification branch, then record native Windows CI and cold plus warm-retry evidence
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

## Sanitized maintainer issue reporting

- Every final transaction now records one stable `TSU-*` issue code. Codes distinguish successful
  completion, concurrency, timeout, network, integrity, validation, permission, filesystem,
  unknown, and incomplete-rollback outcomes; incomplete rollback takes precedence over the
  initiating error class.
- Transaction records bind the updater version, protocol, and exact updater-script SHA-256 without
  retaining its path.
- `scripts/snapshot_upgrade_report.py` renders `latest` or one exact transaction ID as sanitized
  maintainer-ready Markdown or JSON. It is read-only and has no network, `gh`, upload, or publish
  operation.
- The reporter accepts only final records with the allowlisted schema, same platform and
  architecture, private state/report permissions where supported, matching filename identity, and
  a correct derived issue code. It rejects symlinks, malformed JSON, unknown fields,
  foreign-platform records, exposed permissions, unsafe values, and failure records missing their
  bounded stage or error class.
- Rendered reports omit the release-validation cache identity and expose only bounded release and
  updater identity, phase durations, validation/cache mode, issue code, error class, and rollback
  outcome. Prompts, responses, raw output, exception text, workspace paths, usernames, dirty
  filenames, credentials, and secrets are never rendered.
- The documented `ts: upgrade report [latest|<transaction-id>]` route requires separate review and
  external-write authorization before any `gh issue create` action.

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

Result before the reporter scope freeze: preflight passed and all 250 tests passed in 62.814
seconds. After the reporter was added as the final candidate scope, 16 focused reporter, updater,
privacy, documentation-route, focused-client-smoke, timeout, and warm-retry tests passed. The final
warm retry reached installation in 0.200 seconds during focused validation and 0.218 seconds during
the full run. The exact final candidate then passed all 256 tests in 62.718 seconds. Provider
conformance, exact 139-file manifest validation, documentation-site validation, generated indexes,
stale-path checks, work-state review, Program Roadmap validation, disposable all-provider
installation, and template sanity passed. The focused client smoke also passed in a disposable
release image containing the new report command.

## Remaining completion evidence

Native Windows has not executed this unpublished candidate. The owner froze the reporter as the
final `0.27.0` scope and prohibited further features or prerequisite campaigns before
qualification. Campaign completion still requires a Windows cold attempt plus warm retry to pass
with visible heartbeat/timing evidence, dirty-work and rollback preservation, exact cache
identity, and warm progress to backup or installation in under one minute. The next action is a
qualification-branch push, which requires separate authorization. No tag, GitHub Release,
installed-skill synchronization, or Bactron Core upgrade is authorized by that branch push.
