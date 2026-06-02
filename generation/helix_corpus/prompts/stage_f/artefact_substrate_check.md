You are checking whether a generated corpus artefact contains specific canonical facts that its generation prompt was supposed to embed. This is a substrate-completeness check — confirming that the artefact carries the facts it should.

# The artefact

```
{artefact_text}
```

# Facts that should be present in this artefact

{fact_list}

# Your task

For each numbered fact above, output **one line** in this exact format:

```
FACT N: yes | no | partial — <one-line justification>
```

Where:
- **yes**: the fact (or its substantive equivalent — paraphrasing acceptable, dates may be ISO or written-out, names may be slightly varied) is present in the artefact.
- **partial**: the fact is partially mentioned (e.g. the decision is referenced but the reason isn't; the participant is named but the date is wrong; the topic is mentioned but no specifics).
- **no**: the fact is absent OR substantively contradicted by what's in the artefact.

# Important

- Be lenient on phrasing, strict on content. "Maya chose Kubernetes" and "We went with K8s on Maya's recommendation" both count as `yes` for the same fact.
- Dates can be ISO (2023-04-15) or written-out (April 15, 2023) — same fact.
- A fact is `partial` if the gist is there but a key detail (specifically named in the fact) is missing.
- A fact is `no` if you'd have to invent details to claim it's there.

Output exactly N lines, one per fact, no preamble, no code fences, no extra commentary.
