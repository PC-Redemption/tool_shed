# Spike: Evaluate human planning models for Tool Shed

Status: complete
Type: spike
Updated: 2026-08-09
Next Action: none
Parent: work/maps/map-tool-shed-evolution.md
Disposition: planned
Produces: work/wp/completed/wp-evidence-responsive-tool-shed-execution.md

## Question

Which mechanisms from human planning, prioritization, and self-management models measurably improve
Tool Shed's ability to select tools, plan proportionately, adapt to evidence, and complete the
intended outcome without adding more process cost than value?

Subquestions:

- Which recurring agent failure mode does each mechanism address?
- Does the mechanism still make sense when human motivation, emotion, fatigue, and memory are not
  assumed?
- Is the mechanism already present in Tool Shed under another name?
- Should a useful mechanism become a selection heuristic, artifact field, reusable procedure,
  validation rule, or no product change at all?
- Which mechanisms work independently, and which only add value as a small combined workflow?

## Outcome

Produce evidence-backed Tool Shed update recommendations classified as `adopt`, `pilot`, `defer`,
or `reject`. Every adopt or pilot recommendation must name the exact Tool Shed surface to change,
the failure mode addressed, expected benefit, process cost, validation method, and rollback path.

This spike recommends changes only. Implementation belongs in explicitly linked follow-up
artifacts after the recommendations are reviewed.

## Timebox

Bound the first evaluation cycle to:

- one source and mechanism inventory;
- one baseline plus one isolated treatment per shortlisted mechanism;
- up to 12 representative task scenarios;
- one combined-treatment pilot only after isolated results justify it;
- one synthesis and recommendation pass.

Stop expanding the candidate set when two consecutive candidates add no new transferable
mechanism. Do not optimize prompts or Tool Shed rules during measurement; record improvement ideas
for the recommendation stage so the comparisons remain interpretable.

## Candidate Set

Start with these models because they cover distinct operational mechanisms:

| Model or practice | Candidate transferable mechanism | Initial Tool Shed hypothesis |
| --- | --- | --- |
| Getting Things Done | capture, clarify, next action, periodic review | improves conversion of vague commitments into executable work |
| Eisenhower matrix | importance versus urgency | reduces preference for visible urgent work over consequential work |
| OODA loop | observe, orient, decide, act, re-observe | improves replanning when tool or environment evidence changes |
| PDCA/PDSA | planned change plus measured feedback | strengthens iterative validation and process improvement |
| Theory of Constraints | identify and exploit the current bottleneck | reduces parallel optimization that does not advance the outcome |
| Cynefin | classify the problem context before choosing a response mode | improves selection among checklist, analysis, experiment, and containment |
| Premortem | prospective failure analysis | exposes predictable delivery and deployment risks before execution |
| Implementation intentions | condition-to-action rules | improves reliable tool and procedure selection at known triggers |
| WOOP / obstacle-first planning | identify the most likely obstacle and response | prevents outcome plans that omit the dominant blocker |
| Weekly review | reconcile commitments, stale state, and priorities | improves long-running campaign continuity and plan accuracy |

Add a candidate only when it contributes a materially different mechanism. Treat overlapping
labels as one mechanism rather than rewarding brand count.

## Evaluation Principles

- Evaluate mechanisms, not the popularity or branding of a model.
- Use primary or authoritative descriptions where available and record source quality.
- Separate mechanisms aimed at executive structure from those aimed mainly at human motivation or
  emotional regulation.
- Compare against current Tool Shed behavior, including its artifact-selection and campaign rules,
  rather than against an unstructured agent.
- Change one mechanism at a time before testing any bundle.
- Use identical task inputs, tool access, model family, reasoning level, and completion criteria
  within each comparison whenever the environment permits.
- Preserve unfavorable, neutral, and favorable results. Do not rewrite scenarios after seeing a
  treatment result.
- Treat model outputs as variable: repeat ambiguous or close comparisons and report the spread,
  not only the best run.

## Evaluation Plan

### Phase 1: Establish the baseline and failure taxonomy

- Review current Tool Shed rules, representative completed work, incidents, and plan-drift findings.
- Define observable failure modes such as premature completion, wrong work mode, missing next
  action, stale-assumption continuation, priority inversion, unnecessary artifact creation,
  unaddressed bottlenecks, and weak verification.
- Record which candidate mechanisms Tool Shed already implements fully or partially.

### Phase 2: Build the source-backed mechanism inventory

- For each candidate, record its original purpose, operational steps, assumptions about humans,
  transferable mechanism, likely agent failure mode addressed, overlap with Tool Shed, and risks.
- Exclude or narrow techniques whose benefit depends primarily on motivation, affect, subjective
  wellbeing, or long-term habit formation that the agent cannot possess.
- Screen candidates into `shortlist`, `already covered`, `low transfer`, or `insufficient evidence`.

### Phase 3: Freeze representative scenarios and scoring

Create up to 12 compact, replayable scenarios covering:

- vague desired outcomes that need clarification and a next action;
- conflicting urgent and important work;
- a clear bounded task where extra process is harmful;
- complicated work needing analysis rather than experimentation;
- complex work needing probes and feedback;
- deployment or debugging work where new evidence invalidates the plan;
- a project with a dominant bottleneck and distracting parallel opportunities;
- a premortem-relevant delivery risk;
- a long-running campaign with stale or conflicting artifacts;
- a situation where the correct recommendation is to use no additional tool.

For each scenario, freeze the input, available workspace evidence, permitted actions, expected
critical behaviors, forbidden errors, and completion criteria before running comparisons.

