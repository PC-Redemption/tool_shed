# Evidence: Core explicit-reference App Server preparation bound

Status: verified
Type: evidence
Updated: 2026-08-26
Campaign: bound-explicit-reference-app-server-preparation

## Field failure

Bactron Core was upgraded from Tool Shed v0.29.9 to the verified v0.29.10 snapshot and matching
Windows skill in transaction `10d1a24bac665ab990a2f969`. Fresh Core Campaign 022 explicitly named
`docs/app_server_camp_preparation.md`, but v0.29.10 automatic preparation still filled its bounded
snapshot with any repository path matching one generic campaign word. The 79,875-byte deterministic
context therefore excerpted unrelated lifecycle SQLite, corrected-window CSV, role-reference, and
manual PID-run files. The App Server planning turn used 50,595 input tokens and failed closed at the
50,000-token focused-context warning. No execution capsule or lifecycle state was persisted, no
worker launched, and no target file changed.

## Repair

Automatic preparation now treats explicit workspace references as its dominant boundary. In that
mode, supplemental candidates require at least two keyword matches; explicit files and preferred
project instructions remain eligible. Inventory excludes zero- and weak-relevance padding, is
limited to 12,000 bytes, excerpts are limited to eight files, and the complete deterministic
preparation snapshot is capped at 48,000 bytes. Campaigns without explicit paths retain the
existing one-keyword discovery behavior.

The focused Core-shaped regression retains the requested guide, its validator source and test, and
project instructions while excluding unrelated SQLite, CSV, PID-run, and production-inventory
artifacts. It also verifies the hard snapshot cap and the existing no-reference code-before-routing
discovery test remains green.

## Verification

- `python3 -m unittest tests.test_app_server_dispatch`: 20 tests passed.
- The patched builder was loaded from a disposable Windows temp copy and applied read-only to the
  actual Core Campaign 022 and repository inventory. Context fell from 79,875 to 26,821 bytes.
- Selected excerpt headings were only the requested guide, validator test, validator source,
  `AGENTS.md`, `docs/script_index.md`, and `README.md`.
- The disposable patch copy was removed after inspection. Core's v0.29.10 snapshot, Campaign 022,
  and product files were not modified by this verification.

## Boundary

This is a validated local Tool Shed repair only. It has not been published, synchronized to an
installed skill, installed into Core, or used to launch a Core worker. No Bactron deployment,
production, PID, hardware, credential, or completed-campaign replay occurred. Full release
validation, publication, synchronization, the corrective Core upgrade, and the resumed Windows
first-pass proof remain separate stages.
