# Closure red-dot recovery evidence

## Acceptance target

The `tool_shed` project must no longer report `Attention` or a red project indicator merely
because a terminal, reconciled historical outcome retained descriptive residual-work text.
The hosted dashboard is accepted only when a fresh report shows zero active loop findings and
zero closure debt.

## Observed failure

- Before repair, document-store revision 1317 was structurally clean but reported 19 active
  `LINEAGE_RECOVERY_REQUIRED` findings.
- The hosted dashboard consequently reported `Attention`, 19 loop findings, and 19 closure debt.
- Several affected documents displayed `Completed` while recursive closure remained open.

## Root cause

Recursive closure required terminal lifecycle, a reconciled outcome, a successful disposition,
and an empty `residual_work` list. That made descriptive follow-on context behave like a permanent
child dependency. The outcome contract permits a loop to close with an explicit non-success
disposition, and residual text is not itself a lineage edge. Actual child relationships remain the
authority for recursive closure.

## Deterministic repair

- `terminal-closure-reconciliation-v0473.json` is the revision-1317, project-bound repair manifest.
  Its token is `8cbee21f181d4be8`; it reconciled 22 historical cycles and 58 closure elements at
  revision 1318.
- `terminal-document-lifecycle-repair-v0473.json` is the exact lifecycle repair manifest for
  `MAP-0026` and `PRM-0037`. Its token is `4d263c888604d9d8`; it completed those two already-terminal
  documents at revision 1319.
- After regenerating database-owned lifecycle views, the revision-1319 checkpoint digest is
  `5d8eda657589a8b4c0c4f81ec68b184fe5e90dd7cfd20af40b9018e2d7c2503a`.

## Local verification

- Document-store audit: `CLEAN`, zero closure findings, zero semantic findings.
- Loop-finding audit: zero active findings; the 19 historical lineage findings and two follow-on
  lifecycle findings are resolved.
- Outcome audit: zero open, terminal-unreconciled, unpropagated, or invalid outcome cycles.
- Focused regression suite: 58 tests passed.
- Full patch-release qualification: 586 of 586 tests passed, including the temporary fresh-workspace
  install smoke and regenerated database-owned lifecycle views.
- New regression coverage proves that terminal reconciled outcomes with residual context and
  explicit non-success dispositions close locally, and that pre-migration history is repaired only
  from an exact project/revision/domain-bound plan.

GitHub issue 47 remains a separate next-revision enhancement. It is not an actual descendant of
these bounded historical cycles and therefore does not keep them open.

## Remaining release gate

Production acceptance requires the published patch, deployed dashboard, synchronized Codex client,
fresh reporter delivery, and direct verification that the hosted project no longer has the red
indicator or `Attention` state.
