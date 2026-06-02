You are writing a LONG-FORM internal document for a fictional B2B SaaS company — the kind of substantial authoritative artefact a company produces (a PRD, an RFC, an architecture decision record, a detailed postmortem, a board deck narrative, a strategy memo, an annual plan, a QBR deck). These run several thousand words.

# Company

{company_one_liner}

# Document

- Type: **{doc_type}**
- Title / topic: {topic}
- Date: **{doc_date}**
- Era: {era_name} ({era_discipline_level} doc discipline)
- Authoring people (use their names): {authors_block}

{ground_truth_block}

# Your task

Write the full document. It must be LONG and detailed — proper sections, sub-sections, tables where appropriate, an executive summary, body, appendices. Match the genre:

- **PRD**: problem, goals, non-goals, user stories, requirements, success metrics, open questions, rollout.
- **RFC / architecture decision**: context, options considered (with trade-off tables), decision, consequences, migration plan.
- **postmortem**: timeline (minute by minute), impact, root cause, contributing factors, what went well/badly, action items with owners.
- **board deck narrative**: metrics dashboard recap, wins, risks, asks, financial summary.
- **strategy memo / annual plan**: thesis, market, bets, resourcing, milestones, risks.
- **QBR deck**: account health, usage trends, expansion/risk, renewal outlook.

# Hard rules

- Substantial length — this is one of the corpus's big, dense artefacts.
- Era-appropriate rigor (sparse/scrappy early, polished/structured later).
- If a "ground truth to embed" block is present above, the document MUST contain every fact in it, woven naturally into the relevant section.
- Use ONLY the author names provided where authorship/ownership is mentioned.
- No code fences. Output only the document.
