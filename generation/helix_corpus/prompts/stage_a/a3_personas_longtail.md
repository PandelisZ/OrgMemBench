You are filling in the long-tail cast for a fictional B2B SaaS company's corpus.

# Company context

{company_one_liner}

# High-frequency cast already defined (do NOT regenerate them)

{active_personas_summary}

# Your task

Generate **{persona_count} long-tail personas**. These are people who appear in only a small number of artefacts each — junior engineers, individual SDRs, the external legal counsel, departed employees mentioned in retrospectives, a few customer-side names that appear in deal notes.

Output one YAML document per persona, separated by `---` lines. Schema is the same as the active cast but **simpler — fewer required fields**:

```yaml
persona_id: P-NNNN              # continue numbering after the active cast
display_name: <first last>
joined_year: YYYY               # may be earlier than founding if they're external (legal counsel, recruiter)
left_year: YYYY | null
role_history:
  - from: YYYY-MM-DD
    to: null | YYYY-MM-DD
    role: <title>
    manager: <name or null>
voice_markers:
  hedging_frequency: low | medium | high
  formality: low | medium | high
signature_phrases:
  - "<one phrase>"
  - "<a second>"
  - "<a third>"                 # 3 phrases is fine for long-tail
doc_discipline_trait: low | medium | high
domain_expertise:
  - <area>
is_long_tail: true
```

# Rules

- About **half** the long-tail should be people who **left** before now (set `left_year`). They appear in retrospectives, in old Slack threads, in farewell emails.
- About a quarter should be **external**: legal counsel, an external recruiter, an investor partner, a vendor contact. Mark with `is_long_tail: true` and a sensible `domain_expertise`.
- Names must be distinct from the active cast. Cultural and demographic variety.
- No signature phrase may collide with any active-cast persona or with any other long-tail persona.
- Output **only** the YAML documents. Nothing else. No code fences.
