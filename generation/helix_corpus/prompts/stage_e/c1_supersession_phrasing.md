You are writing a benchmark question for the **supersession-with-reason** category (C1). This question tests whether a memory system can recall: (a) the current value, (b) the prior value, (c) when the change happened, (d) the reason for the change — all four jointly.

# Source-of-truth context (you have the answer; the question must NOT)

- **Topic**: {topic_one_liner}
- **Prior value** (was correct before, no longer is): {prior_value}
- **Current value** (the value after supersession): {current_value}
- **Change date**: {change_date}
- **Change reason**: {change_reason}

# Your task

Write **3 distinct natural-language paraphrases** of one question that probes all four facets above (current, prior, when, why). The question must be phrased so a person reading it doesn't know the answer — only what's being asked.

Format strictly. Three sections, each starting with `### Q:`. No code fences. No commentary.

```
### Q: <paraphrase 1, single sentence or short paragraph>

### Q: <paraphrase 2>

### Q: <paraphrase 3>
```

# Important rules

- **Do NOT leak the answer.** The question must not contain the literal `current_value`, `prior_value`, or `change_date`.
- **Refer to the topic by name** (e.g. "the incident-response policy") — the system-under-test needs to know what to look up.
- **Ask all four facets in one question.** Don't ask only "what's the current X" — ask "what's the current X, what was it before, when did it change, and why?"
- **Each paraphrase should sound different** — different sentence order, different surface phrasing — but the semantic content is identical.
- Output **only** the three `### Q:` blocks. No headers above them.
