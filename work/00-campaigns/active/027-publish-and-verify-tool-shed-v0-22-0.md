# Publish and verify Tool Shed v0.22.0

Status: queued
Type: campaign
Updated: 2026-08-18
Next Action: execute when selected from the active campaign queue
Campaign ID: publish-and-verify-tool-shed-v0-22-0
Campaign Number: 027
Outcome: Finish GitHub issue #34 and ship the verified fixes for issues #35 and #36 by freezing the complete v0.22.0 candidate, pushing it, publishing the traceable GitHub release, verifying canonical release and public documentation state, and closing each issue only when its acceptance evidence is satisfied.
Primary Focus Areas: qualification-release
Supporting Focus Areas: snapshot-delivery, provider-portability
Depends On: compact-tool-shed-site-and-publish-guided-workflows, harden-upgrade-campaign-number-convergence, link-public-help-site-from-help-responses
Decision: none
Detour For: none
Return To: none
Completion Gate: The completed public-site campaign and both issue-fix campaigns are verified; release qualification passes on the exact frozen candidate; SHED_VERSION.json records matching commit, v0.22.0 tag, and release timestamp; main is pushed without unrelated changes; the GitHub Actions release checks pass; the GitHub v0.22.0 release and canonical manifest are reachable and internally consistent; ts.rookaro.com still serves the verified customization and help content; upgrade behavior is verified against the published release; and issues #34, #35, and #36 are closed with concise evidence links.
Completion Evidence: none
Disposition: none

## Request

Complete the release-pending portion of
[GitHub issue #34](https://github.com/PC-Redemption/tool_shed/issues/34) after campaigns 025 and 026
finish. Campaign 024 already implemented and deployed the public work-level customization guide;
the remaining issue #34 gate is a pushed, published, and verified v0.22.0 release. Include the
verified upgrade-convergence and public-help-link changes for
[issue #35](https://github.com/PC-Redemption/tool_shed/issues/35) and
[issue #36](https://github.com/PC-Redemption/tool_shed/issues/36) in the same qualified candidate.

Follow the repository release runbook and protected-environment controls. Re-run release
qualification on the exact frozen commit, update release provenance, push, create the v0.22.0 tag
and GitHub Release through the supported release workflow, verify canonical manifest and release
artifacts, verify the already-deployed public site still matches the intended documentation, and
exercise the published updater path. Close each GitHub issue only after its own acceptance evidence
is present; do not treat release publication alone as proof that #35 or #36 is fixed.

## Completion Check

The completed public-site campaign and both issue-fix campaigns are verified; release qualification passes on the exact frozen candidate; SHED_VERSION.json records matching commit, v0.22.0 tag, and release timestamp; main is pushed without unrelated changes; the GitHub Actions release checks pass; the GitHub v0.22.0 release and canonical manifest are reachable and internally consistent; ts.rookaro.com still serves the verified customization and help content; upgrade behavior is verified against the published release; and issues #34, #35, and #36 are closed with concise evidence links.
