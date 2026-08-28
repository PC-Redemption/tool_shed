# Install or Update Tool Shed in One Workspace

Use this single workspace-agent request from a project root. The agent first determines whether the workspace has
a disconnected `tool_shed/` snapshot, then performs either a guarded update or a guarded new
installation.

The supported cross-platform command is:

```text
python /path/to/current-release/scripts/update_snapshot.py --workspace . \
  --project-binding <update-snapshot-binding>
```

For Codex, add `--sync-codex-skill` to install or update the separately discovered user-level skill
at `${CODEX_HOME:-~/.codex}/skills/tool-shed`. Without the flag, the updater remains read-only for
that user-level path and reports whether it is current, missing, stale, modified, or unsafe:

```text
python /path/to/current-release/scripts/update_snapshot.py --workspace . --sync-codex-skill \
  --project-binding <update-snapshot-binding> --json
```

Progress is written to stderr, including clone/fetch, manifest verification, release validation,
staging, post-install validation, and completion. A 20-second heartbeat keeps long phases visible,
while JSON stdout remains valid. Each clone or fetch command has a 120-second default timeout and
each release or post-install validator has a 900-second default timeout. Override these explicit
bounds with `--network-timeout SECONDS` and `--validation-timeout SECONDS`; a timeout stops with an
actionable error instead of waiting indefinitely.

Official releases with an exact qualification attestation run the shipped focused client smoke
after provenance and all manifest hashes pass. Repository overrides, missing or invalid
attestations, and changed validator identities fail over to the complete local validator.
Successful validation is cached only by the exact release commit, validator hash, platform,
architecture, and Python identity so a post-install retry does not repeat unchanged validation.

The updater holds a recoverable user-local singleton lock for the exact workspace. Each attempt
writes a sanitized report beneath
`${CODEX_HOME:-~/.codex}/tool-shed/snapshot-upgrade-transactions/`; it contains stage durations,
validation mode/cache state, a bounded error class, and rollback outcome, never prompts, responses,
command output, credentials, secrets, or workspace paths. State files use mode `0600` where the
platform supports POSIX permissions.

Each final transaction also records a stable `TSU-*` issue code plus the updater version, protocol,
and script hash. Render `latest` or an exact transaction ID locally with
`scripts/snapshot_upgrade_report.py`; Markdown is the default and `--json` emits the equivalent
structured report. The command validates an allowlisted same-platform schema and cannot publish an
issue. Review its sanitized draft before separately authorizing any GitHub write.

For an existing update, the verified archive is the rollback authority after replacement. The
temporary retired snapshot is removed before workspace-wide post-install validators run, so old
Markdown and other retired files cannot contaminate validation of the selected release. A failure
whose recorded stage is release or post-install validation is reported as `TSU-501` even when the
underlying validator emits only an opaque nonzero-exit message.

Synchronization accepts only a missing target or a target that exactly matches a skill recorded
by a stable Tool Shed release. It keeps a timestamped backup under
`${CODEX_HOME:-~/.codex}/tool-shed-backups/`, outside the active skill-discovery directory, when
replacing an older release and refuses modified, unmanaged, non-directory, or symlinked targets.
The release packages compact historical skill digests so updater and direct guidance-only status
checks use the same offline identity set. Start a fresh Codex session after a change.

For an identified workspace, first run the released `project_identity.py identity` command with
operation `update-snapshot`, surface its project target capsule, and pass the returned binding.
The project identity is a tracked UUIDv4 record at `work/tool-shed-project.json`; tokens bind to
both that ID and the resolved root. New installations and legacy upgrades without the file create
it atomically after backup and before snapshot replacement. Existing identity is preserved
byte-for-byte. Malformed, duplicate, conflicting, foreign-project, or root-mismatched identity
fails closed, and rollback removes a newly created identity or restores the prior one.

Use the updater from a current released checkout outside the target project. This matters when an
older installed snapshot predates newer upgrade safeguards. The updater selects the remote release;
the target's stale in-snapshot updater is not a bootstrap authority. Releases declare a
`minimum_updater_protocol`; releases requiring a newer protocol cause legacy updater validation to
stop before snapshot mutation with the supported external-updater command. The current protocol 3
updater supplies its protocol explicitly and adds transactional work-tree convergence.

The frozen Hybrid SQLite state contract reserves protocol 4 for the first database-aware release.
That number is a future compatibility boundary, not a claim that the current protocol 3 updater can
move SQLite authority. Until protocol 4 is implemented, qualified, and declared by a release,
existing file-authority installs and upgrades continue to use protocol 3.

