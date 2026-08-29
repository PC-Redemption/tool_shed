# w1-dev SMB access evidence

Status: complete
Type: evidence
Updated: 2026-08-24
Next Action: none
Campaign: establish-secure-smb-access-to-bactron-workspace
Related: work/00-campaigns/completed/047-establish-secure-smb-access-to-bactron-workspace.md

## Outcome

The Codex host `sup` has a stable read/write filesystem path at `/mnt/w1-dev` to the complete
Windows share `//SH-06172402.local/w1-dev`. The route uses `srv-specops.local` as the network
intermediary because the Codex host cannot resolve or directly reach the Windows SMB endpoint.
Direct file execution is disabled at both mount layers.

## Topology

1. `srv-specops.local` mounts `//SH-06172402.local/w1-dev` as CIFS at `/mnt/w1-dev`.
2. `sup` mounts `srv-specops.local:/mnt/w1-dev` as SSHFS at `/mnt/w1-dev`.
3. The local SSHFS mount runs as `jon` under `w1-dev-sshfs.service`.

## Credential safety

- The existing approved CIFS credential-file mechanism was reused without reading or recording
  the credential path or contents.
- The credential file was verified as `root:root` with mode `0600`.
- The source `fstab` entry uses a credential-file option and contains no inline username or
  password.
- No credential material was written to this repository or emitted in command output.
- Windows ACLs were not changed.

## Packages

- `sshfs` 3.7.3 was installed on `sup`.
- `smbclient` 4.22.10 was installed on `srv-specops.local`.
- Installing `smbclient` upgraded its existing Samba-related packages to the matching Debian
  security release. No package autoremove was run.
- `cifs-utils` and `/usr/sbin/mount.cifs` were already present on `srv-specops.local`.

## Resilience and absent-share behavior

The remote CIFS entry is versioned only in host-local `/etc/fstab`, not in this repository. It
uses these non-secret controls:

- `rw,noexec,nosuid,nodev`
- SMB 3.1.1 with `soft,echo_interval=15`
- `_netdev,nofail,x-systemd.automount,x-systemd.mount-timeout=30s`
- local ownership mapping to UID/GID 1000 with file mode `0660` and directory mode `0770`

The CIFS client checks an unresponsive server every 15 seconds and begins reconnection after two
missed echo intervals. `soft` returns errors instead of hanging callers indefinitely.
`x-systemd.automount` retries mounting on later access, while `nofail` and the bounded mount timeout
prevent an absent share from blocking boot.

The local bridge uses `rw,reconnect,ServerAliveInterval=15,ServerAliveCountMax=3`, plus
`noexec,nosuid,nodev,default_permissions,idmap=user`. The systemd service is enabled at boot and
uses `Restart=always` with a 15-second delay.

## Verification

- Credential-backed transient CIFS mount: passed.
- Remote `fstab` syntax validation: passed.
- Remote systemd automount: active; CIFS mount active.
- Local `w1-dev-sshfs.service`: enabled and active; SSHFS mount active.
- Required `rw,noexec,nosuid,nodev` flags at both layers: passed.
- Share-root enumeration: passed; eight top-level entries observed.
- Full recursive metadata traversal through the local SSHFS path: completed with zero permission
  errors observed.
- Representative read from every top-level area: 8/8 passed.
- `bactron-core` visibility: passed as one included area, not the campaign boundary.
- Two uniquely named create/write/read/rename/delete probes: passed; cleanup verified.
- Pre-existing share content was not intentionally altered during qualification.

`noexec` prevents direct execution from the mounted filesystem. It does not prevent an explicitly
invoked interpreter from reading a script as data; operational use must continue to avoid running
share-hosted code.

## Host-local configuration and recovery

- Remote active configuration: `/etc/fstab` on `srv-specops.local`.
- Remote pre-change backup: `/etc/fstab.tool-shed-20260824T154826Z.bak`.
- Local active configuration: `/etc/systemd/system/w1-dev-sshfs.service`.
- Local mountpoint: `/mnt/w1-dev`.

To recover the remote configuration, stop the `mnt-w1\x2ddev` automount, restore the recorded
backup over `/etc/fstab`, reload systemd, and revalidate the remaining mounts. To recover the local
bridge, stop and disable `w1-dev-sshfs.service`, unmount `/mnt/w1-dev`, remove only that service
unit, and reload systemd. Recovery should preserve the mountpoint directory and never modify share
content or the credential file.
