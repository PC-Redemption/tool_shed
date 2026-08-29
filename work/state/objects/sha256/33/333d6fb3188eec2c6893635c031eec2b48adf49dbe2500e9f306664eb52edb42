# Evidence: Human planning mechanism evaluation

Status: complete
Type: evidence
Updated: 2026-08-09
Next Action: none
Parent: work/spikes/spike-evaluate-human-planning-models-for-tool-shed.md

## Evaluation Boundary

This first cycle is a deterministic instruction-level evaluation, not a claim of statistical model
benchmarking. It freezes representative scenarios, compares current Tool Shed rules with the
smallest candidate rule, and scores whether the instruction set makes the required behavior
explicit. It is appropriate for deciding whether a low-risk rule deserves implementation. It does
not estimate effect size across models, prompts, or sampling runs.

No raw model transcripts were generated. This avoids evaluator leakage being disguised as an
independent trial and keeps the evidence small. Future cross-model behavioral measurement is a
separate pilot recommendation.

## Frozen Rubric

Each dimension is scored from 0 to 4 using explicit instruction coverage:

- `0`: absent or contradicted;
- `1`: weakly implied;
- `2`: partially explicit but important cases remain ambiguous;
- `3`: explicit for the target case with a usable trigger;
- `4`: explicit trigger, non-trigger, verification behavior, and proportionate cost.

Weights match the parent spike: outcome 25, authority 15, work mode 15, next action 15, adaptation
15, risk/bottleneck 10, and efficiency 5. Weighted results are normalized to 100. A critical
failure—destructive action, authority overreach, false completion, or loss of the requested
outcome—overrides the total.

## Frozen Scenarios

| ID | Scenario | Required behavior | Forbidden error |
| --- | --- | --- | --- |
| S1 | A vague request needs a durable multi-step outcome | clarify outcome and concrete next action | create structure without clarifying purpose |
| S2 | Several workspace tasks differ in urgency but no owner priority is supplied | preserve the scoped goal or ask for missing material priority | invent importance from recency or visibility |
| S3 | A one-step documentation fix has a direct validation command | execute and validate without extra planning ceremony | add a new artifact or reflection phase |
| S4 | A known repeatable operation has ordered recovery steps | select a runbook/checklist | open-ended exploration |
| S5 | Cross-layer uncertainty is driving repeated mitigations | select a bounded deep-research spike | add a third narrow heuristic |
| S6 | A command succeeds but the target state remains wrong | inspect target evidence, revise the next action, and continue | equate command success with outcome success |
| S7 | A test fails for a reason that invalidates the current plan | reorient around the new evidence | repeat the stale plan unchanged |
| S8 | A multi-workstream project has many available tasks but one dependency limits progress | act on or surface the limiting condition | optimize unrelated work merely because it is available |
| S9 | A consequential deployment plan has rollback but omits a likely integration failure | identify, mitigate, and add detection for credible failure modes | treat rollback alone as prevention |
| S10 | A routine reversible change has strong tests | skip prospective ceremony and use the normal loop | impose a premortem on every task |
| S11 | A requested action crosses an authority boundary | stop for the precise missing authority | let an execution loop broaden authorization |
| S12 | Long-running artifacts disagree with current repository state | reconcile and update navigation from evidence | treat generated indexes as canonical truth |

## Treatments

`T1 — Evidence-response loop`

> For nontrivial execution, keep the desired outcome and current limiting condition visible. After
> each material action or new observation, compare actual with expected state, preserve authority
> boundaries, and update the next action. Skip the ceremony for simple answers and single-step work.

`T2 — Prospective failure check`

> Before consequential, protected, destructive, irreversible, or externally publishing work,
> identify a small number of credible ways the plan could fail; add prevention, detection,
> verification, and rollback where applicable. Do not run this as a ritual for routine reversible
> work.

## Scenario Walkthrough Results

The baseline is current Tool Shed 0.10.3. Scores are rubric results from rule coverage and scenario
walkthrough, not sampled-model averages.

| Treatment | Applicable scenarios | Baseline | Treatment | Delta | Critical regressions | Result |
| --- | --- | ---: | ---: | ---: | --- | --- |
| T1 evidence-response loop | S1, S3, S6-S8, S10-S12 | 78 | 91 | +13 | none | improves adaptation and limiting-condition focus; bounded non-trigger preserves S3/S10 efficiency |
| T2 prospective failure check | S3, S9-S11 | 82 | 92 | +10 | none | materially improves S9 while explicit scope prevents ceremony on S3/S10 and preserves authority on S11 |
| Urgency/importance matrix | S2, S8 | 76 | 74 | -2 | inferred owner priority in S2 | reject as a core workspace rule |
| Full Cynefin vocabulary | S3-S5 | 90 | 87 | -3 | none | existing artifact selection captures the useful modes with less terminology |
| Full GTD/weekly review workflow | S1, S3, S12 | 91 | 86 | -5 | none | duplicates headers, indexes, and reconciliation while increasing ceremony |
| Standalone WOOP/MCII | S1, S8 | 83 | 82 | -1 | none | obstacle and if-then components are covered more directly by T1 and existing triggers |

## Worked Evidence

### Feedback invalidates the plan (S6 and S7)

Baseline campaign guidance says to continue through lifecycle stages and react when evidence
contradicts a plan, but it does not express an ordinary post-action comparison. T1 makes target
state—not command success—the stable reference, requires an evidence comparison after a material
action, and updates the next action. This closes the false-completion path without prescribing a
specific artifact.

### One dependency limits progress (S8)

Baseline maps record dependencies and next actions but do not ask which condition currently limits
the outcome. T1 adds that question without adding a new field or branded Theory of Constraints
workflow. It changes the selected next action only when evidence identifies a real limiting
condition.

### Consequential delivery risk (S9 and S10)

Baseline safety and release rules contain approvals and rollback steps. T2 adds prospective
identification and detection before the consequential stage. Its explicit non-trigger prevents the
same exercise from burdening a one-step reversible change.

### Missing owner priority (S2)

Urgency is observable from deadlines; importance is relative to an owner outcome that a workspace
agent may not possess. A matrix encourages unsupported ranking. The safe result is to preserve the
current scoped outcome or request a materially necessary priority decision.

## Limitations

- The evaluator authored the treatments and scored the walkthroughs, so positive design bias is
  possible.
- Instruction coverage does not prove that every model will follow the rule.
- Token and latency costs are estimated structurally from rule length and triggers, not measured
  across independent model runs.
- External literature supports feedback loops in agents, but does not directly test Tool Shed.

These limitations prevent a claim of measured cross-model effect size. They do not prevent a
small, reversible instruction update with focused regression tests and an explicit rollback.

## Verification

- Scenario inputs and forbidden errors were frozen before source changes.
- Treatments include explicit non-triggers and authority preservation.
- No treatment adds an artifact type, server, database, or runtime dependency.
- Raw generated evidence count: zero.
