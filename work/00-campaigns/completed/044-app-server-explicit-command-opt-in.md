# Add explicit App Server command opt-in

Status: complete
Type: campaign
Updated: 2026-08-20
Next Action: none
Campaign ID: app-server-explicit-command-opt-in
Campaign Number: 044
Outcome: Let users explicitly select the already-qualified App Server path for planning, verification, and CAMP execution while keeping GUI execution and the global default unchanged.
Primary Focus Areas: provider-portability
Supporting Focus Areas: workspace-safety, campaign-lifecycle
Depends On: none
Decision: none
Detour For: none
Return To: none
Completion Gate: Documented ts: plan, verify, and camp run commands accept explicit App Server selection; GUI-native discussion and unqualified roles cannot be rerouted; compatibility, status, banner, override precedence, GUI fallback, global-default-off, no-API-fallback, and optimized CAMP reuse have regression coverage; session convenience is implemented only if reliable; focused tests and the full Tool Shed validator pass; release readiness is assessed without releasing, deploying, pushing, or changing global configuration.
Completion Evidence: Implementation commit 6b611c7; 29 focused tests and full 194-test Tool Shed validator passed; live Codex 0.144.6 status is qualified_with_blockers with planning Sol/high, verification Terra/low, and optimized CAMP Terra/medium; GUI default, GUI-native discussion, compatibility rejection, no API fallback, status banners, and global default OFF verified; session on/off deferred because reliable skill-owned session storage is unavailable and makes no persistent change; manifest, campaign, roadmap, stale-path, strict work-state, and generated-index checks passed; ready for the next release; no release, deploy, push, fleet update, or global configuration change performed. Historical claim audit: work/evidence/evidence-historical-campaign-external-claims-backfill.md
Completion Date: 2026-08-20
Completion Order: 40
Disposition: completed

## Request

Add a thin user-facing control for selecting the existing qualified Codex App Server execution
path without changing Tool Shed's safe GUI default or redesigning orchestration:

- support `ts: plan <request> --app-server` as planning on `gpt-5.6-sol` / high;
- support `ts: verify <request> --app-server` as verification on `gpt-5.6-terra` / low;
- support `ts: camp run <camp> --app-server` as the existing optimized CAMP execution on
  `gpt-5.6-terra` / medium;
- keep equivalent unflagged commands on the normal GUI path and keep `ts: discuss` GUI-native;
- provide concise execution banners and `ts: appserver status` using centralized role and
  compatibility policy;
- implement session-scoped `ts: appserver on|off` and an explicit GUI override only if current
  Codex/Tool Shed session semantics can do so reliably without persistent configuration;
- fail clearly on incompatible Codex or unqualified roles while preserving GUI fallback and
  prohibiting API fallback; and
- document exact syntax and the recommended post-release real-world test sequence.

Preserve ChatGPT-only authentication, workspace-write boundaries, disabled network, approval
policy `never`, Git mutation safety, no retry after mutation, and every existing CAMP optimization.
Do not enable new roles, add API or Luna routing, alter permissions, reopen watcher work, release,
deploy, push, or change `codex_app_server_enabled = false`.

## Completion Check

The command selector reuses centralized routing, qualification, compatibility, and CAMP execution;
tests prove default GUI behavior, explicit App Server routing and banners, exact role/model/effort,
discussion refusal, unqualified-role enforcement, incompatible-version handling, GUI fallback,
no API fallback, unchanged global default, session behavior or an evidence-backed deferral, and
optimized CAMP reuse. Focused tests and the full Tool Shed validator pass, documentation is
current, the unpublished manifest is internally consistent, and release readiness is reported
without publishing or external mutation.

## Request

Add detailed execution context here.

## Completion Check

Documented ts: plan, verify, and camp run commands accept explicit App Server selection; GUI-native discussion and unqualified roles cannot be rerouted; compatibility, status, banner, override precedence, GUI fallback, global-default-off, no-API-fallback, and optimized CAMP reuse have regression coverage; session convenience is implemented only if reliable; focused tests and the full Tool Shed validator pass; release readiness is assessed without releasing, deploying, pushing, or changing global configuration.
