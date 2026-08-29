# Evidence: App Server first-pass prelaunch collateral

Status: complete
Type: evidence
Updated: 2026-08-26
Next Action: derive and execute M11 Linux first-pass proof campaigns
Campaign: make-app-server-collateral-correct-before-worker-launch
Campaign Reason: G10-PRELAUNCH-COLLATERAL-SAFE completion evidence

## Result

Tool Shed now creates one compact `## App Server Preparation Contract` for every campaign created
through the owner queue or Program Roadmap materialization path. The contract preserves the stable
objective, completion evidence, one-bounded-CAMP intent, dispatch-time exact resolution,
source-freshness requirement, metadata-only asset handling, and orchestrator-owned exactly-once
verification without guessing exact paths during planning.

Automatic dispatch preparation now must return an atomic or independently verifiable bounded slice,
one to three estimated worker turns, an estimated largest tool result no greater than 12,288 bytes,
at most eight expected paths, and at most four focused verification commands. Before capsule
persistence or campaign start, the dispatcher validates context bytes, protected paths, executable
availability, verification scope, likely broad output, turn headroom, and tool-result headroom.
Python launchers are normalized to the active interpreter and scoped Git diff assertions are made
quiet; unsafe or oversized preparation fails before the worker starts.

Every newly automatic capsule is bound to the campaign request and preparation contract, Git HEAD,
the exact capsule boundary, and the current state of its expected and context files. A stale capsule
on a queued campaign is replaced through the guarded campaign transaction and revalidated before
launch. A stale capsule on a working campaign fails closed as
`execution_capsule_stale_after_start`, reports unknown mutation state, and directs reconciliation;
it never replans or replays the worker.

## Focused verification

The focused dispatcher, campaign lifecycle, and Program Roadmap checks passed 20 tests in 2.715
seconds. They include:

- a valid unprepared campaign that prepares, persists a source-bound capsule, starts once, and
  invokes one CAMP worker;
- blocked and unsafe preparation paths that make no campaign or product mutation and invoke no
  worker;
- source-bound queued-capsule regeneration and guarded replacement;
- stale working-capsule no-replay behavior;
- unavailable executable, oversized context, shell, protected lifecycle path, and broad preparation
  rejection;
- automatic campaign preparation-contract creation; and
- campaign lifecycle plus greenfield and existing-project roadmap materialization compatibility.

`git diff --check`, campaign validation, and Program Roadmap validation also passed. The full Tool
Shed validator was intentionally not run; Roadmap Revision 3 reserves it for the separately
authorized release boundary. Real native Linux first-pass executions belong to M11.
