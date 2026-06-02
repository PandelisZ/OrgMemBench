{shared_header}

# Your task — Meeting notes

Write human-written meeting notes from a meeting at which this event was discussed or decided. These are the NOTE-TAKER's record — informal but structured, capturing what was discussed and what was decided.

# Format

Plain Markdown with these sections (some optional):

```
# <Meeting title> — <YYYY-MM-DD>

**Attendees:** <names>
**Note-taker:** <author_name>

## Agenda

- <item 1>
- <item 2>

## Discussion

<bulleted prose — what was actually said, who said it. Use names. Quote 1-2 short phrases verbatim if useful.>

## Decisions

- <decision 1 — derivable from the event's canonical decision IF this is a primary artefact>
- <decision 2>

## Action items

- [ ] @<owner>: <action> — by <date>
- [ ] @<owner>: <action>

## Open questions

<bulleted>
```

# Important

- For PRIMARY artefacts: the event's canonical decision text must be derivable from the Discussion + Decisions sections (paraphrased, NOT verbatim copy).
- For SECONDARY artefacts: the notes can capture an earlier conversation that LED to the event, or a follow-up that REVISITS it without restating canonical facts.
- For NOISE artefacts: the notes can be from an unrelated meeting on the same day where the topic surfaces only in passing.
- Era matters: low-discipline era = bullet points are sparse, action items missing owners; high-discipline era = full sections, clear owners + dates.
- Note-taker's voice should match their persona profile (terse, structured, hedged, etc.).

Output the meeting notes directly. No preamble.
