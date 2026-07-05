# ADR: Hosted Installer Uses Plugin Bootstrapper

Status: example
Type: adr
Updated: 2026-07-05
Next Action: none

## Context

A hosted installer that writes raw Codex MCP config can corrupt unrelated user configuration or create duplicate TOML tables.

## Decision

Make the hosted installer bootstrap the Codex plugin instead of writing `[mcp_servers.lessons]` directly.

## Consequences

Positive:

- avoids raw config mutation
- aligns install path with Codex plugin distribution
- reduces Windows conversion risk

Negative:

- depends on Codex plugin commands being available
- still needs restart validation

