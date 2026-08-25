# Windows deterministic verification repair and release evidence

Date: 2026-08-25
Campaign: route-windows-verification-through-console-sandbox
Result: passed

The Windows CAMP verifier now invokes the already selected exact GUI Codex executable through its zero-model local read-only sandbox. Linux and other platforms retain the existing App Server command execution path. The subprocess is shell-free, inherits the bounded timeout, sets `PYTHONDONTWRITEBYTECODE=1`, and fails closed with a distinct `windows_verification_sandbox_failed` transport category.

A focused regression verifies the Windows sandbox command shape and the existing non-Windows behavior. The full Tool Shed validator passed all 267 tests twice on the release inputs.

The corrected patch release is Tool Shed v0.29.4:

- content commit: `8777b54f07cb04833d7b60ad1602ceab3576e787`
- provenance commit and annotated tag target: `75c742f23477be7ae3e2e81cb9bdd871b9832dd9`
- GitHub release workflow: `32903147909`, passed
- GitHub Release: `https://github.com/PC-Redemption/tool_shed/releases/tag/v0.29.4`

Bactron Core upgraded from v0.29.2 to v0.29.4 using guarded snapshot transaction `95d9d6ea6c5528434bff0584`. The updater verified the official release attestation, preserved workspace work, created backup `E:\dev\bactron-core\tool_shed.backup-20260825T215438Z.tar`, and reported the installed Codex skill current with no synchronization change required.

Fresh Core Campaign 017 then ran once from the active Windows console. Its journal was safe and `verified`, with exactly one passing deterministic verification command, two expected paths, no unexpected paths, and no replay. That proves the release repair in the environment which exposed the failed App Server command RPC.
