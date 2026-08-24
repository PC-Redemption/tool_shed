# Make stable snapshot upgrades fast, observable, and retry-safe

Status: blocked
Type: campaign
Updated: 2026-08-24
Next Action: resolve blocker or decision: The frozen unpublished 0.27.0 candidate, including the final sanitized issue reporter, passes focused and full local validation; native Windows qualification now requires separate authorization to push a qualification branch. A branch push does not authorize a tag, GitHub Release, installed-skill synchronization, or Bactron Core upgrade.
Campaign ID: make-stable-snapshot-upgrades-fast-observable-and-retry-safe
Campaign Number: 053
Outcome: Reduce normal stable-release snapshot upgrade latency and eliminate opaque or repeated validation delays while preserving exact release provenance, content integrity, dirty-work protection, verified backup and rollback, provider convergence, Codex skill synchronization, and fail-closed post-install checks, while producing privacy-safe maintainer-ready issue evidence when an upgrade finds a problem.
Primary Focus Areas: snapshot-delivery
Supporting Focus Areas: qualification-release, workspace-safety
Depends On: none
Decision: The frozen unpublished 0.27.0 candidate, including the final sanitized issue reporter, passes focused and full local validation; native Windows qualification now requires separate authorization to push a qualification branch. A branch push does not authorize a tag, GitHub Release, installed-skill synchronization, or Bactron Core upgrade.
Detour For: none
Return To: none
Completion Gate: Windows-safe phase timeouts exceed measured validation duration; no upgrade phase is silent for more than 30 seconds; every transaction records a sanitized user-local stage, duration, stable issue code, error class, and rollback outcome without prompts, responses, credentials, secrets, workspace paths, usernames, dirty filenames, or raw command output; a deterministic local report route converts a selected transaction into validated sanitized JSON and maintainer-ready Markdown for a Tool Shed GitHub issue without automatically publishing it; stable official releases use exact provenance, manifest hashes, and verifiable exact-tag qualification evidence plus focused client installation smoke instead of rerunning the complete developer suite, while overridden, unattested, or changed validation identities fall back to full local validation; successful release validation is cached only by exact release commit, validator hash, platform, architecture, and Python identity and is safely reusable after post-install retry; concurrent duplicate upgrades fail closed under a recoverable transaction lock; full release CI remains comprehensive; Windows qualification proves ordinary cold and warm-retry upgrades preserve dirty work and rollback invariants with visible timing evidence, with warm retry reaching backup or install in under one minute; focused tests prove issue-code stability, report sanitization, malformed or foreign transaction rejection, and review-before-publication behavior.
Completion Evidence: none
Disposition: none

## Request

The Bactron Core `0.25.2` to `0.26.1` update took two attempts and reran a Windows developer suite
that exceeded the released updater's 300-second default. The updater supplied only phase-boundary
messages and did not retain a durable sanitized failure/timing record, so the first attempt's exact
failure could not be recovered after rollback.

Implement a fail-closed client path that keeps comprehensive release CI while making normal stable
upgrades observable and fast to retry. Official focused validation must depend on exact release
attestation, every noncanonical or changed identity must fall back to full validation, and no cache,
lock, report, backup, or optimization may weaken provenance, dirty-work preservation, rollback, or
provider/skill convergence.

Before release, extend the protected transaction records with stable maintainer-facing issue codes
and add a deterministic local report route for the latest or an explicitly selected transaction.
The route must emit schema-validated sanitized JSON and GitHub-issue-ready Markdown containing only
bounded release/updater identity, platform, failed stage, phase durations, validation/cache mode,
issue code, error class, and rollback outcome. It must reject malformed or foreign records, must not
include raw exception text or owner/workspace data, and must never create an external issue without
separate review and publication authorization. The protected user-local transaction directory
remains the registry; do not create a second database or hosted reporting service.

## Scope Freeze

Owner decision on 2026-08-24: include the stable issue-code registry and sanitized issue-draft
generator as the final `0.27.0` candidate scope. Add no further features or prerequisite campaigns
before qualification. After this reporter and its focused/local validation pass, stop at the
external boundary and request separate authorization to push a qualification branch. A branch push
does not authorize a tag, GitHub Release, installed-skill synchronization, or Bactron Core upgrade.

Current evidence: [snapshot upgrade performance and retry-safety qualification](../../evidence/evidence-snapshot-upgrade-performance-and-retry-safety.md).

## Completion Check

Windows-safe phase timeouts exceed measured validation duration; no upgrade phase is silent for more than 30 seconds; every transaction records a sanitized user-local stage, duration, stable issue code, error class, and rollback outcome without prompts, responses, credentials, secrets, workspace paths, usernames, dirty filenames, or raw command output; a deterministic local report route converts a selected transaction into validated sanitized JSON and maintainer-ready Markdown for a Tool Shed GitHub issue without automatically publishing it; stable official releases use exact provenance, manifest hashes, and verifiable exact-tag qualification evidence plus focused client installation smoke instead of rerunning the complete developer suite, while overridden, unattested, or changed validation identities fall back to full local validation; successful release validation is cached only by exact release commit, validator hash, platform, architecture, and Python identity and is safely reusable after post-install retry; concurrent duplicate upgrades fail closed under a recoverable transaction lock; full release CI remains comprehensive; Windows qualification proves ordinary cold and warm-retry upgrades preserve dirty work and rollback invariants with visible timing evidence, with warm retry reaching backup or install in under one minute; focused tests prove issue-code stability, report sanitization, malformed or foreign transaction rejection, and review-before-publication behavior.
