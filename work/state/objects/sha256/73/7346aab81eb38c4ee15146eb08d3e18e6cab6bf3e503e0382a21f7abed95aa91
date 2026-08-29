# Evidence: Project-scoped App Server dispatch v0.29.2

Status: complete
Date: 2026-08-25
Campaign: repair-project-scoped-app-server-dispatch

The direct dispatcher now loads the explicitly selected App Server config and model policy once
and passes those same objects into bounded CAMP execution. Project qualification records may pin an
`executable_sha256`; status and selection fail closed when the resolved workspace-write executable
does not match it.

Focused regression coverage passed 47 tests. Both unpublished-content and populated-provenance
release validations passed 266 tests plus provider conformance, index, stale-path, work-state,
roadmap, and disposable-client checks.

Release `v0.29.2` identifies content commit
`db5344b31935f6cb2e01f4978dddd63879e740e0` and provenance commit
`ac67a69a6714a3916b105fa257093e557e2ce827`. GitHub release workflow `32900848161` passed, and the
verified nondraft, non-prerelease Release is
`https://github.com/PC-Redemption/tool_shed/releases/tag/v0.29.2`.

Bactron Core upgraded transactionally from `0.29.1` to `0.29.2` in transaction
`539adb14dbac9a08767d1d60`, with backup
`E:\dev\bactron-core\tool_shed.backup-20260825T212722Z.tar`; tracked Core work remained unchanged.
The Core project-scoped status, selector, and compatibility consumer all selected the same GUI
extension executable, version `0.149.0-alpha.4.3`, with exact-qualified CAMP execution. Its live
SHA-256 remained `21f44f04e70d41d011268863d5109f5d7fc2862c14f390083e39ca3398b5ca47`,
matching the reviewed Core qualification record.

No Bactron deployment, product mutation, Campaign 013 replay, permission expansion, API-key
fallback, or automatic App Server retry occurred.
