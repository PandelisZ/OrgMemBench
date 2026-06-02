{shared_header}

# Your task — RFC (Request for Comments)

Write a pre-2023 RFC documenting this event's decision. RFCs are less structured than ADRs — looser headings, more prose, more "let's discuss this" energy. They were the dominant decision-document genre in the founder-era and early growth phase, before the Inés-revival era introduced ADRs.

# Format

Plain Markdown. Loose structure — author has latitude:

```
# RFC: <one-line title>

**Author(s):** <names>
**Date:** <YYYY-MM-DD>
**Status:** Draft | Reviewed | Accepted | Rejected | Stale

## Problem

<2-4 paragraphs framing the problem. Use first-person voice ("I think…", "we noticed…"). Less polished than an ADR's Context.>

## Approach

<2-4 paragraphs proposing the solution. The author's preferred path is clearly visible.>

## Open questions

- <bullet>
- <bullet>
- <bullet>

## Alternatives considered (optional)

<looser than ADR. Sometimes alternatives are buried in the Approach section as parentheticals.>

## Comments

<sometimes RFCs have inline comments from reviewers, e.g. "// Daniel: I disagree, see below" — feel free to include 1-3 of these for realism>
```

# Important

- Era: RFCs are for pre-2023 events. DO NOT use this template for 2023+ events — use ADR instead.
- For PRIMARY artefacts: the canonical decision is the centerpiece of Approach.
- For SECONDARY artefacts: an earlier draft that was rejected, OR a related RFC that links to this one.
- Author voice matters — opinionated authors write opinionated RFCs.

Output the RFC directly. No preamble.
