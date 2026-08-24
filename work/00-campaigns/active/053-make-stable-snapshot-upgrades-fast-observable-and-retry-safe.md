# Make stable snapshot upgrades fast, observable, and retry-safe

Status: blocked
Type: campaign
Updated: 2026-08-24
Next Action: resolve blocker or decision: Native Windows cold and warm-retry qualification of the unpublished 0.27.0 candidate requires either authorization to push the candidate for Windows CI or explicit authorization to mutate and execute it in a Windows workspace; ts: next grants neither.
Campaign ID: make-stable-snapshot-upgrades-fast-observable-and-retry-safe
Campaign Number: 053
Outcome: Reduce normal stable-release snapshot upgrade latency and eliminate opaque or repeated validation delays while preserving exact release provenance, content integrity, dirty-work protection, verified backup and rollback, provider convergence, Codex skill synchronization, and fail-closed post-install checks.
Primary Focus Areas: snapshot-delivery
Supporting Focus Areas: qualification-release, workspace-safety
Depends On: none
Decision: Native Windows cold and warm-retry qualification of the unpublished 0.27.0 candidate requires either authorization to push the candidate for Windows CI or explicit authorization to mutate and execute it in a Windows workspace; ts: next grants neither.
Detour For: none
Return To: none
Completion Gate: Windows-safe phase timeouts exceed measured validation duration; no upgrade phase is silent for more than 30 seconds; every transaction records a sanitized user-local stage, duration, error class, and rollback outcome without prompts, responses, credentials, or secrets; stable official releases use exact provenance, manifest hashes, and verifiable exact-tag qualification evidence plus focused client installation smoke instead of rerunning the complete developer suite, while overridden, unattested, or changed validation identities fall back to full local validation; successful release validation is cached only by exact release commit, validator hash, platform, architecture, and Python identity and is safely reusable after post-install retry; concurrent duplicate upgrades fail closed under a recoverable transaction lock; full release CI remains comprehensive; Windows qualification proves ordinary cold and warm-retry upgrades preserve dirty work and rollback invariants with visible timing evidence, with warm retry reaching backup or install in under one minute.
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

Current evidence: [snapshot upgrade performance and retry-safety qualification](../../evidence/evidence-snapshot-upgrade-performance-and-retry-safety.md).

## Completion Check

Windows-safe phase timeouts exceed measured validation duration; no upgrade phase is silent for more than 30 seconds; every transaction records a sanitized user-local stage, duration, error class, and rollback outcome without prompts, responses, credentials, or secrets; stable official releases use exact provenance, manifest hashes, and verifiable exact-tag qualification evidence plus focused client installation smoke instead of rerunning the complete developer suite, while overridden, unattested, or changed validation identities fall back to full local validation; successful release validation is cached only by exact release commit, validator hash, platform, architecture, and Python identity and is safely reusable after post-install retry; concurrent duplicate upgrades fail closed under a recoverable transaction lock; full release CI remains comprehensive; Windows qualification proves ordinary cold and warm-retry upgrades preserve dirty work and rollback invariants with visible timing evidence, with warm retry reaching backup or install in under one minute.
