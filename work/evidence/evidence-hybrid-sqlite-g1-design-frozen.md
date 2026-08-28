# Evidence: Hybrid SQLite G1 Design Frozen

Status: passed
Type: validation-evidence
Updated: 2026-08-28
Gate: G1-DESIGN-FROZEN
Initiative: hybrid-sqlite-operational-state

## Qualified Outcome

Campaign 103 establishes an independent file/Git bootstrap closure authority before any SQLite
authority exists. The phase-one contract assigns one authority per field, freezes the version-1
schema and accounting behavior, defines deterministic checkpoint and rebuild behavior, records the
HPT2 evidence gap without inventing history, and defines the context-efficiency fixtures and gates.

This evidence passes G1 only. It does not claim that the SQLite substrate, HPT2 reconciliation,
maintainer conversion, release, installed-skill synchronization, or client canary is complete.

## Evidence Set

- `scripts/bootstrap_closure.py` provides project-bound and state-token-guarded baseline,
  material-change, evidence, verdict, verification, and reporting operations.
- `schemas/bootstrap-closure/v1/manifest.schema.json` and
  `templates/bootstrap-closure.json` define the portable version-1 record.
- `docs/hybrid-sqlite-state-v1-contract.md` freezes authority, identity, schema, trigger,
  direct-SQL, checkpoint, worktree, merge, rebuild, backup, migration, updater, rollback,
  downgrade, HPT2 inventory, and efficiency-fixture decisions.
- `scripts/validate_tool_shed.py` checks tracked bootstrap manifests structurally in the full
  profile and requires their final release gates in the release profile.
- `tests/test_bootstrap_closure.py` and `tests/test_validation_profiles.py` prove the guarded
  operations, stale-source detection, rerun enforcement, final-gate refusal, and profile wiring.

## Verification

Final focused rerun executed from `/home/jon/docker/tool_shed` at `2026-08-28T16:31:20Z` after
material-change enforcement was hardened:

```text
PYTHONPATH=scripts:. python3 -m unittest -v \
  tests.test_bootstrap_closure tests.test_validation_profiles
```

Result: 7 tests passed. Material-change coverage includes refusal when no affected requirement or
decision, no evidence rerun, or an unknown superseded change is supplied.

```text
python3 -m json.tool schemas/bootstrap-closure/v1/manifest.schema.json
python3 -m json.tool templates/bootstrap-closure.json
python3 -m py_compile scripts/bootstrap_closure.py scripts/validate_tool_shed.py
```

Result: all structural and compilation checks passed.

The tracked bootstrap manifest binds this evidence and the exact source files by SHA-256. Its G1
verification is the authoritative machine-readable gate result; later evidence must update the
manifest through its guarded commands.

## Residual Work

- G2: implement and qualify the minimum SQLite substrate and HPT2 closed loop.
- G3: rehearse and perform the no-data-loss maintainer conversion.
- G4: separately authorize, qualify, publish, synchronize, and canary the database-aware release.

Those items remain release-blocking and are intentionally not waived by this G1 result.
