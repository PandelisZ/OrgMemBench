You are writing the multi-year decision history of ONE topic at a fictional B2B SaaS company — the chain of versions where each decision was later superseded, reversed, re-attempted, or corrected as the company learned. This becomes ground-truth the memory system must trace.

# Company

{company_one_liner}

# The topic

{topic_line}

# Company era context (so the chain fits the company's real timeline)

{year_arcs_block}

# People who could be involved (use these persona IDs; pick plausible deciders per era — only people active that year)

{personas_block}

# Your task

Write a chain of **{n_versions} versions** of this topic's decision, spanning multiple years (earliest → latest). Each version revises the one before it. The chain MUST include realistic temporal-memory structure:
- Each version after the first **supersedes** (or **reverses**, or **re_attempts**) the previous one.
- Include at least ONE **retroactive correction**: a later version reveals that an EARLIER version's recorded understanding was wrong (e.g. "we recorded the SLA as 99.9% in 2022 but discovered in 2024 the monitoring was miscounting; the true figure had been 99.5%").
- Include at least ONE **contradiction that was later resolved**: at some version two named people disagreed on the call, and a later version records how it was resolved.

# Format — one YAML block per version, separated by lines containing only `---`

```
version: 1
year_month: 2021-06
decider_ids: [P-0001, P-0002]
decision: <the decision made at this version — specific and concrete>
reason: <why this version was chosen>
alternatives: [<alt 1>, <alt 2>]
relation_to_previous: none      # version 1 only
change_reason: <n/a for v1>
corrects_earlier_version: null   # or an integer version number this retroactively corrects
contradiction: null              # or: "<PersonA id> vs <PersonB id>: <what they disagreed on>"
resolution: null                 # or: how a disagreement from an earlier version was resolved here
```

For versions 2+, `relation_to_previous` is one of: supersedes | reverses | re_attempts.

# Rules

- Output EXACTLY {n_versions} version blocks — no fewer. This is a long-lived topic; it genuinely changed {n_versions} times.
- Years must be chronological and within the company's lifetime (2020-2026); space versions across different years.
- decider_ids must be from the list above and plausibly active in that year.
- Make decisions specific to THIS topic and concrete (numbers, tool names, thresholds), not generic.
- Exactly one block per version, separated by `---`. Output ONLY the YAML blocks. No prose, no code fences.