Provider guidance is auto-detected from existing marked instruction files. If none exists, Codex is
the backward-compatible default. Override or install multiple adapters with:

```text
python /path/to/current-release/scripts/update_snapshot.py --workspace . --provider claude-code \
  --project-binding <update-snapshot-binding>
python /path/to/current-release/scripts/update_snapshot.py --workspace . --provider all \
  --project-binding <update-snapshot-binding>
```

Codex convergence leaves one compact conditional Tool Shed routing block in root `AGENTS.md` and
removes legacy expanded Tool Shed blocks without changing owner-authored instruction text.
Directory presence alone does not activate Tool Shed. If the separately installed user-level
Codex skill differs from the workspace snapshot, installation emits
`TOOL_SHED_SKILL_MISMATCH`; use the workspace-local contract until the documented skill sync route
has made the copies exact.

From a downloaded Tool Shed checkout, the equivalent launchers are
`scripts/update-tool-shed.sh --workspace .` and
`scripts/update-tool-shed.ps1 --workspace .`. The Python updater is authoritative; the launchers
only select a native Python 3 runtime.

```text
ts: Ensure this workspace has the newest stable Tool Shed snapshot from:

https://github.com/PC-Redemption/tool_shed

First determine whether this workspace already has tool_shed/. If it has a valid disconnected
snapshot, update it. If tool_shed/ does not exist, perform a new installation. Do not assume which
path applies.

Use the highest remote tag matching exactly ^v[0-9]+\.[0-9]+\.[0-9]+$. Do not use main,
prerelease tags, or an untagged commit. Verified remote stable-tag selection is the sole authority.

This request authorizes changes only in the current workspace. Do not update another project,
host, or Tool Shed installation. Preserve owner-authored work, docs, source code, configuration,
planning content, and repository policy. The selected release's installer may make only its
documented deterministic work-topology, queue-projection, index, inbox-migration, provider-guidance,
and `.gitignore` convergence changes.

Resolve state and choose the path:

1. Resolve and display:
   - the stable Tool Shed project ID and project name, if already present
   - the exact workspace root
   - the exact intended workspace/tool_shed path
   - the parent Git repository root, if present
2. Record the initial Git status and whether root work/ exists. Preserve every existing work/ file.
3. Inspect tool_shed/ without mutating it:
   - If it does not exist, select NEW INSTALLATION.
   - If it exists, require it to be a real directory, not a symlink, not a Git submodule, and to
     contain no .git file or directory. If those checks pass, select EXISTING UPDATE.
   - If tool_shed/ exists but fails any boundary check, stop. Do not replace or repair it
     automatically.
4. Display the selected path before making changes.
   For an identified workspace, require the matching operation-specific project binding. A path
   outside the bound root is `WORKSPACE_MISMATCH`; mentioning it never authorizes a switch.
5. Confirm the parent repository ignores root /tool_shed/. If missing, append only that exact root
   entry to the repository-root .gitignore without replacing or reformatting existing content.

Select and verify the release:

6. Create a temporary directory using the host's native secure temporary-directory API. Clone the
   canonical repository with `core.autocrlf=false`, persist that setting in the temporary clone,
   and keep it disabled for tag checkout. Manifest hashes are byte-sensitive; host Git line-ending
   conversion must not rewrite the release snapshot.
7. Fetch tags and select the highest stable tag matching exactly:
   ^v[0-9]+\.[0-9]+\.[0-9]+$
8. For EXISTING UPDATE, detect the installed version and integrity state when possible. If its
   valid semantic version is newer than the selected tag, stop rather than downgrade. A downgrade
   requires separate explicit authorization.
9. Check out the selected tag in detached-HEAD state.
10. Verify:
    - SHED_VERSION.json is valid JSON.
    - shed_version equals the selected tag without its leading v.
    - release_tag equals the selected tag.
    - released_at is populated and valid ISO 8601.
    - the selected tag resolves to a tag commit:
      tag_commit="$(git rev-parse "${selected_tag}^{commit}")"
    - release_commit is populated and equals the tag commit's first parent:
      content_commit="$(git rev-parse "${tag_commit}^")"
    - git diff --name-only "$content_commit" "$tag_commit" reports exactly SHED_VERSION.json and
      no other path. Tool Shed intentionally uses a content commit followed by a provenance-only
      manifest commit; release_commit must not equal tag_commit.
    - python3 scripts/check_shed_version.py --shed . --local-only --strict
      --updater-protocol <current-protocol> passes.
    - the release qualification attestation matches the exact release commit and shipped validator
      and CI-workflow hashes, then `scripts/validate_snapshot_client.py` passes; or, for an
      overridden, unattested, or changed identity,
      `scripts/validate_tool_shed.py --profile full` passes.
    - When Codex is selected, compare the user-level skill against the selected skill and the exact
      skill hashes recorded by stable release manifests. Report drift even when synchronization was
      not requested. If synchronization was requested and the target is modified, unmanaged, or
      unsafe, stop before mutating the workspace snapshot.
    Stop without installing or replacing anything if any verification fails.

Prepare the disconnected snapshot:

11. Prepare the selected release in a temporary staging directory. Exclude:
    - .git/
    - work/
    - __pycache__/
    - .pytest_cache/
    - *.pyc
    - temporary validation output
    - other generated state
12. Verify the staged snapshot contains SHED_VERSION.json, selection.md, conventions.md,
    existing-projects.md, templates/, and scripts/, but contains no .git and no work/.
    Strict manifest validation must also prove that every versioned portable skill reference,
    provider registry, adapter script, and documentation file is present byte-for-byte.

If EXISTING UPDATE:

13. Show a concise summary of differences between the existing snapshot and staged release.
    Exclude .git, caches, temporary files, generated state, and any work/ directory. Never include
    the project's root work/ in the comparison.
14. Compute and report the exact mutation surface and estimated archive size, then create a
    timestamped repository-root backup archive:
    tool_shed.backup-YYYYMMDDTHHMMSSZ.tar
    Include the existing `tool_shed/`, `.gitignore` when mutable, selected provider instruction
    files, exact Tool Shed-owned work projections/directories, canonical and legacy Q&A migration
    trees, and absence markers needed to remove newly created paths during rollback. Do not include
    unrelated root `work/` content. The embedded manifest records included/excluded paths, hashes,
    source and target versions, updater protocol, timestamp, transaction identity, and estimated
    size. Reject unsafe members and verify every archived file.
    Policy-declared generated output such as `work/evidence/generated/` remains excluded when the
    selected installer cannot mutate it; record and hash that exclusion. If a future migration must
    mutate a normally excluded tree, expand the declared scope and report why before writing. Such
    a release declares `updater_mutation_paths` as a list of objects with a workspace-relative
    `path`, a `mode` of `file`, `tree`, or `directory-marker`, and a non-empty `reason`; reject
    malformed declarations and paths that escape the workspace.
    Before creating the backup, use the staged release's read-only campaign backfill plan to
    discover exact inbound Markdown artifact references that a numbered campaign rename must
    update. Add only those files to the declared mutation surface, record the old and new paths,
    and keep them under the same verified rollback transaction as the campaign tree.
15. Replace only the workspace's tool_shed/ directory with the staged snapshot at this stage. Keep
    the backup; the post-install transaction may then converge only the declared workspace surfaces.

If NEW INSTALLATION:

13. Confirm again that workspace/tool_shed does not exist.
14. Copy the staged snapshot to that exact path. Do not copy or merge anything into the project's
    root work/ directly.

Post-install verification for either path:

16. Confirm the installed tool_shed/ is a real directory, contains no .git and no work/, is not a
    submodule, and is ignored by the parent repository.
17. Run, when present in the installed release:
    - python3 tool_shed/scripts/install_into_workspace.py . --provider <detected>
    - read-only campaign validation; when it reports legacy numbering or filenames, accept exact
      supported legacy projections (including a valid empty pre-numbering queue), preview numbered
      renames and inbound artifact-reference updates, run the exact-token guarded campaign
      convergence inside the release-declared and dynamically planned backup scope, then regenerate
      indexes
    - python3 tool_shed/scripts/workspace_preflight.py --workspace . --json
    - python3 tool_shed/scripts/check_work_tree.py --workspace . --json
    - python3 tool_shed/scripts/check_stale_paths.py --workspace .
    - python3 tool_shed/scripts/review_work_state.py --workspace .
    - python3 tool_shed/scripts/check_shed_version.py --shed tool_shed --local-only --strict
      --updater-protocol <current-protocol> --snapshot
18. Full installation may append or replace marked Tool Shed blocks, update `.gitignore`, migrate
    legacy Q&A paths, create missing canonical work directories, and regenerate indexes. It must
    preserve owner-authored content byte-for-byte, report structural convergence explicitly, and
    never silently overwrite a migration collision.
19. Surface the workspace profile, effective risk budgets, policy sources, preflight findings, and
    reconciliation findings for review. Do not automatically rewrite project planning, relocate
    evidence, or create Level 2 onboarding artifacts unless separately requested.
    - If preflight recommends migration, report the exact prepare command using an output path
      outside the repository.
    - Do not run migration apply during installation or update.
    - Treat invalid `.tool-shed-policy.json` evidence policy as manual follow-up, not permission to
      replace or repair repository policy.
20. When `--sync-codex-skill` was requested, stage and verify the selected released skill beside
    the user-level target. For an exact older released skill, rename it to a timestamped backup
    outside the active `skills/` directory;
    for a missing target, install without a backup. Verify byte-for-byte equality after replacement
    and write a verified sidecar ownership manifest with versions, timestamp, transaction identity,
    and tree hash. Restore the backup and remove its sidecar if synchronization fails. Never merge
    skill directories. Report that a fresh Codex session is required.

Failure handling:

21. For EXISTING UPDATE, if replacement or post-install verification fails:
    - remove only the failed replacement and affected migrated workspace paths
    - report the compact failed transaction stage in JSON and human-readable output so an operator
      can distinguish release selection, staging, campaign planning, backup, replacement,
      post-install validation, and rollback failures without retaining raw logs
    - restore or remove exactly the paths and absence markers declared by the verified backup
      manifest
    - restore every selected provider instruction file byte-for-byte, removing only files created
      by the failed guidance refresh
    - verify the restored snapshot
    - report the failure and restoration result
22. For NEW INSTALLATION, if post-install verification fails:
    - remove only the newly installed tool_shed/ directory
    - restore or remove selected provider instruction files using the pre-install capture
    - restore the exact declared pre-install work projections, Q&A migration paths, provider files,
      directory markers, and `.gitignore` state from the temporary verified transaction backup
    - report any remaining empty directories for manual review

Success report:

23. After every installation, convergence check, optional skill synchronization, and validation
    succeeds, inventory canonical updater-owned workspace and user-skill backups. Verify structure,
    ownership manifest, versions, paths, and content before classification. Protect the current
    immediate rollback archive and retain the newest two verified archives by default, including
    the protected archive. Prune only older verified updater-owned archives. Preserve and report
    unknown, manually named, malformed, unsupported, symlinked, or unverifiable candidates. Never
    prune on failure or rollback. Backup deletion is irreversible.
    - `--backup-retention COUNT` overrides the total retained count and cannot be below one.
    - `--no-prune-backups` performs classification without deletion.
    - `--prune-preview` performs only read-only workspace and user-skill classification; it does
      not fetch, install, synchronize, or delete.
    - `.tool-shed-policy.json` may set `backup_policy.retention`; an explicit CLI value wins.
    - A byte-identical current-version check creates no redundant archive.
24. Report:
    - whether NEW INSTALLATION or EXISTING UPDATE was performed
    - previous local version and integrity state, when applicable
    - installed version and selected release tag
    - tag commit and verified content release_commit
    - exact backup path, when applicable
    - declared mutation scope, exclusions, and embedded manifest metadata
    - temporary-clone and installed-snapshot validation results
    - Git status changes relative to the initial status
    - confirmation that owner-authored work content was preserved, whether Tool Shed-owned work
      topology or projections changed, and whether the final work tree passed structural checks
    - auto-detected or explicitly selected provider adapters and guidance-refresh result
    - workspace profile, adaptive risk budgets, and their policy sources
    - preflight or reconciliation warnings and recommended mitigation level
    - user-level Codex skill state, exact path, synchronization result, backup path, and restart
      requirement when Codex is selected
    - configured retention source, protected/retained/removable/pruned/unknown backup sets,
      cleanup errors, and bytes reclaimed for both workspace and user-skill backups
    - remaining manual follow-up

Do not commit, push, manually delete unknown or unverifiable recovery material, update another
workspace, perform a fleet rollout, downgrade a newer snapshot, or create project planning
artifacts without separate explicit authorization. Normal verified retention is part of an
explicit updater invocation unless `--no-prune-backups` is used.
```

Remote stable tags and the selected tag's two-commit release provenance are authoritative.

For standalone verification rather than an updater invocation, replace `--updater-protocol ...`
with `--verification-only --snapshot`. Validation inside a disconnected snapshot skips
canonical-repository work indexing and reconciliation and verifies that snapshot files remain
unchanged.
