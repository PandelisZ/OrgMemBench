You are identifying causal and lineage relationships between events in a company's source-of-truth timeline.

# Company context

{company_one_liner}

# All events to-date (the candidate set for relationships)

{events_block}

# Your task

Identify pairs of events that should be connected by one of these relationships. Output **one triple per line** in this exact format:

```
EV-YYYY-NNN -> <relation> -> EV-YYYY-NNN
```

The closed set of relations:

- **supersedes**: a later strategic_decision / policy_change explicitly replaces an earlier one. The earlier event's outcome no longer holds; the later event's outcome is the current state. Example: `EV-2023-014 -> supersedes -> EV-2022-029` if the 2023 ADR replaces the 2022 ADR.
- **contradicts**: two events express conflicting claims about the same fact. Use when two parties remembered or stated different things about the same situation. Example: contradiction_episode events almost always link to a strategic_decision or customer_event via this relation.
- **caused_by**: this event happened because of an earlier event. Incidents are often caused_by a launch (a launch triggered an incident); a customer_event (escalation) can be caused_by an earlier incident.
- **retroactively_corrected_by**: an earlier event's recorded_at was wrong — a later event corrects what was understood about an earlier moment in time. This is the bi-temporal pattern. Example: a 2024 retrospective revealing that a 2022 incident's true root cause was different from what was reported at the time.
- **reverses**: a later event explicitly undoes an earlier one (subset of supersedes — reverses is "we went back" while supersedes is "we replaced with something new"). E.g. the v3 rewrite was greenlit then reversed in 2023.
- **re_attempts**: a later event takes another swing at something an earlier event tried and failed. Example: a 2024 v3 architecture re-attempt picks up where the 2022 v3 attempt left off.
- **resolved_by**: a contradiction or open question was settled by a specific later event.

# Important rules

- **Direction matters**: `A -> supersedes -> B` means "A came later and replaced B".
- **Date ordering**: for supersedes / reverses / re_attempts / resolved_by, the source event's occurred_at MUST be AFTER the target event's occurred_at.
- **Don't force relationships**: not every event has links. A pure hire event probably has no relations. Only emit triples you're confident about.
- **Mix the relation types**: do NOT emit only supersedes. A real company timeline has all 7 types.
- **No invented events**: only use IDs from the events_block above.
- **Output ONLY the triples**, one per line. No headers, no commentary, no code fences. Lines that don't match the pattern will be silently dropped.

Expected output range: roughly 1 relation per 3-5 events. So {expected_count} events → ~{expected_relations} triples.
