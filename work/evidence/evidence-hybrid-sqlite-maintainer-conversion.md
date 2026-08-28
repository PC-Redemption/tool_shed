# Hybrid SQLite Maintainer Conversion Evidence

Status: passed
Evidence ID: EVID-G3-MAINTAINER
Gate: G3-MAINTAINER-CONVERSION-PROVEN
Campaign: 106-rehearse-and-convert-maintainer-to-hybrid-state
Target: canonical Tool Shed maintainer, local work3 candidate
Candidate version: 0.34.0
Date: 2026-08-28

## Exact Source And Recovery Envelope

The conversion source was the clean local commit
`3aaacdf20c8c2112e4d372bbd6e69f16d3eb13df`. The external archive is retained at
`/home/jon/docker/tool_shed-conversion-archives/20260828-3aaacdf/maintainer-pre-cutover.tar.gz`
through the first hybrid release and completed disconnected-client canary. It has SHA-256
`08b8cb0aa4c1e2739c37ada2a77dc11763e39cf23f1d98edd122d229dc65e2b9` and inventory digest
`4ffc8fa33f0b5874698299254ce2ac0c5d79d144ecdcbfb67a076a5da3c0d0e2`.

The byte inventory accounts for 426 tracked files, 40 ignored files, zero untracked files, and 20
selected retained-source imports. All 466 files restored from the archive in each rollback proof.
The archive is outside the repository, contains no live SQLite database, and was byte-verified
member by member. The assigned source fingerprint remained
`c65f07ae0d39831591aa0363bde64939b0ade0083722696b03b3d3ec0c7e3cea` across every no-write
window. Every original source file remains present.

## Disposable Rehearsal And Rollback

Two independent disposable clones restored the exact archive and produced rehearsal token
`2cdc0a32a337a9afdfe100f8c36f5f7e45fb78439d12441d4e1b751c4a4d8cc3`. Their time-independent
semantic digest was identical:
`4cd08e0a29ed2618881391ed9653b94b37cdc536307007919af5c45b585983d5`.

Each rehearsal proved:

- exact reuse of all 20 artifact and first-import UUIDv4 assignments;
- bootstrap projection and all eight HPT2 operation results matched the file authority;
- shadow and hybrid checkpoints rebuilt with identical per-run domain state;
- the SQLite backup API produced a verified clean pre-cutover backup;
- simulated interruption rolled back to `CLEAN` without a domain-digest change;
- direct SQL entered `UNMANAGED_REVIEW`, then checkpoint rebuild restored clean state;
- a real detached Git worktree refused a copied database as invalid foreign lineage; and
- archive restore reproduced all 466 tracked, ignored, and untracked inventory members.

The detailed archive and rehearsal reports remain external beside the archive. This tracked record
contains only the compact identities and verdicts needed to reproduce or audit the result.

## Canonical Cutover And Soak

The live controller required the same commit, archive SHA, inventory digest, rehearsal token, clean
source state, and fresh project-bound `hybrid-state` session binding before mutation. It initialized
shadow state, imported HPT2 and all assigned retained sources, checked file/hybrid parity, wrote and
rebuilt a shadow checkpoint, made a verified SQLite backup, and only then activated `hybrid` mode
from the exact checkpoint digest.

The canonical result is `CLEAN` at revision 4 with domain digest
`fb0e4836b331d4803b19d0f3aef4632de07d3d880366495c9d0c93562b53afa2`. The tracked portable
checkpoint digest is `a9c3557a9a904b0878e7191b588660d040a54d0840233fa340a419881f07f1ca`; a fresh hybrid rebuild
matches the live domain digest. The verified pre-cutover SQLite backup has SHA-256
`e1d92f52c55dddd4207bfe388e8d85fbdf784ba01c2e7ca8be783f43d85d542b`. Legacy writes to
SQLite-owned fields are refused while file-owned document bodies remain writable.

A 5.04-second local functional soak made two independent audits. Both remained `CLEAN`, `hybrid`,
revision 4, checkpoint-current, and byte-identical in domain digest. This is the recorded M3 soak
window; release and client-canary soak requirements remain separate M4 evidence gates.

No disconnected snapshot updater ran against the maintainer. No push, publication, release,
installed-skill synchronization, downstream client mutation, legacy-file retirement, or GitHub
operation occurred.

## Repository Qualification

Before source freeze, the full Tool Shed profile passed 341 of 341 tests, provider-adapter
conformance, deterministic index regeneration, stale-path checks, reconciled work state, Program
Roadmap validation, and bootstrap-closure validation. After live cutover and tracked-checkpoint
creation, the same complete profile passed again with 341 of 341 tests and every listed repository
contract. The later bootstrap-to-hybrid sync path also passed its focused reconciliation test before
G3 closure.
