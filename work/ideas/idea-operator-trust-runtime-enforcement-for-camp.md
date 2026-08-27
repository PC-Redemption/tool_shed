# Idea Brief: Operator-Trust Runtime Enforcement for CAMP

Status: promoted
Type: idea-brief
Updated: 2026-08-27
Next Action: use the approved project-map direction and Program Roadmap for delivery
Produces: work/maps/map-operator-trust-camp-runtime-enforcement.md

## Current Synthesis

### Idea

Replace exact Codex version/executable certification as the universal CAMP permission gate with an
operator-trust policy backed by live behavioral enforcement. When the operator explicitly enables
`ts: app-server on`, Tool Shed should allow every supported local App Server role—including bounded
CAMP workspace writes—provided the current invocation passes the existing runtime and containment
path and its exact version is not explicitly recorded as `unqualified` with reviewed evidence.

Codex version, executable path, and executable hash remain useful telemetry for diagnosis,
reproduction, status, and optional certification. They should not decide whether an otherwise
compatible new CLI may write. The governing principle is: **version is telemetry; behavior is
truth**.

### Why It Matters

The current exact-version and optional executable-hash gates turn frequent Codex releases into
recurring Tool Shed qualification, evidence, documentation, and release work. This cost occurs even
when the relevant protocol and containment behavior have not changed, and it prevents the passive
App Server dogfooding mode from exercising real CAMP work on newly updated CLIs.

### Desired Outcome

An operator opts into local App Server use once and newly installed Codex versions can immediately
run bounded CAMP work when live startup, authentication, protocol, model, sandbox, repository, path,
journal, budget, and verification controls succeed. Unsafe observations stop the affected run,
preserve the existing mutation journal for reconciliation, and never trigger automatic replay. Only
an exact version explicitly recorded as `unqualified` with reviewed evidence is denied; a new or
fixed version runs normally. None of this expands production, credential, destructive, deployment,
publication, or cross-workspace authority.

## Recommended Direction

Use `ts: app-server on` as the explicit operator-trust signal for supported local roles. Keep the
committed default off and retain `--app-server` as a strict one-command backend request and `--gui`
as a one-command override. Introduce three independently reported dimensions instead of one
"qualified" decision:

1. **Trust policy:** `off`, `operator-runtime`, or optional `strict-certified`.
2. **Runtime readiness:** `unchecked`, `ready`, or `blocked`, per role and current invocation.
3. **Observed safety:** `clear` or `denylisted`, based on an evidence-backed exact `unqualified`
   record.

Certification becomes a fourth, informational dimension: `exact`, `related`, `missing`, or `stale`.
Strict environments may make `exact` certification a gate, but normal operator-runtime mode does
not.

