# Publish and verify Tool Shed v0.22.0

Status: working
Type: campaign
Updated: 2026-08-18
Next Action: execute the campaign completion gate
Campaign ID: publish-and-verify-tool-shed-v0-22-0
Campaign Number: 027
Outcome: Ship one verified Tool Shed v0.22.0 release that contains and accounts for every repository update since v0.21.0: the compact public operator workflows and follow-up layout/cache fix, upgrade campaign-number convergence, public help links, targeted and wildcard queue batches, fail-closed workspace identity and routing, nested cycle ownership, and the workspace doctor; freeze the exact candidate, push and publish it traceably, verify canonical release, updater, and public documentation state, and close issues #34 through #39 only when each issue's acceptance evidence is satisfied.
Primary Focus Areas: qualification-release
Supporting Focus Areas: snapshot-delivery, provider-portability
Depends On: compact-tool-shed-site-and-publish-guided-workflows, harden-upgrade-campaign-number-convergence, link-public-help-site-from-help-responses, extend-next-with-targeted-and-wildcard-batches, define-nested-cycles-and-owning-transitions, fail-closed-on-cross-workspace-routing, add-workspace-wide-ts-doctor-command
Decision: none
Detour For: none
Return To: none
Completion Gate: Every commit and tracked change from v0.21.0 through the exact frozen candidate is inventoried and attributable to the compact public workflow guide plus its layout/cache follow-up, campaign-number upgrade convergence, public help links, targeted and wildcard queue batches, fail-closed workspace identity and routing, nested cycle ownership, or the workspace doctor; campaigns 024, 025, 026, 028, 029, 030, and 031 retain passing completion evidence; release qualification passes on that exact candidate; SHED_VERSION.json records the matching commit, v0.22.0 tag, and release timestamp; main is pushed without unrelated changes; GitHub Actions release checks pass; the GitHub v0.22.0 release and canonical manifest are reachable and internally consistent; ts.rookaro.com still serves all verified post-v0.21.0 documentation behavior; a published upgrade from v0.21.0 to v0.22.0 verifies the included migration, identity, queue, cycle, help, and doctor behavior; and issues #34, #35, #36, #37, #38, and #39 are closed with concise acceptance-evidence links.
Completion Evidence: none
Disposition: none

## Request

Publish one v0.22.0 candidate containing every repository update after the v0.21.0 tag through the
release freeze. At freeze time, inventory the exact `git log` and tracked `git diff` from
`v0.21.0` to the candidate and account for every commit and path. The intended update set is:

- campaign 024's compact public operator workflows and work-level customization guide, including
  the follow-up reference-command alignment and asset cache busting;
- campaign 025's campaign-number upgrade convergence for
  [issue #35](https://github.com/PC-Redemption/tool_shed/issues/35);
- campaign 026's universal public help links for
  [issue #36](https://github.com/PC-Redemption/tool_shed/issues/36);
- campaign 028's targeted, stable-reference, and wildcard `ts: next` batch selection;
- campaign 030's fail-closed workspace identity and mutation routing for
  [issue #38](https://github.com/PC-Redemption/tool_shed/issues/38);
- campaign 031's workspace-wide read-only doctor for
  [issue #39](https://github.com/PC-Redemption/tool_shed/issues/39); and
- campaign 029's nested cycles and shared Cycle State Capsule for
  [issue #37](https://github.com/PC-Redemption/tool_shed/issues/37).

Campaign 024 already implemented and deployed the public work-level customization guide for
[issue #34](https://github.com/PC-Redemption/tool_shed/issues/34). Preserve every campaign's
acceptance evidence and do not silently omit a later commit that lands before the candidate freezes.

Follow the repository release runbook and protected-environment controls. Re-run release
qualification on the exact frozen commit, update release provenance, push, create the v0.22.0 tag
and GitHub Release through the supported release workflow, verify canonical manifest and release
artifacts, verify the already-deployed public site still matches the intended documentation, and
exercise the published updater path from v0.21.0. Verify the queue-batch, workspace-identity,
cycle-state, public-help, and doctor behavior from the published release. Close each GitHub issue
only after its own acceptance evidence is present; do not treat release publication alone as proof
that any issue from #34 through #39 is fixed.

## Completion Check

Every commit and tracked change from v0.21.0 through the exact frozen candidate is inventoried and attributable to the compact public workflow guide plus its layout/cache follow-up, campaign-number upgrade convergence, public help links, targeted and wildcard queue batches, fail-closed workspace identity and routing, nested cycle ownership, or the workspace doctor; campaigns 024, 025, 026, 028, 029, 030, and 031 retain passing completion evidence; release qualification passes on that exact candidate; SHED_VERSION.json records the matching commit, v0.22.0 tag, and release timestamp; main is pushed without unrelated changes; GitHub Actions release checks pass; the GitHub v0.22.0 release and canonical manifest are reachable and internally consistent; ts.rookaro.com still serves all verified post-v0.21.0 documentation behavior; a published upgrade from v0.21.0 to v0.22.0 verifies the included migration, identity, queue, cycle, help, and doctor behavior; and issues #34, #35, #36, #37, #38, and #39 are closed with concise acceptance-evidence links.
