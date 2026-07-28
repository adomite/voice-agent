# utterance-audio-fidelity Specification

## Purpose
TBD - created by archiving change fix-chunked-resample-audio-corruption. Update Purpose after archive.
## Requirements
### Requirement: Live-pipeline transcription matches whole-clip transcription for the same clear audio
For a clearly-spoken utterance, transcribing it through the live capture pipeline (mic → segmenter → Whisper) SHALL produce a transcript equivalent to resampling and transcribing the same raw audio as a single continuous clip — the segmenter's chunked capture SHALL NOT introduce resampling artifacts that degrade transcription quality.

#### Scenario: Clear utterance transcribes correctly end-to-end
- **WHEN** a user speaks a clear, unambiguous sentence into the live pipeline
- **THEN** the resulting `[USER]` transcript matches what the same recorded audio would transcribe to if resampled once and sent to Whisper directly (verified via an A/B comparison: record the same utterance, transcribe it directly, and transcribe it live)

### Requirement: Utterance audio is resampled once per utterance, not once per chunk
The audio buffer handed to STT for a completed utterance SHALL be built by resampling the concatenated raw (native-sample-rate) audio a single time, not by concatenating audio that was independently resampled chunk-by-chunk as it arrived.

#### Scenario: No chunk-boundary artifacts in reconstructed utterance audio
- **WHEN** an utterance spans multiple mic chunks (the normal case for any utterance longer than one blocksize)
- **THEN** the final audio sent to Whisper is the result of one resample call over the concatenated raw chunks, not multiple independent per-chunk resample calls concatenated together

