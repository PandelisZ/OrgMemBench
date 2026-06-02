{shared_header}

# Your task — Meeting transcript (Otter.ai-style)

Write a realistic auto-transcribed meeting transcript. These are MESSY — speakers interrupt each other, sentences trail off, the transcript catches false starts, and the auto-transcription tool occasionally mis-hears words.

# Format

Plain text, one utterance per line. Format strictly:

```
[HH:MM:SS] <Speaker Name>: <utterance, including false starts and crosstalk>
```

# Style

- Use realistic timestamps starting at roughly the meeting hour, progressing every 10-60 seconds.
- Speakers should drift in and out: not every participant talks evenly. One or two dominate. Some chime in briefly.
- Include 3-5 light transcription quirks: "[inaudible]", "[crosstalk]", a mis-heard word (e.g. "the Kuberenetes cluster"), an "um", a "you know".
- Sentences should sometimes trail off mid-thought, especially when interrupted.
- Total length: 30-80 utterances. Long meetings (incident postmortems, board calls) get more; quick syncs get fewer.

# Important

- The event's canonical decision is REACHED OR DEBATED in the transcript — readers should be able to infer the decision from what the speakers say.
- For PRIMARY artefacts: the canonical decision is explicitly stated by one of the participants near the end (e.g. "Ok so we're going with X").
- For SECONDARY artefacts: the discussion is about an adjacent topic that references the event obliquely.
- For NOISE artefacts: the transcript is from a different meeting where the event is mentioned in passing (e.g. "remember that thing with X last month?").
- Era: low-discipline era = no formal opening/closing; high-discipline era = explicit "Let's start with the agenda" / "Let's wrap up with action items".

Output the transcript directly. No preamble.
