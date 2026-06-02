You are writing a benchmark question for the **justification chains** category (C5). This question tests whether a memory system can walk an asserted belief back to the supporting evidence — the conversation turns, documents, or inferences that led to it.

# Source-of-truth context

- **Asserted belief / claim**: {claim_one_liner}
- **Topic**: {topic_one_liner}
- **Supporting evidence trail** (artefacts that ground this claim): {evidence_summary_block}
- **Evidence types in the trail**: {evidence_types}
- **Inferential steps** (if any): {inferential_steps}

# Your task

Write **3 distinct paraphrases** of one question that asks: "you stated X. Walk me through the exact conversation turns or documents that support this conclusion, and for each, indicate whether it's direct testimony or an inference."

Format strictly:

```
### Q: <paraphrase 1>

### Q: <paraphrase 2>

### Q: <paraphrase 3>
```

# Rules

- **Reference the claim by its TOPIC, not its full text.** The question should anchor on what the claim is *about* (e.g. "your conclusion about the Kubernetes adoption", "your statement about the v3 rewrite reversal", "your finding about the pricing-model change"). Do **not** quote specific names, dates, or values from the claim — the system must recover those from the corpus.
- The question must ask for BOTH the evidence trail AND the testimony-vs-inference attribution.
- **Do NOT enumerate the evidence trail** in the question — the system must recover it.
- **Do NOT list participants by name in the question.** If the claim mentions "Leo Chen, Jiro Tanaka, and Liam O'Connor chose X", the question should say "your conclusion about the choice of X for [topic]", not "your conclusion that Leo Chen, Jiro Tanaka, and Liam O'Connor chose X" — the system shouldn't have the names handed to it.
- Output only the `### Q:` blocks. No code fences.
