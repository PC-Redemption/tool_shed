# Codex App Server Maintainer Note

Status: maintenance/watch; experimental; global default disabled

App Server support exists, but the
[official App Server documentation](https://developers.openai.com/codex/app-server) currently
describes it as experimental and unsupported for production workloads. Do not enable it globally.
Normal Tool Shed and `ts: discuss` remain on the existing GUI path; Terra is the normal interactive
model unless the operator intentionally selects Sol for difficult direct GUI work.

Only explicit read-only planning (`gpt-5.6-sol` / high) and verification (`gpt-5.6-terra` / low)
are qualified. Workspace writing remains blocked pending reliable cancellation, supported GUI
approvals, understood restricted reads, and a stable production contract.

After a Codex update, run:

```bash
python3 scripts/codex_app_server_compatibility.py status
python3 scripts/codex_app_server_compatibility.py smoke --cwd .
```

Record reviewed results in `adapters/codex-app-server-qualifications.json`; never inherit or
automatically declare qualification for a new version. Resume engineering only for a concrete CLI,
support-status, cancellation, restricted-read, approval, or production-contract change.
