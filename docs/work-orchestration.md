# Scripted Work1 And Work2 Orchestration

`scripts/work_orchestration.py` moves settled Tool Shed preparation and closeout mechanics out of
model turns. It is a thin caller of the existing identity, work-level, document, validation,
checkpoint, Doctor, and release-cohort surfaces. Those commands remain independently callable and
authoritative.

The runner does not implement product behavior, judge evidence, choose a version or target, deploy,
push, release, or close an owning outcome. Codex or the operator supplies those decisions and the
current target evidence. Work1 and Work2 remain stopping points.

## Fixed Phase Contract

Preparation runs:

1. project identity and work-level resolution (`always-run`);
2. document-state audit (`always-run`);
3. disposable lifecycle-view regeneration (`exact-local-digest`);
4. the existing changed-path validation policy and selected profile (`exact-local-digest`).

Closeout runs:

1. candidate-commit reachability (`always-run`);
2. current target-evidence validation for Work2 (`current-external-evidence`);
3. Work2 release-cohort registration (`exact-local-digest`);
4. logical checkpoint and disposable rebuild proof (`exact-local-digest`);
5. an exact logical-checkpoint Git commit, including only its JSON and referenced immutable content
   objects (`exact-local-digest`);
6. strict Doctor (`always-run`).

The caller first requests a read-only plan and passes its project-bound state token to the mutation.
A changed database revision, source tree, Git state, work-level envelope, candidate, or evidence
digest invalidates the token. `--resume` skips only a previously passed phase with the exact same
run ID and input digest. Always-run and current-external-evidence phases never trust old success.
An exclusive local lock rejects duplicate execution instead of letting two writers race.

## Work1 Example

Obtain the orchestration binding once:

```bash
python3 scripts/project_identity.py --workspace . identity \
  --operation work-orchestration --json
```

Plan and run preparation with the exact changed paths:

```bash
python3 scripts/work_orchestration.py --workspace . plan work1 \
  --stage prepare --changed-path scripts/example.py
python3 scripts/work_orchestration.py --workspace . prepare work1 \
  --expect <plan-state-token> --project-binding <work-orchestration-binding> \
  --changed-path scripts/example.py --run-id <stable-run-id>
```

After Codex makes the scoped product commit, plan and run closeout:

```bash
python3 scripts/work_orchestration.py --workspace . plan work1 \
  --stage closeout --commit <candidate-sha>
python3 scripts/work_orchestration.py --workspace . closeout work1 \
  --expect <plan-state-token> --project-binding <work-orchestration-binding> \
  --commit <candidate-sha> --checkpoint-message "Checkpoint Work1 state" \
  --run-id <stable-run-id>
```

## Work2 Evidence And Closeout

Deployment remains a project-specific action outside the runner. After deployment and focused
changed-behavior checks, write an ignored local evidence envelope:

```json
{
  "schema_version": 1,
  "kind": "tool-shed-target-evidence",
  "endpoint": "work2",
  "target": "the exact configured development target",
  "checked_at": "2026-08-29T18:00:00Z",
  "checks": [
    {"id": "health", "status": "passed", "reference": "https:status/200"}
  ]
}
```

Every check must pass, the target and endpoint must match, and evidence must be no more than two
hours old. Then include the nearest open owning cycle:

```bash
python3 scripts/work_orchestration.py --workspace . plan work2 \
  --stage closeout --commit <candidate-sha> --origin-cycle <cycle-uuid> \
  --target-evidence .tool-shed/evidence/work2.json
python3 scripts/work_orchestration.py --workspace . closeout work2 \
  --expect <plan-state-token> --project-binding <work-orchestration-binding> \
  --commit <candidate-sha> --origin-cycle <cycle-uuid> \
  --target-evidence .tool-shed/evidence/work2.json \
  --checkpoint-message "Checkpoint Work2 release cohort" --run-id <stable-run-id>
```

The closeout registers the exact product commit and its open parent chain. It may commit only
`work/state/checkpoints/state-v2.json` and immutable content objects referenced by that checkpoint;
unrelated changes fail closed.

## Telemetry And Dashboard Aggregate

The detailed JSONL journal is local and ignored under `.tool-shed/orchestration/`. It retains at
most 10,000 events and 30 days. Events classify work as `reasoning-required`,
`deterministic-script`, `recovery-retry`, or `external-wait`. Duration, result, calls, output bytes,
retries, and exact state tokens support diagnosis without becoming project truth.

Qualified providers may record exact input and output usage with `record`. GUI-native work omits
usage; missing tokens remain unknown, never zero or estimated. The aggregate keeps exact measured
remedial tokens, coverage, and GUI-portable proxies separate:

```bash
python3 scripts/work_orchestration.py --workspace . report \
  --hours 24 --output .tool-shed/reports/work-efficiency-v1.json
```

The versioned per-project payload contains only project identity, counter epoch, window,
freshness, counts, exact covered token totals, and proxies. It excludes prompts, commands, paths,
source, and diagnostics, so the hosted dashboard can ingest it without receiving granular model
activity. Dashboard or network failure never blocks local work.

Use guarded `reset-telemetry --confirm-reset` to start a new counter epoch. Reset affects ignored
operational telemetry only; it does not alter work state, outcome history, or release cohorts.

## Failure And Recovery

Success output is compact. A failed phase records its exact phase ID, input token, bounded final
diagnostic, duration, and retry count in the local journal. Resume only after the cause is corrected;
changed inputs rerun the phase. A runner failure never grants permission to skip the underlying
check. Diagnose it, record any recovery as `recovery-retry`, and use the independently callable
command only as an explicit fallback.

The frozen representative baseline lives at
`tests/fixtures/work-orchestration-baseline-v1.json`. It compares the same Work1 and Work2 corpus,
reports interactions and output as proxies, and does not claim unavailable provider-token totals.
