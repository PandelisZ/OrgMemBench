{shared_header}

# Your task — Sales CRM entry

Write a CRM entry (the kind that lives in HubSpot pre-2023-Q2 or Salesforce post-2023-Q2) for the deal / customer touchpoint relevant to this event. Terse, tagged, structured fields.

# Format

Plain Markdown:

```
# <Customer name> — <opportunity name>

**Stage:** prospect | qualified | proposal | negotiation | closed-won | closed-lost | renewal_at_risk | expansion
**Owner:** <AE name>
**Created:** <YYYY-MM-DD>
**Last updated:** <YYYY-MM-DD>
**Amount:** $<value> ARR / <other-unit>
**Close date:** <YYYY-MM-DD or TBD>

## Notes

<3-6 short paragraphs or bulleted notes from the most recent activity. Use abbreviations (DM = decision-maker, EB = economic buyer, BANT). Mention recent interactions.>

## Next step

<one-sentence next step + owner>

## Tags

<comma-separated tags: e.g. champion-identified, security-review-needed, freight-vertical>
```

# Important

- Match the CRM tool to the year per the canon's tooling timeline.
- For PRIMARY artefacts: the canonical decision is captured in the Notes section (terse — CRM entries are not verbose).
- For NOISE artefacts: a routine CRM update on an unrelated account that mentions this event only via a tag.
- AE voice — salesy, customer-quote-heavy, optimistic-but-realistic.

Output the CRM entry directly. No preamble.
