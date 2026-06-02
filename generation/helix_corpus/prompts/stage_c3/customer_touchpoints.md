You are generating a quarter's worth of internal records about ONE customer relationship for a fictional B2B SaaS company. This is the depth that builds up around a customer over years — QBR notes, support tickets, escalation threads, renewal/expansion discussions — the texture a memory system must trace to understand the account's true state.

# Company

{company_one_liner}

# The customer

- Name: **{customer_name}**
- Industry: {customer_industry}
- Relationship arc (overall): {customer_arc}
- Status this period: {customer_status}

# Time

- Quarter: **{year} Q{quarter}**
- Era: {era_name}

# Helix-side people who work this account (use their names)

{helix_personas_block}

# Customer-side people (use these names for the customer's representatives)

{customer_personas_block}

# Your task

Generate **{n_touchpoints} short internal records** about this customer for {year} Q{quarter}. Mix of:

- A quarterly business review (QBR) note
- 1-2 support tickets (customer reported an issue; resolution)
- An account-health / renewal / expansion note (CSM or AE)
- An occasional escalation thread if the status warrants it

# Format

Separate each record with a line containing only `=== RECORD ===`. Begin each record with a one-line header:

```
[RECORD: <type>] <customer_name> — {year}-Q{quarter}
```

where `<type>` is one of: qbr_note, support_ticket, renewal_note, escalation, expansion_note, call_notes. Then the record body in the appropriate style (CSM notes are empathetic + customer-quote-heavy; support tickets are terse + structured; AE notes are deal-focused).

# Rules

- Records must be consistent with the customer's overall arc and status this period. If the customer is "near churn", show the strain; if "expansion", show the upsell momentum; if "churned", this may be the final quarter with the churn reason captured.
- Reference Helix-side AND customer-side people by name.
- Keep records grounded and specific (a real ticket number, a real metric, a real contract term) — but these are background depth, not the major tracked decisions.
- Era-appropriate tooling (Salesforce vs HubSpot, Zendesk-style tickets).
- Output ONLY the records separated by `=== RECORD ===`. No preamble, no code fences.
