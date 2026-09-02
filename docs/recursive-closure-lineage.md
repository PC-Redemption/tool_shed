# Recursive Closure Lineage

Status: Work2 development candidate
Hybrid schema: 3
Evaluator: `recursive-closure-v1`

Tool Shed schema 3 keeps local closure separate from recursive effective closure. Every migrated
nonterminal cycle and accepted requirement receives a versioned closure element. Its envelope owns
the current immediate lineage claim; requirement-bound `lineage_claim` rows, ancestor paths,
rollups, blockers, and dashboard fields are indexed projections.

The four status fields are independent:

| Field | Values |
| --- | --- |
| `local_closure` | `open`, `closed-loop`, `closed-manual` |
| `evidence_health` | `not-required`, `current`, `missing`, `stale`, `checker-error` |
| `graph_health` | `valid`, `recovery-required`, `invalid` |
| `effective_closed` | Boolean recursive result |

A locally closed element remains effectively open while any governing obligation or descendant is
open, unproven, stale, recovery-required, invalid, or unreconciled. Manual closure applies to one
exact subject revision only and cannot close descendants. Production, release, security, and
compliance outcomes reject manual closure unless an owning policy explicitly enables the protected
override.

## Schema-2 migration

Migration is a two-step exact-manifest operation. Planning reads only explicit nonterminal cycles,
requirements, and active `outcome-parent` relationships. It never chooses among multiple parent
cycles or requirements and never infers lineage from prose, paths, titles, or timestamps.

```bash
python3 scripts/closure_lineage.py --workspace . --json migration-plan \
  > .tool-shed/closure-schema3-manifest.json
python3 scripts/closure_lineage.py --workspace . --json migration-validate \
  --manifest .tool-shed/closure-schema3-manifest.json
python3 scripts/closure_lineage.py --workspace . --json migrate \
  --manifest .tool-shed/closure-schema3-manifest.json \
  --expect <manifest-token> --project-binding <hybrid-state-binding>
```

The apply step rejects a stale database revision/digest, unresolved parent or requirement binding,
foreign project, changed manifest, or stale migration shadow. It creates and audits a verified
schema-2 backup under `.tool-shed/backups/`, qualifies a schema-3 shadow, then atomically promotes
it. A pre-promotion interruption leaves the live schema-2 database unchanged. The standard
`hybrid_state.py restore` route can restore the authorized backup by exact SHA-256 and current live
revision.

Schema 3 is a deliberate old-writer fence. Schema-1/2 clients report it as unsupported before a
managed mutation. The current document store accepts schema 2 only for planning/migration and
schema 3 for normal closure-aware operation.

## Status and closure

```bash
python3 scripts/closure_lineage.py --workspace . --json status <element-or-artifact-id>

python3 scripts/closure_lineage.py --workspace . --json close \
  --project-binding <hybrid-state-binding> --element <element-id> \
  --method closed-loop --evidence-health current \
  --evidence <reference> --authorization <reference> --actor <actor>
```

`status` returns exact subject, graph, and evaluator revisions; reasons; descendant counts; and up
to the first 100 nearest obligation-scoped blockers. Every closure mutation supersedes the prior
current record, rebuilds paths/rollups in the same guarded revision, and fails if the resulting
state cannot audit.

## Proof recipes

A recipe is immutable and content-addressed. Its declaration must bind the obligation and target;
read, write, network, credential, production, and external-cost classes; workspace/target
boundaries; timeout/resources; retry/cooldown/freshness; output schema/redaction; and explicit
pass/fail meaning. The checker has its own immutable digest. Generated free-form shell is not a
recipe.

`proof-record` is idempotent on element, obligation, subject revision/digest, recipe digest, and
target. A passed safe recipe emits a current closed-loop record. Mutating, networked, credentialed,
production, or costly recipes become `blocked` unless the invocation carries explicit current
authority. Failed, blocked, timed-out, checker-error, or superseded attempts cannot close work.

## Recovery

`recovery-open` creates or reuses one active case for an element and reason. An active case changes
graph health to `recovery-required`, propagates open status through affected ancestry, and remains
visible in blockers. `recovery-resolve` accepts only:

- `restored` after exact authority is recovered;
- `reparented` with explicit authorization; or
- `retired` with explicit authorization and a durable tombstone.

Reparent and retirement dispositions append lineage tombstones. Recovery never synthesizes a
parent's requirements, lifecycle, evidence, or ancestors from child hints.

## Checkpoint and compatibility

The schema-2 document checkpoint format now records its exact `hybrid_schema`. For schema 3 it
includes every closure authority and projection table. Rebuild recreates schema-3 triggers,
rehydrates document content objects, and must reproduce the complete domain digest. Updater
protocol 4 recognizes schema 3 and performs the same tracked `state-v2.json` rebuild before snapshot
mutation. Production remains schema 2 until a separately authorized Work5 promotion.
