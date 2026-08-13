# Ticket: Mitigate Tool Shed churn for Direct coding requests

Status: complete
Type: ticket
Updated: 2026-08-13
Next Action: none
Parent: work/maps/map-tool-shed-evolution.md
Source: https://github.com/PC-Redemption/tool_shed/issues/21

## Problem

Tool Shed describes Direct coordination, but its campaign, `ts:ask`, and `ts:ship` guidance can
still cause a bounded coding request to expand into artifact creation, repeated orientation,
full-suite qualification, deployment, publication, or historical-worktree review without concrete
risk or repository policy requiring those steps. The conflict is especially visible between
minimum-sufficient coordination and the broad lifecycle language installed into provider
instruction files.

## Expected Behavior

A clear, reversible, single-repository coding change should select Direct coordination regardless
of whether it arrives as an ordinary request or through `ts:ask`. The agent should orient once,
make the focused change, and run proportionate focused verification. It should escalate only when
explicit operator scope, repository policy, consequence, ambiguity, conflicting evidence, or an
observed failure justifies broader coordination or validation.

`ts:ship` remains an end-to-end authorization route, but "applicable lifecycle stage" must not be
interpreted as automatic artifact creation, PR publication, deployment, or full-suite validation
when those stages do not apply to the requested outcome or target repository.

## Implementation Plan

1. Define one portable Direct-route contract in `skills/tool-shed/SKILL.md`:
   - make Direct the default for bounded bug fixes and enhancements;
   - add an orient-once and focused-tests-first rule;
   - prohibit artifacts and lifecycle expansion unless explicitly requested, mandated, or
     evidence-justified;
   - state concrete escalation triggers and preserve campaign continuity without coordination
     escalation.
2. Align `skills/tool-shed/references/campaign-routes.md`:
   - make `ts:ask` dispatch the selected request under its natural coordination level;
   - clarify that campaign continuity advances the requested outcome but does not upgrade Direct;
   - constrain `ts:ship` to applicable stages and require a stated reason for broader validation,
     deployment, or publication.
3. Update `scripts/install_into_workspace.py` so managed coordination, ship, campaign, and Q&A
   blocks install the same contract across provider adapters without overwriting owner guidance.
4. Document low-churn examples in `docs/operator-guide.md` and `README.md`: one Direct web bug fix
   and one contrasting coordinated qualification campaign.
5. Add regression coverage in `tests/test_scripts.py` and `scripts/validate_tool_shed.py` for:
   - ordinary Direct prompts;
   - a `ts:ask` fixture containing a bounded web bug;
   - `ts:ship`-adjacent wording that preserves Direct unless end-to-end delivery is explicit;
   - provider installation and snapshot-update idempotence for the new managed guidance.
6. Run focused installer/routing tests first, then the repository validator because portable skill
   and generated guidance are release surfaces.

## Scope Boundaries

- Do not add a runtime router, server, database, or persistent coordination-state format.
- Do not create artifacts automatically for Direct requests; an explicit `Coordination: direct`
  or `Route: direct` marker may be accepted as an override, but correctness must not depend on it.
- Do not change protected-environment, destructive-action, credential, or explicit approval rules.
- Do not publish a release, update installed clients, or perform fleet snapshot updates as part of
  this ticket unless separately authorized.

## Acceptance Criteria

- [x] A bounded bug-fix fixture selects Direct through an ordinary prompt and through `ts:ask`
  without creating a ticket, workpackage, map, ADR, evidence artifact, PR, or worktree.
- [x] Direct guidance requires one target-repository orientation pass, focused implementation, and
  focused tests before any broader survey or validation.
- [x] Full-suite validation, deployment, and external publication occur only when explicitly
  requested, mandated by repository policy, or justified by concrete observed risk or failure.
- [x] Campaign continuity explicitly preserves forward progress without upgrading Direct to Guided,
  Coordinated, or Deep.
- [x] `ts:ship` distinguishes explicitly requested end-to-end delivery from adjacent wording and
  treats inapplicable lifecycle stages as inapplicable.
- [x] Portable skill text, generated provider guidance, README, and operator guide describe the
  same Direct-route contract and escalation triggers.
- [x] Installer and snapshot tests prove managed-block idempotence and owner-guidance preservation.
- [x] Focused routing/installer tests and `python3 scripts/validate_tool_shed.py` pass.

## Verification

Run the smallest relevant `unittest` cases for installer, inbox, and snapshot routing while
developing. Then run:

```bash
python3 -m unittest tests.test_scripts
python3 scripts/validate_tool_shed.py
```

Review the installed guidance in disposable Codex and at least one non-Codex provider fixture.
The fixture must demonstrate that Direct remains artifact-free and focused-tests-first; text
presence alone is insufficient.

Verified 2026-08-13 with four frozen routing scenarios, disposable installs for all five provider
adapters, a non-mutating `ts:ask` fixture, 91 passing unit tests, and the full repository validator.
Live installed-client behavior remains a release/deployment verification step rather than an
implementation acceptance criterion.

## Risks And Controls

- Risk: weakening `ts:ship` breaks legitimate delivery campaigns. Control: preserve explicit
  end-to-end authorization and test both explicit ship and ship-adjacent cases.
- Risk: duplicated guidance drifts across skill, installer, and docs. Control: make validator
  assertions cover shared contract phrases on every generated provider surface.
- Risk: prompt-only tests prove wording but not behavior. Control: add disposable scenario fixtures
  that assert prohibited Direct-route side effects are absent.
