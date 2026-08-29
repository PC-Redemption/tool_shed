# Evidence: Tool Shed v0.29.8 release and maintainer-skill synchronization

Status: complete
Type: evidence
Updated: 2026-08-26
Next Action: complete Campaign 067 and derive the M8 Core snapshot campaign without upgrading Core
Campaign: publish-and-synchronize-bounded-app-server-release

## Verified release

- Version: `0.29.8`.
- Content commit: `038e2f4c624b1795932a30892edb12bd325c1bd9`.
- Provenance commit: `b2f59550fe63d4f59685792b36cfaa3cf118e1b3`.
- Annotated tag: `v0.29.8`.
- Released at: `2026-08-26T10:17:23Z`.
- GitHub Release: `https://github.com/PC-Redemption/tool_shed/releases/tag/v0.29.8`.
- Release workflow: `https://github.com/PC-Redemption/tool_shed/actions/runs/32957593636`, completed
  successfully against the provenance commit.
- Local and canonical version checks both reported verified Tool Shed `0.29.8`; the GitHub Release
  is non-draft, non-prerelease, and the latest release.
- The full validator passed before the content commit and again after provenance was populated, as
  required by the two-commit release procedure.

## Installed maintainer skill

- Released source: `/home/jon/docker/tool_shed/skills/tool-shed`.
- Installed target: `/home/jon/.codex/skills/tool-shed`.
- Rollback backup: `/home/jon/.codex/skills/tool-shed.backup-20260826T102132Z`.
- The source, backup, staged copy, and installed target passed `quick_validate.py` where
  applicable.
- The reviewed pre-deployment drift was exactly
  `references/campaign-routes.md`; the final recursive diff was empty.
- Released and installed tree SHA-256:
  `e91b452355f48a6fbdc34c0382bbc2f5ae0cd8abc31e73d2cd3325216333635e`.
- Backup tree SHA-256:
  `b361125afd15dd17ebda774fb8b80d4684940bb03057ea4957ff6cdd91f612d7`.
- The replaced transient installed directory was moved to recoverable trash only after the
  validated backup existed and exact installed parity passed.

## Fresh-session policy smoke

A fresh ephemeral, read-only Codex task used `gpt-5.6-luna` with low reasoning and invoked
`ts: version`. It loaded the released Tool Shed version route, reported local Tool Shed `0.29.8`
with verified integrity, and returned `Campaign status: COMPLETE`. The task completed in 24.7
seconds using 20,082 input tokens. It was explicitly forbidden to edit, browse, publish,
synchronize, or run a campaign and did not wrap App Server campaign execution.

## Result

G7-CORRECTIVE-RELEASE-USABLE passes. The bounded live App Server CAMP contract is publicly
released and available to fresh maintainer sessions. Bactron Core was not upgraded and no
application was deployed.
