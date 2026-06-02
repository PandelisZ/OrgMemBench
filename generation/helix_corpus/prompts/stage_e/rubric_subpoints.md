You are writing the scoring rubric sub-points for a benchmark question. The rubric tells the judge how to score an answer point-by-point — each sub-point worth a fraction of the total.

# Question

{question_text}

# Ground-truth answer (the canonical projection from the source-of-truth graph)

{ground_truth_block}

# Category template

The {category} category has this canonical sub-point structure: **{subpoint_structure}**

# Your task

For each sub-point in the category template, write the **rubric criterion**: a 1-2 sentence description of what the judge looks for to award the sub-point. The criterion must reference the ground-truth value the answer must hit.

Format strictly. One sub-point per line as a Markdown list item:

```
- {category}.sub1 | <max-points-as-decimal e.g. 0.25> | <criterion>
- {category}.sub2 | <max-points> | <criterion>
```

# Rules

- **Sub-point IDs** are `{category}.sub1`, `{category}.sub2`, ... in order matching the category template.
- **Max points per sub-point** is `1.0 / number_of_subpoints` (e.g. 4 sub-points = 0.25 each, 3 sub-points = 0.333).
- **Criterion** must be specific to the ground-truth value, not generic. E.g. NOT "current value is correct" — instead "the answer covers the substantive content of `<ground-truth current value>` (paraphrasing acceptable; key facts present)".
- **Grade for substantive coverage, not verbatim format.** A candidate answer that conveys the right facts in narrative prose deserves credit even if it doesn't list them as a "set". Specifically:
  - For set-of-facts sub-points: award FULL points if the narrative covers ≥80% of the facts; HALF points if 50-79%; zero if <50%.
  - For single-fact sub-points: award FULL points for semantic equivalence (dates can be ISO or written-out; values paraphrased OK); HALF for partial match; zero for absent.
  - Specificity matters: a generic "the strategy was changed" doesn't earn points if the GT specifies what changed; but "the company pivoted from freight-visibility to analytics" DOES earn points even if the GT phrasing was different.
- For each sub-point, decide a fail criterion too — what counts as zero. Append " | FAIL: <criterion>" to the line.

Output only the Markdown list. No code fences. No commentary.
