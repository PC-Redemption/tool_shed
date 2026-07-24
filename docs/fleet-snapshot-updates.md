# Tool Shed Fleet Snapshot Updates

Workspace-local `tool_shed/` directories remain disconnected, one-way snapshots. Fleet operations
must never add Git metadata, pull inside a snapshot, push workspace changes upstream, or modify a
project's `work/`, documentation, or code.

## Read-only inventory

Run from a verified canonical Tool Shed checkout:

```bash
python3 scripts/inventory_tool_shed_fleet.py --all-ssh-hosts
```

The command searches the configured roots on the local host and literal aliases in the user's SSH
configuration. It hashes the instruction files that control Tool Shed behavior and reports:

- `current`: a disconnected snapshot whose instruction hashes match canonical
- `stale`: a snapshot with one or more changed instruction files
- `incomplete`: a snapshot missing an instruction file
- `checkout`: a Git checkout, which fleet replacement must never touch
- `unreachable`: SSH could not complete a read-only scan

Use explicit `--host` and `--root` values when the approved fleet is narrower than the SSH config.
Inventory does not imply approval to update any reported path.

For a single snapshot, `scripts/check_shed_version.py` compares its semantic version with the
canonical `SHED_VERSION.json` and verifies its tracked content hashes. Version status distinguishes
an older clean snapshot from a locally modified snapshot; neither status authorizes replacement.

## Guarded mass-update design

An apply-capable updater must use a reviewed JSON inventory as its target list and default to a
dry-run. Applying requires both an explicit `--apply` flag and confirmation of the canonical commit.
For every target it must:

1. Revalidate that the path is a disconnected snapshot and is not a symlink, Git checkout, or
   submodule.
2. Recompute the pre-update hashes and stop if they differ from the reviewed inventory.
3. Stage a verified canonical snapshot in a sibling temporary directory without `.git/`, `work/`,
   caches, generated state, or host-local configuration.
4. Preserve a timestamped, recoverable backup of the previous snapshot.
5. Replace only the `tool_shed/` directory; never touch the containing project's `work/`, docs, or
   code.
6. Re-run inventory and repository-boundary checks. Report success only when hashes match canonical
   and the parent repository still ignores `/tool_shed/`.

Remote updates should use the same staged payload and validation on the target host. Unreachable,
modified-after-review, unrecognized, or non-ignored targets must be skipped, not forced. Rollout
should stop on the first validation failure until a human reviews the evidence.

The first fleet rollout remains approval-gated. Periodic drift checks are a separate later decision.
