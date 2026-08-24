# Tool Shed maintenance and provider-specific routes

Read this reference for version, update, snapshot, or explicit reasoning-maintenance requests.

## Version Routes

- `ts: version`: run `python3 <shed>/scripts/check_shed_version.py --shed <shed> --local-only`.
- `ts: check for updates` or `ts: update status`: run
  `python3 <shed>/scripts/check_shed_version.py --shed <shed>`.

Report integrity, local and canonical versions, relation, and modified or missing tracked files.
A check never authorizes replacement.

## Full Tool Shed Upgrade Route

Treat `ts: fulltsupgrade` and `ts:fulltsupgrade` as authorization to upgrade the current existing
Tool Shed installation end-to-end from the latest verified published stable release on the
canonical GitHub repository. Inspect the target first and choose its supported path: fast-forward a
clean canonical checkout, or run a current released updater against a disconnected workspace
snapshot. Never replace a canonical checkout with a snapshot.

The route authorizes all normal in-scope functions needed to finish the one upgrade without
repeated confirmation: fetch release metadata and tags; verify provenance and hashes; preserve
unrelated work; create a verified rollback backup; update or replace the supported installation;
run released installer and provider-guidance convergence; verify exact release qualification and
run the focused client smoke, falling back to full local validation for overridden, unattested, or
changed identities; perform post-update verification; synchronize the separately installed Codex
skill when Codex is in use, even when the
workspace snapshot was already current; verify exact skill parity; and roll back if a post-update
check fails. Apply retention only to verified updater-owned backups and preserve unknown or
unverifiable recovery material.

This command does not waive credential, protected-target, or safety boundaries. It does not
authorize publishing a new Tool Shed release, rewriting Git history, forcing over modified or
unmanaged installations, deleting unknown recovery material, or updating any other workspace or
fleet target. In the canonical Tool Shed development checkout, follow the host-local development
workspace procedure for the Git fast-forward and client synchronization path.

## Upgrade Issue Report Route

Treat `ts: upgrade report` and `ts: upgrade report latest` as requests to render the newest
protected snapshot-upgrade transaction. An exact transaction ID may replace `latest`. Run:

```bash
python3 <shed>/scripts/snapshot_upgrade_report.py <latest-or-transaction-id>
```

The route is read-only and local. It accepts only the allowlisted final transaction schema from the
current platform and emits sanitized maintainer-ready Markdown by default; use `--json` for the
equivalent structured report. It rejects malformed, symlinked, permission-exposed,
foreign-platform, unknown-field, mismatched-identity, and incorrect-issue-code records. It never
prints raw exception text or owner/workspace data and has no network or GitHub publication
capability. Review the exact draft and obtain separate external-write authorization before using
`gh issue create`.

## Snapshot Install And Update

Before mutating an identified workspace, run `project_identity.py identity` for operation
`update-snapshot` or `workspace-install`, surface the target capsule, and pass its
operation-specific `--project-binding`. A new or legacy workspace without an identity is the only
exception: the installer/updater creates one atomic UUIDv4 identity under
`work/tool-shed-project.json`, includes that path in rollback scope, and preserves it exactly on
later runs. Malformed, duplicate, or conflicting identity fails before snapshot mutation.

For a normal project workspace, use a current released checkout:

```bash
python <current-shed>/scripts/update_snapshot.py --workspace <workspace> \
  --project-binding <update-snapshot-binding>
```

Never pull inside or develop from the disconnected workspace snapshot. The updater selects the
highest stable release, verifies provenance and content hashes, stages a disconnected snapshot,
preserves owner-authored root `work/` content, replaces the snapshot so removed files cannot linger,
retains a verified mutation-surface backup, runs the selected release's full installer to converge documented work
topology and provider guidance, and restores the snapshot, affected workspace state, and instruction
files after failed post-install checks. Do not bootstrap an upgrade with an older in-snapshot updater
when a current released updater is available outside the target project.

When read-only campaign validation reports legacy Campaign Number headers, unnumbered lifecycle
filenames, or stale projections, automatically run guarded `backfill-numbers` only when the selected
release declares `work/00-campaigns` as a backed-up tree mutation surface. Require the exact
pre-migration state token, preserve owner extensions and semantic campaign content, regenerate
indexes, validate the converged tree, and restore the exact prior tree if any later check fails.

Ordinary backups exclude policy-declared generated outputs that the selected installer cannot
mutate. After complete success, the updater protects the immediate rollback archive, retains the
newest two verified updater-owned workspace and optional user-skill backups by default, prunes only
older verified archives, and preserves unknown or unverifiable material. Use `--prune-preview` for
a read-only classification, `--backup-retention COUNT` to override the count, or
`--no-prune-backups` to suppress deletion. Backup deletion is irreversible.

For a new project that still needs its `work/` tree initialized, or to add an explicit provider
adapter outside the snapshot updater, run:

```bash
python3 <shed>/scripts/install_into_workspace.py <workspace> --provider <provider-id> \
  --project-binding <workspace-install-binding>
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
