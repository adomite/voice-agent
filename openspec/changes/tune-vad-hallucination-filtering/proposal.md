## Why

Across every ThinkPad test during the audio-overflow investigation (`fix-audio-input-overflow-cpu`, `fix-tts-audio-duplex-overflow` — both archived), a separate symptom kept recurring regardless of overflow, TTS state, or headphones vs. speakers: Whisper produces garbage transcripts on audio that isn't real user speech — canned hallucinated phrases ("¡Suscríbete!", "Subtítulos por la comunidad de Amara.org") and repetition loops ("Chuchu Chuchu Chuchu...", a string of "g"s). It was reproduced with headphones on (rules out acoustic echo) and on the very first utterance of a session before any TTS has occurred, so it is not related to audio duplex, TTS playback, or the overflow bug — it is the WebRTC VAD (`app/stt/segmenter.py`, `app/stt/vad.py`) classifying non-speech audio (background noise, breath, room tone) as speech, and Whisper hallucinating on that ambiguous input, combined with `app/stt/postprocess.py` only filtering single very-short words (not these patterns).

## What Changes

- Tighten VAD sensitivity in `app/stt/segmenter.py` (e.g. `vad_aggressiveness`, `min_speech_frames`) so brief noise/breath is less likely to be classified as a speech segment worth sending to Whisper at all.
- Add hallucination-pattern filtering to `app/stt/postprocess.py`: reject outputs that are repetition loops (the same token/short phrase repeated many times consecutively) and reject a small set of known canned Whisper hallucination phrases (e.g. "Subtítulos por la comunidad de Amara.org", "¡Suscríbete!") in addition to the existing short-word filter.
- Keep changes environment-agnostic (same segmenter/postprocess logic on both machines) unless evidence during implementation shows otherwise — this is a VAD/decoding quality issue, not a ThinkPad-vs-MSI hardware difference like the overflow bug was.

## Capabilities

### New Capabilities
- `transcript-hallucination-filtering`: The STT pipeline SHALL avoid emitting Whisper hallucinations (canned phrases, repetition loops) as if they were real user speech, and SHALL be less prone to triggering an utterance on non-speech audio in the first place.

### Modified Capabilities
(none)

## Impact

- Code: `app/stt/segmenter.py` (VAD tuning parameters), `app/stt/postprocess.py` (new filtering logic), possibly `app/stt/vad.py` if an energy-based pre-gate is added.
- No new env vars anticipated, though VAD tuning parameters could be made overridable if empirical tuning differs meaningfully between the two machines (to be decided during implementation, not assumed here).
- Must not regress genuine short user utterances (e.g. "Sí", "No", "Ok") being incorrectly filtered out — the existing short-word filter already treads this line; any tightening needs to preserve real short replies.
- Non-goals (carried over from the audio-overflow changes, still applicable): improving proper-noun transcription accuracy, and anything related to audio device/overflow — that's resolved and out of scope here.
- Verification: primarily on the ThinkPad, where this was observed and is easiest to reproduce (background noise is more audible on CPU-only hardware sessions run so far); spot-check on MSI for regressions in legitimate short-utterance handling.
