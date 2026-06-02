You are generating a ROUTINE internal wiki / Notion page at a fictional B2B SaaS company — the everyday documentation that accumulates in a company's knowledge base. NOT an authoritative strategy doc or a momentous decision record (those are tracked separately).

# Company

{company_one_liner}

# What the company is doing this period (the page must make sense for this — its content should fit the company's actual projects, customers, and concerns this year)

{year_context}

# The page

- Type: **{doc_type}**
- Owning team / topic: {topic}
- Last updated: **{doc_date}**
- Era: {era_name} ({era_discipline_level} doc discipline)

# People who might author/edit this (use their names)

{personas_block}

# Your task

Write this {doc_type} as it would appear in the company wiki. Match the format:

- **status_page**: a weekly/monthly team status with sections (shipped, in progress, blocked, next).
- **runbook**: step-by-step operational procedure (deploy, on-call, incident response).
- **onboarding_doc**: how a new hire on this team gets set up.
- **process_doc**: how the team does something (code review, sprint cadence, release process). Include a "last updated" note and maybe a changelog showing it evolved.
- **okr_page**: objectives + key results with rough progress.
- **meeting_notes_index**: a rolling page linking recent meeting notes.
- **how_to / faq**: answers to common internal questions.

# Hard rules

- Routine and operational. It must NOT contain a momentous strategic decision or anything that reads like ground-truth canon. Deliberately low-signal background.
- Reflect the era's doc discipline: sparse/scrappy early, structured/maintained later. A process_doc in a high-discipline era may show a small changelog (evolution over time).
- Use ONLY the names listed above where authorship/edits are mentioned.
- Begin with a one-line header: `[WIKI: {doc_type}] {topic} — updated {doc_date}`.
- Output only the page content. No code fences, no preamble.
