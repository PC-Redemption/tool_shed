# Historical Campaign External-Claim Evidence Backfill

Status: qualified
Type: evidence
Updated: 2026-08-28
Scope: Doctor external-evidence findings for 17 completed campaigns

## Outcome

The 17 completed campaigns identified by Doctor now have one durable, tracked audit record. This
record separates four kinds of statements that the keyword-based Doctor check had grouped together:

- externally reobserved release, workflow, issue, or route facts;
- historical local-runtime observations that cannot be reproduced as the same past environment;
- repository qualification results preserved by the completion commit or a purpose-built evidence
  record; and
- explicit statements that no release, deployment, production publication, or live database was
  performed.

This backfill does not claim that every old runtime environment is still running or that every old
test suite was replayed. It makes the historical basis and any limitation durable instead of
silently treating a completion sentence as current external truth.

## Reobservation Envelope

Read-only observations on 2026-08-28 established:

- GitHub Validate run `32057123667` remains successful for commit
  `b0419aeb692e2a499dc0374b5c248663281b1494`.
- GitHub runs `32179421159`, `32179423039`, and `32179423109` remain successful for commit
  `d4cef7999dce636f36e8c33f806cd70e467d05fa`.
- GitHub Release `v0.23.0` remains published, non-draft, and non-prerelease.
- GitHub issues `#34`, `#35`, `#36`, and `#40` remain closed.
- `https://ts.rookaro.com/` returned HTTP 200 with `X-Rookaro-Route: ts.rookaro.com`.

The current route observation establishes present reachability only. It does not assert that the
current site bytes equal a 2026-08-17 build.

## Campaign Reconciliation

| Campaign | Durable basis | Classification and limitation |
| --- | --- | --- |
| `012-unify-dependency-aware-campaign-readiness` | Completion commit `611f727c6903ac1279ff30e5d19a4fa4101a8b70` | Repository qualification. The runtime keywords occur in an explicit statement that deployment and browser stages were inapplicable; no external runtime success was claimed. |
| `021-standardize-campaign-numbering-during-tool-shed-upgrades` | Completion commit `611f727c6903ac1279ff30e5d19a4fa4101a8b70`; `work/evidence/evidence-tool-shed-0-22-0-release-and-upgrade.md` | Repository and disposable-snapshot qualification, later carried by the independently recorded v0.22.0 release. The campaign itself did not claim a production deployment. |
| `022-publish-tool-shed-documentation-site-at-ts-rookaro-com` | Completion commit `1d2bb93f0bcbe966b79456a13a335fd0fcdfeb64`; successful GitHub run `32057123667`; current HTTP 200 route observation | Historical deployment is supported by the frozen completion record and GitHub run; the route is currently reachable. The original container instance, exact old bytes, and old browser session were not replayed. |
| `024-compact-tool-shed-site-and-publish-guided-workflows` | Completion commit `28d647157a5da0e24ffcb50888bb6be09ffbf19d`; closed issue `#34`; `work/evidence/evidence-tool-shed-0-22-0-release-and-upgrade.md` | Historical build/browser/route claims are preserved by the completion commit and subsequent release record. Current reachability was reobserved, but the old hashes and browser session were not replayed. |
| `025-harden-upgrade-campaign-number-convergence` | Completion commit `33eb452c8c38c79a02609397f1e2353def76d2f4`; closed issue `#35`; `work/evidence/evidence-tool-shed-0-22-0-release-and-upgrade.md` | Repository and disposable-updater qualification, later published in v0.22.0. The historical test execution was not replayed during this audit. |
| `026-link-public-help-site-from-help-responses` | Completion commit `33eb452c8c38c79a02609397f1e2353def76d2f4`; closed issue `#36`; `work/evidence/evidence-tool-shed-0-22-0-release-and-upgrade.md` | Repository qualification and later published-release verification. The completion record did not claim that this campaign itself performed a deployment. |
| `032-make-workflow-cycles-first-class-site-concept` | Completion commit `9e2afc30acddbaa7f4d840edc5189b6b84e6cfa9`; successful v0.23.0 workflows and published release listed above | Repository/site-build qualification later shipped in v0.23.0. Its completion sentence explicitly says production publication was not performed or claimed. |
| `033-update-github-actions-dependencies-before-node-20-removal` | Completion commit `8966a2ebd0ab87f09cf0da9a8e86d0bc28041ed2`; reobserved runs `32179421159`, `32179423039`, `32179423109`; published v0.23.0 release; closed issue `#40` | External release and workflow facts were independently reobserved. Local qualification was not replayed. |
| `044-app-server-explicit-command-opt-in` | Completion commit `c9d29f63355554a049854745c273fbd48fcf0522` | Historical local Codex 0.144.6 observation preserved by the frozen completion record. That exact past host/runtime session is not reproducible; the record explicitly says no release or deployment occurred. |
| `054-harden-app-server-camp-verification-handoff` | Completion commit `5f4ee1e04b0d27fe9257b1f2a95320e8b96dc731` | Repository qualification. Runtime keywords occur in the explicit no-release/no-deployment boundary, not an external success claim. |
| `063-repair-project-scoped-app-server-dispatch` | `work/evidence/evidence-project-scoped-app-server-dispatch-v0-29-2.md` | Purpose-built release, Core transaction, executable identity, and project-scoped consumer evidence already exists. |
| `099-consolidate-validation-profiles-and-contracts` | Completion commit `3d4563c872f1963f82e0faf288feab1140fbfdc0` | Repository performance and qualification. “release” names the release validation profile; it is not a publication claim. Historical timings were not replayed. |
| `100-replace-camp-version-gate-with-operator-runtime-trust` | Completion commit `840be4b3445adec09106c62ec1d111166b2d42cf`; `work/evidence/evidence-operator-trust-camp-runtime-enforcement.md` | Repository qualification, with the operator-runtime contract subsequently covered by purpose-built boundary evidence. No external deployment was claimed. |
| `103-establish-hybrid-bootstrap-closure-and-design-contract` | `work/evidence/evidence-hybrid-sqlite-g1-design-frozen.md` | Purpose-built G1 design and qualification evidence. Runtime keywords refer to still-open release gates, not completed external publication. |
| `104-implement-minimum-sqlite-operational-substrate` | `work/evidence/evidence-hybrid-sqlite-substrate.md` | Purpose-built G2 substrate evidence. The completion sentence explicitly says no live database, deployment, or release occurred. |
| `105-implement-and-qualify-hpt2-closed-loop-vertical-slice` | `work/evidence/evidence-hybrid-sqlite-hpt2-parity.md`; `work/evidence/evidence-hybrid-sqlite-efficiency.md` | Purpose-built parity and efficiency evidence. The completion sentence explicitly says no live database, deployment, release, or client mutation occurred. |
| `106-rehearse-and-convert-maintainer-to-hybrid-state` | `work/evidence/evidence-hybrid-sqlite-maintainer-conversion.md` | Purpose-built no-data-loss live maintainer conversion, recovery, checkpoint, and qualification evidence. It explicitly excludes publication, release, skill synchronization, and client mutation. |

## Audit Rule

A future reviewer may strengthen this record with a newer purpose-built evidence file, but must not
turn a historical local observation into a current-runtime assertion without a new observation.
Doctor may treat the listed claims as durably referenced; it must continue to report
`external_truth_observed: false` for its repository-only scan because this file is a historical
audit artifact, not a live external probe.
