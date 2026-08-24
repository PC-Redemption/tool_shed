# Establish read/write SMB access to the complete w1-dev Windows share

Status: complete
Type: campaign
Updated: 2026-08-24
Next Action: none
Campaign ID: establish-secure-smb-access-to-bactron-workspace
Campaign Number: 047
Outcome: Make the complete \\SH-06172402\w1-dev share readable and writable from this Codex instance through srv-specops.local, using an approved SMB identity with read/write permission throughout the share, while disabling direct file execution and never exposing secrets.
Primary Focus Areas: snapshot-delivery
Supporting Focus Areas: workspace-safety
Depends On: none
Decision: none
Detour For: none
Return To: none
Completion Gate: Required SMB/CIFS and intermediary client support is installed through the approved administrative route; this Codex instance has a stable read/write filesystem path to //SH-06172402.local/w1-dev through srv-specops.local using an approved SMB identity with read/write permission throughout the share and without inspecting, logging, or storing secrets in this repository; direct file execution is disabled with noexec or an effective equivalent while directory traversal remains available; the share root and every top-level area can be enumerated, a recursive metadata traversal completes without permission exclusions, representative files across the share including bactron-core can be read, and a dedicated temporary probe created by this campaign is successfully created, written, read, renamed, and removed without altering pre-existing content; the execution boundary is documented and tested; and no unintended modification or credential disclosure occurred.
Completion Evidence: work/evidence/evidence-w1-dev-smb-access.md; live rw/noexec CIFS and SSHFS mounts; resilient systemd configurations; full traversal, 8/8 representative reads, and cleaned write probes passed
Completion Date: 2026-08-24
Completion Order: 43
Disposition: completed

## Request

The current Codex host cannot resolve or directly reach the Windows share at
`\\SH-06172402\w1-dev`. Use `srv-specops.local` as the intermediate host because it is on the
same network as the Windows system. The requested access boundary is the complete share—not only
the `bactron-core` subtree—and it must be usable from this Codex instance.

Observed discovery evidence:

- SSH access to `srv-specops.local` works through the existing approved SSH configuration.
- From that host, `SH-06172402.local` resolves to `10.1.2.190` and TCP port 445 is reachable.
- `cifs-utils` and `/usr/sbin/mount.cifs` are already available on `srv-specops.local`, but
  `smbclient` is not. The available `gio` route did not provide usable share access.
- An unrelated existing CIFS mount at `/mnt/sec_results` is backed by a root-managed credential-file
  option with no inline username or password. Reuse that approved mechanism without reading,
  printing, copying, or recording its path or secret material.
- SSH to the Windows host itself is not available, so SMB through the intermediate host is the
  viable access route.
- The current Codex host cannot resolve `SH-06172402.local` or reach its SMB port directly. It has
  FUSE support but not `sshfs`; neither host currently has a `/mnt/w1-dev` mountpoint.

Ensure the required clients are present through the approved administrative route: install the
missing `smbclient` package on `srv-specops.local` and `sshfs` on the current Codex host while
retaining the installed `cifs-utils`. Configure read/write access to
`//SH-06172402.local/w1-dev` on `srv-specops.local`, preferably at `/mnt/w1-dev`, then expose a
stable read/write filesystem path to the current Codex process through SSHFS. Use the existing
root-managed credential-file mechanism with an approved SMB identity that has read/write permission
throughout the share. A one-time interactive SMB client or manual SSH command may be used for
diagnosis, but it does not satisfy the outcome.

Verify access beyond `bactron-core`: enumerate the share root and every top-level area, complete a
recursive metadata traversal without permission exclusions, and read representative files across
the share. Verify writes only with a uniquely named temporary probe created for this campaign:
create it in an approved test location, write and read known content, rename it, remove it, and
confirm cleanup. Do not alter or delete pre-existing content during access qualification.

Disable direct file execution from the exposed filesystem with `noexec` or an effective equivalent
and do not run share-hosted code during qualification. Directory search/traversal permission must
remain enabled because it is required to access files below directories.

Creating this campaign authorizes only durable planning. Package installation, credential-backed
mount configuration, persistence changes, and execution against the remote workspace require the
normal explicit authorization when this campaign is selected.

## Completion Check

Required SMB/CIFS and intermediary client support is installed through the approved administrative route; this Codex instance has a stable read/write filesystem path to //SH-06172402.local/w1-dev through srv-specops.local using an approved SMB identity with read/write permission throughout the share and without inspecting, logging, or storing secrets in this repository; direct file execution is disabled with noexec or an effective equivalent while directory traversal remains available; the share root and every top-level area can be enumerated, a recursive metadata traversal completes without permission exclusions, representative files across the share including bactron-core can be read, and a dedicated temporary probe created by this campaign is successfully created, written, read, renamed, and removed without altering pre-existing content; the execution boundary is documented and tested; and no unintended modification or credential disclosure occurred.
