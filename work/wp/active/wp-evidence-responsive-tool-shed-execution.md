# Evidence-responsive Tool Shed execution Workpackage

Status: active
Type: workpackage
Updated: 2026-08-09
Next Action: run focused regression tests and inspect generated workspace guidance

Project Map: work/maps/map-tool-shed-evolution.md

## Current Context

Tool Shed 0.10.3 has end-to-end ship routing, campaign continuity, artifact selection, validation,
and work-state reconciliation. It reacts to explicit contradiction and requires target
verification, but the distributed agent instructions do not contain a compact ordinary loop for
comparing post-action evidence with expected state. Consequential ship work has authorization and
rollback boundaries but no narrowly scoped prospective failure scan.

The completed evaluation and decision are:

- `work/evidence/evidence-human-planning-mechanism-evaluation.md`
- `work/decisions/decision-human-planning-mechanisms-for-tool-shed.md`

## Recommendation

Add the two mechanisms as concise native instructions. Do not add branded methodology names,
artifact types, mandatory fields, an urgency matrix, or ritual reflection for bounded work.

## Current State

Completed:

- Source-backed mechanism inventory.
- Frozen instruction-level scenario evaluation.
- Decision matrix selecting two native mechanisms.

Incomplete:

- Canonical skill, installer guidance, documentation, tests, release, and client deployment.

## Goal

Canonical documentation, the distributable skill, installed workspace guidance, and tests express
the two adopted native mechanisms without branded vocabulary or new artifact types:

- nontrivial work compares actual with expected state after material actions and updates the next
  action around the current limiting condition;
- consequential ship stages identify up to three credible failures and add proportionate
  prevention, detection, verification, or rollback;
- simple answers and known single-step reversible work skip explicit loop ceremony;
- neither mechanism broadens scope or authority.

## Why It Matters

Agents can mistake command success for outcome success, persist with stale plans, or spend effort
away from the condition limiting progress. Existing safety controls catch known risks but do not
systematically elicit credible missing failure modes before consequential stages.

## Major Outcomes

- Evidence-responsive execution guidance distributed to workspace agents.
- Prospective failure guidance scoped to consequential ship stages.
- Operator documentation and regression coverage.
- Validated canonical release and exact installed-client deployment.

## Delivery Stages

Use stages when sequencing, parity gates, or handoff cost matter.

| Stage | Outcome | Entry Evidence | Exit Evidence |
| --- | --- | --- | --- |
| 1 | Canonical guidance and docs | decided mechanisms and frozen scenarios | focused assertions pass |
| 2 | Repository qualification | focused tests pass | full validator and skill validation pass |
| 3 | Release and deployment | clean intended scope and release authority | canonical provenance and installed exact-diff verification |

## Related Artifacts

- Tickets:
- Checklists:
- Spikes: `work/spikes/spike-evaluate-human-planning-models-for-tool-shed.md`
- ADRs:
- Runbooks:
- Inventories: `work/inventories/inventory-human-planning-mechanisms-for-tool-shed.md`
- Decision matrices: `work/decisions/decision-human-planning-mechanisms-for-tool-shed.md`

## Rough Sequence

1. Update canonical guidance and operator documentation.
2. Update installer-managed blocks and regression tests.
3. Regenerate root guidance and indexes.
4. Run focused and full validation.
5. Follow release procedure, deploy the installed skill, and verify exact parity.

## Milestones

### Milestone 1: Guidance and documentation

Completion criteria:

- [ ] Canonical skill and managed workspace instructions contain both mechanisms.
- [ ] README, conventions, and operator guide explain triggers and non-triggers.

### Milestone 2: Qualification

Completion criteria:

- [ ] Installer regression tests and full validator pass.
- [ ] Canonical and staged skill validation pass.

### Milestone 3: Release and client deployment

Completion criteria:

- [ ] Manifest provenance and tag validate.
- [ ] Canonical remote manifest matches the release.
- [ ] Installed client exactly matches canonical `skills/tool-shed/`.

## Open Questions

- Can the active client reload a replaced skill without a new task? No; report the required fresh
  task smoke after exact deployment verification.

## Completion Standard

This workpackage is complete when the evaluated instructions are documented, regression-tested,
released when publication is authorized, deployed to the installed client, and verified there.

## Closeout Routing

- Current truth promoted to: README.md; conventions.md; docs/operator-guide.md; skills/tool-shed/SKILL.md
- Historical context remains in: the evaluation spike, inventory, evidence, and decision matrix
- Runtime/status evidence: validation output and installed-client exact comparison
- Cleanup deferred to: independent cross-model behavioral pilot
