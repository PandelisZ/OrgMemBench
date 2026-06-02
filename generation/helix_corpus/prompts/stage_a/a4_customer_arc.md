You are writing the arc summary for one of the named customers in a fictional B2B SaaS company's corpus.

# Company context

{company_one_liner}

# Year arcs (for plausibility)

{year_arcs_block}

# Existing customers (do NOT duplicate)

{existing_customers_block}

# This customer's slot

- Customer index: **{customer_index} of {total_customers}**
- Narrative role this customer plays: **{narrative_role}**
- First year of relationship: **{first_year}**

# Your task

Write one YAML document (no code fences) describing this customer's arc from `{first_year}` through {current_year}. Schema:

```yaml
customer_id: C-NNNN             # use C-{customer_index_padded}
name: <invented company name>   # plausible industry; not a real company
industry: <one or two words>
size: small | mid | large | enterprise
first_year: YYYY
last_year: YYYY | null          # null if still active
arc_summary: |
  <2-4 sentences describing the relationship arc — initial contact,
  notable events (escalation, near-churn, expansion), current state>
narrative_roles:
  - <one of: design_partner, near_churn, churned, happy_reference,
    difficult_escalation, expansion, biggest_contract, contracts_redline_drama>
  - <may add a second narrative role if the arc spans multiple>
renewal_timeline:
  - year: YYYY
    event: <one of: signed, renewed, expanded, downgrade, churn_risk, churned, escalation, recovered>
  - year: YYYY
    event: <...>
                                # 3-6 entries; chronological order
contract_notes: |
  <1-2 sentences about a contract specific to this customer — payment
  terms, SLA, custom features, anything that creates a paper trail
  the benchmark questions can probe>
```

# Important

- Customer name must be inventive — not a real freight forwarder / logistics company.
- The arc must include at least one **specific event** (a year + a thing that happened) that the corpus can later reference.
- If the narrative role is `churned` or `churn_risk`, you must include the **reason** in the `arc_summary` — this is a benchmark probe.
- Output only the YAML. No prose preamble.
