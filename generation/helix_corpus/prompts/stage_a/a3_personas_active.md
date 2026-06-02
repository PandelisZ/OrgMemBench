You are populating the named cast for a fictional B2B SaaS company's internal corpus.

# Company context

{company_one_liner}

# Founders (already defined as P-0001 and P-0002 — DO NOT regenerate them)

{founders_block}

# Year arcs (use these to derive plausible hiring waves and tenures)

{year_arcs_block}

# Doc-discipline eras (use these to time who joined during which discipline era)

{eras_block}

# Your task

Generate **{persona_count} distinct high-frequency personas** beyond the founders. These are people who will appear frequently in Slack, in meeting transcripts, in design docs and decision write-ups across the corpus. They must feel like distinct human beings — different voices, different writing styles, different opinions.

## Required role coverage (the cast MUST include at least one of each)

The active cast must collectively span the company's leadership and tenure structure. **Across the {persona_count} active personas you generate, you must cover:**

**Leadership / executive (at least 4-5 of these):**
- VP / Head of Engineering (typically joined during the 2023 doc-discipline revival era)
- VP / Head of Sales (or first sales hire if pre-VP)
- VP / Head of Product
- CFO (typically joined during the multi-team-maturity era — post-Series-A)
- Head of People / HR (typically joined during hypergrowth)
- Head of Customer Success
- CMO / Head of Marketing (if applicable to company stage)

**Engineering ICs / mid-level (at least 2-3):**
- A Principal Engineer or Staff Engineer who joined early (founding-or-2021)
- An Engineering Manager
- A Senior Engineer hired during the growth era

**Go-to-market / customer-facing (at least 2):**
- Account Executive
- Sales Engineer
- Customer Success Manager
- Senior Designer or Product Designer

**Operations (at least 1):**
- Operations Manager, Controller, or similar finance / ops role

## Required tenure spread

Across the active cast, distribute joined_year so we cover the full company history, not just recent hires:

- **At least 1** persona joined in the founding year ("early team")
- **At least 1** persona joined during the 2021 docs-initiative era
- **At least 1** persona joined during the 2022 hypergrowth-collapse era
- **At least 2** personas joined during the 2023 revival era (the new leadership wave)
- **At least 2** personas joined during the 2024-2025 multi-team-maturity era

This tenure spread is structural — the benchmark will probe "who has been here since X" and "who joined after Y".

## Output

Output **one YAML document per persona**, separated by `---` lines. Do not output anything else. Do not use code fences.

Required fields per persona:

```yaml
persona_id: P-NNNN              # start numbering at P-0003 (P-0001 and P-0002 are founders)
display_name: <first last>      # invent names; vary cultural background; no real public figures
pronouns: she/her | he/him | they/them
joined_year: YYYY               # plausible given the role and the year arcs
role_history:
  - from: YYYY-MM-DD
    to: null                    # or YYYY-MM-DD if they were promoted / transferred
    role: <title>
    manager: <name or null>
                                # at least 2 personas must have TWO intervals
                                # (promotion or role change), proving the
                                # company has internal mobility
voice_markers:
  hedging_frequency: low | medium | high
  emoji_use: rare | occasional | frequent
  formality: low | medium | high | very_high
  typical_message_length_words: <integer>
  writes_long_docs: true | false
signature_phrases:
  - "<verbatim turn of phrase this person uses>"
  - "<another>"
  - "<a third>"
                                # exactly 3-5 phrases per persona; no
                                # duplicates across personas
doc_discipline_trait: low | medium | high | very_high
communication_channel_mix:
  slack: 0.NN
  email: 0.NN
  notion: 0.NN
  meeting: 0.NN
                                # must sum to 1.0
domain_expertise:
  - <area>
  - <area>
is_long_tail: false
seniority: <one of: leadership, manager, senior_ic, ic, junior>
tenure_tier: <one of: founding_era, early_2021, growth_2022, revival_2023, maturity_2024_plus>
```

# Important rules

- **The two founders are already P-0001 and P-0002. Start your numbering at P-0003.**
- **Leadership roles named above must each have someone**: if no one has VP Sales as their role, the cast is incomplete.
- **No two personas may share a signature phrase.** This is the structural defence against everyone sounding the same.
- **Voice markers must vary** — at least three personas should have `hedging_frequency: low`, at least three should have `high`. Mix it up.
- **Leadership personas tend to write more long-form** (`writes_long_docs: true`); ICs tend to be Slack-heavy.
- At least three personas have `writes_long_docs: false` — Slack-only contributors.
- Output **only** the YAML documents. Nothing else.
