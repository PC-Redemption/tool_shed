# Install or Update Tool Shed in One Workspace

Use this single workspace-agent request from a project root. The agent first determines whether the workspace has
a disconnected `tool_shed/` snapshot, then performs either a guarded update or a guarded new
installation.

The supported cross-platform command is:

```text
python /path/to/current-release/scripts/update_snapshot.py --workspace .
```

Use the updater from a current released checkout outside the target project. This matters when an
older installed snapshot predates newer upgrade safeguards. The updater selects the remote release;
the target's stale in-snapshot updater is not a bootstrap authority.

Provider guidance is auto-detected from existing marked instruction files. If none exists, Codex is
the backward-compatible default. Override or install multiple adapters with:

```text
python /path/to/current-release/scripts/update_snapshot.py --workspace . --provider claude-code
python /path/to/current-release/scripts/update_snapshot.py --workspace . --provider all
```

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
host, or Tool Shed installation. Never overwrite, move, delete, archive, or rewrite the project's
work/, docs/, source code, configuration, planning artifacts, or repository policy.

Resolve state and choose the path:

1. Resolve and display:
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
    - python3 scripts/check_shed_version.py --shed . --local-only --strict passes.
    - python3 scripts/validate_tool_shed.py passes.
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
14. Create a timestamped repository-root backup archive:
    tool_shed.backup-YYYYMMDDTHHMMSSZ.tar
    Confirm it contains only the existing tool_shed/ snapshot and no project work/.
15. Replace only the workspace's tool_shed/ directory with the staged snapshot. Keep the backup.

If NEW INSTALLATION:

13. Confirm again that workspace/tool_shed does not exist.
14. Copy the staged snapshot to that exact path. Do not copy or merge anything into the project's
    root work/ directly.

Post-install verification for either path:

16. Confirm the installed tool_shed/ is a real directory, contains no .git and no work/, is not a
    submodule, and is ignored by the parent repository.
17. Run, when present in the installed release:
    - python3 tool_shed/scripts/install_into_workspace.py . --guidance-only --provider <detected>
    - python3 tool_shed/scripts/workspace_preflight.py --workspace . --json
    - python3 tool_shed/scripts/check_stale_paths.py --workspace .
    - python3 tool_shed/scripts/review_work_state.py --workspace .
    - python3 tool_shed/scripts/check_shed_version.py --shed tool_shed --local-only --strict
18. Guidance-only installation may append or replace marked Tool Shed blocks in the selected
    provider instruction files. It must preserve owner-authored instruction content and leave
    `.gitignore`, `work/`, indexes, and the Q&A inbox byte-for-byte unchanged.
19. Surface the workspace profile, effective risk budgets, policy sources, preflight findings, and
    reconciliation findings for review. Do not automatically rewrite project planning, relocate
    evidence, or create Level 2 onboarding artifacts unless separately requested.
    - If preflight recommends migration, report the exact prepare command using an output path
      outside the repository.
    - Do not run migration apply during installation or update.
    - Treat invalid `.tool-shed-policy.json` evidence policy as manual follow-up, not permission to
      replace or repair repository policy.

Failure handling:

20. For EXISTING UPDATE, if replacement or post-install verification fails:
    - remove only the failed replacement
    - restore tool_shed/ from the backup archive
    - restore every selected provider instruction file byte-for-byte, removing only files created
      by the failed guidance refresh
    - verify the restored snapshot
    - report the failure and restoration result
21. For NEW INSTALLATION, if post-install verification fails:
    - remove only the newly installed tool_shed/ directory
    - restore or remove selected provider instruction files using the pre-install capture
    - never remove or roll back work/
    - report any remaining empty directories for manual review

Success report:

22. Report:
    - whether NEW INSTALLATION or EXISTING UPDATE was performed
    - previous local version and integrity state, when applicable
    - installed version and selected release tag
    - tag commit and verified content release_commit
    - exact backup path, when applicable
    - temporary-clone and installed-snapshot validation results
    - Git status changes relative to the initial status
    - confirmation that root work/ and work/index files were unchanged
    - auto-detected or explicitly selected provider adapters and guidance-refresh result
    - workspace profile, adaptive risk budgets, and their policy sources
    - preflight or reconciliation warnings and recommended mitigation level
    - remaining manual follow-up

Do not commit, push, delete an update backup, update another workspace, perform a fleet rollout,
downgrade a newer snapshot, or create project planning artifacts without separate explicit
authorization.
```

Remote stable tags and the selected tag's two-commit release provenance are authoritative.
