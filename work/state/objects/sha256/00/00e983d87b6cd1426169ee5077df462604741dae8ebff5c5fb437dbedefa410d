# Generated Evidence Safety and Migration Workpackage

Status: complete
Type: workpackage
Updated: 2026-07-25
Next Action: none

Project Map: work/maps/map-tool-shed-evolution.md

## Current Context

Feedback from the `7520553_SMI_FW` workspace records a Codex Desktop crash after
raw firmware evidence accumulated in tracked `work/evidence/` paths. The measured
fixture included 2,065 tracked files, about 190 MiB in the working tree, roughly
603 MiB of loose Git objects, 124 new untracked artifacts, and review responses
around 1.5 MiB.

Canonical Tool Shed already:

- reserves ignored `work/evidence/generated/` for raw payloads;
- preserves small Markdown and manifest evidence as versioned records;
- appends Tool Shed ignore rules without replacing existing `.gitignore` content;
- warns about excessive untracked count and bytes, binary files beneath versioned
  `work/`, oversized tracked diffs, and visible Tool Shed backup archives;
- documents that preflight is read-only.

The remaining gap is safe adoption across different repository shapes. A
firmware workspace, web application, data project, and documentation repository
do not produce the same evidence or tolerate the same volume. Tool Shed does not
yet derive a workspace profile, combine it with explicit local policy, or tailor
its warnings and migration candidates accordingly. There is also no prepare-only
migration command, verified candidate manifest, archive gate, or apply workflow.

## Recommendation

Deliver this as an adaptive safety pipeline with explicit gates:

1. discover the workspace's repository shape, declared policy, existing evidence
   conventions, and dirty state without mutation;
2. calculate an explainable risk budget using both general safety limits and the
   observed workspace profile;
3. detect and explain risks relative to that profile without allowing an already
   unsafe baseline to normalize the problem away;
4. prepare a workspace-specific inventory, classification, hashes, and archive;
5. require human review of the exact candidate manifest;
6. apply only approved current-snapshot changes;
7. verify retained evidence, dirty product work, Tool Shed state, and rollback
   material.

Keep Git-history rewriting outside this workpackage. Do not make preflight move,
delete, ignore, stage, or commit files. Do not use filename extension alone as
the final migration decision; allow durable evidence and deliberately curated
images to remain tracked. Local policy may refine classification and thresholds,
but may not silently disable hard safety limits; explicit exceptions must be
documented and surfaced in every result.

## Current State

Completed:

- The imported incident records measured failure conditions and recovery steps.
- `work/evidence/generated/` policy and ignore installation exist.
- Initial preflight warnings and configurable thresholds exist.
- Installer idempotency and basic preflight behavior have focused tests.
- The firmware incident provides one high-risk regression profile.

Incomplete:

- None within this workpackage. Git-history rewriting and the independent Codex
  Desktop robustness defect remain explicitly deferred.

## Goal

Make Tool Shed select proportionate mitigations from the workspace it is
installed in, prevent common repository triggers for oversized Codex review
state, and provide a reversible, human-approved cleanup path without losing
evidence or unrelated work.

## Why It Matters

The reported failure interrupted hardware qualification and made both the
original task and a history-preserving fork unsafe to open. Prevention must work
before a large campaign, while migration must remain conservative enough for
repositories containing irreplaceable captures and dirty source changes.

## Major Outcomes

- Preflight emits an explainable workspace profile and identifies which local
  policy, observed baseline, relative-growth rule, or hard safety limit produced
  each finding.
- Mitigations scale from guidance only, to stricter preflight, to prepare-only
  migration, to human-gated cleanup according to measured risk.
- Existing unsafe evidence layouts can be prepared for migration without Git or
  filesystem mutation.
- Apply is impossible without a verified archive and an exact approved manifest.
- Retained evidence and unrelated dirty work are proven unchanged.
- Installer, migration, and verification behavior is cross-platform and
  idempotent.
- Operator and Codex guidance clearly separates generated evidence, durable
  records, local ignores, current-snapshot cleanup, and history rewriting.

## Delivery Stages

| Stage | Outcome | Entry Evidence | Exit Evidence |
| --- | --- | --- | --- |
| 1. Profile | Workspace shape and policy are discovered without mutation | Representative workspace profiles and imported incident | Stable profile schema identifies repository scale, evidence conventions, dirty state, and policy sources |
| 2. Budget | General hard limits and workspace-relative signals produce explainable risk levels | Profile schema and agreed safety invariants | Tests prove unsafe baselines cannot suppress warnings and local exceptions remain visible |
| 3. Detect | Preflight reports actionable tracked and untracked risk | Profile and risk-budget contracts | Focused tests pass across firmware, application, data, media, and documentation profiles |
| 4. Prepare | Read-only migration preparation emits workspace-specific classification, hashes, and archive evidence | Detection output and retention policy | Repeated preparation is deterministic and performs no Git mutation |
| 5. Apply | Exact approved candidates move to the workspace's generated boundary or leave the current snapshot | Verified archive and candidate manifest | Only approved paths change; retained and dirty files match pre-apply hashes |
| 6. Integrate | Installer and guidance route users through proportionate prevention and recovery | Proven prepare/apply workflow | Cross-platform edge cases, idempotency, repository validation, and work-state checks pass |
| 7. Field verify | Safeguards are exercised in varied disposable workspaces | All automated gates green | Evidence report maps every ticket criterion to multiple workspace profiles |

## Related Artifacts

