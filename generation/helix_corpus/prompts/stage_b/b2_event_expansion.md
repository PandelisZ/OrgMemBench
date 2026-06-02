You are expanding an event sketch into its full record for the source-of-truth graph. The benchmark answers questions by **deterministically projecting fields from this record** — so every field must be specific, accurate, and consistent with the canon.

# Company context

{company_one_liner}

# Year arc (for tone and texture)

{year_arc_block}

# Doc-discipline era

{era_block}

# Persona context (only the participants in this event)

{participants_block}

# Customer context (if this event involves a customer)

{customer_block}

# Event sketch (from B1, your source of truth for what this event IS)

{event_sketch}

# Your task

Expand this event into a full YAML record. Output **exactly one YAML document** (no code fences, no preamble). Schema:

```yaml
id: <verbatim from sketch — EV-YYYY-NNN>
type: <verbatim from sketch>
occurred_at: <verbatim from sketch>
recorded_at: <usually same as occurred_at, BUT for retroactive corrections this is a LATER date>
participants:
  - P-XXXX
  - P-XXXX
decision: |
  <2-4 sentences specific to what was decided / what happened. Name people,
  name alternatives, name the outcome. This is the canonical answer the
  benchmark will project from.>
reason_canonical: |
  <1-2 sentences: WHY this happened. The reason a system-under-test must
  recover from the corpus. For strategic decisions, this is the deciding
  factor; for incidents, the root cause; for departures, the
  departure_circumstance; for policy changes, the trigger.>
alternatives_considered:
  - <name of alternative 1 — required for strategic_decision events; empty list otherwise>
  - <name of alternative 2>
                                # for strategic_decision events, MUST have
                                # at least 2 alternatives. For other event
                                # types, optional.
category_target: <verbatim from sketch>
summary: <verbatim from sketch>
doc_dispersal_pattern: <one of: informal_primary, authoritative_primary, mixed>
                                # informal_primary: primary evidence will be
                                # in Slack threads / meeting transcripts / emails.
                                # 60-70% of events should be informal_primary.
                                # Pick authoritative_primary ONLY for events
                                # that genuinely warrant a clean ADR / Notion
                                # doc / contract.
evidence_in_corpus:
  - role: primary
    genre: <one of: slack_thread, meeting_transcript, meeting_notes, email_thread,
            adr, rfc, notion_doc, incident_report, postmortem, customer_call_transcript,
            customer_call_notes, sales_crm_entry, retrospective, contract_redline>
    author: P-XXXX                # the persona who creates this artefact
    slot_id: ART-{event_id}-001   # unique placeholder ID Stage C will materialise
  - role: secondary
    genre: <...>
    author: P-XXXX
    slot_id: ART-{event_id}-002
                                # typical: 1 primary + 2-3 secondary artefact slots.
                                # primary slot carries the answer the question probes.
                                # secondary slots contribute context.
```

# Field-specific guidance

- **decision** is the field a benchmark question for C1/C2 will project to "the answer". For a strategic_decision, this should read like the conclusion of a clean meeting summary. For a policy_change, the new policy text. For an incident, what happened and how it was resolved.
- **reason_canonical** is the answer a question of type "why X" projects to. Keep it tight.
- **alternatives_considered** is what a C2 (decision provenance) question projects to. It must be a real list of named alternatives, not generic phrases.
- **evidence_in_corpus[*].genre** determines what Stage C generates. Mix genres according to the §4.2 dispersal principle (most primary slots informal).
- **evidence_in_corpus[*].author** must be a P-ID from `participants` (the people in the room are the ones who write the artefacts).

# Important

- **The id and type and occurred_at and category_target and summary MUST be verbatim from the sketch.** Do not invent or change.
- **Do not output anything other than the single YAML document.** No prose preamble, no code fences.
- Be specific. Generic answers won't survive Stage F validation.
