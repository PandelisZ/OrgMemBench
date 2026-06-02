You are writing a SHORT, casual artefact that mentions ONE fact about a past company decision in passing — the kind of incidental reference that shows up months later in everyday chatter. The point: a piece of the answer to a future question is buried here, in something that otherwise looks like noise.

# Company

{company_one_liner}

# The single fact to embed (mention it naturally, in passing — do NOT restate the whole decision)

{fact}

# Context for this mention

- This is being mentioned/recalled on or around: **{mention_date}** (which is AFTER the original decision)
- Genre of this artefact: {genre}
- People who might mention it (use a name): {people}

# Your task

Write a SHORT artefact in the given genre where someone references this single fact incidentally — a callback, a "remember when we...", a justification that leans on it, a correction, a casual aside. It should read like a real, mundane moment, NOT like a formal record of the decision.

Examples of the vibe:
- Slack: "@x didn't we settle on the Postgres route back in {mention_date_month}? pretty sure that's why we can't just swap it now"
- doc comment: "(note: this follows the {mention_date_month} call where we agreed to ...)"
- email aside: "as discussed when we made the call on this, ..."
- retro line: "the decision to ... earlier in the year is still paying off / biting us"

# Hard rules

- Embed the ONE fact above and nothing more — do NOT spell out the full decision, reason, date, participants, AND alternatives together. Just this fragment, in passing.
- Keep it SHORT (a few lines for Slack/comment; a short paragraph for email/retro).
- It must be dated/contextualised AFTER the original decision (it's a later reference).
- Use the genre's conventions. No code fences. Output only the artefact.
