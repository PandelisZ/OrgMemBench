You are generating realistic everyday INTERNAL email threads for a fictional B2B SaaS company — routine internal correspondence, not momentous decisions. This is background noise a memory system must sift through.

# Company

{company_one_liner}

# What the company is doing this period (ground the threads in real work that fits this)

{year_context}

# Team / context

- Team: **{team}**
- Month: **{year_month}**
- Era: {era_name} ({era_discipline_level} discipline)

# People (internal — use their names + plausible @helix.example addresses)

{personas_block}

# Your task

Generate **{n_threads} INTERNAL email threads** for {year_month}. Each thread is a realistic back-and-forth of **4-8 emails** between employees, WITH quoted history accumulating in each reply (the `>` quoted text from earlier messages grows down the thread, as real email does). These are routine: meeting scheduling, document review requests, sprint coordination, PTO/logistics, "quick question", forwarding an FYI, weekly team summaries, reply-all discussions that wander. NOT major decisions or tracked events.

# Format

Separate each THREAD with a line containing only `=== THREAD ===`. Within a thread, separate emails with `---`. Each email:

```
From: <Name> <name@helix.example>
To: <comma-separated names>
Date: {year_month}-DD HH:MM
Subject: <subject; replies prefix "Re: ">

<body — 1-3 short paragraphs. Later emails may quote with > prefix.>
```

# Hard rules

- **INTERNAL ONLY.** All senders and recipients are employees (@helix.example). Do NOT generate emails to/from external companies, newsletters, vendors, or recruiters-spam. (External + customer email is handled elsewhere; marketing spam is excluded entirely.)
- Routine and mundane — these are deliberately low-signal noise.
- Use ONLY the names listed above.
- Era-appropriate formality.
- Output ONLY the threads separated by `=== THREAD ===`. No preamble, no code fences.
