# Tool Shed provider portability qualification

Date: 2026-08-09
Target: canonical Tool Shed development workspace
Scope: discussion route, minimum sufficient coordination, progressive skill loading, and native provider adapters

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
| All three on-demand references combined | 182 | 8,595 |
| New complete skill bundle | 314 | 15,724 |

The default skill body is 15,244 bytes smaller, about a 68% reduction. The complete bundle is also
smaller, and a request loads only its applicable route reference.

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
- 66 unit tests passed.
- Only `codex-cli 0.144.6` was found among the provider CLIs checked on this host.
- Full `scripts/validate_tool_shed.py` passed with the `0.12.0` unpublished manifest and 53
  manifest-tracked product files.

## Remaining Release Evidence

- Release provenance and live canonical-manifest verification after external publication approval.
- Installed Codex skill exact-diff and fresh-task verification after the live release is verified.
