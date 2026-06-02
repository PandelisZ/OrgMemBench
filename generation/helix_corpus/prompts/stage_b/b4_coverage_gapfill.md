You are reviewing the source-of-truth timeline for a fictional company benchmark. Your job: identify which **benchmark categories are under-represented** and propose new events to fill the gaps.

# Coverage so far

{coverage_block}

# Targets (events per category for this size)

{targets_block}

# Existing events in the timeline (compact)

{events_summary_block}

# Existing relationships

{relations_summary_block}

# Personas and customers available

{personas_summary}

{customers_summary}

# Your task

Identify which categories (C1-C6) are below their target and propose new events to fill the gaps. The output is a list of event sketches in **the same format as B1's master timeline** — `## EV-YYYY-NNN` blocks with `type:`, `occurred_at:`, `participants:`, `summary:`, `category_target:`.

Specifically generate:
{gapfill_directives_block}

# Important

- Events must fit chronologically into existing years (between {min_year} and {max_year}).
- Use existing P-IDs and C-IDs only.
- For C1 events: include events that look like good supersession-with-reason candidates. The B3 cross-event-linking pass will later attach `supersedes` edges. Mark these as `type: policy_change` or `type: strategic_decision` (the former gets superseded by a later one).
- **For C3 (retroactive correction) events: structurally different from other categories.** A C3 event is a NEW event that retrospectively reveals that an EARLIER event's recorded understanding was wrong. The new event MUST:
  - Pick one EARLIER event from the timeline above as its target (must occurred_at ≥ 6 months before the new event)
  - Have summary text that explicitly references the earlier event being corrected (e.g. "2024 retrospective discovered that the 2022 incident root cause was X, not Y as previously reported")
  - Carry a `corrects_event_id: EV-YYYY-NNN` field naming the target event
  - Mark `type: customer_event` OR `type: contradiction_episode`
  - Have `recorded_at` set to the new event's occurred_at, but the SUMMARY should make clear the event is about understanding a PAST event differently
  Example C3 event format:
  ```
  ## EV-2024-XXX
  type: contradiction_episode
  occurred_at: 2024-06-15
  participants: P-0003, P-0005
  summary: Retrospective audit revealed that the 2022-03 launch failure was caused by data-pipeline misconfiguration, not the production capacity issue documented at the time.
  category_target: C3
  corrects_event_id: EV-2022-014
  ```
- For C5 events: include events with rich evidence trails (incident_report, postmortem, multiple meeting transcripts). Mark `type: incident`.
- For C6 events: include explicit contradiction_episode events where two named people disagreed.

Output **only the new event sketches** in B1 format, separated by `\n\n`. No commentary, no code fences. If a category is already at target, do NOT generate events for it.
