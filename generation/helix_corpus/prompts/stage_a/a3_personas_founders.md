You are writing the persona profiles for the two founders of a fictional B2B SaaS company.

# Company context

{company_one_liner}

# Founding section (raw from the skeleton — this is your source of truth)

{founding_section}

# Year arcs (for context on how their roles evolved over time)

{year_arcs_block}

# Doc-discipline eras (for context on each founder's writing posture)

{eras_block}

# Your task

Write **exactly 2 YAML documents**, one per founder, separated by `---`. Use the names and voice blurbs from the founding section as authoritative — those names are not negotiable.

Schema:

```yaml
persona_id: P-0001              # founder 1 first named in founding section
display_name: <verbatim from founding section>
pronouns: <pick a plausible pronoun set>
joined_year: <founding year from skeleton>
left_year: null                 # unless year arcs show they departed
role_history:
  - from: <founding-date>
    to: null | <date>           # closed only if year arcs show role change
    role: <one of: CEO, CTO, COO, President, Chair — pick what fits>
    manager: null               # founders report to nobody
                                # include multiple entries if year arcs
                                # show role transitions (e.g. CEO → Chair)
voice_markers:
  hedging_frequency: <low | medium | high — derive from founding blurb>
  emoji_use: rare | occasional | frequent
  formality: <derive from founding blurb>
  typical_message_length_words: <integer>
  writes_long_docs: true | false
signature_phrases:
  - "<turn of phrase consistent with the voice in the founding blurb>"
  - "<another>"
  - "<a third>"
  - "<a fourth>"
  - "<a fifth>"
                                # 5 phrases for founders (high frequency)
doc_discipline_trait: low | medium | high | very_high
communication_channel_mix:
  slack: 0.NN
  email: 0.NN
  notion: 0.NN
  meeting: 0.NN
                                # must sum to 1.0
domain_expertise:
  - <area drawn from their prior career>
  - <another>
is_long_tail: false
is_founder: true
```

# Important

- The founding-section blurb is canonical. If it says "terse, opinionated" then `hedging_frequency: low` and `typical_message_length_words: 40-80`. If "long-form, structured" then `writes_long_docs: true` and `typical_message_length_words: 200-400`.
- If the year arcs show one founder stepping down or changing role (e.g. 2026 leadership change), reflect that in `role_history` with TWO intervals.
- **The two founders must have distinct voices.** That is the entire point of a 2-founder origin story.
- Output **only** the two YAML documents separated by `---`. No commentary. No code fences.
