# Updating an Existing Tool Shed Snapshot

Use this Codex request from the root of the one project whose disconnected `tool_shed/` snapshot
should be updated. It authorizes a single-workspace update only.

```text
ts: Update only this workspace's disconnected tool_shed/ snapshot from:

https://github.com/PC-Redemption/tool_shed

Use the highest remote tag matching exactly ^v[0-9]+\.[0-9]+\.[0-9]+$. Do not use main,
prerelease tags, or an untagged commit. The expected newest stable tag is currently v0.3.1, but
verify remote tags before proceeding.

This request authorizes replacement only of this workspace's tool_shed/ snapshot. Do not update
other projects, hosts, installations, work/, docs/, source code, configuration, or planning
artifacts except for installer-generated workspace guidance, required root Git ignore entries,
and regenerated work indexes described below.

Preflight and boundaries:

1. Resolve and display:
   - the exact workspace root
   - the exact existing tool_shed/ path
   - the parent Git repository root, if present
2. Confirm tool_shed/:
   - exists
   - is a real directory, not a symlink
   - is not a Git submodule
   - contains no .git file or directory
   If any check fails, stop without modifying anything.
3. Record the initial Git status and existing Tool Shed version/integrity state when detectable.
4. Never copy, replace, move, delete, archive, or rewrite the project's work/ directory.
5. Confirm the parent repository ignores root /tool_shed/. If missing, append only that exact root
   entry to the repository-root .gitignore without replacing or reformatting existing content.

Release selection and verification:

6. Create a temporary directory with mktemp -d and clone the canonical repository there.
7. Fetch tags and select the highest stable tag matching exactly:
   ^v[0-9]+\.[0-9]+\.[0-9]+$
8. If the installed snapshot has a valid semantic version newer than the selected tag, stop and
   report that applying the tag would be a downgrade. Do not downgrade without separate explicit
   authorization.
9. Check out the selected tag in detached-HEAD state.
10. Verify:
    - SHED_VERSION.json is valid JSON.
    - shed_version equals the selected tag without its leading v.
    - release_tag equals the selected tag.
    - release_commit is populated and equals git rev-parse "${selected_tag}^{commit}".
    - released_at is populated and valid ISO 8601.
    - python3 scripts/check_shed_version.py --shed . --local-only --strict passes.
    - python3 scripts/validate_tool_shed.py passes.
    Stop without replacing the snapshot if any verification fails.

Review and backup:

11. Show a concise summary of differences between the existing snapshot and selected release.
    Exclude .git, caches, temporary files, generated state, and any work/ directory from the
    comparison. Do not include the project's root work/ in the comparison.
12. Create a timestamped repository-root backup archive:
    tool_shed.backup-YYYYMMDDTHHMMSSZ.tar
    Confirm it contains only the existing tool_shed/ snapshot and no project work/.
13. Prepare the replacement in a sibling staging directory. Remove only staging-copy metadata and
    generated state:
    - .git/
    - __pycache__/
    - .pytest_cache/
    - *.pyc
    - temporary validation output
    - any work/ directory contained inside the cloned Tool Shed repository
14. Verify the staged replacement has no .git and no work/ directory.

Replacement and rollback:

15. Replace only the workspace's tool_shed/ directory. Preserve the backup until all verification
    succeeds.
16. Run, when present in the installed release:
    - python3 tool_shed/scripts/install_into_workspace.py .
    - python3 tool_shed/scripts/workspace_preflight.py --workspace .
    - python3 tool_shed/scripts/update_work_index.py --workspace .
    - python3 tool_shed/scripts/check_stale_paths.py --workspace .
    - python3 tool_shed/scripts/review_work_state.py --workspace .
    - python3 tool_shed/scripts/check_shed_version.py --shed tool_shed --local-only --strict
17. Surface reconciliation and preflight findings for review. Do not automatically rewrite project
    planning or move/delete evidence.
18. If replacement or post-install verification fails:
    - remove only the failed replacement
    - restore tool_shed/ from the backup archive
    - verify the restored snapshot
    - report the failure and restoration result

Success report:

19. Report:
    - previous local version and integrity state, if detectable
    - installed version and selected release tag
    - verified release commit
    - exact backup archive path
    - temporary validation results
    - post-install validation results
    - Git status changes relative to the initial status
    - changed tracked work/index files
    - reconciliation or preflight warnings
    - remaining manual follow-up

Do not commit, push, delete the backup, update another snapshot, perform a fleet rollout, or
downgrade a newer local snapshot without separate explicit authorization.
```

The expected tag is only a sanity check. Remote stable tags and the selected tag's release
provenance remain authoritative.
