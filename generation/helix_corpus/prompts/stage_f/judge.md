You are scoring a benchmark answer against the canonical ground-truth answer. For each rubric sub-point, decide whether the candidate's answer awards full points, partial points (half), or zero.

# Question

{question_text}

# Canonical ground-truth answer (the correct answer)

{ground_truth_block}

# Rubric sub-points (what to score)

{rubric_block}

# Candidate answer (the one being judged)

{candidate_answer}

# Your task

For each sub-point, output ONE line in this exact format:

```
SUB-POINT <id> <awarded>/<max> <one-line justification>
```

Where `<awarded>` is a decimal (0.0, half of max, or max).

**Grading philosophy — be strict on substance, lenient on format.** The candidate is judged on whether it covers the GROUND-TRUTH SUBSTANCE, not whether it matches the ground-truth's exact wording or layout:

- Semantic equivalence = full points (dates can be ISO or written-out; values paraphrased; lists or narrative prose both fine).
- Substantive coverage of a set: ≥80% of items covered = full points; 50-79% = half; <50% = zero.
- A narrative answer that conveys the right facts deserves credit even if it doesn't enumerate them as a list.
- Wrong specifics (wrong date, wrong name, wrong value) = zero for that sub-point.
- Omissions of key facts = partial or zero depending on coverage.

# Output

One line per sub-point. No headers. No code fences. No commentary outside the lines.
