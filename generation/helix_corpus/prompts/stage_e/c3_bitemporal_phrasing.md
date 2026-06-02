You are writing a benchmark question for the **bi-temporal disambiguation under retroactive correction** category (C3). This question tests whether a memory system can answer: (a) what does the system currently believe, (b) when did it learn each version of the fact, (c) what would the system have answered if asked at an earlier point in time.

# Source-of-truth context (you have the answer; the question must NOT)

- **Topic**: {topic_one_liner}
- **Original recorded value** (what was learned first): {original_value}
- **Original recorded_at** (when system learned the original): {original_recorded_at}
- **Corrected value** (what was learned later was actually true): {corrected_value}
- **Correction recorded_at** (when system learned the correction): {correction_recorded_at}
- **True occurred_at** (when the fact was *actually* true in the world): {true_occurred_at}

# Your task

Write **3 distinct paraphrases** of one question that probes the bi-temporal aspect (current belief, when each version was learned, what the system would have said at an earlier time).

Format strictly:

```
### Q: <paraphrase 1>

### Q: <paraphrase 2>

### Q: <paraphrase 3>
```

# Rules

- **Reference the topic by name** but do not include either value.
- **Anchor the "earlier time" question to a specific date** between {original_recorded_at} and {correction_recorded_at} (pick a date in that window — the system must reconstruct what it believed then).
- The question must probe all three temporal facets jointly.
- Output only the `### Q:` blocks. No code fences.
