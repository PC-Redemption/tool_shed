# Add program-roadmap lifecycle between project maps and campaign execution

Status: complete
Type: campaign
Updated: 2026-08-17
Next Action: none
Campaign ID: add-program-roadmap-lifecycle-between-project-maps-and-campaign-execution
Outcome: Deliver GitHub issue #33 by adding an opt-in, file-based Program Roadmap layer for both greenfield projects and existing or upgraded projects, including evidence-backed ingestion of existing work into approved roadmap state, milestone campaign manifests, and whole-project overview state without silently approving or starting work.
Primary Focus Areas: campaign-lifecycle
Supporting Focus Areas: artifact-workflows, provider-portability, qualification-release
Depends On: discover-focus-areas-and-render-readiness-cards
Decision: none
Detour For: none
Return To: none
Completion Gate: GitHub issue #33 acceptance criteria pass for both entry modes: an empty greenfield project can establish its initial map and roadmap, while an existing or upgraded project can preserve and ingest its populated work tree, classify completed, active, remaining, and uncertain work from evidence, and preview its roadmap mapping without inventing history; exact proposal approval, stale-input rejection, milestone and gate validation, campaign preview and approved materialization, progress rollup, overview and drift reporting, compatibility, documentation, greenfield and populated-work lifecycle tests, and full Tool Shed validation pass.
Completion Evidence: scripts/validate_tool_shed.py: 121 tests plus provider, installer, index, stale-path, work-state, roadmap validation, and temp-workspace smoke passed
Completion Date: 2026-08-17
Completion Order: 16
Disposition: completed

## Request

Deliver [GitHub issue #33](https://github.com/PC-Redemption/tool_shed/issues/33).

- Add an opt-in Program Roadmap artifact and validated lifecycle between project maps and campaigns.
- Keep roadmap development and campaign derivation read-only until separate exact approvals.
- Support stable milestones and gates, dependency-aware campaign manifests, stale-input rejection,
  revision history, campaign progress rollup, and a whole-project `ts: overview` route.

### Greenfield entry mode

- Support a brand-new project whose `work/` tree is empty or newly initialized.
- Establish and approve the initial project map before proposing the first Program Roadmap.
- Derive initial outcomes, phases, milestones, gates, decisions, unknowns, and candidate campaigns
  without prematurely materializing or starting campaign work.

### Existing-project and upgrade entry mode

- Preserve every owner-authored `work/` artifact and allow roadmap ingestion to be invoked during
  or after an upgrade without making installation itself silently rewrite project planning.
- Read canonical docs, the project map, focus areas, indexes, active/completed/deferred/abandoned
  campaigns, and all supported `work/**/*.md` artifacts as project evidence.
- Classify existing outcomes and artifacts as completed, active, remaining, superseded, excluded,
  or uncertain; require concrete evidence for completion and mark ambiguous history as uncertain.
- Produce a non-mutating, exact mapping preview showing how existing work rolls into roadmap
  phases, milestones, gates, decisions, dependencies, and candidate campaigns, including unmapped
  and conflicting work.
- Require a fresh source-state token and explicit owner approval before establishing the roadmap
  baseline or materializing new campaigns; preserve prior approved revisions when replanning.

### Compatibility and verification

- Preserve existing standalone maps and queues and support incremental, opt-in adoption.
- Remain file/script/Git-based and cover both an empty greenfield `work/` tree and representative
  populated current and legacy work trees in deterministic lifecycle, migration, drift, and
  end-to-end tests.

## Completion Check

GitHub issue #33 acceptance criteria pass for both entry modes: an empty greenfield project can establish its initial map and roadmap, while an existing or upgraded project can preserve and ingest its populated work tree, classify completed, active, remaining, and uncertain work from evidence, and preview its roadmap mapping without inventing history; exact proposal approval, stale-input rejection, milestone and gate validation, campaign preview and approved materialization, progress rollup, overview and drift reporting, compatibility, documentation, greenfield and populated-work lifecycle tests, and full Tool Shed validation pass.
