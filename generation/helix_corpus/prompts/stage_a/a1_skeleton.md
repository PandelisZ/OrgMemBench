You are designing the dimensional grid for a fictional B2B SaaS company that will be used as the substrate for a memory benchmark.

# Company anchor

- Working name: **{company_name}**
- Archetype: **{company_archetype}**
- The company has gone through five distinct documentation-discipline eras between founding and now, spanning roughly 6 years.

# Your task

Produce a single Markdown brief with the section headings shown below. Be specific, opinionated, and internally consistent. Do not use code fences. Do not output anything other than the Markdown brief.

## Founding
One sentence: founding year + the immediate problem the founders set out to solve. Founders should be **exactly 2 people**. Give their names, prior roles, and a one-line description of each founder's writing voice (terse vs long-form, structured vs scrappy, opinionated vs hedged).

## Year arcs
One Markdown line per year from founding through {current_year}. Format strictly:
```
- YYYY: <one-sentence theme for this year>
```
Cover {year_arc_count} years total. Every theme should imply real events: a hiring boom, a near-miss outage, a strategic pivot, a layoff, a customer escalation, a product launch, a funding round, a leadership change.

## Doc-discipline eras
Exactly 5 eras with these labels. Each block:
```
### Era <N>: <era-name>
- Date span: YYYY-MM to YYYY-MM
- Discipline level: low | medium | high
- Characterisation: <1-3 sentences describing what documentation looks like in this era>
```
The set must include at least one low-discipline era and at least one high-discipline era. Date spans must be mostly monotonic and cover the founding-to-now range with no gaps.

## Product lines
A bullet list of 1-3 product lines the company ships today. For each: name, year launched, one-line description.

## Customer arc count
A single integer between 8 and 10 — this is how many named customers the corpus will track. Just the number on its own line.

## Tooling timeline
A list of tooling adoptions / replacements over the company's history. Format each line:
```
- YYYY-Qn: <tool-name> adopted for <category> (replaced <prev-tool> | first tool in category)
```
Cover categories: CRM, eng tickets, meeting transcripts, design tool, internal wiki, source control hosting, data warehouse. Order chronologically. A tool replacement always cites the predecessor.

# Important

Be concrete and specific. Use real product names where natural (HubSpot, Salesforce, Linear, Notion, etc.) — this is a fictional *company*, but the *tools* are real industry products. Avoid generic phrases like "the company grew rapidly"; commit to specifics.
