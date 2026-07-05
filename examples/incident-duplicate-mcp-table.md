# Incident: Duplicate MCP Table Broke Codex

Status: example
Type: incident
Updated: 2026-07-05
Next Action: none

## Impact

Codex could not parse global config and could not resume the affected session.

## Cause

Duplicate `[mcp_servers.lessons]` tables were created during manual/native Windows adaptation of a shell installer.

## Recovery

Back up the config, reduce the lessons MCP entry to exactly one table, then fully restart Codex.

## Prevention

Prefer plugin bootstrap over raw config mutation. If config mutation is unavoidable, make it preserving, idempotent, and backed up.

