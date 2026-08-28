# Publish compact end-to-end Tool Shed workflow guide

Status: complete
Type: campaign
Updated: 2026-08-17
Next Action: none
Campaign ID: compact-tool-shed-site-and-publish-guided-workflows
Campaign Number: 024
Outcome: Restructure ts.rookaro.com into a compact operator guide with distinct new-project and existing-project entry paths that join a shared Project Map to Program Roadmap to campaign generation to queue selection to work1-work5 execution to completion-and-review workflow; compact spacing across the entire site; replace the large /ref command tiles with a dense accessible row-and-column table generated from the canonical command catalog; and preserve direct-loadable paths, mobile usability, and clear links among Guide, Help, and Reference.
Primary Focus Areas: provider-portability
Supporting Focus Areas: qualification-release
Depends On: none
Decision: none
Detour For: none
Return To: none
Completion Gate: Canonical source and the site generator produce the complete guided workflow hierarchy and compact site-wide layout; the Project Map, roadmap develop/propose/approve, campaign derive/approve, overview/next, work1-work5, completion, and roadmap-review boundaries are explicit; every workflow action presents an accurate selectable Tool Shed prompt with an accessible copy control and placeholder guidance so it can be pasted into Codex; /ref uses a compact accessible table rather than large tiles without duplicating docs/commands.md; focused documentation-site tests and the full Tool Shed validator pass; desktop and mobile layouts have no excessive section gaps or overflow; documentation and deployment instructions are current; and the exact generated candidate is deployed and verified on every public ts.rookaro.com route.
Completion Evidence: Frozen candidate 9a6988f generates 22 direct-loadable pages and 55 canonical reference commands; focused site tests and full Tool Shed validation (143 tests) passed; Playwright desktop/mobile checks found zero document overflow on every route and verified exact accessible clipboard behavior; all 22 public routes and assets returned 200 through X-Rookaro-Route ts.rookaro.com with hashes matching the candidate; GitHub issue #34 was updated with release-pending evidence. Historical claim audit: work/evidence/evidence-historical-campaign-external-claims-backfill.md
Completion Date: 2026-08-17
Completion Order: 22
Disposition: completed

## Request

Turn the existing public documentation into three clearly distinct operating surfaces:

- **Guide:** ordered instructions an operator can follow from entry through review.
- **Help:** explanations of individual Tool Shed facets and concepts.
- **Reference:** a dense command lookup generated from `docs/commands.md`.

Add this compact guided hierarchy:

```text
/guide/
├── new-project/
├── existing-project/
├── project-map/
├── roadmap/
├── generate-campaigns/
├── queue-and-select/
├── execute/
└── complete-and-review/
```

The new-project and existing-project paths must converge on one shared end-to-end workflow:

```text
Project Map
    ↓
ts: develop roadmap              read-only analysis
    ↓
ts: propose roadmap              creates an exact proposal
    ↓
ts: approve roadmap <token>      approves the strategic baseline
    ↓
ts: derive campaigns for milestone M1
                                 previews campaigns; no queue changes
    ↓
ts: approve campaign plan <token>
                                 creates the campaigns
    ↓
ts: overview                     confirms roadmap and queue state
    ↓
ts: next                         selects the first ready campaign
    ↓
ts:work1 … ts:work5              executes to the chosen endpoint
    ↓
Campaign completion
    ↓
ts: roadmap status / review roadmap
                                 rolls evidence into the roadmap
```

The guide must explicitly distinguish roadmap approval from campaign creation and campaign-plan
preview from materialization. It must also show the bounded-work shortcut from Project Map through
`ts: add`, `ts: next`, and the selected work level without making Program Roadmaps mandatory for
small work.

Every guide page should use one tight, predictable structure:

```text
Step N of M
Purpose
Required state
Command
What it reads
What it changes
Approval required
Success looks like
Previous ← → Next
```

Compact the entire site rather than limiting density improvements to the new guide. Reduce hero,
section, grid, sidebar, card, and footer whitespace; remove unnecessary minimum heights; keep
headings and navigation readable; and verify density at desktop and mobile widths. Prefer concise
rows and progressive detail over large decorative tiles.

Replace `/ref/` command cards with one or more semantic, accessible tables. Each command should be
one compact row with columns for command, purpose, example, and the applicable Guide or Help link.
Keep stable section anchors and direct command anchors where practical, wrap cleanly on narrow
screens, and continue generating the reference from the canonical `docs/commands.md` inventory.

### Copy-and-paste Tool Shed prompts

Every actionable workflow step must display the actual `ts:` prompt an operator can paste into
Codex. The visible command must be selectable without surrounding prose and have a nearby
keyboard-accessible **Copy** control that copies only that prompt. Announce copy success accessibly.
Placeholders such as `<token>`, `<goal>`, `<campaign-number-or-id>`, and `<project idea>` must remain
visually obvious and include a one-line instruction describing what value to substitute. Formal
routes must come from `docs/commands.md`; copy-ready natural-language requests must be clearly
identified and must follow Tool Shed's supported `ts:` routing rather than pretending to be new
rigid subcommands.

At minimum, place these copy-ready prompts on the applicable workflow pages:

**New project entry**

```text
ts: version
ts: discuss <project idea>
ts: map the active workstreams
```

**Existing project adoption**

```text
ts: fulltsupgrade
ts: version
ts: onboard this existing project
ts: build focus areas
ts: review work state
ts: reconcile campaigns
```

Explain that `ts: fulltsupgrade` applies to an existing managed installation; an absent Tool Shed
must first be installed through the documented installation route.

**Project Map and roadmap**

```text
ts: develop roadmap
ts: propose roadmap
ts: approve roadmap <token>
```

**Generate campaigns**

```text
ts: derive campaigns for milestone M1
ts: approve campaign plan <token>
```

**Bounded-work shortcut**

```text
ts: add <campaign outcome>
```

**Queue and selection**

```text
ts: overview
ts: status
ts: next
```

**Execution endpoints and validation**

```text
ts:work1 <goal>
ts:work2 <goal>
ts:work3 <scope>
ts:work4 <scope>
ts:work5 <scope>
ts:check focused
```

**Completion and roadmap feedback**

```text
ts: review the current campaign against its completion gate and complete it if verified
ts: roadmap status
ts: review roadmap
```

Reference-table command cells should use the same copy behavior. Regression tests must verify that
the copied string exactly matches the visible prompt, that copy controls are keyboard accessible,
and that adding copy behavior does not expose private paths or duplicate the canonical command
catalog.

Update the primary navigation and homepage entry actions so an operator can reach the Guide, Help,
and Reference directly. Link Reference commands back into the relevant workflow stage, and link
workflow stages to deeper Help only when additional explanation is useful.

Related GitHub work: issue #34 covers publishing work-level customization instructions in the
public command reference; satisfy or update that issue within this broader guided-site campaign.

## Completion Check

Canonical source and the site generator produce the complete guided workflow hierarchy and compact site-wide layout; the Project Map, roadmap develop/propose/approve, campaign derive/approve, overview/next, work1-work5, completion, and roadmap-review boundaries are explicit; every workflow action presents an accurate selectable Tool Shed prompt with an accessible copy control and placeholder guidance so it can be pasted into Codex; /ref uses a compact accessible table rather than large tiles without duplicating docs/commands.md; focused documentation-site tests and the full Tool Shed validator pass; desktop and mobile layouts have no excessive section gaps or overflow; documentation and deployment instructions are current; and the exact generated candidate is deployed and verified on every public ts.rookaro.com route.
