You are REPAIRING a corpus artefact that is missing canonical facts it was supposed to contain. The artefact below was generated for a fictional company benchmark, but a substrate check found that specific required facts are absent. Your job: rewrite the artefact so it reads naturally AND contains every required fact.

# Original artefact

```
{artefact_text}
```

# Required facts that MUST appear in the rewritten artefact

{missing_facts_block}

# Facts already present (keep them)

{present_facts_block}

# Your task

Rewrite the artefact in the SAME genre and voice, preserving everything that already works, but weave in EVERY required fact above so it is unambiguously present. The facts should appear naturally in the artefact's flow (in dialogue, in a decision line, in an email body, etc.) — not as a bolted-on list.

# Hard rules

- The rewritten artefact MUST contain every required fact. A reader (or a fact-checker) must be able to find each one.
- Keep the genre conventions (a meeting_transcript stays a transcript with speaker labels + timestamps; an email_thread stays emails; etc.).
- Keep it the same approximate length or slightly longer. Do not truncate.
- Names must appear verbatim where a "participant by name" fact is required (use the persona's display name, e.g. "Omar Al-Jabri", not just "Omar" or the persona ID).
- Dates must appear in a recognisable form (ISO 2023-03-05 or written-out March 5, 2023).
- Do NOT include the testimony_metadata HTML comment header — that gets re-added by the pipeline.
- Do NOT use code fences. Output only the rewritten artefact body.

Output the rewritten artefact now.
