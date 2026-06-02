You are writing the arc summary for a **historical customer** — a customer that was relevant in the company's past but is **no longer an active account**. These appear in old artefacts, in retrospectives, in references like "remember the Sterling deal that fell apart in 2023."

# Company context

{company_one_liner}

# Year arcs

{year_arcs_block}

# Active customers already defined (do NOT duplicate)

{active_customers_block}

# Historical customers already in this batch (do NOT duplicate)

{existing_historical_block}

# This historical customer's slot

- Index: **{customer_index} of {total_historical}**
- Outcome category: **{outcome_category}**
- Tenure: **{first_year}** through **{last_year}**

# Your task

Write one YAML document (no code fences) describing this historical customer. Schema:

```yaml
customer_id: C-NNNN             # use C-{customer_index_padded} (continue numbering past active)
name: <invented company name>
industry: <one or two words>
size: small | mid | large | enterprise
first_year: YYYY
last_year: YYYY                 # ALWAYS set — these are no longer active
outcome: <one of: churned, lost_at_pitch, design_partner_left, acquired_out_of_business, never_renewed_after_pilot, lawsuit_separation>
arc_summary: |
  <2-4 sentences describing the customer's arc from first_year to
  last_year, the reason they left/never-came, and any lasting impact
  on the company. Include at least one specific named event.>
narrative_roles:
  - <one of: churned, design_partner_left, lost_pitch, lost_to_competitor, acquired, contract_dispute, pilot_dropoff>
renewal_timeline:
  - year: YYYY
    event: <one of: signed, renewed, expanded, downgrade, churn_risk, churned, escalation, pitch_lost, pilot_started, pilot_ended>
                                # 2-5 entries, ending in a terminal event
contract_notes: |
  <1-2 sentences about specific contract details if any existed —
  payment terms, SLA promised, custom features promised>
referenced_in: |
  <one short line about how/where this customer might be referenced
  in later artefacts. E.g. "Cited in 2024 sales retro as the
  cautionary tale of over-customising for design partners.">
```

# Important

- Customer name must be distinct from all already-named customers.
- Outcome must match the category requested ({outcome_category}).
- The `referenced_in:` line is the noise hook — it tells the corpus generation phase where this customer should plausibly surface even after they're gone.
- Output only the YAML document. No prose preamble. No code fences.
