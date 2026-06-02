{shared_header}

# Your task — Notion document

Write a Notion-style document that documents this event. Notion docs are the closest thing the company has to authoritative reference material — they get cited, sometimes go stale, and live alongside other docs in a wiki structure.

# Format

Plain Markdown. Loose structure — Notion is forgiving:

```
# <Document title>

> **Last updated:** <YYYY-MM-DD>
> **Owner:** <name>
> **Status:** Draft | Approved | Stale | Archived

<Optional table of contents for long docs>

## <Section 1>

<paragraphs of prose>

## <Section 2>

<paragraphs>

## Open questions / TODOs

- <bullet>
- <bullet>

## Related

- <link to other Notion doc>
- <link to ADR / RFC>
```

# Style

- Notion docs vary wildly in quality. Match the author's `doc_discipline_trait`:
  - `low`: 1-2 paragraphs, missing sections, abandoned-feeling
  - `medium`: standard structure but some sections sparse
  - `high` / `very_high`: full structure, cited references, polished prose
- Last-updated date can be the event date OR a later date that suggests the doc was revised after the fact.
- Status field: "Draft" if the doc is in-progress; "Approved" if signed-off; "Stale" if it hasn't been revised since a known supersession.

# Important

- For PRIMARY artefacts: the canonical decision is the centerpiece of the doc body.
- For SECONDARY artefacts: this can be an EARLIER version of a doc that has since been revised (mark Status: Stale or set Last updated to a pre-supersession date — this is the doc-evolution noise mechanism §4.2 calls out).
- For NOISE artefacts: a Notion doc on an adjacent topic that mentions this event in the Related section.

Output the Notion doc directly. No preamble.
