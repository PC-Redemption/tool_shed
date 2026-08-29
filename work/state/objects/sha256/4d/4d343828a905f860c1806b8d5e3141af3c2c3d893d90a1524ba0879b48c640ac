# Fail closed on cross-workspace Tool Shed routing and mutations

Status: complete
Type: campaign
Updated: 2026-08-18
Next Action: none
Campaign ID: fail-closed-on-cross-workspace-routing
Campaign Number: 030
Outcome: Resolve critical GitHub issue #38 by establishing stable project and session identity, binding every Tool Shed mutation to the selected project and resolved root, rejecting cross-workspace paths and tokens without mutation, and requiring an explicit verified workspace switch before another project can be targeted.
Primary Focus Areas: workspace-safety
Supporting Focus Areas: snapshot-delivery, provider-portability, campaign-lifecycle, qualification-release
Depends On: none
Decision: none
Detour For: none
Return To: none
Completion Gate: GitHub issue #38 acceptance criteria pass: every workspace has one stable tracked project identity created atomically for new and legacy installations and preserved across clones and upgrades; a read-only identity command and pre-mutation target capsule expose the project ID, name, resolved root, repository fingerprint when available, active campaign or operation, and session binding; campaign, roadmap, reconciliation, work-level, maintenance, and provider-routed generic mutation paths require project-bound tokens and reject missing, malformed, conflicting, foreign-project, or root-mismatched identity with no partial writes; outside-root paths produce WORKSPACE_MISMATCH and never imply a switch; an explicit use route reloads target instructions and requires fresh target-bound state; two-repository isolation, identical-state foreign-token, path-mention, explicit-switch, legacy-upgrade, idempotence, direct-script, provider-route, read-only inspection, and rollback tests pass; portable and generated guidance plus recovery documentation are aligned; the full validator passes; and issue #38 is updated with verified evidence.
Completion Evidence: full-validator:151-tests; provider-conformance; stale-path/work-state/roadmap/smoke; github-issue-38-comment-5329358658
Completion Date: 2026-08-18
Completion Order: 26
Disposition: completed

## Request

Deliver the critical project-isolation boundary in
[GitHub issue #38](https://github.com/PC-Redemption/tool_shed/issues/38). Introduce a stable tracked
project identity outside the reusable `tool_shed/` snapshot, create distinct identities during new
installations, preserve them across clones and upgrades, and add a read-only identity surface that
reports the project name and ID, canonical resolved root, repository fingerprint when available,
active campaign, and bound operation.

Bind each provider session to the exact project ID and resolved root before its first mutation.
Bind mutation tokens and every deterministic mutation family—campaign, roadmap, reconciliation,
numbered work, maintenance, installation, and upgrade—to that identity. A token from another
project must fail even when both projects have byte-identical state. Missing, malformed,
duplicated, conflicting, or mismatched identity must fail closed with recovery guidance and no
partial writes.

Treat absolute paths outside the bound root as `WORKSPACE_MISMATCH`: mentioning or inspecting a
path is evidence, not authorization to switch. Provide an explicit `ts: use
<project-alias-or-path>` boundary that reloads the target workspace instructions and skill and
requires fresh target-bound state. Align provider guidance so generic editing or shell tools cannot
bypass the same fence, while keeping read-only cross-project inspection from silently changing the
active binding.

Prove the boundary with adjacent temporary repositories, identical campaign trees, foreign-token
rejection, outside-path continuation, explicit switching, legacy and repeated upgrades, direct
scripts, provider-routed generic tools, read-only inspection, and injected failure recovery. Keep
both repositories byte-stable outside each explicitly intended mutation surface.

## Completion Check

GitHub issue #38 acceptance criteria pass: every workspace has one stable tracked project identity created atomically for new and legacy installations and preserved across clones and upgrades; a read-only identity command and pre-mutation target capsule expose the project ID, name, resolved root, repository fingerprint when available, active campaign or operation, and session binding; campaign, roadmap, reconciliation, work-level, maintenance, and provider-routed generic mutation paths require project-bound tokens and reject missing, malformed, conflicting, foreign-project, or root-mismatched identity with no partial writes; outside-root paths produce WORKSPACE_MISMATCH and never imply a switch; an explicit use route reloads target instructions and requires fresh target-bound state; two-repository isolation, identical-state foreign-token, path-mention, explicit-switch, legacy-upgrade, idempotence, direct-script, provider-route, read-only inspection, and rollback tests pass; portable and generated guidance plus recovery documentation are aligned; the full validator passes; and issue #38 is updated with verified evidence.
