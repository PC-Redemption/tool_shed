# Lifecycle Qualification Harness

Status: Work2 local lifecycle and recovery corpus
Contract: `lifecycle-qualification-v1`
Oracle: `lifecycle-truth-oracle-v1`

The lifecycle qualification harness is a deterministic, no-model driver and independent read-only
oracle for Tool Shed database truth. It is intentionally small: checked-in scenarios state the
invariants, a sealed run manifest fixes every input, an append-only hash-chained journal records
actions, and a compact result names the first divergence and replay inputs. It does not create a
second operational database.

Every manifest binds one exact checkpoint ID declared by its scenario. A scenario with one
checkpoint selects it by default; a multi-checkpoint scenario requires `--checkpoint <id>`. The
selector participates in the manifest digest and run ID and is repeated in the result summary.

## Record contract

| Record | Authority | Location |
| --- | --- | --- |
| Scenario | Versioned test intent | `schemas/lifecycle-qualification/v1/scenarios/QH-*.json` |
| Run manifest | Immutable execution inputs; its canonical JSON digest derives the run ID | generated evidence |
| Journal event | Append-only execution evidence with contiguous sequence and prior-event digest | ignored generated evidence |
| Result | Versioned compact verdict, invariant checks, evidence hashes, and replay arguments | selected evidence summary |

Schemas are under `schemas/lifecycle-qualification/v1/`. The manifest seal excludes only
`manifest_digest` and `run_id`; the run ID is `tsqh-` plus the first 24 hexadecimal characters of
the full manifest digest. Changing candidate, scenario, fixture identity, serial, seed, baseline,
platform, or target therefore creates a different run.

Verdicts are `PASS`, `PRODUCT-FAIL`, `HARNESS-FAIL`, and `INFRA-BLOCKED`. Missing or unknown required
observations cannot pass. A result evaluates exact expected sets and the unexpected-row set, so
extra state fails even when every expected row exists.

## Independent oracle boundary

`scripts/lifecycle_qualification.py` opens SQLite in read-only mode and calculates lineage and
effective closure from `closure_element`, parent-owned `requirement`, current `lineage_claim`,
current `closure_record`, and active `recovery_case` rows. It does not import
`closure_lineage.py`, and it never reads `closure_ancestor_path`, `closure_blocker`, or
`closure_rollup` while deriving expected state. Only after evaluation does it compare the result
with `closure_rollup`.

Truth-vector fields identify their layer and authority class. Local SQLite facts are
`authoritative`; reporter/outbox facts are `transport-record`; hosted database rows are
`hosted-projection`; HTTP and browser claims are `presentation`. A downstream layer may agree with
authority but cannot replace it.

## Scenario corpus

- `QH-001` exports every raw development project and instance, then requires the visible project
  set to equal the two enrolled disposable fixtures. The two optional seed UUIDs must be absent or
  hidden, and project/instance identities must be unique.
- `QH-002` creates one run-tagged Idea, project map, Program Roadmap, campaign, and governed result
  through guarded document/outcome services. It reconciles child to parent, completes document
  lifecycle, and requires a terminal clean tail plus independent closure/projection parity.
- `QH-003` mixes manual and closed-loop child completion in reverse branch order and proves a
  locally closed parent remains effectively open until every governing child closes. A separate
  non-governing child remains open without blocking the parent.
- `QH-004` builds a three-document-level diamond with one shared leaf. It proves both indexed
  ancestry paths, bounded and deduplicated blockers, recursive completion, and oracle parity.
- `QH-005` closes one obligation, changes its authoritative subject, observes the old closure
  record become superseded, and re-proves the new subject while retaining both records.
- `QH-006` commits a terminal child before its parent transition, resumes after that explicit
  interruption point, and replays the resume. Exactly one terminal verdict, reconciliation, and
  parent-result propagation may exist.
- `QH-008` writes a logical schema-3 checkpoint, rebuilds a distinct database, and requires exact
  domain-digest and independently calculated closure parity with a clean rebuilt audit.
- `QH-009` copies healthy authority into three isolated databases and injects one missing parent,
  one conflicting lineage digest, and one cycle. Each finding must be explicit while the healthy
  source database and an unrelated control element remain unchanged.
- Local `QH-010` constructs sanitized, structurally faithful file-owned and Hybrid snapshots,
  upgrades each in place, and checks stable artifact IDs, retained document history, recovered
  parent claims, explicit unresolved ancestry, idempotent replay, and zero invisible orphans.
  Hosted ingestion of these snapshots remains an M3 activity and uses an ephemeral development
  database until the M4 qualification namespace exists.

Normal QH-002 runs are append-only and retained. M2 local runs use a distinct nested workspace
below `.tool-shed/qualification/runs/<run-id>/` on the exact disposable OS fixture. This keeps
malformed graph and pre-upgrade snapshots out of the fixture's operational database without
moving execution off the target platform. Reusing an already-complete manifest returns the sealed
result as an idempotent resume. A partial run is refused until its last authoritative checkpoint
is understood; the harness does not guess whether an incompletely observed mutation happened.

## Commands

Seal a run after recording the exact candidate and fixture baseline:

```bash
python3 scripts/lifecycle_qualification.py seal \
  --scenario QH-002 --candidate-commit <sha> --candidate-version <version> \
  --checkpoint terminal-clean-tail \
  --platform linux-x86_64 --project-id <uuid> --instance-id <uuid> \
  --serial 1 --seed 0 --target-environment development \
  --baseline-digest <sha256> --output <manifest.json>
```

Drive QH-002 only in a verified disposable development workspace:

```bash
python3 scripts/lifecycle_qualification.py drive-qh002 \
  --workspace <fixture> --manifest <manifest.json> \
  --project-binding <fresh-hybrid-state-binding> --output <drive.json>
```

Drive any M2 local scenario (`QH-003` through `QH-006`, `QH-008`, `QH-009`, or local `QH-010`):

```bash
python3 scripts/lifecycle_qualification.py drive-local \
  --workspace <fixture> --manifest <manifest.json> --output <drive.json>
```

The driver refuses any target environment other than `development`. It imports the installed
candidate's guarded lifecycle services; only QH-005's subject-revision hook and QH-009's isolated
malformed copies use bounded test mutations. Evaluate and seal the resulting local record with:

```bash
python3 scripts/lifecycle_qualification.py evaluate \
  --manifest <manifest.json> --local <drive.json> --output <result.json>
```

After its reporter converges, evaluate the local truth vector and hosted snapshot together. The
hosted comparison is identity-bound to the exact run artifacts and fixture project/instance; a
missing row or a non-terminal, unreconciled, or ineffectively closed row fails qualification.

```bash
python3 scripts/lifecycle_qualification.py evaluate \
  --manifest <manifest.json> --local <truth.json> --dashboard <snapshot.json> \
  --output <result.json>
```

Export the hosted raw snapshot from the development dashboard container, then evaluate QH-001:

```bash
python /app/dashboard/manage.py export_dashboard_qualification_snapshot
python3 scripts/lifecycle_qualification.py evaluate \
  --manifest <manifest.json> --dashboard <snapshot.json> --output <result.json>
```

Generated manifests, journals, raw database observations, and browser captures belong below
ignored `work/evidence/generated/` or `.tool-shed/qualification/`. A retained summary records their
hashes and target identity. Production execution is refused by the QH-002 driver and production
deployment remains a separate Work5 decision.
