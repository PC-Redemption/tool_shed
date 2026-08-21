# Codex App Server Maintainer Note

Status: maintenance/watch; experimental; global default disabled

App Server support exists, but the
[official App Server documentation](https://developers.openai.com/codex/app-server) currently
describes it as experimental and unsupported for production workloads. Do not enable it globally.
Normal Tool Shed and `ts: discuss` remain on the existing GUI path; Terra is the normal interactive
model unless the operator intentionally selects Sol for difficult direct GUI work.

Explicit read-only planning (`gpt-5.6-sol` / high), verification (`gpt-5.6-terra` / low), and one
explicitly scoped `camp_execution` step (`gpt-5.6-terra` / medium) are qualified. CAMP writing must
use `camp-run`, exact declared paths, the hardened workspace-write sandbox, and a Git mutation
journal. It remains opt-in. The representative CAMP used 241,524 input tokens and did not establish
savings in the original qualification; Campaign 040 subsequently reduced the same
fixture to 61,516 input tokens and two model requests while 22 focused tests passed. The result is
economically useful for bounded work but does not change the support or promotion boundary. See
[the token optimization report](codex-app-server-camp-token-optimization-2026-08-20.md). Broader
writing, build, deployment, permission expansion, and automatic lifecycle transitions remain
blocked.

The user-facing opt-ins are `ts: plan <request> --app-server`, `ts: verify <request>
--app-server`, `ts: camp run <camp> --app-server`, and `ts: next --app-server`; the last performs
normal next-action selection and forwards only to an already-qualified role rather than making
`next` a role. `ts: appserver status` reports the exact
local compatibility and routing state. The unflagged forms use the GUI. Session-wide on/off is
deliberately unavailable because the Codex skill surface has no reliable skill-owned session
storage, and no `--gui` alias is needed while the unflagged form is authoritative. The selector
fails closed before App Server starts when the installed Codex version or role is unqualified.

All Codex consumers use one resolver: supported explicit override, `PATH`, then bounded trusted
platform locations, including newest-valid OpenAI VS Code extension bundles. It validates the CLI
version and App Server command independently and reports the selected path and source as `NOT
FOUND`, `INVALID EXECUTABLE`, `APP SERVER UNAVAILABLE`, `UNQUALIFIED VERSION`, or qualified
`AVAILABLE`. The resolver also backs install/upgrade readiness, reasoning refresh, smoke, startup,
version detection, and qualification. It neither installs Codex nor changes permanent `PATH`,
persists user paths, searches arbitrary locations, auto-qualifies a version, or enables API
fallback. Missing Codex therefore leaves normal GUI Tool Shed work available.

Linux extension discovery is bounded to the desktop, Insiders, remote-server, and remote-server
Insiders extension roots under the user's home directory, with x86_64, aarch64, and arm64 Codex
payloads. This covers normally launched local and remote Linux GUI sessions without modifying
`PATH`.

Automated Windows and Linux regression coverage is not the Windows release gate. Before release,
collect external evidence from a fresh normally launched Codex GUI with `Get-Command codex` still
not found and no `PATH` preparation: status must discover the trusted VS Code bundle, and a
GUI-triggered `--app-server` operation, smoke, startup, version detection, and qualification must
use that same executable identity. Do not claim this gate has passed until those field results are
recorded.

After a Codex update, run:

```bash
python3 scripts/codex_app_server_compatibility.py status
python3 scripts/codex_app_server_compatibility.py smoke --cwd .
python3 scripts/codex_app_server_write_qualification.py --help
```

Record reviewed results in `adapters/codex-app-server-qualifications.json`; never inherit or
automatically declare qualification for a new version. After a version change, run and review the
disposable write harness separately before retaining CAMP qualification. Resume broader engineering
only for a concrete CLI, support-status, cancellation, restricted-read, approval, token-efficiency,
or production-contract change.

The current reviewed version is Codex CLI 0.149.0. Its 2026-08-21 smoke and disposable write
qualification retained explicit planning, verification, and CAMP roles with blockers; see
[`codex-app-server-requalification-2026-08-21.md`](codex-app-server-requalification-2026-08-21.md).
