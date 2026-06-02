{shared_header}

# Your task — Incident report

Write a real-time incident report, written DURING or IMMEDIATELY AFTER the incident (NOT the polished postmortem that comes later). This is a status-update style document — what we know, what we're doing, what's resolved.

# Format

Plain Markdown:

```
# Incident: <one-line title> — INC-<YYYY-MM-DD>-NN

**Status:** Investigating | Identified | Monitoring | Resolved
**Severity:** SEV-<1-4>
**Started:** <YYYY-MM-DD HH:MM>
**Resolved:** <YYYY-MM-DD HH:MM or TBD>
**Customer impact:** <description>
**Incident commander:** <name>

## Current understanding

<2-3 sentences updated as the incident progresses. What we know now.>

## Timeline (live-updated)

- HH:MM — <event>
- HH:MM — <event>

## Mitigation

<what we've tried, what's working, what's not>

## Customer comms

<bullet — when / how customers were notified>

## Next update

<by HH:MM or "on resolution">
```

# Important

- This document is written WHILE the incident is happening, not after. Tone is urgent but factual.
- For PRIMARY artefacts: includes the canonical root cause (matching the event's `reason_canonical`) and resolution actions.
- Postmortems (separate genre) come LATER with full analysis.
- Author voice: SRE / engineer voice — concise, technical, no speculation.

Output the incident report directly. No preamble.
