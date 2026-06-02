{shared_header}

# Your task — Incident postmortem

Write a structured postmortem for an incident event. Postmortems are written 1-4 weeks AFTER the incident with a calm, blameless, evidence-driven posture.

# Format

Plain Markdown:

```
# Postmortem: <incident title> — <postmortem YYYY-MM-DD>

**Incident date:** <YYYY-MM-DD from the event context above>
**Severity:** SEV-<1-4>
**Authors:** <author_name and 1-2 others involved>
**Status:** Final | Draft

## Summary

<3-4 sentences: what happened, scope, customer impact>

## Timeline

<chronological bullet list of events during the incident, with timestamps. Include detection, escalation, mitigation, resolution>

- HH:MM — <event>
- HH:MM — <event>
- ...

## Root cause

<2-3 paragraphs: the underlying technical cause. MUST match the event's `reason_canonical` for primary artefacts.>

## Contributing factors

- <bullet — non-root factors that made things worse>
- <bullet>
- <bullet>

## What went well

- <bullet>
- <bullet>

## What went poorly

- <bullet>
- <bullet>

## Action items

- [ ] @<owner>: <action> — by <date> [P1|P2|P3]
- [ ] @<owner>: <action>
- [ ] @<owner>: <action>

## Lessons learned

<short paragraph>
```

# Important

- For PRIMARY artefacts: the canonical root cause MUST match the event's `reason_canonical`. The decision/action items must be derivable from the event's `decision`.
- For SECONDARY artefacts: an EARLIER postmortem for a similar incident, OR a partial draft that didn't become the final version.
- For NOISE artefacts: a postmortem for an unrelated incident that mentions this one as a precedent.
- Author voice — SRE / engineer voice. Calm, specific, no blame.
- Era: postmortems are characteristic of high-discipline eras. In a low-discipline era, the postmortem might be a 2-paragraph Notion doc rather than this structured format — keep the body, simplify the form.

Output the postmortem directly. No preamble.
