# Tool Shed Focus Areas

Status: approved
Type: focus-area-catalog
Updated: 2026-08-15
Next Action: review when an enduring responsibility boundary changes

This owner-approved catalog records Tool Shed's enduring responsibility boundaries. Refresh it
when a durable product, repository, integration, runtime, qualification, release, regulatory,
supply, or ownership boundary changes, or when repeated work does not fit an existing area.

## Discovery Evidence And Coverage

The catalog was derived from the repository README and operating documentation, portable skill and
provider adapters, Python command surfaces, templates, tests and fixtures, CI and release workflow,
snapshot installation and fleet boundaries, and durable work history.

No separate service, deployed application, hardware, regulatory, or supply-chain boundary exists
in this repository. Tool Shed's executable surface is Python scripts plus POSIX and PowerShell
launchers; there is no separate package or product build target. There were no active campaigns at
approval time, so the approved active-campaign assignment set was empty.

## Focus Areas

Focus Area ID: artifact-workflows
Name: Artifact Workflows
Purpose: Define and maintain Tool Shed's portable Markdown artifact model and deterministic work-artifact lifecycle.
Includes: Artifact selection, templates, composition rules, onboarding, artifact creation and completion, work-tree structure, indexes, stale-path detection, and work-state review.
Excludes: Owner campaign scheduling, snapshot distribution, and release publication.
Evidence: selection.md; conventions.md; templates/; scripts/new_artifact.py; scripts/update_work_index.py; scripts/review_work_state.py; existing-projects.md
Uncertainty: None. Work-state validation belongs here; generated-evidence safety belongs under workspace-safety.

Focus Area ID: campaign-lifecycle
Name: Campaign Lifecycle
Purpose: Provide the durable owner-facing queue, readiness, focus-area, intake, and reconciliation model.
Includes: Campaign lifecycle transitions, dependency-aware readiness, queue projections, focus-area catalogs and assignments, Q&A intake, whole-work coverage, stale-write protection, and Dangler Resolution.
Excludes: Generic artifact design, cross-workspace portfolio management, and automatic multi-campaign execution.
Evidence: scripts/campaign_queue.py; scripts/reconcile_campaign_queue.py; scripts/read_ask_inbox.py; templates/campaign-request.md; templates/focus-area-catalog.md; work/00-campaigns/active-queue.md; Tool Shed document WP-0004
Uncertainty: Cross-workspace portfolio aggregation remains intentionally outside the project boundary.

Focus Area ID: provider-portability
Name: Provider Portability
Purpose: Keep Tool Shed's routing and coordination behavior portable while integrating honestly with provider-native instruction and reasoning surfaces.
Includes: The portable skill, route references, provider registry and instruction contracts, provider conformance, operator commands, routing scenarios, and the optional Codex reasoning catalog.
Excludes: Snapshot transport and rollback, provider features beyond their qualified capability, and project-specific work state.
Evidence: skills/tool-shed/SKILL.md; adapters/providers.json; docs/provider-adapters.md; scripts/provider_adapters.py; scripts/reasoning_catalog.py; docs/commands.md; tests/fixtures/direct-routing-scenarios.json
Uncertainty: Codex is qualified to Level 5; the four non-Codex adapters currently have static Level 2 qualification rather than representative runtime qualification.

Focus Area ID: snapshot-delivery
Name: Snapshot Delivery
Purpose: Install, update, synchronize, inventory, and recover disconnected Tool Shed snapshots without damaging owner work.
Includes: Workspace installation and convergence, snapshot acquisition and replacement, verified backups and rollback, repository boundaries, Codex skill synchronization, launchers, and read-only fleet inventory.
Excludes: Authoring portable provider behavior, modifying owner project code or work content, and canonical release qualification and tagging.
Evidence: scripts/install_into_workspace.py; scripts/update_snapshot.py; scripts/codex_skill_sync.py; scripts/inventory_tool_shed_fleet.py; docs/install-or-update-snapshot.md; docs/fleet-snapshot-updates.md
Uncertainty: Read-only fleet inventory is supported, but a fleet-wide apply operation remains approval-gated and is not an active project outcome.

Focus Area ID: workspace-safety
Name: Workspace Safety and Performance
Purpose: Protect repository and agent reliability from oversized generated evidence while providing privacy-safe performance measurements.
Includes: Workspace profiling and adaptive risk budgets, generated-evidence boundaries, prepare/apply migration safeguards, aggregate performance profiling, incident-derived regression profiles, and privacy controls.
Excludes: Snapshot backup archives, artifact-state reconciliation, and external report collection or telemetry.
Evidence: scripts/workspace_preflight.py; scripts/migrate_generated_evidence.py; scripts/profile_workspace_performance.py; docs/workspace-performance-profiling.md; tests/test_workspace_performance.py; Tool Shed document WP-0003
Uncertainty: A centralized performance-report collector is neither implemented nor currently justified. Firmware and hardware appear only as test and incident contexts, not as Tool Shed runtime boundaries.

Focus Area ID: qualification-release
Name: Qualification and Release
Purpose: Prove cross-platform behavior and publish traceable, integrity-verifiable Tool Shed releases.
Includes: Unit and integration tests, disposable workspace smoke tests, provider conformance, full validation, CI matrices, manifest integrity, semantic version status, release provenance, and tagging procedures.
Excludes: Installing a released snapshot into projects, fleet rollout, and expanding provider runtime qualification without evidence.
Evidence: scripts/validate_tool_shed.py; tests/test_scripts.py; .github/workflows/validate.yml; SHED_VERSION.json; scripts/update_shed_manifest.py; scripts/check_shed_version.py; docs/releasing.md
Uncertainty: The current 0.18.0 manifest has no release commit or release timestamp, so it represents an unpublished release candidate rather than completed release provenance.

## Approval

Owner decision: approved as proposal FA-2026-08-15-v1 on 2026-08-15.

Active-campaign assignments at approval: none; the active queue contained no campaigns.
