You are identifying **retroactive corrections** in a fictional company's event timeline.

# What's a retroactive correction?

A retroactive correction is when a **later event** materially **changes the recorded understanding** of an **earlier event** — not just supersedes it with a new policy, but reveals that the earlier event's narrative was wrong.

Examples:
- 2022 incident postmortem stated "customer X churned because of pricing". 2024 retrospective discovered "the real reason was integration issues, not pricing". → `EV-2022-X -> retroactively_corrected_by -> EV-2024-Y`.
- A 2023 ADR committed to a deployment date. A 2024 audit revealed the actual deployment happened on a different date than recorded. → retroactive correction.
- A 2021 customer event recorded a churn date that was later corrected by a 2023 reconciliation.

# What's NOT a retroactive correction?

- A normal supersession (policy V1 → policy V2 by deliberate change). That's `supersedes`, NOT `retroactively_corrected_by`.
- A new launch that builds on a prior decision.
- A status update or progress report.

The key distinction: **retroactive correction = we previously believed X happened, now we believe Y happened instead**, applied to the *same past event*, not a new policy choice.

# Events to examine

{events_block}

# Your task

Identify pairs where a LATER event materially corrects the recorded understanding of an EARLIER event.

Output one triple per line in this exact format:

```
EV-X -> retroactively_corrected_by -> EV-Y
```

Where:
- **EV-X is the EARLIER event** (the one whose understanding is being corrected).
- **EV-Y is the LATER event** (the correction itself).
- **EV-Y.occurred_at MUST be at least 3 months after EV-X.occurred_at.**
- Both events must be about the **same topic / customer / incident / decision**.

If you find no qualifying retroactive corrections, output exactly:
```
NO_RETROACTIVE_CORRECTIONS
```

Output ONLY the triples (or the no-corrections marker). No prose. No commentary. No code fences. No headers.
