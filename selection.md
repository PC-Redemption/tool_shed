# Artifact Selection

Choose the artifact by the kind of thinking the work needs, not by how important the work feels.

## Decision Tree

Use a checklist when:

- the work is bounded
- the steps are known
- it should complete in one session
- forgetting a step is the main risk

Use a ticket when:

- there is a specific bug or enhancement
- expected behavior is clear
- acceptance criteria fit in a few bullets

Use a project map when:

- the project has multiple workstreams or moving parts
- a visual thinker needs to move between 30,000 ft and ground level
- dependencies, active areas, and next actions need one navigation surface
- several workpackages, tickets, decisions, or checklists must stay coordinated

Use a workpackage when:

- the work is a multi-step transformation
- current state and desired state both matter
- decisions, risks, and sequencing need to survive chat handoff
- future continuation cost is high

Use an ADR when:

- a decision may be relitigated
- there were real alternatives
- consequences matter later

Use a runbook when:

- an operation must be repeated safely
- commands and order matter
- recovery guidance matters

Use an incident note when:

- something broke
- impact, cause, recovery, and prevention should be preserved

Use a spike when:

- the outcome is uncertain
- exploration should be time-boxed
- the deliverable is learning, not production change

Use an inventory when:

- the work is classify, keep, move, delete, own, or route
- the main need is a complete list plus decisions

Use a decision matrix when:

- there are two to five plausible options
- tradeoffs need to be visible
- the chosen path should be explainable later

## Fast Rule

- Checklist for bounded execution.
- Ticket for specific behavior change.
- Project map for visual coordination across moving parts.
- Workpackage for ambiguous transformations.
- ADR for durable decisions.
- Runbook for repeatable operations.
- Incident for break/fix learning.
- Spike for uncertainty.
- Inventory for classification.
- Decision matrix for tradeoffs.

## Project Map Trigger

Create or recommend a project map when any of these are true:

- the project has two or more active workpackages
- the work spans three or more artifact types
- dependencies or sequencing affect what should happen next
- the user needs to see the whole project or move from big picture to ground tasks
- `tool_shed` is being loaded into an existing project and Codex needs to learn/backfill the work

Do not create a project map for a single linear task, a small isolated ticket, or a checklist-sized cleanup unless the human asks for a visual map.

When loading `tool_shed` into an existing project, default to Level 2 backfill: create a project map, then create an inventory of existing docs/code/work surfaces before deciding whether to backfill detailed work artifacts.

Use `existing-projects.md` for the Level 2 onboarding runbook. Use `existing-project-inventory` when creating the inventory artifact.

## Composition Rule

Use the smallest artifact that fits the immediate work, then connect it to nearby artifacts with plain Markdown links.

- Project maps coordinate multiple workstreams and show the current ground task.
- Workpackages deliver larger slices and may reference tickets, checklists, spikes, ADRs, runbooks, inventories, and decision matrices.
- Tickets define specific behavior changes inside or near a workpackage.
- Checklists carry bounded known steps, including task lists extracted from a workpackage.
- Spikes answer uncertainty before implementation work expands.
- ADRs preserve decisions that should survive beyond the current chat.
- Runbooks preserve repeatable procedures discovered during the work.
- Inventories and decision matrices support classification and tradeoff work.

Do not force every detail into the top-level artifact. The coordinating artifact should point to the right tool for each kind of thinking.

## Anti-Patterns

- Do not make a workpackage for a small cleanup unless handoff and sequencing are real risks.
- Do not make a project map for a single linear task.
- Do not bury settled truth in completed workpackages; promote it to `docs/`.
- Do not put active project artifacts inside `tool_shed/`.
- Do not create a server for `tool_shed` until plain files and scripts fail.
