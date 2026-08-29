# Inventory: Human planning mechanisms for Tool Shed

Status: complete
Type: inventory
Updated: 2026-08-09
Next Action: none
Parent: work/spikes/spike-evaluate-human-planning-models-for-tool-shed.md

## Scope

Human planning and self-management models that might transfer useful decision structure to Tool
Shed. The unit of analysis is the operational mechanism, not the branded methodology.

Source quality labels:

- `primary`: original paper, author material, or original briefing;
- `authoritative`: steward or professional-body description;
- `secondary`: used only for historical qualification, not adoption evidence.

## Items

| Model or practice | Source and quality | Transferable mechanism | Current Tool Shed coverage | Classification |
| --- | --- | --- | --- | --- |
| Getting Things Done | [Official five-step method](https://gettingthingsdone.com/what-is-gtd/) (`authoritative`) | capture, clarify outcomes and next actions, organize, review, engage | Strong: artifacts capture work; headers require outcome/next action; `work/index.*` organizes; `review_work_state.py` reconciles; campaign rules engage | `already covered` |
| Urgent/important matrix | [Historical description](https://www.eisenhowerlibrary.gov/research/online-documents) and later Covey-style matrix (`secondary`) | distinguish time pressure from outcome importance | Weak, but Tool Shed usually receives one scoped workspace outcome and lacks authority to infer owner-level importance | `defer` |
| OODA | [John Boyd, *The Essence of Winning and Losing*](https://www.coljohnboyd.com/static/documents/1995-06-28__Boyd_John_R__The_Essence_of_Winning_and_Losing__PPT-PDF.pdf) (`primary archive`) | re-observe the environment after action and reorient before continuing | Partial: tools provide observations and campaign rules react to contradictory evidence, but no compact always-visible execution loop says to compare result with expected state | `shortlist` |
| PDCA/PDSA | [ASQ PDCA procedure](https://asq.org/quality-resources/pdca-cycle) (`authoritative`) | make a small change, inspect evidence, incorporate learning, repeat | Strong in `ts:ship`, validation, and verification; the post-action evidence comparison can reinforce the OODA gap | `already covered`; merge useful remainder |
| Theory of Constraints | [TOCICO five focusing steps](https://www.tocico.org/resource/collection/B6E9C93D-AFC5-407E-9D8B-AD70D0AEAFE0/Ferguson%2C_Lisa_TOCICO_FM_Basics_Ferguson_Lenhartz_EN_130507%28FINAL%29.pdf) (`authoritative`) | identify the condition currently limiting progress and subordinate distractions | Partial: next actions and dependencies exist, but long campaigns do not explicitly re-check the current limiting condition | `shortlist` as one execution-loop question |
| Cynefin | [Cynefin framework overview](https://thecynefin.co/about-us/about-cynefin-framework/) and [domain responses](https://thecynefin.co/effective-decision-making-support-tool/) (`authoritative`) | match response mode to clear, complicated, complex, or chaotic context | Strong: checklist/runbook for known work, spike for uncertainty, deep research for cross-layer ambiguity, incident/containment for break-fix | `already covered` |
| Project premortem | [Gary Klein, *Performing a Project Premortem*](https://doi.org/10.1109/EMR.2008.4534313) (`primary`) | assume a consequential plan failed, identify credible causes, add prevention/detection | Partial: approval and rollback rules address known risk but do not require a prospective failure scan before consequential multi-stage work | `shortlist` with a narrow trigger |
| Implementation intentions | [Gollwitzer, 1999](https://www.socmot.uni-konstanz.de/publications/implementation-intentions-strong-effects-simple-plans) (`primary`) | bind a specific situational cue to a response using an if-then rule | Strong: request prefixes, artifact triggers, deep-research triggers, evidence mitigations, and approval boundaries are explicit condition-action rules | `already covered` |
| WOOP / MCII | [Official WOOP practice](https://woopmylife.org/en/practice) and [MCII meta-analysis](https://pmc.ncbi.nlm.nih.gov/articles/PMC8149892/) (`authoritative`, `research synthesis`) | contrast desired outcome with the central obstacle, then form an if-then plan | The obstacle maps to the limiting condition; the plan maps to existing trigger rules. Wish/outcome imagery and motivation assumptions do not transfer | `low transfer` as a separate method |
| Weekly review | [Official GTD review material](https://gettingthingsdone.com/2025/06/weekly-review-best-practices/) (`authoritative`) | periodically reconcile commitments, stale state, and priorities | Strong: `review_work_state.py`, stale-path checks, work index refresh, and explicit weekly backstop | `already covered` |

## Agent-Specific Corroboration

Human-origin evidence does not establish that the same mechanism improves an AI agent. The transfer
case is therefore limited to mechanisms that also match observed agent architecture:

- [ReAct](https://react-lm.github.io/) interleaves reasoning and environmental actions so new
  observations can update plans and handle exceptions.
- [Reflexion](https://papers.nips.cc/paper_files/paper/2023/hash/1b44b878bb782e6954cd888628510e90-Abstract-Conference.html)
  reports improved task performance when language agents incorporate feedback from prior trials.
- The recent [Agent Planning Benchmark](https://arxiv.org/abs/2606.04874) reports planning gaps in
  long-horizon tasks, tool-noise robustness, infeasibility recognition, and feedback-conditioned
  planning. It is recent preprint evidence and is treated as corroboration, not a release gate.

## Recommendations

- Do not import branded methodologies into the operator vocabulary.
- Evaluate two native mechanisms: an evidence-response loop for nontrivial execution and a
  prospective failure check for consequential work.
- Include a `current limiting condition` question inside the loop rather than adding a separate TOC
  artifact or field.
- Preserve the existing Tool Shed mechanisms for next action, artifact selection, trigger rules,
  and reconciliation; document their conceptual overlap instead of duplicating them.
- Defer urgency/importance prioritization until Tool Shed has an authorized source of relative
  owner priorities. Do not let a workspace agent invent importance.

## Verification

- Each candidate has at least one source, a mechanism, current-state mapping, and classification.
- Branded overlap is consolidated into native mechanisms.
- Shortlisted mechanisms have scenario-level evaluations in
  `work/evidence/evidence-human-planning-mechanism-evaluation.md`.
