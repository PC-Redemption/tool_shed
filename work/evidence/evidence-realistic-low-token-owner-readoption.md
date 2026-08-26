# Evidence: Realistic low-token App Server owner readoption

Status: complete
Type: evidence
Updated: 2026-08-26
Next Action: publish and synchronize the post-v0.29.8 preparation and verifier repair only after separate owner authorization
Campaign: requalify-realistic-low-token-owner-loop
Campaign Reason: G9-OWNER-READOPTION completion evidence

## Operating result

The minimum owner path is one explicit command in the normal Codex GUI:

```text
ts: next --app-server
```

The current owner contract, hard ceilings, recovery actions, measurements, interaction counts,
and platform boundaries are consolidated in
`docs/codex-app-server-maintainer-note.md`. The detailed protocol contract remains in
`docs/codex-app-server-execution.md`.

The live defaults are four observed model requests, 180,000 cumulative input tokens, 65,536
cumulative serialized tool-result bytes, and 16,384 bytes for one result. A ceiling before
mutation returns `resume_bounded_camp`; a ceiling after an authorized mutation returns
`reconcile_workspace_then_resume_bounded_camp`. Reserved verification is skipped after an
interruption, and mutated work is never replayed automatically.

The representative Linux proof used 40,016 input tokens, 26,600.0 weighted units, two model
requests, 1,820 tool-result bytes, 16.851 seconds model time, and 17.350 seconds CAMP time. It
needed no mid-run owner interaction and ended safe and verified.

The representative Windows proof used 81,570 input tokens, 168,501.6 combined weighted units,
three model requests including preparation, 2,362 tool-result bytes, 75.240 seconds across model
stages, and 79.843 seconds total dispatch time. No mid-run prompt occurred before the safe reserved
verification stop. One no-replay reconciliation was required because released v0.29.8 selected an
unavailable Python launcher and a broad Git assertion; the built-in console verifier then passed
three commands and Campaign 020 completed. The old 5,403-byte verifier payload did not recur.

The earlier two-turn Linux/Windows asset fixtures remain historical transport evidence. They no
longer support a general efficiency claim, and the 893,723-token nested-wrapper fixture remains an
unsupported anti-pattern rather than a supported route.

## Boundaries

- Routine CAMP execution uses Terra/medium; capsule preparation uses Sol/high only when needed.
- Linux direct execution is field-proven with qualified local Codex.
- Windows execution and deterministic verification require the logged-in GUI console. Direct SSH
  service processes cannot reach its sandbox pipe.
- The canonical Python-launcher, broad-diff, and UTF-8 repairs are tested but unpublished. Tool
  Shed v0.29.8 clients do not receive them until a separately authorized release and upgrade.
- API fallback, global enablement, unqualified workspace writing, macOS, deployment, production,
  and unsupported roles remain outside the qualified contract.
- Weighted usage is a relative proxy, not cost or ChatGPT allowance; outer GUI tokens are not
  exposed.

## Focused smoke

Documentation assertions verify the command, all four ceilings, both recovery actions, both
representative input-token and weighted-usage measurements, the Windows console limitation, the
unpublished repair boundary, and the explicit supersession of fixture-only conclusions. No
implementation inputs changed during this campaign, so no implementation suite was repeated.
