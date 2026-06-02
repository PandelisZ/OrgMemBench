You are writing a benchmark question for the **audit replay** category (C4). This question tests whether a memory system can reconstruct its own state at an arbitrary historical point.

# Source-of-truth context

- **Topic**: {topic_one_liner}
- **As-of date** (the historical point we're asking about): {as_of_date}
- **Facts true on the as-of date** (what the system knew then): {asof_facts_block}
- **Facts changed since** (what's been superseded or corrected since): {changed_facts_block}
- **Replacements for the changed facts**: {replacements_block}

# Your task

Write **3 distinct paraphrases** of one question that asks the system to:
- Reconstruct what it knew about the topic as of {as_of_date}
- Identify which facts have since been changed or removed
- For each changed fact, identify what replaced it

Format strictly:

```
### Q: <paraphrase 1>

### Q: <paraphrase 2>

### Q: <paraphrase 3>
```

# Rules

- **The as-of date {as_of_date} must appear** in the question — that's the anchor for the audit replay.
- **Do NOT include the facts themselves** in the question. The system must recover them.
- The question should be phrased like a real audit request from a regulator or board — formal, specific, scope-bounded.
- Output only the `### Q:` blocks. No code fences.
