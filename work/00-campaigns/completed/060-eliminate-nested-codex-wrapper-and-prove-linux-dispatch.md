# Eliminate the nested Codex wrapper and prove one-call Linux App Server dispatch

Status: complete
Type: campaign
Updated: 2026-08-25
Next Action: none
Campaign ID: eliminate-nested-codex-wrapper-and-prove-linux-dispatch
Campaign Number: 060
Outcome: Make the normal Tool Shed GUI route a thin deterministic dispatcher so App Server, not a second Codex agent, performs bounded campaign work; prove the corrected path on Linux before Windows.
Primary Focus Areas: provider-portability
Supporting Focus Areas: campaign-lifecycle, workspace-safety, qualification-release
Depends On: prove-installed-native-linux-app-server-workflow
Decision: none
Detour For: prove-bactron-core-native-windows-app-server-workflow
Return To: prove-bactron-core-native-windows-app-server-workflow
Completion Gate: A fresh Linux GUI-path proof uses one deterministic dispatch command, no nested codex exec, existing qualified camp-run, pre-mutation host checks, one exact journaled change, one declared verification, compact output, and separately reported dispatcher and inner App Server usage; Campaign 059 remains untouched.
Completion Evidence: work/evidence/evidence-direct-linux-app-server-dispatch.md
Completion Date: 2026-08-25
Completion Order: 54
Disposition: completed

## Request

Replace the model-managed `ts: next --app-server` handoff with one cross-platform deterministic
dispatcher command. The dispatcher must reuse ordinary queue selection, require a strict
campaign-local execution capsule, perform writable Codex-state plus managed ChatGPT
authentication/network/model preflight before mutation, start a selected queued campaign through
the guarded lifecycle, and call the existing qualified `camp-run` implementation without spawning
`codex exec` or duplicating App Server policy. Reject unsafe paths, symlink traversal, shell-based
verification, missing qualification, and malformed capsules before mutation. Return compact
route, model/effort, dispatcher overhead, App Server tokens/turns/time/tool calls, journal paths,
exactly-once verification, terminal state, and one recovery action without raw prompts or model
responses.

Use focused unit tests while repairing. Once the candidate is unchanged, run the required full
validator once. Then create a clean disposable native Linux client with one queued proof campaign
and capsule, and invoke only the new dispatcher command directly from this GUI session. The proof
must create one exact marker path through App Server, run one declared shell-free verification,
show zero dispatcher model tokens and no nested Codex process, and preserve compact output. Do not
publish, synchronize the maintainer skill, change Bactron Core, start Campaign 059, or rerun the
full validator after successful candidate validation.

## Completion Check

A fresh Linux GUI-path proof uses one deterministic dispatch command, no nested codex exec, existing qualified camp-run, pre-mutation host checks, one exact journaled change, one declared verification, compact output, and separately reported dispatcher and inner App Server usage; Campaign 059 remains untouched.
