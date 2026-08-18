# Extend ts: next with targeted and wildcard batch execution

Status: complete
Type: campaign
Updated: 2026-08-18
Next Action: none
Campaign ID: extend-next-with-targeted-and-wildcard-batches
Campaign Number: 028
Outcome: Allow ts: next to execute an explicit ordered batch selected by queue positions or stable campaign references, preserve ts: next 1,2 as a supported shorthand, and accept ts: next * to sequentially drain the active queue snapshot without weakening completion gates, dependency readiness, stale-state protection, stop conditions, or authority boundaries.
Primary Focus Areas: campaign-lifecycle
Supporting Focus Areas: provider-portability, qualification-release
Depends On: none
Decision: none
Detour For: none
Return To: none
Completion Gate: The portable route and deterministic queue tooling define and implement single-target, comma-separated queue-position, comma-separated campaign-number-or-ID, and wildcard selection; all selections resolve from one fresh validated queue snapshot to stable campaign IDs; execution remains sequential with at most one working campaign; each campaign must pass its own completion gate before the batch advances; dependencies and readiness are recomputed after every transition; the batch stops with a precise resumable result on failure, blocker, decision, stale state, protected action, missing authority, or an unsatisfied dependency; wildcard selection excludes campaigns added after invocation; ts: next retains existing one-campaign behavior; ts: next 1,2 remains a documented compatibility shorthand; no batch implicitly authorizes work5, release, deployment, or other consequential external action; operator docs, command/help surfaces, provider guidance, and focused regression tests are aligned; and the full Tool Shed validator passes.
Completion Evidence: Full validator passed 147 tests plus manifest, provider, index, stale-path, work-state, roadmap, and smoke validation; targeted batch and docs-site checks passed.
Completion Date: 2026-08-18
Completion Order: 24
Disposition: completed

## Request

Extend the owner-facing `ts: next` route without changing its safe single-campaign default.
Support these operator forms:

- `ts: next` — select or resume one campaign using existing readiness behavior;
- `ts: next 1,2` and `ts: next que 1,2` — execute the campaigns occupying those queue positions
  in the fresh invocation snapshot;
- `ts: next camp 025,example-campaign-id` — execute explicit stable campaign numbers or full IDs;
- `ts: next *` — execute every campaign present in the validated active-queue snapshot.

Resolve every requested position or reference before execution begins, reject duplicates and
missing or ambiguous targets, and retain the resolved stable campaign IDs even as completion
changes queue positions. Never add campaigns created later to an in-flight wildcard batch.

Run targets sequentially. Resume a targeted working campaign first; otherwise start only a ready
target. After each campaign passes its completion gate, complete it through the guarded lifecycle
command, refresh indexes, validate campaign state, check stale paths, review work state, and
recompute readiness before advancing. Stop with a precise completed/remaining/result summary if a
target fails, blocks, needs a decision, becomes stale, has an unsatisfied dependency, or reaches an
authority boundary. Preserve the remaining targets for an explicit resume instead of skipping or
silently reordering them.

Batch selection is execution scope, not expanded authority. A selected campaign still uses its own
coordination and requested work level, and `ts: next *` must not itself authorize deployment,
release, production promotion, destructive work, credentials, or another consequential external
action. Update portable and generated provider guidance, operator help, command documentation, and
regression coverage so the syntax and stop/resume behavior are consistent across installations.

## Completion Check

The portable route and deterministic queue tooling define and implement single-target, comma-separated queue-position, comma-separated campaign-number-or-ID, and wildcard selection; all selections resolve from one fresh validated queue snapshot to stable campaign IDs; execution remains sequential with at most one working campaign; each campaign must pass its own completion gate before the batch advances; dependencies and readiness are recomputed after every transition; the batch stops with a precise resumable result on failure, blocker, decision, stale state, protected action, missing authority, or an unsatisfied dependency; wildcard selection excludes campaigns added after invocation; ts: next retains existing one-campaign behavior; ts: next 1,2 remains a documented compatibility shorthand; no batch implicitly authorizes work5, release, deployment, or other consequential external action; operator docs, command/help surfaces, provider guidance, and focused regression tests are aligned; and the full Tool Shed validator passes.
