# ADR: Guarded Restart Supersedes Status Only

Status: example
Type: adr
Updated: 2026-07-05
Next Action: none
Supersedes: work/adr/adr-service-status-only.md
Superseded By:

## Context

A previous decision kept a service check in status-only mode because automatic remediation was too aggressive. Later validation showed a guarded restart policy could recover persistent failures while avoiding repeated restarts.

## Decision

Supersede the status-only policy with guarded apply mode.

The guarded policy requires:

- multiple confirmed failures before action
- a persistent failure counter
- a cooldown after restart
- published status evidence
- rollback instructions in current docs

## Consequences

Positive:

- persistent failures can recover automatically
- status remains visible while the guardrail is active
- the old decision remains available as historical context

Negative:

- restart-capable behavior must be documented and tested
- ignored local config may materially affect behavior

## Alternatives Considered

- Keep status-only forever.
- Restart immediately on first failure.
- Move remediation back to the old host scheduler.

## Supersession Notes

Update the old ADR header:

```text
Superseded By: work/adr/adr-guarded-restart-supersedes-status-only.md
```

Promote the current operating policy to docs or README files. Keep both ADRs as decision history.
