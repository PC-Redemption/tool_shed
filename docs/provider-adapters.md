# Tool Shed provider adapters

Tool Shed is a portable coordination protocol with native AI-provider packaging. The portable core
owns artifacts, campaign behavior, authority boundaries, evidence-response rules, deterministic
workspace operations, and conformance scenarios. Adapters own instruction discovery, native
configuration paths, permissions, hooks, tools, and product-specific lifecycle behavior.

## Product Boundary

```text
operator request
      |
provider-native instruction adapter
      |
portable Tool Shed SKILL.md contract
      |
workspace files + deterministic Python utilities
      |
portable work artifacts and verified outcomes
```

Files and Git are authoritative project state. MCP may expose deterministic Tool Shed operations
to a provider, but it is optional and must not become a second source of artifact truth.

## Supported Adapters

The versioned adapter registry is `adapters/providers.json`.

| Provider ID | Native instruction file | Static qualification |
| --- | --- | --- |
| `codex` | `AGENTS.md` | Level 5 in the canonical development/client environment |
| `claude-code` | `CLAUDE.md` | Level 2 packaging and planning contract |
| `gemini-cli` | `GEMINI.md` | Level 2 packaging and planning contract |
| `github-copilot` | `.github/copilot-instructions.md` | Level 2 packaging and planning contract |
| `cursor` | `.cursor/rules/tool-shed.mdc` | Level 2 packaging and planning contract |

Static qualification proves safe, idempotent installation, preservation of owner content, portable
routing, discussion behavior, coordination behavior, and artifact compatibility. It does not claim
that a provider's web, IDE, CLI, cloud, and API surfaces have identical tools or authority.

## Capability Levels

1. `Discussion`: analyze and recommend without durable workspace mutation.
2. `Planning`: read and create portable Tool Shed artifacts.
3. `Workspace`: edit files, run deterministic utilities, and validate results.
4. `Integrated`: use MCP, hooks, policies, permissions, or structured provider tools.
5. `Delivery`: plan, implement, build, deploy, and verify end to end.

Compatibility is always a provider-surface plus level claim. Before increasing an adapter's
declared qualification, run frozen scenarios in that actual surface and record outcome evidence.

## Install Native Guidance

From a released workspace snapshot:

```bash
python3 tool_shed/scripts/install_into_workspace.py . --provider codex
python3 tool_shed/scripts/install_into_workspace.py . --provider claude-code
python3 tool_shed/scripts/install_into_workspace.py . --provider gemini-cli
python3 tool_shed/scripts/install_into_workspace.py . --provider github-copilot
python3 tool_shed/scripts/install_into_workspace.py . --provider cursor
```

Repeat `--provider` or use `--provider all`. Omitting the option installs `codex` for backward
compatibility. The installer preserves existing instruction-file content and creates or replaces
only marked Tool Shed blocks. Re-running it is idempotent. Cursor receives MDC frontmatter only
when its Tool Shed rule is first created.

The installed routing tells the provider to read the workspace-local
`tool_shed/skills/tool-shed/SKILL.md` when a request begins with `ts:`. This avoids copying and
eventually drifting five separate workflow implementations.

Snapshot upgrades use `--guidance-only` automatically. They detect every provider instruction file
that already contains marked Tool Shed guidance, default to Codex when none exists, replace the
entire disconnected snapshot so removed Markdown cannot linger, and verify all skill references
through the release manifest. The update transaction captures selected instruction files and
restores them together with the old snapshot if any post-install check fails. Root `work/`, indexes,
the Q&A inbox, and `.gitignore` remain untouched by the guidance refresh.

Codex has one additional provider-owned lifecycle boundary: auto-discovery may load a user-level
copy from `${CODEX_HOME:-~/.codex}/skills/tool-shed` before workspace routing takes effect. The
installer reports when that copy differs from the released workspace skill. The snapshot updater's
explicit `--sync-codex-skill` option installs a missing copy or backs up and replaces an exact prior
released copy. Backups remain outside the active `skills/` discovery directory; modified,
unmanaged, or symlinked targets are refused. A fresh Codex session is
required after synchronization.

`adapters/codex-skill-releases.json` carries compact tree digests for prior stable skills. It lets
the disconnected installer and updater classify a byte-exact older release consistently without
network access or embedded Git history. Manifest refresh regenerates this catalog from valid
stable tags, and connected validation rejects catalog drift.

## Portable Versus Provider-Owned Behavior

Portable core:

- `ts:` request meaning, including discussion and ship routes;
- minimum sufficient coordination;
- artifact shapes, state, indexing, and reconciliation;
- campaign continuity, authority discipline, and outcome verification;
- generated-evidence safeguards;
- deterministic CLI interfaces and output contracts.

Provider adapters:

- instruction filename and precedence;
- skill or plugin discovery and invocation syntax;
- tool names and available filesystem or shell operations;
- permission, sandbox, approval, policy, and hook enforcement;
- model catalogs, reasoning controls, session restart behavior, and distribution packaging.

The Codex reasoning catalog remains an optional Codex extension. It is not part of the portable
core and must not run on ordinary request paths for other providers.

## Discussion And Coordination Contract

`ts: discuss <topic>` is the authoritative discovery route. `discussion:` is an informal read-only
entry signal. Neither writes workspace state without an explicit capture or planning request.

The agent starts at the lowest adequate level:

- Direct: no artifact, direct execution and verification.
- Guided: checklist or ticket with targeted validation.
- Coordinated: workpackage or map with staged verification.
- Deep: bounded research and controlled evidence for consequential cross-layer uncertainty.

Route-specific skill references load only when needed. Continuation preserves a compact capsule of
the outcome, current constraint, decisions, evidence, authority boundary, and next action.

## Conformance Gates

Provider qualification evaluates outcomes rather than exact prompts or tool-call sequences:

- discussion remains non-mutating;
- owner instruction content survives installation and update;
- repeated installation produces no additional changes;
- the smallest sufficient coordination level and artifact are selected;
- portable artifacts remain readable after switching providers;
- authority boundaries and campaign verdicts remain consistent;
- declared capability never exceeds observed execution and verification behavior;
- instruction overhead, turns, failed attempts, corrections, and recovery are measured when the
  surface exposes them.

Codex remains the end-to-end reference adapter. A broad generic-product claim requires at least two
independent non-Codex adapters to pass representative runtime scenarios; static Level 2 adapters
are labeled accordingly until that evidence exists.
