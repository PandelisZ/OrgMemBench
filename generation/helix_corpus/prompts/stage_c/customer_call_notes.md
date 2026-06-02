{shared_header}

# Your task — Customer-call notes

Write the internal-facing notes from a customer call. These are the CSM or AE's record of what was discussed with the customer, NOT a transcript and NOT customer-facing.

# Format

Plain Markdown:

```
# Customer call: <customer name> — <YYYY-MM-DD>

**Customer:** <name>
**Attendees (Helix side):** <names>
**Attendees (customer side):** <names + roles>
**Account owner:** <name>
**Call type:** quarterly_business_review | escalation | renewal_pitch | onboarding | discovery

## Summary

<2-3 sentences: what was discussed, what the customer wants/needs/feels>

## Key topics

- <bullet — topic + brief detail>
- <bullet>

## Customer quotes (paraphrased)

> "<quote>" — <Customer rep name>
> "<quote>" — <another>

## Action items

- [ ] @<helix-owner>: <action> — by <date>
- [ ] @<customer-owner>: <action> — by <date>

## Risk flags

- <bullet — concerns, escalation triggers, account health signals>

## Next call

<date or "TBD">
```

# Important

- If the event involves a specific customer, name them in the customer field. Otherwise this artefact-genre may not be the best fit for non-customer events — but it can document a customer call where this event came up as context.
- For PRIMARY artefacts: the customer's perspective on the canonical decision/outcome is captured (e.g. "Customer expressed satisfaction with the new SLA policy").
- For SECONDARY artefacts: the customer call touches the event obliquely as context for a different conversation.
- For NOISE artefacts: a routine QBR or onboarding call that references the event in passing.
- Author voice: empathetic CSMs use empathetic phrasing; transactional AEs are blunt.

Output the call notes directly. No preamble.
