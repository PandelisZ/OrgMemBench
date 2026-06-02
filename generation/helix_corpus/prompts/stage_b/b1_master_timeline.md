You are writing the master timeline of significant events for a fictional B2B SaaS company. These events will be the **ground truth** the benchmark probes against.

# Company context

{company_one_liner}

# This window

- **Year-Quarter**: {year}-Q{quarter}
- **Team**: {team}
- **Doc-discipline era**: {era_name} ({era_discipline_level})
- **Year theme (from canon)**: {year_theme}

# Personas active in this window (use their IDs in `participants:`)

{personas_window_block}

# Customers relevant to this window

{customers_window_block}

# Depth arcs already established (you may elaborate but not duplicate)

{depth_arcs_summary}

# Your task

Write **{target_event_count} significant events** that happened in {year}-Q{quarter} on the **{team}** team. Each event is a structured Markdown block. Format strictly:

```
## EV-{year}-NNN

type: <one of: strategic_decision, hire, departure, launch, incident, customer_event, supersession, contradiction_episode, policy_change>
occurred_at: YYYY-MM-DD
participants: P-XXXX, P-XXXX
summary: <one sentence describing what happened — concrete, specific, with a named actor and a named outcome>
category_target: <one of C1, C2, C3, C4, C5, C6, or "none">
```

# Event-type guidance

- **strategic_decision**: a multi-party choice with at least 2 alternatives considered. Tag `category_target: C2` (decision provenance). Some of these will later be marked superseded by a later strategic_decision in B3.
- **hire**: someone joining. Use P-IDs from the personas block — if a persona's `joined_year` matches this window, that's the hire event.
- **departure**: someone leaving. Departure_circumstance should match what's in the persona profile.
- **launch**: a product release, feature ship, or initiative kickoff. `category_target: none` unless it has lineage.
- **incident**: an outage, security event, or operational failure. Tag `category_target: C5` (justification chains) — incidents will be reconstructed from postmortems.
- **customer_event**: a customer-related event (escalation, renewal, churn, expansion). Tag `category_target: C2` or `C6` depending.
- **supersession**: when this event explicitly replaces a prior policy / decision / fact. Tag `category_target: C1` (supersession-with-reason).
- **contradiction_episode**: two parties expressing conflicting views on the same fact. Tag `category_target: C6` (contradiction with attribution).
- **policy_change**: a written policy update (refund policy, hiring rubric, SLA). Tag `category_target: C1`.

# Category targets — distribute across categories

Spread the event mix across categories. A typical {target_event_count}-event window includes:
- ~30-40% strategic_decision (covers C2)
- ~15-20% hires
- ~5-10% departures
- ~10% launches
- ~10% incidents (covers C5)
- ~10% customer_events (covers C6 / C2)
- ~10-15% policy_changes / supersessions (covers C1)
- some contradiction_episodes (covers C6) — at least one per window if possible

If you can't reasonably cover all categories in this window, prefer covering C1, C2, C5 first (those are the load-bearing benchmark capabilities).

# Important rules

- **Event IDs are NUMBERED**: use `EV-{year}-001` through `EV-{year}-NNN`. Numbering may continue from earlier windows (the runner will renumber if needed).
- **occurred_at must fall within this window** ({year}-Q{quarter}, i.e. the relevant 3 months).
- **participants must reference real persona IDs** from the personas block above. **No invented names** at this stage.
- **summary must be concrete**: not "a decision was made" but "Daniel Fiala chose Postgres over MongoDB for the v2 storage layer, citing better operational tooling, over Pavel's preference for Mongo".
- **No code fences** around the output.
- Output **only** the {target_event_count} `## EV-...` blocks. No preamble. No headers above them. No commentary.