The smallest product change is to preserve the existing preference command and selection order,
replace CAMP's exact-record predicate with `operator trust + the existing runtime path + no exact
reviewed unqualified record`, and reinterpret the existing registry as certification evidence plus
the minimal explicit denylist rather than a default allowlist. No new server, preflight subsystem,
policy engine, state store, or general permission system is required.

## Runtime Safety Gates

The following remain true gates and must fail before mutation when they cannot be established:

- the resolved executable exists, starts App Server, completes protocol initialization, and exposes
  every feature required by the selected role;
- managed ChatGPT authentication is usable, the policy-selected model and reasoning setting are
  available, and the requested sandbox/permission profile is actually supported;
- the project identity, requested work endpoint, authority envelope, writable repository root, Git
  state, and clean-worktree requirement are valid;
- the CAMP/preparation capsule is current and bounded, expected paths avoid protected locations,
  verification commands are shell-free and available, and context/tool/turn budgets fit policy;
- the mutation journal is created before write access and controller-owned deterministic checks are
  reserved until the worker returns a valid verification-pending handoff.

Post-start enforcement remains unchanged: unexpected paths, malformed or partial results,
interrupts, budget ceilings, failed verification, or uncertain mutation state stop lifecycle
advance. Tool Shed reconciles the journal and Git state and never automatically replays a step that
may have mutated the workspace.

Runtime startup, authentication, model availability, and sandbox support should be checked live for
each operation. A cache may accelerate diagnostic discovery, but cached success must not replace the
live handshake that authorizes the current run.

## Possibilities And Tradeoffs

| Possibility | Benefits | Costs / Risks | Recommendation |
| --- | --- | --- | --- |
| Exact certification for every CAMP-capable CLI | Strong reviewed provenance and simple fail-closed reasoning | Recurring release toil; new safe versions are unusable; identity substitutes for behavior | Retain only as optional strict mode |
| `app-server on` means operator trust plus live enforcement | Smallest command/config change; matches persistent dogfooding intent; new versions work immediately | Changes the meaning of an existing preference and makes runtime probes security-critical | Recommended, with migration consent handling |
| Add a separate `trust-writes` switch | Avoids changing existing `on` semantics | Adds another persistent setting and repeats the ceremony this idea aims to remove | Migration fallback, not desired steady state |
| Automatic first-write disposable canary per new version | Adds behavioral evidence before real work | Recreates version-triggered latency and harness maintenance; canary may not represent the real task | Do not require by default |
| Central allowlist plus exception for unknown versions | Incremental implementation | Retains two competing authorization models and ambiguous status | Avoid |

## Qualification Machinery Disposition

- **Qualification registry:** keep as optional strict-certification evidence, known compatibility
  notes, and the exact evidence-backed `unqualified` denylist. Remove positive qualification from
  normal CAMP admission.
- **Executable hash:** record as diagnostic/journal evidence; do not require a pre-certified hash
  for operator-runtime admission.
- **Disposable write harness:** retain for strict certification, release qualification, regression
  reproduction, and investigation after unsafe behavior. Stop running it merely because a version
  changed.
- **Dirty-read cache:** retire it as an authorization surface. If useful, replace it with a short-TTL
  capability-discovery cache whose success is advisory and cannot bypass the live per-operation
  handshake. Preserve reviewed unsafe records separately from transient capability results.

## Denylist And Recovery

Do not add automatic quarantine state or a second recovery system. The existing mutation journal,
Git reconciliation, deterministic verification, and no-replay behavior already own uncertain-write
recovery. Transient startup, authentication, network, model, sandbox, and malformed-result failures
remain run failures and do not persist a version block.

The existing qualification registry supplies the only normal-mode version denial: an exact record
with `status: unqualified` and a non-empty reviewed evidence reference. It blocks only that recorded
version. A new or fixed version that does not exactly match runs normally. Removal or correction of
the reviewed record restores normal admission.

## Status And Operator Experience

`ts: app-server status` should report, without collapsing the dimensions:

- effective trust policy and its source (`default-off`, explicit operator runtime trust, or strict
  workspace policy);
- resolved executable path, version, hash/fingerprint, and discovery source as telemetry;
- current runtime readiness for planning, verification, and CAMP, including the first failed live
  gate or `unchecked` when no live probe has run;
- observed-safety state (`clear` or `denylisted`) and the matching reviewed evidence when denied;
- optional certification state and evidence age, clearly labeled as required only in strict mode;
- unchanged GUI-native routes, GUI fallback behavior, disabled API fallback, and protected authority
  boundaries.

Avoid phrases such as `write-not-qualified` in operator-runtime mode. Prefer `trusted; runtime
unchecked`, `runtime ready`, `runtime blocked: <category>`, or `denylisted: <evidence>`.

## Backward Compatibility And Migration

The preference schema needs an explicit consent version because an existing stored `on` value was
created under narrower write semantics. Recommended migration:

- new `on` commands write schema v2 with `trust_policy: operator-runtime` and a consent timestamp;
- existing schema-v1 `on` remains read-role preference until the operator runs `ts: app-server on`
  once after upgrade, with status showing `legacy-on; CAMP trust not yet confirmed`;
- `off`, `--gui`, strict `--app-server`, GUI fallback, and user-local storage locations remain
  compatible;
- a repository or protected user-local setting may select `strict-certified` without changing the
  normal default; malformed or unsupported policy fails to GUI/off, never to broader trust;
- existing qualification records and dirty-read cache files are read for status/migration only and
  are not destructively removed during upgrade.

An alternative is to reinterpret every existing `on` immediately. It is simpler, but it silently
expands previously granted workspace-write trust and is therefore not recommended.

## Tests And Documentation

Minimum proof should cover:

- an unknown/new Codex version with no registry record passes live gates and may run bounded CAMP
  under fresh operator-runtime consent;
- missing protocol features, authentication, model, sandbox support, project binding, clean Git
  state, capsule/path constraints, journal creation, or budgets fail before mutation;
- unexpected paths, malformed handoff, interruption after possible mutation, and deterministic
  verification failure preserve the journal, block lifecycle advance, and never replay;
- an evidence-backed exact `unqualified` record denies only the recorded version, while a new or
  fixed version runs normally;
- strict-certified mode still requires matching certification, while normal mode treats version and
  hash only as telemetry;
- legacy preference migration does not silently broaden write trust; snapshot upgrades preserve
  preferences and certification/denylist evidence;
- work1-work5 endpoints and credentials, destructive operations, cross-workspace actions, push,
  deployment, production, publication, and release boundaries remain unchanged.

Update operator help, App Server execution/maintainer documentation, preference and status schemas,
qualification guidance, snapshot migration notes, and the Tool Shed skill route. Historical
qualification reports remain evidence and should not be rewritten.

## Open Questions

- Should strict certification be selected only by repository policy, or also by a protected
  user-local preference?
- After legacy migration, is one repeated `ts: app-server on` sufficient consent, or should status
  provide a dedicated `trust CAMP writes` action for the transition release only?
- Which exact protocol calls and permission-profile properties constitute the minimum CAMP
  handshake across supported platforms?
- Who owns reviewed `unqualified` records, and what reproduced evidence threshold justifies adding
  or removing one?
- Can strict certification match a behavior/protocol profile rather than an exact executable hash,
  or is exact identity the point of that optional mode?

## Decisions

- Preserve all existing Git containment, path allowlists, mutation journals, bounded execution,
  deterministic verification, reconciliation, and no-replay controls.
- Keep external and protected-operation authority independent from local App Server trust.
- Prefer operator trust plus live runtime evidence over version-based admission.
- Treat exact certification as optional strict policy, not the universal CAMP gate.
- Keep the promoted synthesis aligned with the approved project map and owner decisions.

## Readiness Criteria For PRM

Promote this brief when the owner has selected:

1. the exact legacy-`on` consent migration;
2. the configuration owner and precedence for optional strict-certified mode;
3. the minimum live CAMP handshake and which checks must occur every invocation;
4. the reviewed exact-version denial rule;
5. the first milestone boundary: preference/schema migration, selector/status refactor, existing
   runtime gates, tests, and documentation—with no deployment or publication implied.

## Don't Forget

- Runtime readiness failures are not evidence of unsafe behavior and must not poison a denylist.
- A successful handshake does not authorize the requested task; it only permits the selected local
  backend to act inside the existing project, endpoint, and authority envelope.
- Diagnostic identity data must not become a hidden authorization gate again.
- Status should explain the effective decision in operator language without requiring inspection of
  registry files or qualification reports.

## Exploration Log

### 2026-08-27

- Idea Brief created from the owner's request to replace exact-version CAMP qualification with
  operator-trust runtime enforcement.
- Discovery separated trust policy, live readiness, observed safety, and optional certification so
  one overloaded qualification state no longer controls all four concerns.
- Recommended `ts: app-server on` as the steady-state operator-trust signal, with schema-versioned
  migration consent for existing enabled preferences.
- Preserved runtime containment and external authority boundaries while repositioning the registry,
  executable hash, disposable harness, and dirty-read cache.
- The owner selected this synthesis for PRM promotion. The initial Plan Cycle baseline included a
  proposed narrow quarantine, later superseded by the owner-directed KISS correction below.
- The approved project-map direction captured this synthesis in
  `work/maps/map-operator-trust-camp-runtime-enforcement.md`; this brief remains discovery
  provenance for the PRM lifecycle.
- The owner rejected the proposed quarantine/preflight expansion as too restrictive. Delivery was
  pruned to the existing runtime and recovery path, with an evidence-backed exact `unqualified`
  registry record as the only normal-mode version denial.

Keep the synthesis current and append only useful dated exploration notes. Use `Status: ready-for-prm`
when the owner chooses to promote it, `promoted` after approved project-map direction captures it,
or `parked` when it is intentionally set aside. A promoted brief names its output in `Produces:`.
