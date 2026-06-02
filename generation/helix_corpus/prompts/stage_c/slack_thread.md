{shared_header}

# Your task — Slack thread

Write a realistic Slack channel thread that documents this event. The thread should:

- Have a parent message (a post) from one of the participants.
- Have 3-10 replies from other participants AND/OR other personas plausibly in the channel.
- Use Slack conventions: `@name` mentions, `:emoji:` markers (e.g. `:fire:`, `:+1:`, `:eyes:`), code blocks for technical content, brief sentences, occasional crosstalk and rapid-fire replies.
- Reflect the era's discipline level: low era = more emoji, more informal, more typos; high era = more structured, more cross-references to docs.

# Output format

Plain text, one message per block. Format strictly:

```
[YYYY-MM-DD HH:MM] @<author>: <message>
```

(One line per message. Use realistic timestamps within the event's day. Indent reply messages with a `↳ ` prefix.)

# Channel context

- Channel: pick one of `#eng-platform`, `#proj-<topic>`, `#general`, `#incident-<id>`, `#cust-<customer>`, `#exec` — match the event type.
- The PRIMARY artefact (if this is one) must carry the canonical decision text from the event. Don't restate it word-for-word — have someone say something like "Ok decided: <paraphrase of event_decision>". The decision MUST be derivable from the thread.
- For SECONDARY artefacts: the thread can be a side-conversation, follow-up, or earlier brainstorm that PARTIALLY references the event without restating it.
- For NOISE artefacts: keep the thread topically adjacent but NOT informative about the event's canonical facts.

# Length

- 4-12 messages total. Length matches the event's significance: an incident gets a long thread, a routine policy change gets a short one.

Output the thread directly. No preamble.
