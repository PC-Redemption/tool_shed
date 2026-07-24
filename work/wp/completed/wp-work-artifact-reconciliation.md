# Work artifact reconciliation Workpackage

Status: complete
Type: workpackage
Updated: 2026-07-24
Next Action: none

Project Map: work/maps/map-tool-shed-evolution.md
Canonical Truth: README.md; conventions.md; skills/tool-shed/SKILL.md

## Current Context

Tool Shed generates a work index and checks stale Markdown paths, but neither check determines
whether active artifacts remain connected to planning or whether completed spikes produced a
decision. Workspace-local `tool_shed/` snapshots are ignored by design; project-specific `work/`
artifacts need a separate, explicit tracking and review policy.

## Recommendation

Add a read-only reconciliation command with text and JSON output. Make warnings visible during
normal validation while leaving strict CI enforcement opt-in. Track `work/` by default, keep
`tool_shed/` ignored, and never rewrite plans automatically.

## Current State

Completed:

- Work index generation, stale-path checking, artifact headers, and full validation exist.
- Repository instructions already describe disconnected snapshot installation.

Incomplete:

- Plan drift currently treats legitimate historical links as active dependencies.
- Equal version strings can hide divergent canonical manifests.
- Manifest writes do not yet enforce intentional version bumps or record release provenance.

## Goal

Humans and Codex can regularly detect planning drift, understand how findings should be resolved,
and safely install or update Tool Shed without losing project work.

## Why It Matters

Unnoticed artifacts create false confidence: the work exists on disk but does not influence
planning or reminders. Reconciliation turns that silent failure into reviewable evidence.

## Major Outcomes

- A deterministic, read-only `review_work_state.py` command.
- Spike disposition and output linkage conventions.
- Default Git policy for `work/`.
- Codex instructions for new installs and existing snapshot updates.
- Release mismatch detection, intentional bump enforcement, and release provenance.
- Section-aware plan-drift findings that preserve historical and related links.
- Unit and end-to-end validation coverage.

## Delivery Stages

Use stages when sequencing, parity gates, or handoff cost matter.

| Stage | Outcome | Entry Evidence | Exit Evidence |
| --- | --- | --- | --- |
| 1 | Define reconciliation contract | observed drift modes | finding codes and severity policy documented |
| 2 | Implement and test | contract agreed | focused tests cover clean and drifted workspaces |
| 3 | Integrate guidance | passing focused tests | full repository validation passes |
| 4 | Harden release and drift semantics | field review findings | mismatch, bump, provenance, and section-aware tests pass |

## Related Artifacts

- Tickets:
- Checklists:
- Spikes:
- ADRs:
- Runbooks:
- Inventories:
- Decision matrices:

## Rough Sequence

1. Add the reconciliation script and artifact header support.
2. Add tests for orphan, stale, spike disposition, broken links, JSON, and strict mode.
3. Integrate the check into validation and document review cadence.
4. Add Codex install/update prompts and verify the complete repository.
5. Detect equal-version manifest divergence and enforce intentional release bumps.
6. Record release provenance and restrict plan-drift checks to planning-bearing locations.

## Milestones

### Milestone 1: Reconciliation command

Completion criteria:

- [x] Findings are deterministic and machine-readable.
- [x] Default execution is advisory and `--strict` is enforceable.

### Milestone 2: Lifecycle and adoption guidance

- [x] Spike disposition and tracked-`work/` conventions are documented.
- [x] New-install and existing-update prompts preserve workspace boundaries.

### Milestone 3: Verification

- [x] Focused unit tests pass.
- [x] Full repository validation passes.

### Milestone 4: Hardening

- [x] Equal-version content divergence reports `release-mismatch`.
- [x] Manifest writes require a valid greater semantic version unless explicitly rebuilding.
- [x] Release tag, commit, and timestamp provenance are generated and reported.
- [x] Historical and related links do not trigger plan drift.
- [x] Active dependencies and unchecked tasks pointing at finished work still trigger plan drift.

## Open Questions

- Whether strict mode should become the default CI policy after field use.
- Whether cadence should remain guidance or gain a scheduler-specific runbook later.

## Completion Standard

This workpackage is complete when the command, tests, validation integration, templates,
conventions, and Codex prompts agree and the full validation suite passes.

## Closeout Routing

- Current truth promoted to: `README.md`, `conventions.md`, `skills/tool-shed/SKILL.md`
- Historical context remains in: this completed workpackage
- Runtime/status evidence: focused unit tests and `scripts/validate_tool_shed.py`
- Cleanup deferred to: guarded fleet rollout after human review
