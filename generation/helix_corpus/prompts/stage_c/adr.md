{shared_header}

# Your task — Architecture Decision Record (ADR)

Write a formal ADR documenting this event's decision. ADRs are the high-discipline-era go-to for engineering decisions — structured, opinionated, with explicit alternatives and consequences.

# Format

Plain Markdown:

```
# ADR-<YYYY>-<NNN>: <one-line title>

## Status

<one of: Proposed | Accepted | Superseded by ADR-X | Deprecated>

## Date

<YYYY-MM-DD>

## Authors

<comma-separated names>

## Context

<2-4 paragraphs of the situation that prompted this decision. Names. Customer names if relevant. Prior decisions if relevant.>

## Decision

<2-3 paragraphs of what we are doing. Concrete and specific.>

## Alternatives Considered

### <Alternative 1 name>

<paragraph explaining what this alternative was and why we did not choose it>

### <Alternative 2 name>

<paragraph>

### <Alternative 3 name (optional)>

<paragraph>

## Consequences

<2-3 paragraphs on what will change as a result of this decision. Include both positive and negative consequences.>

## References

- <inline citation to prior work, customer ticket, Slack thread, related ADR if applicable>
- <another>
```

# Important

- **For PRIMARY artefacts**: the canonical decision text MUST be the Decision section. Alternatives MUST include the canonical `alternatives_considered` from the event (paraphrased OK; semantic match required).
- **For SECONDARY artefacts**: this can be an EARLIER ADR that touched on the same topic but didn't make the final call, OR a later ADR that references this event without restating it.
- **For NOISE artefacts**: an ADR on an adjacent topic that mentions this event in passing in References.
- **Era**: ADRs are characteristic of the Inés-revival era and later (2023+). DO NOT generate ADRs for pre-2022 events — use RFC genre instead (or fall back to slack_thread).
- **Author voice**: match the author's persona — opinionated authors write opinionated Decision sections, hedged authors include more caveats.

Output the ADR directly. No preamble.
