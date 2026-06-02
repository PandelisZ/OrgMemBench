You are defining a DEEPLY NUANCED benchmark question for a fictional B2B SaaS company — the kind whose answer was NEVER written down anywhere and must be reconstructed from how people actually behaved over years. The question sounds simple on the surface ("what was their approach to X?") but there is no document that states the answer; it only exists as an emergent pattern across scattered Slack messages, meetings, calls, and offhand remarks.

# Company

{company_one_liner}

# How the company evolved (ground the pattern in this real arc)

{year_arcs_block}

# People (use real persona IDs/names where the pattern involves specific people)

{personas_block}

# The theme for THIS pattern

{theme}

# Your task

Define one emergent-pattern question on this theme, grounded in THIS company's actual history. The defining property: the honest answer is a *de-facto* pattern that existed in practice, often BEFORE it was ever formalised — so a naive reader who finds the later formal version (a written playbook, a policy doc) would get it WRONG. The real answer is what people actually did, inferred from behaviour.

Output EXACTLY these keys, each on its own line (`KEY: value`), with FACETS as a numbered list:

QUESTION: <a surface-simple question, phrased as if it were a lookup, e.g. "What was the product team's approach to onboarding new customers before mid-2025?">
TEMPORAL_QUALIFIER: <the time framing that makes it subtle, e.g. "the period 2021-2025, before any onboarding playbook existed">
FORMALIZATION: <if/when a formal version later appeared, and why answering with THAT would be wrong — e.g. "A formal onboarding playbook was written in Dec 2025; answering with its standardised steps misses that none of that existed earlier.">  (write "none" if there was never a formal version)
GT_ANSWER: <2-4 sentences describing the de-facto pattern as it actually was — the synthesised truth>
FACETS:
1. <a distinct, concrete component of the pattern that could be SHOWN by a specific behaviour — e.g. "Onboarding was founder-led: Maya personally ran the first call for almost every customer through 2023">
2. <another distinct facet>
3. <another>
4. <another>
5. <optional fifth facet>
6. <optional sixth facet>

# Rules

- 4-6 facets. Each facet must be something that could be EXHIBITED by a concrete behaviour in a Slack message / meeting note / call note (not an abstract statement) — because we will generate scattered evidence that shows each one.
- Ground everything in the company's real timeline, teams, customers, and people. Use specific persona names where natural.
- The pattern must be genuinely emergent (never stated as a rule in any single place). Avoid anything that would just be a recorded decision.
- Output ONLY the keyed lines above. No preamble, no code fences.
