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
journal. It remains opt-in because the representative CAMP used 241,524 input tokens and did not
establish savings. Broader writing, build, deployment, permission expansion, and automatic
lifecycle transitions remain blocked.

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
