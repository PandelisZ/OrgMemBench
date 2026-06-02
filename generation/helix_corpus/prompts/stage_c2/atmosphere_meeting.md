You are generating notes from a ROUTINE recurring group meeting at a fictional B2B SaaS company — the kind of meeting that happens on a regular cadence and is NOT a momentous one-off decision. This is background texture a memory system must sift through.

# Company

{company_one_liner}

# What the company is doing this period (the meeting must make sense for this — its agenda, projects, customers, and concerns should fit the company's actual situation this year)

{year_context}

# The meeting

- Type: **{meeting_type}**
- Attendee scope: {attendee_scope}
- Date: **{meeting_date}**
- Era: {era_name} ({era_discipline_level} discipline)
- Company size context: {headcount_note}

# Attendees (use their names; pick the subset that fits this meeting type)

{personas_block}

# Your task

Write the notes/minutes for this {meeting_type}. Match the format to the meeting type:

- **all-hands**: agenda + company updates per function + a few Q&A items + shout-outs. Light, broad.
- **standup / team sync**: round-robin of "what I did / what's next / blockers" per person.
- **sprint planning**: committed tickets, capacity, carry-over.
- **sprint retro**: what went well / what didn't / action items.
- **architecture / ADR review**: proposals discussed, leaning, follow-ups (but NOT a final binding decision — that would be a tracked event).
- **pipeline review**: deals by stage, at-risk accounts, forecast.
- **product review**: features in flight, feedback, prioritisation chatter.
- **hiring sync**: open roles, candidates in pipeline, scheduling.
- **finance review**: burn, runway, spend flags.
- **board meeting**: high-level metrics recap + topics raised (routine cadence, not a fundraise decision).
- **OKR planning / cross-functional sync**: objectives, owners, dependencies.

# Hard rules

- This is a ROUTINE meeting. It must NOT contain a momentous strategic decision, a postmortem root-cause, a policy change, or anything that reads like ground-truth canon. Keep it operational and mundane — deliberately low-signal.
- It is a GROUP meeting. Do NOT generate 1:1 / private / performance / compensation content.
- Era-appropriate: 2020-2021 scrappy and short; 2024+ structured with clear sections.
- Use ONLY the names listed above. Reference the era's tooling where natural.
- Begin with a one-line header: `[MEETING: {meeting_type}] {attendee_scope} — {meeting_date}`.
- Output only the meeting notes. No code fences, no preamble.
