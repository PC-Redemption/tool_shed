# Releasing Tool Shed

Tool Shed snapshots are disconnected from Git. A release must therefore carry enough manifest
information to identify its shipped content without creating a circular commit dependency.

## Provenance Model

`release_commit` means the Git commit containing all shipped Tool Shed content immediately before
the provenance-only manifest commit. `release_tag` identifies the final provenance commit.

`SHED_VERSION.json` is intentionally excluded from its own `content_hashes`, so adding provenance
does not change the content commit it identifies.

`minimum_updater_protocol` declares the oldest updater lifecycle that may install the release.
Protocol 2 adds transactional provider guidance and strict disconnected-snapshot boundaries.
Protocol 3 adds transactional work-tree convergence, affected-workspace rollback coverage, and an
explicit structural verification step. Do not lower this field to preserve compatibility with an
updater that cannot satisfy the release lifecycle.

Published provenance also records `release_qualification`: the exact content commit, full
validator hash, focused client-smoke hash, and hashes of both comprehensive CI workflows. The
updater accepts the focused path only from the canonical repository when every identity matches.
Overrides, unattested releases, and any changed identity run full local validation instead.

## Release Procedure

1. Confirm the work tree contains only the intended release scope.
2. Select and record the new `MAJOR.MINOR.PATCH` version.
3. Refresh the unpublished manifest:

   ```bash
   python3 scripts/update_shed_manifest.py \
     --write \
     --version MAJOR.MINOR.PATCH \
     --allow-same-version \
     --notes "Release summary"
   ```

   Use `--allow-same-version` only when the version was already selected in the current unpublished
   work tree. The write also refreshes `adapters/codex-skill-releases.json` from valid stable tags
   before hashing release content; review and commit that catalog as shipped content.

4. Run `python3 scripts/validate_tool_shed.py --profile release --max-seconds 60`. Confirm its
   repository-policy coverage includes tracked `work/`, stale root ignores, documented exceptions,
   unrelated nested rules, and ignored `/tool_shed/` with tracked `work/`. Release qualification
   also verifies every tracked `work/evidence/bootstrap-closure-*.json` manifest with
   `--require-final`; an open gate, pending evidence, incomplete migration item, or incomplete
   upgrade target blocks the release instead of being waived by campaign completion.
5. Commit all shipped content, including the manifest with null `release_commit` and `released_at`.
6. Capture that content commit:

   ```bash
   git rev-parse HEAD
   ```

7. Push the frozen content commit on its branch. Wait for the `Validate` push workflow whose
   `head_sha` exactly equals `CONTENT_COMMIT_SHA`; its complete Ubuntu/Windows and Python 3.11/3.x
   matrix must succeed. A pull-request run or a successful run for another SHA is insufficient.
   Stop before provenance or tagging if that exact run is absent, incomplete, skipped, or failed.
8. Populate provenance without changing the selected version:

   ```bash
   python3 scripts/update_shed_manifest.py \
     --write \
     --version MAJOR.MINOR.PATCH \
     --allow-same-version \
     --release-commit CONTENT_COMMIT_SHA \
     --release-tag vMAJOR.MINOR.PATCH \
     --released-at YYYY-MM-DDTHH:MM:SSZ \
     --notes "Release summary"
   ```

9. Run the strict local version and manifest checks. The exact content commit was already qualified;
   do not repeat its unit cases after changing only provenance:

   ```bash
   python3 scripts/check_shed_version.py --shed . --local-only --strict --verification-only
   python3 scripts/update_shed_manifest.py --check
   ```

10. Commit only `SHED_VERSION.json` as the provenance commit.
11. Tag the provenance commit:

   ```bash
   git tag -a vMAJOR.MINOR.PATCH -m "Tool Shed vMAJOR.MINOR.PATCH"
   ```

12. Push the provenance commit and tag. The `Publish GitHub Release` workflow verifies the exact
    two-commit provenance, requires the successful `Validate` push run for the recorded content
    commit, and then creates an idempotent, non-draft GitHub Release marked latest without repeating
    the already-qualified test cases.
13. Verify both publication surfaces. The raw manifest and GitHub Release must report the same tag;
    a tag-only publication is incomplete:

    ```bash
    python3 scripts/check_shed_version.py --shed .
    gh release view vMAJOR.MINOR.PATCH \
      --repo PC-Redemption/tool_shed \
      --json tagName,isDraft,isPrerelease,publishedAt,url
    ```

    If automation is unavailable after the tag's full validation succeeds, create the missing
    Release object explicitly and then run the same verification:

    ```bash
    python3 scripts/prepare_github_release.py \
      --repository . \
      --tag vMAJOR.MINOR.PATCH \
      --notes-file release-notes.md
    gh release create vMAJOR.MINOR.PATCH \
      --repo PC-Redemption/tool_shed \
      --verify-tag \
      --latest \
      --title "Tool Shed vMAJOR.MINOR.PATCH" \
      --notes-file release-notes.md
    ```

Do not reuse a published version. Do not populate `release_commit` from a dirty work tree. Never
describe a tag as fully published until its GitHub Release object is verified. Updating workspace
snapshots remains a separately authorized operation.
