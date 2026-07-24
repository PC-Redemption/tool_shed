# Releasing Tool Shed

Tool Shed snapshots are disconnected from Git. A release must therefore carry enough manifest
information to identify its shipped content without creating a circular commit dependency.

## Provenance Model

`release_commit` means the Git commit containing all shipped Tool Shed content immediately before
the provenance-only manifest commit. `release_tag` identifies the final provenance commit.

`SHED_VERSION.json` is intentionally excluded from its own `content_hashes`, so adding provenance
does not change the content commit it identifies.

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
   work tree.

4. Run `python3 scripts/validate_tool_shed.py`.
5. Commit all shipped content, including the manifest with null `release_commit` and `released_at`.
6. Capture that content commit:

   ```bash
   git rev-parse HEAD
   ```

7. Populate provenance without changing the selected version:

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

8. Run full validation again and commit only `SHED_VERSION.json` as the provenance commit.
9. Tag the provenance commit:

   ```bash
   git tag -a vMAJOR.MINOR.PATCH -m "Tool Shed vMAJOR.MINOR.PATCH"
   ```

10. Push the branch and tag, then verify that the canonical raw manifest reports the expected
    version, content commit, tag, timestamp, and hashes.

Do not reuse a published version. Do not populate `release_commit` from a dirty work tree. Updating
workspace snapshots remains a separately authorized operation.
