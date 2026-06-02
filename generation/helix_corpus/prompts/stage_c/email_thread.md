{shared_header}

# Your task — Email thread

Write a realistic internal email thread that documents this event. The thread has 2-5 emails, each from a participant. Standard email conventions apply.

# Format

Plain text. Each email separated by a `\n---\n` divider. Format each:

```
From: <Name> <name@helix.example>
To: <comma-separated names>
Cc: <comma-separated names — optional>
Date: <YYYY-MM-DD HH:MM>
Subject: <subject line; later emails start with "Re: " or "Fwd: ">

<body — paragraphs separated by blank lines. Quoted prior content uses `> ` prefix>
```

# Style

- Subjects: descriptive, short. The first email's subject becomes the thread's subject (later emails prepend "Re: ").
- Bodies: match the era. Founder-era + low-discipline: terse, 2-3 sentences. High-discipline: structured, sometimes with headers and bullet lists.
- Threading: later emails should quote relevant snippets of earlier emails with `> ` prefix. Sometimes responders trim quotes; sometimes they leave the full chain.
- Signatures: brief in early years (just first name), more formal in later years (name + title).

# Important

- For PRIMARY artefacts: at least one email in the thread states the canonical decision plainly (e.g. "Decided: we'll go with X").
- For SECONDARY artefacts: the thread can be a preliminary discussion that didn't reach the final decision, OR a customer-facing email that mentions the decision in passing.
- For NOISE artefacts: an email about an adjacent topic that name-drops the event without elaboration.
- One email should plausibly come from an executive participant if the event is strategic-decision-level.

Output the thread directly. No preamble. No code fences.
