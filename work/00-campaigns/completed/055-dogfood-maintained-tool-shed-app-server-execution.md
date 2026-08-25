# Dogfood maintained Tool Shed App Server execution

Status: complete
Type: campaign
Updated: 2026-08-25
Next Action: none
Campaign ID: dogfood-maintained-tool-shed-app-server-execution
Campaign Number: 055
Outcome: Use the current candidate to complete one useful bounded Tool Shed campaign through App Server and close only defects exposed by that real run.
Primary Focus Areas: provider-portability
Supporting Focus Areas: workspace-safety, campaign-lifecycle
Depends On: none
Decision: none
Detour For: none
Return To: none
Completion Gate: G1-DOGFOOD-WORKS passes with real-run, focused-check, journal, model-routing, and usage evidence.
Completion Evidence: G1-DOGFOOD-WORKS passed. GUI repair added the visible no-fallback banner and focused unittest passed 1/1 in 0.380s. Initial whole-file context exceeded 100000 bytes; relative-path smoke attempts failed safely with no mutation. Repaired handoff used the absolute authorized path and a 7405-byte focused capsule. Successful App Server smoke used /home/jon/.local/bin/codex 0.149.0, gpt-5.6-terra medium, API fallback disabled, 2 model turns, 41745 input plus 380 output plus 34 reasoning tokens (42125 total), weighted usage 25823.4, 12.151s model duration and 12.677s camp duration, 1 fileChange call, exactly 1/1 deterministic verification, exactly one declared modified path, no unexpected paths, pre-existing work preserved, and journal final_state verified.
Completion Date: 2026-08-25
Completion Order: 50
Disposition: completed
Roadmap: low-token-cross-platform-campaign-execution
Roadmap Revision: 1
Milestone: M1-MAINTAINER-DOGFOOD
Unlocks Gate: G1-DOGFOOD-WORKS

## Request

Choose the smallest currently useful Tool Shed source or operator-facing improvement with one deterministic focused check and a narrow declared path set. From the canonical maintained Linux workspace, attempt this campaign through the explicit App Server route using the current qualified execution role. Capture selected executable/model/effort, bounded context, model turns, raw and weighted usage, elapsed time, tool calls, declared verification counts, changed paths, and journal state. If an ordinary defect blocks the run, preserve its smallest diagnostic, repair it through the normal GUI inside this same campaign, rerun only the failed focused check, then perform one App Server end-to-end smoke. Do not run the full validator, publish, synchronize an installed skill, create a detour campaign, or expand platform scope.

## Completion Check

G1-DOGFOOD-WORKS passes with real-run, focused-check, journal, model-routing, and usage evidence.
