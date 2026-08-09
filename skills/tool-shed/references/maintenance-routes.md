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
preserves root `work/`, retains a verified backup, and restores after failed post-install checks.

After installation or update, run:

```bash
python3 <shed>/scripts/install_into_workspace.py <workspace> --provider <provider-id>
```

Supported provider IDs come from `<shed>/adapters/providers.json`. Repeat `--provider` or use
`--provider all` to install multiple native instruction adapters.

## Codex Reasoning Extension

This section applies only when the current product is Codex and the request explicitly targets
reasoning maintenance or current-session metadata exposes Codex picker choices.

When available, choose the model before effort: Luna for clear repeatable work, Terra for everyday
engineering, and Sol for ambiguous or high-judgment work. Use Light for quick scoped tasks, Medium
for ordinary planning, High for difficult multi-step implementation or releases, Extra High for
long reasoning-heavy work, and Ultra only when useful independent subproblems justify it.

Ordinary requests must not read or refresh a catalog. Explicit routes are:

- `ts: refresh reasoning catalog`: run `python3 <shed>/scripts/reasoning_catalog.py refresh`.
- `ts: reasoning status`: run `python3 <shed>/scripts/reasoning_catalog.py status`.
- `ts: recommend reasoning <task>`: refresh, then recommend a concrete advertised pair.

The catalog uses Codex app-server `model/list`, preserves unfamiliar effort labels, writes
atomically, and retains the last verified cache on refresh failure. It cannot prove the active
thread setting.
