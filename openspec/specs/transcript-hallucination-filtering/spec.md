# transcript-hallucination-filtering Specification

## Purpose
TBD - created by archiving change tune-vad-hallucination-filtering. Update Purpose after archive.
## Requirements
### Requirement: Repetition-loop transcripts are rejected
The transcript post-processing pipeline SHALL reject outputs where a short word or phrase (up to a few words) repeats consecutively several times in a row (a repetition loop), rather than emitting it as if it were real user speech.

#### Scenario: Whisper single-word repetition loop is filtered
- **WHEN** Whisper returns a transcript where the same word or token is repeated far more than would occur in normal speech (e.g. "Chuchu Chuchu Chuchu Chuchu Chuchu Chuchu Chuchu Chuchu Chuchu Chuchu")
- **THEN** the transcript is rejected and not forwarded to the LLM or shown as `[USER]` output

#### Scenario: Whisper multi-word phrase repetition loop is filtered
- **WHEN** Whisper returns a transcript where a short phrase (not just a single word) repeats consecutively several times (e.g. "¡Vamos a ir! ¡Vamos a ir! ¡Vamos a ir! ¡Vamos a ir! ¡Vamos a ir!")
- **THEN** the transcript is rejected and not forwarded to the LLM or shown as `[USER]` output

### Requirement: Known canned hallucination phrases are rejected
The transcript post-processing pipeline SHALL reject a small set of known Whisper training-data-leakage phrases when they appear as the sole or near-sole content of a transcript.

#### Scenario: Known hallucinated phrase is filtered
- **WHEN** Whisper returns a transcript matching a known canned hallucination (e.g. "Subtítulos por la comunidad de Amara.org", "¡Suscríbete!") with no other substantive content
- **THEN** the transcript is rejected and not forwarded to the LLM or shown as `[USER]` output

### Requirement: Genuine short utterances are preserved
Filtering added to address hallucinations SHALL NOT reject genuine short user speech longer than a single word of 3 characters or fewer (the pre-existing `is_unstable_short_utterance` filter already rejects single words that short, independent of this change — that pre-existing behavior is not part of this requirement).

#### Scenario: Short real reply is still accepted
- **WHEN** the user says a short, genuine reply of more than 3 characters (e.g. "claro", "vale", "de acuerdo")
- **THEN** it is still transcribed and forwarded normally, not rejected by the new filtering

