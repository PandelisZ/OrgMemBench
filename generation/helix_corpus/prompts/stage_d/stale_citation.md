You are writing a stale-citation that should be inserted into an artefact in a fictional company's corpus. A stale citation is when a later artefact references an OLDER document that has SINCE been superseded — but the citer doesn't know or doesn't update, so the reference still points at the outdated source.

This is the §4.2 dispersal noise mechanism that gives the benchmark its bite: the system-under-test must recognise that the cited doc is stale and recover the actual current state from later artefacts.

# Source artefact (the artefact you're appending the citation TO; this is the LATER artefact)

- Genre: {source_genre}
- Author: {source_author_name}
- Event it documents: {source_event_summary}
- Date: {source_date}

# Stale target (the OUTDATED artefact being cited — the citer wrongly treats this as current)

- Genre: {target_genre}
- Event it documents: {target_event_summary}
- Date: {target_date}

# Note

The target artefact has since been **superseded** by a newer artefact ({superseder_event_summary}, {superseder_date}). The citer in the source artefact is unaware of this — they cite the old one as if it still holds.

# Your task

Write **one short phrase** (5-30 words) appropriate to the source genre that cites the OLDER (stale) artefact AS IF IT WERE CURRENT. The citer must sound confident — they think the stale doc is the right reference.

Examples:

- In a 2024 onboarding doc: `Per our refund policy (see the 2021 customer-onboarding playbook, section 4), customers are entitled to…`
- In a 2025 Slack thread: `Yeah just use the alerting SLA from Maya's old runbook, that's still the standard.`
- In a 2024 customer email: `As stated in our 2022 service agreement, response times are…`

# Constraints

- Match the source genre's conventions.
- The citation must sound INNOCENT — like the citer believes the reference is current.
- Do NOT add preamble or commentary. Output the phrase only, on one line.
