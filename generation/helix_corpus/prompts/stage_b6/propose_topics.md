You are identifying the policies, processes, and architectural decisions at a fictional B2B SaaS company that **evolved over multiple years** — the kind of thing that was decided one way, then revised, reversed, or corrected as the company learned. These multi-year decision threads are what a memory system must trace.

# Company

{company_one_liner}

# How the company evolved (year by year)

{year_arcs_block}

# Tooling / process migrations that happened

{tooling_block}

# Your task

List **{n_topics} distinct topics** at this company that plausibly went through **3-5 revisions across different years** (a decision made, later superseded, sometimes reversed, sometimes re-attempted, occasionally a past record turning out to be wrong and corrected later). Favour topics that are realistic for a freight-forwarding SaaS scaling from 4 to ~85 people: engineering policies, customer/commercial policies, ops processes, people/org policies.

Examples of the SHAPE (do not just copy — ground yours in THIS company's actual arc): an alerting/SLA policy, a release/deploy process, a pricing/discount model, an on-call rotation, a data-retention policy, a customer-tiering scheme, an architecture choice that was changed, a hiring rubric.

# Format

One topic per line:

```
- <short topic title> | <one-line note on how/why it likely changed over the years>
```

Output ONLY the list. {n_topics} lines. No preamble, no code fences.
