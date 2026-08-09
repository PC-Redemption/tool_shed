# Tool Shed provider portability qualification

Date: 2026-08-09
Target: canonical Tool Shed development workspace
Scope: discussion route, minimum sufficient coordination, progressive skill loading, native provider adapters, and existing-snapshot upgrades

## Outcome

Passed for the implemented static contract. Codex remains the locally available end-to-end
reference provider. Claude Code, Gemini CLI, GitHub Copilot, and Cursor are qualified only through
Level 2 static packaging and planning behavior until representative scenarios run in those actual
provider surfaces.

## Provider Matrix

| Provider | Native instruction path | Qualified level | Result |
| --- | --- | --- | --- |
| OpenAI Codex | `AGENTS.md` | 5: Delivery | adapter conformance passed; local CLI available |
| Anthropic Claude Code | `CLAUDE.md` | 2: Planning | static adapter conformance passed; runtime unavailable on this host |
| Google Gemini CLI | `GEMINI.md` | 2: Planning | static adapter conformance passed; runtime unavailable on this host |
| GitHub Copilot | `.github/copilot-instructions.md` | 2: Planning | static adapter conformance passed; runtime unavailable on this host |
| Cursor | `.cursor/rules/tool-shed.mdc` | 2: Planning | static adapter conformance passed; runtime unavailable on this host |

Static conformance verifies native path creation, preservation of owner content, idempotent
reinstallation, portable routing, discussion behavior, and minimum-coordination guidance.

## Progressive Loading Measurement

| Surface | Lines | Bytes |
| --- | ---: | ---: |
| Previous always-loaded `SKILL.md` | 418 | 22,373 |
| New portable always-loaded `SKILL.md` | 132 | 7,129 |
| All three on-demand references combined | 188 | 9,166 |
| New complete skill bundle | 320 | 16,295 |

The default skill body is 15,244 bytes smaller, about a 68% reduction. The complete bundle is also
smaller, and a request loads only its applicable route reference.

## Existing Installation Upgrade Qualification

The release updater was evaluated against a synthetic older installation whose always-loaded skill
was 400 lines and whose skill directory contained a stale Markdown reference. The candidate release
was built with real provider metadata, installer code, compact skill, and on-demand references.

| Upgrade property | Qualification result |
| --- | --- |
| Compact Markdown replacement | entire `tool_shed/` snapshot replaced; candidate skill directory matched the release byte-for-byte |
| Removed Markdown | stale old reference absent after success and present in the verified backup |
| Provider guidance | existing marked adapter auto-detected; owner prefix preserved; every managed block installed exactly once |
| Project state | root `work/`, indexes, Q&A inbox, and `.gitignore` unchanged by guidance-only refresh |
| Failed update | old snapshot and selected provider instruction files restored byte-for-byte |
| Unsafe targets | symlinked provider instruction targets rejected before snapshot mutation |
| Bootstrap | documentation requires a current released updater outside the project, so older snapshots receive current safeguards |

The updater now verifies exact pre-update snapshot fingerprints after rollback and verifies every
captured provider instruction file after restoration. It attempts snapshot and instruction
rollback independently so one reported rollback error does not prevent the other recovery step.
An end-to-end disposable workspace then upgraded the actual tagged `v0.11.0` snapshot to the local
tagged `v0.12.0` candidate and repeated the run with injected post-install failure. Success and
rollback both passed; the installed skill directory matched the candidate exactly, the old snapshot
and instruction file matched their pre-update fingerprints after rollback, and `work/` plus
`.gitignore` remained byte-identical. Backup restoration explicitly accepts only regular files and
directories and supplies an extraction policy on Python runtimes that support it.

## Commands

```text
python3 -m py_compile scripts/*.py tests/*.py
python3 scripts/check_provider_adapters.py --json
python3 /home/jon/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/tool-shed
python3 -m unittest discover -s tests -v
```

## Results

- Python compilation passed.
- Portable skill validation passed.
- Five provider adapter fixtures passed static conformance.
- 71 unit tests passed, including five upgrade-specific success, preservation, rollback, and path-safety scenarios.
- Only `codex-cli 0.144.6` was found among the provider CLIs checked on this host.
- Full `scripts/validate_tool_shed.py` passed with the `0.12.0` unpublished manifest and 53
  manifest-tracked product files.

## Remaining Release Evidence

- Release provenance and live canonical-manifest verification after external publication approval.
- Installed Codex skill exact-diff and fresh-task verification after the live release is verified.
