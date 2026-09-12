# 100k Project Executive View

`work/100k.md` is Tool Shed's standard, easy-to-find whole-project review. It is the project-level
“CEO view”: a concise decision surface backed by an exhaustive strategic ledger. It does not own
strategy, priority, lifecycle, or completion truth.

The executive section shows canonical authority and digest, project health, the release completion
horizon, deterministic next-cycle candidates, attention signals, recent material changes, and
approved focus-area coverage. The ledger accounts for every canonical Idea, Project Map, Program
Roadmap, and Campaign with lifecycle, planning, outcome, reconciliation, closure, parent, and
produces state. Existing commands remain available for detail and mutations.

```bash
python3 scripts/project_projection.py --workspace . 100k
python3 scripts/project_projection.py --workspace . render-100k
python3 scripts/project_projection.py --workspace . check-100k
```

The first command renders without writing. `render-100k` atomically refreshes the tracked file and
refuses to overwrite content that lacks the generated marker. `check-100k` compares exact expected
bytes and fails for missing, stale, manually edited, or truncated accounting. Strict Doctor applies
the same freshness gate. Installation, snapshot update, and Work2 release-cohort registration
refresh the projection at their controlled checkpoints.

Rendering is deterministic: it contains source timestamps and digests, not the current wall clock.
Under Hybrid authority it reads database-owned documents and outcome state; under file authority it
uses the established file projection and reports unavailable capabilities honestly. It performs no
project-state mutation beyond replacing its own marked generated output.
