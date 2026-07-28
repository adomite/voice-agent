## ADDED Requirements

### Requirement: Repetition-loop transcripts are rejected
The transcript post-processing pipeline SHALL reject outputs where a single word/token dominates the transcript (a repetition loop), rather than emitting it as if it were real user speech.

#### Scenario: Whisper repetition loop is filtered
- **WHEN** Whisper returns a transcript where the same word or token is repeated far more than would occur in normal speech (e.g. "Chuchu Chuchu Chuchu Chuchu Chuchu Chuchu Chuchu Chuchu Chuchu Chuchu")
- **THEN** the transcript is rejected and not forwarded to the LLM or shown as `[USER]` output

### Requirement: Known canned hallucination phrases are rejected
The transcript post-processing pipeline SHALL reject a small set of known Whisper training-data-leakage phrases when they appear as the sole or near-sole content of a transcript.

#### Scenario: Known hallucinated phrase is filtered
- **WHEN** Whisper returns a transcript matching a known canned hallucination (e.g. "Subtítulos por la comunidad de Amara.org", "¡Suscríbete!") with no other substantive content
- **THEN** the transcript is rejected and not forwarded to the LLM or shown as `[USER]` output

### Requirement: Genuine short utterances are preserved
Filtering added to address hallucinations SHALL NOT reject genuine short user speech.

#### Scenario: Short real reply is still accepted
- **WHEN** the user says a short, genuine reply (e.g. "sí", "no", "ok")
- **THEN** it is still transcribed and forwarded normally, not rejected by the new filtering
