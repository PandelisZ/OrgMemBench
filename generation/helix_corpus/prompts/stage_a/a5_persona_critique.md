You are reviewing a persona library for a fictional B2B SaaS company. Your job is to detect personas that sound too similar to each other.

# The personas

{personas_block}

# Your task

Read every persona's `display_name`, `voice_markers`, `signature_phrases`, and `domain_expertise`. Identify pairs of personas whose **voices are too similar** to be distinguishable in writing. Two personas are too similar if any of these is true:

- Both have the same `hedging_frequency` AND `formality` AND `emoji_use`, with `typical_message_length_words` within 20 of each other.
- Their `signature_phrases` are stylistically interchangeable (same register, same kind of metaphors, same level of jargon).
- Their `domain_expertise` overlaps and they have no other differentiating voice markers.

# Output

Plain text, one collision per line, in this exact format:
```
P-NNNN <-> P-NNNN: <one-sentence reason>
```

If there are no collisions, output exactly:
```
NO_COLLISIONS
```

Do **not** output anything else. No code fences. No commentary. No headers.
