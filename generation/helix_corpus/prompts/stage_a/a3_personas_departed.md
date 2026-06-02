You are populating the **departed cast** for a fictional B2B SaaS company's corpus. These are people who **used to work at the company** and are no longer there. They appear in old artefacts, in retrospectives, in farewell threads, in references like "remember when Trevor used to handle the Quayside account?".

# Company context

{company_one_liner}

# Year arcs (use these to derive plausible tenures and departure circumstances)

{year_arcs_block}

# Existing cast (do NOT duplicate; these people are still around)

{existing_cast_summary}

# Your task

Generate **{persona_count} departed personas**. They all left the company between {min_departure_year} and {max_departure_year}. Their tenures should span the company's history — some joined in 2020 and left in 2022, some joined 2023 and left 2025, etc. Cover the range.

Output one YAML document per persona, separated by `---` lines. Schema:

```yaml
persona_id: P-NNNN              # continue numbering after the active + long-tail cast
display_name: <first last>
joined_year: YYYY
left_year: YYYY                 # MUST be set — these are departed
departure_circumstance: <one of: layoff, poached, founder_friction, family_reasons, performance, retired, startup_of_their_own, mutual_separation, returned_to_school>
left_for: <where they went next, in one line — invented company OR "unknown" OR "consultancy">
role_history:
  - from: YYYY-MM-DD
    to: YYYY-MM-DD             # always closed for departed personas
    role: <title>
    manager: <name or null>
voice_markers:
  hedging_frequency: low | medium | high
  formality: low | medium | high
domain_expertise:
  - <area>
signature_phrases:
  - "<one phrase>"
  - "<a second>"
  - "<a third>"                # 3 phrases is fine
mentioned_in_passing: true     # marks this persona as referenceable but not a primary actor
is_long_tail: true
```

# Rules

- **Departure circumstances should vary** — at least one of each of: layoff, poached, founder_friction, performance, mutual_separation across the batch.
- **Tenure variance** — some short (6-18 months), some long (3+ years).
- **Signature phrases should be distinct** from active / long-tail cast.
- **No names that duplicate** the existing cast.
- **Some of these people will be mentioned positively** in old artefacts ("Trevor really pushed for the rate-limiter rewrite, and he turned out to be right"), some negatively ("the original pricing model we inherited from Lisa was a mess").
- Output only YAML documents separated by `---`. No code fences. No commentary.
