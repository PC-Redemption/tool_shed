# Customize work-level actions per workspace

Status: working
Type: campaign
Updated: 2026-08-17
Next Action: execute the campaign completion gate
Campaign ID: customize-work-level-actions-per-workspace
Campaign Number: 023
Outcome: Allow each Tool Shed workspace to declaratively add ordered actions before or after the standard work1-work5 behavior, or explicitly suppress the standard behavior for a selected level, without changing defaults for other Tool Shed installations.
Primary Focus Areas: provider-portability
Supporting Focus Areas: snapshot-delivery, qualification-release
Depends On: none
Decision: none
Detour For: none
Return To: none
Completion Gate: A documented, versioned workspace-local configuration contract supports validated before/default/after behavior for work1-work5 and their aliases; ordering and cumulative-level semantics are deterministic; absent configuration preserves current defaults; explicit suppression is visible and cannot expand authority or bypass safety; installation and upgrade preserve owner configuration; portable instructions, operator documentation, examples, and regression tests are updated; focused and full validation pass.
Completion Evidence: none
Disposition: none

## Request

Extend the numbered work-level model so an individual installed Tool Shed workspace can customize
what happens when `ts:work1` through `ts:work5` (and their aliases) are invoked. Keep the existing
standard work-level definitions as portable defaults; do not add one project's special delivery,
documentation, hardware, deployment, or review steps to every Tool Shed installation.

### Desired operator behavior

Provide a tracked workspace-local declaration, preferably by extending the existing
`work/tool-shed.yaml` contract unless implementation evidence supports a cleaner existing surface.
For each canonical work level, allow the workspace to declare:

1. ordered actions to perform before the standard work-level behavior;
2. whether the standard behavior runs;
3. ordered actions to perform after the standard behavior.

The conceptual execution envelope is:

```text
workspace before actions
→ standard work-level behavior, unless explicitly disabled
→ workspace after actions
```

A workspace must be able to express cases such as:

- Work2 performs a project-specific environment preparation step, then the normal Work2 behavior,
  then a project-specific smoke check.
- Work3 performs the normal documentation, validation, build, and freeze behavior, then generates
  an additional project handoff artifact.
- Work4 replaces the normal Work4 behavior with a workspace-specific controlled publication flow.
- Work5 adds required site, device, compliance, or operations verification after the standard
  production endpoint.

Support the smallest portable representation that can reliably describe agent-executed steps and
existing workspace commands or scripts. Do not require a new server or provider-specific hook
system when tracked configuration plus native workspace capabilities are sufficient.

### Deterministic semantics

- Resolve aliases to their canonical level before applying customization. An alias must not cause
  duplicate execution or silently select a separate configuration.
- Define and test whether a cumulative invocation applies only the selected level's customization
  envelope or also applies lower-level envelopes. Choose one clear model, document the reason, and
  prevent duplicate before/after actions.
- Preserve declaration order. Define failure behavior so a failed required action cannot be hidden
  by later actions or a success summary.
- Make standard-behavior suppression explicit in configuration and visible in the agent's execution
  summary before it acts. Missing configuration, a missing level entry, or omitted suppression must
  retain today's standard behavior.
- Reject unsupported schema versions, unknown work levels, invalid action shapes, conflicting
  declarations, and ambiguous aliases rather than guessing.

### Authority and safety boundaries

Invoking a configured work level should make its declared in-scope workspace actions part of the
expected endpoint, so the operator does not need to repeat them in every prompt. The declaration
must not bypass credentials, protected-environment approvals, destructive-action safeguards,
repository policy, or the scope of the current goal. Disabling the standard behavior must never
disable safety rules, campaign continuity, evidence comparison, or required outcome verification.

Do not store credentials in the configuration. Surface consequential configured actions before
execution, apply the existing prospective failure check where appropriate, and preserve unrelated
workspace changes.

### Portability, installation, and maintenance

- Update the portable skill and every managed provider guidance surface that communicates numbered
  work levels.
- Ensure installation initializes a valid minimal configuration only where current behavior already
  does so, and never overwrites an owner-authored workspace declaration.
- Ensure snapshot upgrades preserve valid owner customization exactly, safely converge schema-owned
  defaults when required, and reject malformed state without partial mutation.
- Document configuration examples, alias behavior, cumulative ordering, default suppression,
  failure handling, authorization boundaries, and how an existing workspace adopts or removes a
  customization.
- Add regression coverage for no-configuration compatibility, before/default/after ordering,
  default suppression, aliases, cumulative levels, malformed declarations, installer idempotence,
  upgrade preservation and rollback, and provider guidance convergence.
- Update the public generated documentation site source when the operator-facing command behavior
  changes so its next deployment will reflect the canonical documentation.

## Completion Check

A documented, versioned workspace-local configuration contract supports validated before/default/after behavior for work1-work5 and their aliases; ordering and cumulative-level semantics are deterministic; absent configuration preserves current defaults; explicit suppression is visible and cannot expand authority or bypass safety; installation and upgrade preserve owner configuration; portable instructions, operator documentation, examples, and regression tests are updated; focused and full validation pass.
