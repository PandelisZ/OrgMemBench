You are modelling how a fictional B2B SaaS company's Slack workspace evolved over its lifetime. Real companies don't have a static set of channels — channels are born when a need appears, renamed when tools or teams change, and archived when projects end or people leave.

# Company context

{company_one_liner}

# Year arcs (the company's evolution)

{year_arcs_block}

# Doc-discipline eras

{eras_block}

# Tooling timeline (tool migrations often rename channels)

{tooling_block}

# Teams that exist by the present day

{teams_block}

# Your task

Generate the company's Slack channel timeline from founding through {current_year}. Output **one YAML document per channel**, separated by `---` lines. A channel that gets renamed (e.g. when a tool migrates, or a project becomes a team) is TWO records linked by `renamed_from`.

Schema per channel:

```yaml
channel: "#channel-name"          # lowercase, slack-style, hyphenated
created: YYYY-MM                   # when the channel was created
archived: YYYY-MM | null          # when archived/abandoned, or null if still active
team: <owning team or "company-wide">
kind: <one of: general, team, project, customer, incident, tooling-notifications, social, announcements>
purpose: <one line — what this channel is for>
renamed_from: "#old-name" | null  # if this channel replaced an earlier one
peak_years: [YYYY, ...]           # years this channel was most active
```

# How a company like this evolves (follow this arc)

- **Founding (2020):** only 2-4 channels exist — `#general`, `#random`, maybe `#eng`. Everything informal.
- **First growth (2021):** function channels appear (`#product`, `#sales`, `#customers`). A docs push may create a `#docs` channel.
- **Hypergrowth (2022):** channel EXPLOSION. Sub-team channels (`#eng-platform`, `#eng-workflow`), project channels (`#proj-<name>`) that are very active then **abandoned when the project ends**, `#incidents`, `#hiring`. A tool migration (e.g. GitHub Issues → Linear) renames a notifications channel.
- **Revival / pivot (2023):** new leadership creates decision/architecture channels (`#eng-decisions`, `#architecture`). A layoff archives some channels (a departed leader's pet channel goes quiet/archived). Another tool migration (e.g. HubSpot → Salesforce) renames a deals channel. A new strategic project channel is born.
- **Maturity (2024):** a successful project channel becomes a team channel (`#proj-x` → `#team-x`). Finance/board channels appear with a new CFO.
- **Scale (2025-2026):** geographic channels (`#eu-expansion`), read-only `#announcements`, on-call channels. A mature `#team-*` / `#proj-*` / `#cust-*` taxonomy.

# Rules

- Produce **20-40 channels** total across the lifetime (including renamed pairs and archived ones).
- At least **3 channels must be archived** (project ended, person left, tool migrated).
- At least **2 rename pairs** (tool migration or project→team).
- Channel creation dates must be chronologically consistent with team/tooling existence (no `#salesforce-deals` before Salesforce was adopted).
- Use real product names where natural (`#linear`, `#salesforce-deals`).
- Output ONLY the YAML documents separated by `---`. No prose, no code fences.
