# Evidence: Realistic Core App Server token regression

Status: complete
Type: evidence
Updated: 2026-08-26
Next Action: none
Campaign: standalone
Campaign Reason: contradictory field evidence that reopens the low-token Program Roadmap

## Result

The one-command App Server path can prepare, mutate, journal, and verify real work, but the first
representative Bactron Core execution did not satisfy the low-token outcome established by the
small two-turn fixtures.

| Stage | Input tokens | Total tokens | Model turns |
| --- | ---: | ---: | ---: |
| Automatic capsule preparation | 40,913 | not retained | not retained |
| Foundation CAMP worker | 540,741 | 549,329 | 14 |
| Runtime CAMP worker | 625,383 | 635,582 | 14 |

The workers received a bounded capsule with approximately 2,879 inline bytes, so initial prompt
size was not the dominant failure. Repeated model turns and accumulated tool results caused the
context to grow without a proactive cumulative ceiling. By comparison, the earlier Windows proof
used 38,324 input tokens in two model turns and exercised only a tiny two-path fixture. It proved
transport and mutation safety, not representative campaign efficiency.

The Windows built-in deterministic verifier transport also failed twice with the same 5,403-byte
stderr payload and hash prefix `436398`; direct verification then passed. The repeatable transport
failure is separate from product correctness and remains a Windows-specific follow-up after the
shared Linux-first usage bound is proven.

## Consequence

The historical G5 adoption evidence remains preserved, but its general low-token conclusion is
superseded for realistic campaigns. The corrective sequence is:

1. enforce proactive cumulative input, turn, and tool-output budgets;
2. stop safely or hand off a deterministic bounded continuation before runaway growth;
3. prove the behavior on a representative native Linux campaign; and
4. only after a separately authorized release, synchronization, and Core snapshot upgrade, repair
   and re-prove the Windows verifier transport and realistic Windows budget.

No Bactron deployment or Campaign 013 replay occurred.
