You are filling in the **messy, emotional, dropped-context backstory** of a fictional B2B SaaS company. This is the noise that makes a real corpus *feel* real — events that get referenced in passing, people who left under odd circumstances, deals that fell through, political fights that shaped culture without ever being formally documented.

Most of what you write here will **never directly answer a benchmark question**. Its job is to be *realistic ambient context* the corpus can later reference. Think of it as the things people remember when a colleague says "remember that Q1 we almost…" or "this is the same thing that happened with the Atlas deal in 2022 except worse." The benchmark wants the system-under-test to navigate a corpus that has *exactly this kind of texture*.

# Company context

{company_one_liner}

# Year arcs already established (use these as scaffolding — your arcs can elaborate on them, complicate them, or sit in the gaps between them)

{year_arcs_block}

# Personas already established

{personas_block}

# Customers already established

{customers_block}

# Your task

Write **{arc_count} short narrative entries** (1-2 paragraphs each), separated by `---` lines (Markdown horizontal rules). Each entry is a single named arc — give it a header and then prose. Format:

```
## ARC: <short title>

<1-2 paragraphs of narrative>
```

Each arc should be **one of these patterns** (mix them up — variety matters):

1. **Failed fundraise that became a successful one.** A round was pitched, fell through (specific reason), then a customer contract / product milestone enabled a different raise later. Name the firms, name the partners who passed, name the bridge customer.
2. **Near-pivot that didn't happen.** The team seriously considered a different strategy, debated it, drew up an alternate roadmap, then chose not to. Name the alternate strategy. Reference internal dissent.
3. **Lost-the-pitch deal.** A specific prospect that the team thought they had, then lost (to a competitor, to a build-vs-buy decision, to a champion leaving the prospect company). Name the prospect, the competitor, the loss reason.
4. **Internal political fight.** Two leaders (or two teams) on opposite sides of a decision — pricing change, hiring philosophy, build-vs-buy, performance review structure. Show the fight texture, name the sides, give the unresolved-or-resolved outcome.
5. **Person who came and went.** An employee who joined with fanfare, stayed 6-18 months, left under a specific circumstance (poached, performance, founder-friction, family reasons), and is now referenced in passing. Name them; their persona should slot into the long-tail or departed cast generated elsewhere — pick a name not in the persona library.
6. **Customer churn that taught a lesson.** A customer left, the team did a postmortem, the lessons changed something in the product or process. Name the customer (can be one that doesn't appear elsewhere), the reason, the lesson.
7. **The lunch that became a hire.** A casual conversation with a competitor, advisor, or someone at a conference that ended in an offer + accept. Name both sides.
8. **A doc that never got written.** A planned-but-abandoned strategic doc (RFC, north-star, comp plan, GTM plan). What it was supposed to be, why it didn't happen, what filled the gap.

# Rules

- **Each arc must reference at least one specific year** (between {min_year} and {max_year}).
- **Each arc must include at least one specific name** (person OR company OR product OR document).
- **No arc may be a paraphrase of an already-established year arc.** Add to the texture, don't restate the skeleton.
- **Mix outcomes:** some arcs end well, some don't, some are still unresolved at {max_year}. Avoid every arc being a triumph or every arc being a disaster.
- **Voice should be retrospective** — written as if recalling something rather than reporting it live. Phrases like "as it turned out", "in hindsight", "by the time…" are welcome.
- **Do not use code fences.** Output is plain Markdown.
- **Output only the arcs**, separated by `---`. No preamble.
