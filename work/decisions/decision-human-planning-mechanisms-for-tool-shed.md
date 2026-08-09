# Decision Matrix: Human planning mechanisms for Tool Shed

Status: decided
Type: decision-matrix
Updated: 2026-08-09
Next Action: implement the evidence-response loop and conditional prospective failure check
Parent: work/spikes/spike-evaluate-human-planning-models-for-tool-shed.md

## Decision

Which evaluated human-planning mechanisms should change Tool Shed now, and which should be covered
by existing behavior, deferred, or rejected?

## Options

| Option | Evidence and benefit | Cost or limitation | Decision |
| --- | --- | --- | --- |
| Evidence-response loop, synthesizing OODA/PDCA and constraint focus | +13 instruction-coverage points; closes command-success/target-failure and stale-plan paths; agent research independently supports interleaving action and feedback | adds a small repeated check to nontrivial work | `adopt` with an explicit single-step non-trigger |
| Conditional prospective failure check | +10 points; catches missing prevention/detection before consequential work | can become generic ceremony if unbounded | `adopt` with a narrow trigger and at most three credible failures |
| Urgent/important matrix | can expose urgency bias | workspace agent often lacks authorized owner-level importance; scenario introduced a critical inference risk | `reject` as core Tool Shed behavior |
| Full GTD or weekly review workflow | established capture/clarify/review structure | duplicates artifact headers, work index, and reconciliation; reduced scenario efficiency | `reject` as a new layer; document existing overlap only in research artifacts |
| Full Cynefin vocabulary | useful reminder that different contexts need different responses | existing selection rules already map known, uncertain, deep-research, and incident work with less terminology | `reject` as operator vocabulary; keep current native selection |
| Standalone implementation-intention feature | explicit cue-response rules are useful | Tool Shed routes already use this pattern extensively | `already covered`; preserve exact trigger/non-trigger authoring |
| WOOP/MCII | obstacle-first thinking overlaps the limiting-condition question | motivational and imagery assumptions do not transfer; if-then component duplicates routing | `reject` as a separate method |
| Cross-model behavioral benchmark | could estimate compliance, variance, token cost, and model-specific effects | needs an independent controlled execution lane and a larger evidence budget | `pilot later`; not required for the reversible instruction release |

## Recommendation

Implement the two adopted rules as native Tool Shed behavior:

1. Add an evidence-response loop to the canonical skill and installed `AGENTS.md` guidance for
   nontrivial execution. It keeps the desired outcome and current limiting condition visible,
   compares actual with expected state after material actions, and revises the next action.
2. Add a prospective failure check to `ts:ship` before consequential stages. Limit it to up to
   three credible failures and require prevention, detection, verification, or rollback as
   applicable.

Document both rules in `README.md`, `conventions.md`, and the operator guide. Add installer and
validation regression coverage. Do not add a template or artifact field in this release.

Implementation: `work/wp/active/wp-evidence-responsive-tool-shed-execution.md`.
