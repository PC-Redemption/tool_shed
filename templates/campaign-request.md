# {{ title }}

Status: queued
Type: campaign
Updated: {{ date }}
Next Action: execute when selected from the active campaign queue
Campaign ID: {{ campaign_id }}
Campaign Number: {{ campaign_number }}
Outcome: {{ outcome }}
Primary Focus Areas: none
Supporting Focus Areas: none
Depends On: none
Decision: none
Detour For: none
Return To: none
Completion Gate: {{ completion_gate }}
Completion Evidence: none
Disposition: none
Roadmap: none
Roadmap Revision: none
Milestone: none
Unlocks Gate: none

## Request

Describe the detailed execution request, constraints, and relevant context.

## App Server Preparation Contract

```json
{
  "campaign_id": "{{ campaign_id }}",
  "completion_evidence": "{{ completion_gate }}",
  "exact_resolution": "dispatch-time",
  "execution_shape": "single-bounded-camp",
  "inline_assets": "metadata-only",
  "objective": "{{ outcome }}",
  "schema_version": 1,
  "source_freshness": "required",
  "verification": "orchestrator-exactly-once"
}
```

## Completion Check

State how the owner or agent can verify that the full outcome—not merely an intermediate step—is complete.