### Phase 4: Run controlled comparisons

- Run the current Tool Shed baseline for each applicable scenario.
- Run the same scenario with one candidate mechanism expressed as the smallest usable instruction
  or artifact addition.
- Capture decisions, tool and artifact choices, reorientation after evidence, final outcome,
  unnecessary steps, and human intervention required.
- Repeat ties, surprising results, and high-variance scenarios at least twice.
- Test a combined `classify -> anticipate -> feedback` workflow only if isolated results support
  Cynefin, premortem, and OODA/PDCA mechanisms individually.

### Phase 5: Score results and examine costs

Use a 0-4 anchored score per dimension and preserve the rationale:

| Dimension | Weight | What good looks like |
| --- | ---: | --- |
| Outcome correctness and completeness | 25 | satisfies the actual desired outcome and completion criteria |
| Constraint and authority retention | 15 | preserves scope, safety, and operator boundaries |
| Work-mode and tool selection | 15 | chooses a proportionate method and avoids needless structure |
| Next-action and sequencing quality | 15 | identifies the decisive executable step and dependencies |
| Adaptation to new evidence | 15 | re-observes and revises rather than following a stale plan |
| Risk and bottleneck recognition | 10 | finds likely failure causes and the limiting constraint |
| Process efficiency | 5 | avoids needless turns, artifacts, tool calls, and explanation |

Record critical failures separately; a weighted total must not hide destructive action, authority
overreach, false completion, or loss of a required outcome.

### Phase 6: Produce update recommendations

Classify each mechanism:

- `adopt`: repeatable material improvement with no critical regression and acceptable overhead;
- `pilot`: promising but narrow, variable, or insufficiently tested;
- `defer`: plausible value but blocked by missing evidence or measurement capability;
- `reject`: no meaningful transfer, duplicates current behavior, or costs more than it improves.

An `adopt` recommendation should improve its target failure mode in more than one scenario family,
avoid degrading clear bounded tasks, and remain understandable without naming the originating
self-help brand. Prefer the smallest native Tool Shed rule over importing an entire methodology.

For each proposed update, specify:

- exact files or surfaces (`selection.md`, `conventions.md`, skill routing, template, helper script,
  operator guide, validator, or test fixture);
- current behavior and proposed behavior;
- triggering condition and explicit non-trigger;
- expected benefit and measured evidence;
- added cognitive, token, turn, and artifact cost;
- tests, rollout scope, observability, and rollback;
- interactions or conflicts with existing Tool Shed rules.

## Evidence and Deliverables

Keep the spike concise and link detailed evidence rather than embedding raw transcripts. Expected
outputs during execution:

- a versioned source and mechanism inventory;
- a frozen scenario manifest and scoring rubric;
- a small results summary with representative evidence locations;
- a decision matrix comparing shortlisted mechanisms;
- a final recommendation section in this spike;
- follow-up tickets or a workpackage only for approved implementation candidates.

Before any evaluation campaign that could emit many transcripts or fixtures, run workspace
preflight and keep raw captures under `work/evidence/generated/` with a small versioned manifest.

## Findings

- The source-backed inventory is complete at
  `work/inventories/inventory-human-planning-mechanisms-for-tool-shed.md`.
- Tool Shed already covers the transferable core of GTD, weekly review, implementation
  intentions, PDCA, and Cynefin through artifact headers, indexes, reconciliation, trigger rules,
  lifecycle verification, and uncertainty-based artifact selection.
- The frozen instruction-level walkthrough is recorded at
  `work/evidence/evidence-human-planning-mechanism-evaluation.md`. An evidence-response loop scored
  91 versus a 78 baseline on applicable scenarios; a conditional prospective failure check scored
  92 versus 82. Neither introduced a critical regression.
- Urgency/importance ranking introduced an owner-priority inference risk. Full GTD, Cynefin, and
  WOOP layers duplicated existing behavior or added ceremony.
- The evaluation is a deterministic design test, not an independent cross-model effect-size
  claim. A future behavioral benchmark remains a pilot rather than a release requirement.

## Recommendation

Adopt two small native mechanisms without importing branded vocabulary:

1. For nontrivial work, keep the desired outcome and current limiting condition visible, compare
   actual with expected state after material actions, and revise the next action when evidence
   differs.
2. Before an already-authorized consequential ship stage, identify at most three credible failure
   modes and add proportionate prevention, detection, verification, or rollback.

Preserve explicit non-triggers for simple answers and known single-step reversible work. Do not add
artifact types or mandatory template fields. The durable decision is
`work/decisions/decision-human-planning-mechanisms-for-tool-shed.md`.

## Follow-Up

- [x] Inventory authoritative descriptions of the candidate models.
- [x] Translate each model into mechanisms, assumptions, and target failure modes.
- [x] Map current Tool Shed coverage and eliminate duplicates.
- [x] Freeze scenario fixtures, expected behaviors, and the scoring rubric.
- [x] Run workspace preflight before generating evaluation evidence.
- [x] Capture instruction-level baseline results.
- [x] Run isolated mechanism walkthroughs.
- [x] Decide that a combined-treatment pilot is unnecessary for this bounded release.
- [x] Score benefits, regressions, variance limitations, and process cost.
- [x] Create the comparison decision matrix and update recommendations.
- [x] Set this spike's disposition and link the implementation workpackage.

When the spike finishes, set `Disposition:` to `planned`, `documented`, `no-action`, or
`superseded`. A `planned` disposition must name the follow-up `work/*.md` artifact in `Produces:`.