- Tickets: `work/tickets/ticket-field-verify-generated-evidence-safeguards.md`
- Checklists:
- Spikes:
- ADRs:
- Runbooks:
- Inventories:
- Decision matrices:
- Incident: `work/incidents/incident-codex-desktop-crash-from-tracked-raw-evidence.md`

## Rough Sequence

1. Define a versioned workspace-profile schema and precedence rules for explicit
   local policy, discovered conventions, relative-growth signals, and hard safety
   limits.
2. Build compact fixtures for firmware, application logs, data/science outputs,
   media-heavy validation, and documentation-first repositories; retain the
   reported incident as one regression profile.
3. Define risk levels and proportionate mitigations before changing migration
   behavior.
4. Extend preflight metrics and finding codes to explain every conclusion.
5. Define a versioned candidate-manifest schema with keep, migrate, and review
   classifications plus hashes and reasons.
6. Implement prepare-only inventory and archive verification.
7. Add an apply mode gated by the verified archive and exact manifest.
8. Add post-apply integrity, Tool Shed index, stale-path, and work-state checks.
9. Update operator, installer, and Codex-facing guidance.
10. Run all disposable workspace profiles and record criterion-by-criterion
    evidence.

## Milestones

### Milestone 1: Workspace profile and adaptive risk contract

Completion criteria:

- [x] Profile records repository scale, tracked and untracked evidence, dominant
  types, large files, dirty state, ignore sources, existing generated paths, and
  explicit Tool Shed policy.
- [x] Risk calculation combines hard safety limits, relative growth, repository
  composition, and declared policy with documented precedence.
- [x] An already unsafe workspace baseline cannot make equivalent new risk pass.
- [x] Local overrides require a reason, are included in JSON and human output,
  and cannot silently disable non-overridable safety gates.
- [x] Mitigation levels distinguish guidance, warning, strict failure,
  prepare-only migration, and human-gated apply eligibility.
- [x] Fixtures cover firmware, application, data, media, and documentation
  workspace profiles without retaining bulk payloads.
- [x] The exact firmware measurements and extensions remain a regression case,
  not global defaults.
- [x] Preflight JSON distinguishes tracked evidence, untracked evidence, total
  bytes, large individual files, raw/binary candidates, and tracked diff size.
- [x] Finding codes and configurable thresholds are documented and tested.

### Milestone 2: Reversible preparation

Completion criteria:

- [x] Prepare mode performs no Git index, working-file, ignore, or history
  mutation.
- [x] Candidate manifest records normalized path, classification, size, SHA-256,
  reason, tracked state, intended action, and the workspace policy or heuristic
  that selected it.
- [x] Preparation creates or verifies a recoverable archive outside the mutation
  target.
- [x] A second run produces equivalent classifications and hashes.

### Milestone 3: Guarded current-snapshot cleanup

Completion criteria:

- [x] Apply refuses missing, stale, edited, or unverified manifests and archives.
- [x] Apply changes only explicitly approved migrate candidates.
- [x] Apply uses the generated-evidence destination declared or discovered for
  that workspace, falling back to `work/evidence/generated/`.
- [x] Dirty source, build, script, `.gitignore`, `AGENTS.md`, and retained
  evidence remain byte-identical.
- [x] Current-snapshot cleanup is clearly separated from optional future
  Git-history rewriting.
- [x] Recovery instructions are tested against the prepared archive.

### Milestone 4: Integration and field verification

Completion criteria:

- [x] Installer remains idempotent and preserves existing policy files.
- [x] Windows paths, spaces, mixed-case extensions, non-firmware file families,
  custom evidence paths, and unrelated dirty changes pass focused tests.
- [x] Tool Shed validation, work index, stale-path, and work-state checks pass.
- [x] Operator guidance recommends preflight before large campaigns and a blank
  handoff after exceptionally renderer-heavy campaigns.
- [x] A versioned evidence report maps all acceptance criteria in the related
  ticket to commands, outcomes, and results across multiple workspace profiles.

## Open Questions

- Should apply move approved files into `work/evidence/generated/`, remove them
  only from the Git index while leaving them in place, or support both explicit
  modes?
- Which file types should be high-confidence generated candidates versus
  mandatory review candidates?
- Should the verified archive be mandatory for all apply operations or only when
  tracked files leave the current snapshot?
- Should preflight remain warning-only by default in every entry point, with
  strict behavior reserved for explicit CI use?
- Which safety limits are non-overridable, and which may be adjusted by explicit
  workspace policy?
- Should relative growth compare against a versioned workspace baseline, recent
  Git history, the current clean tree, or a combination?
- What fixture scaling technique best exercises varied Git path-count and byte
  behavior without storing large test corpora?

## Completion Standard

This workpackage is complete when Tool Shed derives explainable, proportionate
mitigations from varied workspace profiles; the incident-derived ticket is
satisfied by automated tests and disposable field verification; migration is
reversible and human-gated; retained evidence and unrelated dirty work are proven
unchanged; and the durable operating policy is published in canonical docs.

## Closeout Routing

- Current truth promoted to: `README.md`, `conventions.md`,
  `docs/operator-guide.md`, and migration documentation
- Historical context remains in:
  `work/incidents/incident-codex-desktop-crash-from-tracked-raw-evidence.md` and
  this completed workpackage
- Runtime/status evidence: compact manifests and Markdown results under
  `work/evidence/`, with raw fixture output under
  `work/evidence/generated/`
- Cleanup deferred to: any Git-history rewrite and the external Codex Desktop
  robustness defect
