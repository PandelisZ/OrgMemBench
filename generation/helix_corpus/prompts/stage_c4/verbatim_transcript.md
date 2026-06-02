You are producing a VERBATIM meeting transcript for a fictional B2B SaaS company — the kind of long, raw, auto-transcribed recording (Otter.ai / Granola style) where a real decision gets argued out in full. This is a LONG artefact: a real hour-long meeting transcript runs many thousands of words.

# Company

{company_one_liner}

# The meeting (this is a REAL tracked decision — the transcript must contain the ground truth, but woven through the conversation, NOT stated as a clean summary)

- Meeting topic: {event_summary}
- Date: **{event_date}**
- The decision that was reached: {decision}
- The reason it was reached: {reason}
- Alternatives that were debated: {alternatives}
- People in the room (use their names; give them distinct voices/positions): {participants}

# Your task

Write the FULL verbatim transcript of this meeting. Requirements:

- **Long and realistic** — aim for a substantial transcript (the meeting ran ~45-60 minutes). Many speaker turns, tangents, interruptions, "can you hear me?", people talking over each other, someone joining late, action items at the end.
- **The ground truth must be RECOVERABLE but DISPERSED through the dialogue**: the decision emerges from debate (not announced up front); the reason surfaces across several people's arguments; the alternatives are each championed by someone before being set aside; the date is referenced naturally (e.g. "before end of {event_date_month}"). A reader must follow the whole conversation to reconstruct who decided what and why.
- **Distinct voices**: give each named participant a consistent speaking style and a position in the debate. Show disagreement and how it resolves.
- **Realistic transcript artifacts**: timestamps per turn, [inaudible], [crosstalk], filler words, someone going off on a tangent that is pure noise.
- Era-appropriate: if before 2023, note it's hand-typed notes rather than auto-transcript at the top; 2023+ can be an Otter.ai/Granola auto-transcript with a confidence header.

# Format

Start with a header line:
`[TRANSCRIPT] {event_summary} — {event_date}`

Then turns:
`[HH:MM:SS] Speaker Name: <what they said>`

# Hard rules

- Do NOT summarise. This is verbatim dialogue, turn by turn.
- The decision, reason, every alternative, the date, and every named participant MUST appear somewhere in the dialogue.
- Use ONLY the participant names provided (plus the occasional unnamed "someone").
- No code fences. Output only the transcript.
