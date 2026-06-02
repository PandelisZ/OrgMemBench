You are generating realistic Slack messages of REAL WORK happening at a fictional B2B SaaS company — the day-to-day operational hum of people actually doing their jobs. This is "noise" only in the sense that it does NOT contain the major tracked decisions; it is NOT idle banter. It must read like genuine work, so a memory system has to understand real activity to tell it apart from the load-bearing decisions.

# Company

{company_one_liner}

# What the company is doing this period (ground the chatter in this — the work discussed must fit the company's actual situation this year)

{year_context}

# Channel

- Name: **{channel_name}**
- Purpose: {channel_purpose}
- Owning team: {channel_team}

# Time

- Month: **{year_month}**
- Era: {era_name} ({era_discipline_level} discipline)
- Tooling active now: {tooling_active}

# People active on/around this channel this month (use their names)

{personas_block}

# Your task

Generate **{n_messages} realistic Slack messages** for this channel in {year_month}. These are people DOING REAL WORK appropriate to this channel and this team — concrete, specific, operational. Draw on the kind of work in scope:

- Progress on actual tasks/tickets ("got the rate-limit middleware merged, moving to the retry logic on the webhooks")
- Debugging real problems ("the {channel_team} dashboard is double-counting EU shipments since the timezone change — looking now")
- Coordinating real work ("can you review the PR for the carrier-API adapter before the release?", "moving the integration test run to tonight")
- Deploy / ops / on-call activity ("deploying the billing fix to prod", "rollback done, the migration locked the orders table")
- Customer-driven work ("<a real customer> flagged slow exports again, opened HXL-#### to track")
- Cross-references to real projects, channels, tickets, and people in passing
- Brief, on-topic clarifying questions and answers between teammates

Keep it grounded and specific to the freight-forwarding domain and this company's real projects/customers this year. A LITTLE human texture is fine (a quick "nice!", a PTO heads-up) but the substance is WORK.

# Format

One message per line:

```
[{year_month}-DD HH:MM] @<name>: <message>
```

Use plausible day/time within the month. Reply messages get a `↳ ` prefix.

# Rules

- REAL WORK, not chit-chat. Avoid pure banter, memes, lunch threads. Every message should plausibly be someone doing or coordinating actual work.
- These messages MUST NOT state the major strategic decisions / incidents-with-root-cause / policy changes themselves (those are tracked elsewhere). They are the surrounding operational activity.
- Match the era tone: 2020-2021 scrappy and informal; 2024+ more structured and professional.
- Use ONLY the names listed above. Don't invent new employees. Reference period-correct tooling (Linear vs GitHub Issues, Salesforce vs HubSpot).
- Output ONLY the messages. No preamble, no headers, no code fences.
