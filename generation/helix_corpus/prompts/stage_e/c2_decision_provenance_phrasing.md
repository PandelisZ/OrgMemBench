You are writing a benchmark question for the **decision provenance** category (C2). This question tests whether a memory system can recall: (a) who decided, (b) when, (c) what alternatives were considered, (d) what the deciding factor was — all four jointly.

# Source-of-truth context (you have the answer; the question must NOT)

- **Decision topic**: {topic_one_liner}
- **Decision**: {decision}
- **Decided by** (participants): {participants_names}
- **Decision date**: {decision_date}
- **Alternatives considered**: {alternatives}
- **Deciding factor (reason_canonical)**: {decision_reason}

# Your task

Write **3 distinct paraphrases** of one question that probes all four facets above (who, when, alternatives, why). The question must NOT leak the answer.

Format strictly:

```
### Q: <paraphrase 1>

### Q: <paraphrase 2>

### Q: <paraphrase 3>
```

# Rules

- **Reference the decision topic by name** ("the v3 platform rewrite", "the refund policy change", etc).
- **Do NOT name the deciders or the deciding factor** in the question.
- **Do NOT list the alternatives** in the question — that's what the system must recover.
- All three paraphrases should probe the same four facets; differ in surface phrasing.
- Output only the three `### Q:` blocks. No code fences. No commentary.
