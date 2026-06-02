You are writing a short cross-reference phrase that should be inserted into an artefact in a fictional company's corpus.

# Source artefact (the artefact you're appending the reference TO)

- Genre: {source_genre}
- Author: {source_author_name}
- Event it documents: {source_event_summary}
- Date: {source_date}
- Era: {era_name} ({era_discipline_level} discipline)

# Target artefact (the artefact being referenced)

- Genre: {target_genre}
- Event it documents: {target_event_summary}
- Date: {target_date}
- Slot ID: {target_slot_id}

# Relationship

- Relation: **{relation_type}** (e.g. supersedes, reverses, caused_by, contradicts)

# Your task

Write **one short phrase** (5-30 words) appropriate to the source artefact's genre that points at the target artefact. Examples:

- For an ADR referencing a superseded ADR: `Supersedes: ADR-2023-014`
- For a Slack thread referencing an older Slack thread: `cf. the thread Maya started back in March about this`
- For a postmortem referencing an earlier incident: `For context, see the May 2022 outage postmortem (INC-2022-05-08).`
- For a Notion doc referencing another Notion doc: `(See: https://notion.so/helix/architecture-v2)`

# Constraints

- Match the source genre's conventions (formal for ADRs, casual for Slack).
- Match the era's discipline (sparse for low era, structured for high).
- The phrase should be SELF-CONTAINED — it gets inserted in a single line.
- Do NOT add any preamble, code fences, or commentary. Output the phrase only, on one line.
