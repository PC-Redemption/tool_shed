# Universal Closed-Loop G5 Released-Client Canary Evidence

Status: passed
Evidence ID: EVID-CLOSED-G5-CANARY
Gate: G5-RELEASE-CANARY-PROVEN
Campaign: release-and-canary-universal-closed-loop-reconciliation
Date: 2026-08-28

## Isolation And Upgrade

One disposable Tool Shed-owned client used local Git with zero remotes, an isolated Codex home, and
an isolated GitHub configuration whose `gh auth status` reported no authenticated hosts. No
unrelated project or account content was copied or inspected. Its exact published v0.34.2
disconnected baseline was clean and doctor-healthy before upgrade.

The published protocol-4 updater transaction `2641525d845a00de21f46f32` upgraded the client from
v0.34.2 to v0.35.0. It selected content commit
`e486943e56310321205fdd940db2b15fa54a97ca`, used the attested focused smoke, preserved project
identity `f92cb310-15f7-4e96-9be8-82ce53fb2d72`, retained verified rollback archive
`tool_shed.backup-20260828T215515Z.tar`, converged the work tree, and installed an exact matching
skill only inside the isolated Codex home.

Two nonqualifying baseline-preparation attempts failed safely: an explicit repository override
selected full validation and was refused by the older release's historical bootstrap state; an
empty v0.34.2 new-install attempt reached its doctor check and restored its pre-install state. The
qualified path began only after the exact v0.34.2 baseline was clean and committed.

## New Origin-To-Product Loop

The released client created a genuinely new file-authoritative Idea Brief and retained one material
execution change, accepted requirement, released product truth, exact target evidence, and passed
verification in structured state. Its root Idea cycle
`ea47cc2b-e3cd-4b70-ad51-123e583949f1` stayed open after the initial import. Direct product-result
cycle `aef5d6ae-5796-4d74-9ef4-92b3c87f58ef` then completed as `satisfied/reconciled` and
propagated upward. Only after that result was present did the guarded root transition make the Idea
cycle terminal `satisfied/reconciled` with no residual work. The final generic audit reported zero
open, invalid, terminal-unreconciled, or unpropagated cycles.

## Recovery, Rollback, And Soak

- Final hybrid revision: 4, storage mode `hybrid`, classification `CLEAN`.
- Domain digest: `5c6c7637ac78cb31d82980d95078e58d9f50319d59cbf0ba3d96ca586185650e`.
- Checkpoint digest: `51a8db36a264509626e3236aab99733a1a005c08422b01244ae8cc5af92ef426`.
- Verified SQLite backup SHA-256:
  `ece13e6c3dd0b194ccae1e8520647f0debf6463de6ff2874fab7320b5c1f302e`.
- Independent rebuild reproduced the exact domain digest.
- A write inside an explicit transaction on the disposable rebuilt database was rolled back; the
  accepted outcome and database SHA-256
  `402c1d394d21daf1ce667059d38919c0ff42ae3de859a3ed5d53efeccc225fd2` were unchanged.
- One hundred read-only generic audit/report rounds left both the live database SHA-256
  `bdc388ae6a4dcd6c67c52331959ba4a8d886d3a1c2b11d9bcfe3e6879387b237` and tracked checkpoint
  SHA-256 `0671a063e806af63235981b963860f3e683319cbafd22cffc3b1e96a98b7f9bd`
  unchanged.
- Final doctor verdict: `HEALTHY`, with zero findings, a clean Git worktree, fresh indexes, verified
  0.35.0 snapshot integrity, and zero unclassified work.

## Verdict

The released feature closes a new Idea-to-product loop in an isolated client and retains exact
recovery, rollback, and nonmutation evidence. `UPG-CLOSED-SYNTHETIC-CLIENT` passes. Fleet rollout
and unrelated projects remain outside this campaign.
