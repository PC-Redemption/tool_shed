# Evidence: Native Linux installed App Server workflow

Status: complete
Type: evidence
Updated: 2026-08-25
Next Action: use Campaign 060 to eliminate the nested wrapper and prove direct Linux dispatch before returning to the Windows consent gate
Campaign: prove-installed-native-linux-app-server-workflow

## Target and release

- Disposable native Linux client: `/tmp/tool-shed-m3-linux-ulV39wiM/client`
- Isolated Codex home: `/tmp/tool-shed-m3-linux-ulV39wiM/codex-home`
- Starting snapshot and installed skill: released `v0.27.1`
- Selected release: `v0.28.0`, content commit
  `b777c1a57a287df4dd4f5fd48f0d77bd46b7d25f`
- Scope stayed inside the disposable client and isolated Codex home. Bactron Core and other installs
  were not inspected or changed.

## Guarded update and recovery

- An injected failure at snapshot replacement produced transaction
  `5895c2bce363bb9320ece3d2`, issue `TSU-801`, with rollback outcome `restored` in 1.968 seconds.
  The snapshot remained verified at `v0.27.1`, the installed skill remained `v0.27.1`, the client
  Git state was unchanged, and the workspace backup was retained as
  `tool_shed.backup-20260825T194054Z.tar`.
- The normal retry produced transaction `d8088af7daafca9576427aee`, installed `v0.28.0` in 2.907
  seconds, and used the official attested focused-smoke validation cache. Work and Git status were
  unchanged. The snapshot backup was retained as `tool_shed.backup-20260825T194132Z.tar`.
- The stale released skill was synchronized with a rollback copy under the isolated
  `tool-shed-backups/` directory. Final snapshot integrity was verified and the installed skill was
  byte-for-byte equal to the snapshot skill.

## Readiness and controlled failure

- Final discovery selected `/home/jon/.local/bin/codex` `0.149.0`; App Server and workspace-write
  qualification were both `exact-qualified`; CAMP routing was `gpt-5.6-terra` with medium
  reasoning; API fallback was disabled.
- An intentionally missing explicit Codex executable failed before mutation with category
  `codex_app_server_unavailable`, qualification `unsafe-blocked`, and recovery action to rerun
  without `--app-server`. Git status was unchanged.
- An installed-skill run under an isolated, unauthenticated Codex home failed with HTTP 401 before
  mutation. No credential was inspected or copied.
- Authenticated outer runs with workspace-write alone failed safely because spawned commands
  inherited the outer filesystem and network restrictions: first the nested Codex state directory
  was read-only, then an added state-directory grant still left network disabled. No client file
  changed in either attempt.

## Real installed-use result

The fresh installed `v0.28.0` skill accepted `ts: next --app-server` in the disposable client. With
the authenticated outer Codex task allowed to initialize nested Codex state and use the network,
the inner App Server CAMP still ran under its declared exact-root workspace-write sandbox and Git
mutation journal. It:

- created only `docs/linux-app-server-proof.md` with the exact declared marker;
- preserved the clean preexisting Git state and reported no unexpected paths;
- executed the single declared deterministic verification exactly once and passed it;
- reached journal final state `verified`; and
- completed disposable campaign `001-verify-linux-app-server-client-marker` with reconciled work
  indexes.

Inner App Server telemetry recorded `gpt-5.6-terra` / medium, two model turns, one `fileChange`,
8.496 seconds, 39,458 input tokens (19,200 cached), 252 output tokens, and 59 reasoning-output
tokens. The enclosing fresh `codex exec` task consumed 893,723 input tokens (826,624 cached), 3,809
output tokens, and 1,251 reasoning-output tokens. This proves installed operation but not useful
token reduction through a nested outer-agent wrapper; M5 must measure and optimize the actual GUI
entry path without treating the wrapper's cached-token volume as savings.

The outer task also ran the full 260-test snapshot validator successfully after the required
focused proof. Its generated Python cache was removed from the disposable snapshot, and strict
disconnected-snapshot integrity was reverified with no forbidden or modified files.

## Gate result

`G3-LINUX-INSTALLED-WORKS` passes: install/update, rollback, exact readiness, controlled safe
failure, recovery, real installed App Server mutation, single deterministic verification, and usage
evidence are all present. The permission-inheritance and wrapper-token observations remain explicit
constraints for later cross-platform usability and optimization work; they do not invalidate the
bounded native Linux proof.
