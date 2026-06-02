You are writing a benchmark question for the **contradiction-with-attribution** category (C6). This question tests whether a memory system, given two parties who made contradictory claims, can: (a) state what each said, (b) attribute each to its source with timing, (c) describe how the contradiction was resolved (or is still unresolved).

# Source-of-truth context

- **Topic of the disagreement**: {topic_one_liner}
- **Party A**: {party_a_name}
- **Party A's claim**: {party_a_claim}
- **Party A's claim date**: {party_a_date}
- **Party B**: {party_b_name}
- **Party B's claim**: {party_b_claim}
- **Party B's claim date**: {party_b_date}
- **Resolution status**: {resolution_status} — either "resolved by Y", "superseded by Z", or "unresolved"
- **Resolution details**: {resolution_details}

# Your task

Write **3 distinct paraphrases** of one question that asks the system to attribute each claim, date each, and describe the resolution.

Format strictly:

```
### Q: <paraphrase 1>

### Q: <paraphrase 2>

### Q: <paraphrase 3>
```

# Rules

- **Both party names ({party_a_name} and {party_b_name}) must appear** in the question (we're explicitly asking about their disagreement).
- **Do NOT include the actual claims** in the question — the system must recover them.
- The question must probe per-source claim, per-source timing, AND resolution status.
- Output only the `### Q:` blocks. No code fences.
