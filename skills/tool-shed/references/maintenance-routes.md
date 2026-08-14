# Tool Shed maintenance and provider-specific routes

Read this reference for version, update, snapshot, or explicit reasoning-maintenance requests.

## Version Routes

- `ts: version`: run `python3 <shed>/scripts/check_shed_version.py --shed <shed> --local-only`.
- `ts: check for updates` or `ts: update status`: run
  `python3 <shed>/scripts/check_shed_version.py --shed <shed>`.

Report integrity, local and canonical versions, relation, and modified or missing tracked files.
A check never authorizes replacement.

## Snapshot Install And Update

For a normal project workspace, use a current released checkout:

```bash
python <current-shed>/scripts/update_snapshot.py --workspace <workspace>
```

Never pull inside or develop from the disconnected workspace snapshot. The updater selects the
highest stable release, verifies provenance and content hashes, stages a disconnected snapshot,
preserves owner-authored root `work/` content, replaces the snapshot so removed files cannot linger,
retains a verified backup, runs the selected release's full installer to converge documented work
topology and provider guidance, and restores the snapshot, affected workspace state, and instruction
files after failed post-install checks. Do not bootstrap an upgrade with an older in-snapshot updater
when a current released updater is available outside the target project.

For a new project that still needs its `work/` tree initialized, or to add an explicit provider
adapter outside the snapshot updater, run:

```bash
python3 <shed>/scripts/install_into_workspace.py <workspace> --provider <provider-id>
```

Supported provider IDs come from `<shed>/adapters/providers.json`. Repeat `--provider` or use
`--provider all` to install multiple native instruction adapters. A protocol-3 snapshot update
already runs the selected release's full installer for auto-detected or explicitly selected
providers; do not run it again merely to finish an update.

## Codex Reasoning Extension

This section applies only when the current product is Codex and the request explicitly targets
reasoning maintenance or current-session metadata exposes Codex picker choices.

When a current catalog or current-session metadata supplies model descriptions and supported effort
labels, choose the lowest adequate advertised model first and then the lowest adequate effort.
Never encode release-time model names or assume a fixed effort ladder in durable Tool Shed policy.

Ordinary requests must not read or refresh a catalog. Explicit routes are:

- `ts: refresh reasoning catalog`: run `python3 <shed>/scripts/reasoning_catalog.py refresh`.
- `ts: reasoning status`: run `python3 <shed>/scripts/reasoning_catalog.py status`.
- `ts: recommend reasoning <task>`: refresh, then recommend a concrete advertised pair.

The catalog uses Codex app-server `model/list`, preserves unfamiliar effort labels, writes
atomically, and retains the last verified cache on refresh failure. It cannot prove the active
thread setting.
