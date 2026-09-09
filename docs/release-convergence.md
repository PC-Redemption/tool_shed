# Release Capability Convergence

Tool Shed releases describe workspace migrations and compatibility work in
`schemas/release-convergence/v1/capabilities.json`. The inventory separates three kinds of work:

- schema migrations are ordered, guarded transitions from the current Hybrid SQLite schema to the
  release target;
- required compatibility backfills restore behavior that the release promises, such as explicit
  document-header relationships;
- optional semantic enrichment is reported but never inferred or applied automatically.

The thin `scripts/release_convergence.py` orchestrator calls the existing domain migration tools.
It does not replace their stale-state checks, backups, rollback procedures, or semantic validation.
Safe automatic steps run during direct workspace installation and snapshot update. A release
summary is emitted whether the workspace converged, needs a safe automatic step, is blocked by a
runtime or semantic finding, or is coherently deferred at an owner decision.

## Inspect And Apply

Status and planning are read-only:

```bash
python3 tool_shed/scripts/release_convergence.py --workspace . status
python3 tool_shed/scripts/release_convergence.py --workspace . --json plan \
  --output .tool-shed/convergence-plan.json
```

Apply a fresh plan with the exact token and the `hybrid-state` project binding:

```bash
python3 tool_shed/scripts/release_convergence.py --workspace . apply \
  --plan .tool-shed/convergence-plan.json --expect <plan-token> \
  --project-binding <hybrid-state-binding>
```

The plan binds the project, inventory, database revision and digest, authority resolution,
configured runtimes, work Markdown, and Git status. Any relevant change makes it stale. Repeating
an apply is safe: completed schema steps and existing semantic relationships are reported as
satisfied instead of being duplicated.

## Runtime Readiness

Convergence probes both the interactive Python and the configured background Python in disposable
temporary databases. A probe checks ordinary JSON reads separately from a guarded write through a
trigger with `trusted_schema=OFF`. This distinguishes a readable database from a runtime that can
actually execute Tool Shed's hardened accounting triggers.

`SQLITE_TRUSTED_SCHEMA_TRIGGER_UNSAFE` means the selected Python/SQLite combination rejects the
trigger's JSON function. Select a newer compatible Python/SQLite runtime for that role, then rerun
status. Diagnostics use bounded codes and versions; raw exception text and workspace content are
not written to the convergence journal.

Doctor exposes the same distinction as read health versus mutation readiness. A runtime can
therefore remain usable for inspection while all migrations and other guarded writes fail closed.

## Journal And Recovery

Every attempted schema step appends a bounded, hash-chained event to
`.tool-shed/convergence/journal-v1.jsonl`. Events contain only a sequence, run and plan IDs, step,
state, attempt number, diagnostic code, schema bounds, and chain hashes. The journal is local and
ignored; it contains no prompts, document bodies, command output, credentials, or raw errors.

If a run stops after recording an attempt, rerun `plan`, then `apply` with the fresh token. Existing
guarded migrations discover the durable schema level and continue from the first unsatisfied step.
If a domain migration reports ambiguity, use that domain tool's plan and rollback guidance; do not
edit the database or journal to force progress.

## Document Authority Decision

Switching from file authority to database document authority is intentionally not automatic. The
status report keeps one explicit `document-authority` decision with impact, coherent fallback,
rollback, and an exact continuation command. To approve it, choose an archive path outside the
workspace:

```bash
python3 tool_shed/scripts/release_convergence.py --workspace . apply \
  --plan .tool-shed/convergence-plan.json --expect <plan-token> \
  --project-binding <hybrid-state-binding> --allow document-authority \
  --archive /protected/outside/path/tool-shed-document-source.tar
```

The guarded path archives retained sources, imports stable identities, extracts only resolvable
explicit relationships, verifies semantic parity, writes a recovery checkpoint, and then changes
authority. An unresolved or ambiguous reference blocks the required backfill; it is never guessed.
Optional historical enrichment remains separate and never runs as a side effect of conversion.
