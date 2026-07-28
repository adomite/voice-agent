## Context

`app/stt/segmenter.py`'s `WebRTCUtteranceSegmenter` currently runs with `vad_aggressiveness=2` (mid-range, WebRTC VAD scale 0-3), `start_speech_frames=3` (90ms of continuous VAD-positive frames to open an utterance), `min_speech_frames=6` (180ms minimum to keep it), `end_silence_frames=14` (420ms of silence to close it). `app/stt/vad.py` is a thin wrapper with no additional energy gating beyond WebRTC VAD's own frame classifier. `app/stt/postprocess.py`'s `is_unstable_short_utterance` only rejects single words of ≤3 characters — it does not catch multi-word or longer hallucinated output.

Observed evidence (ThinkPad, multiple sessions, reproduced with headphones on and before any TTS occurred in-session, so unrelated to audio duplex/echo): short bursts of ambient audio (background noise, breath, room tone) are classified as speech by the segmenter, sent to Whisper, and Whisper — as documented behavior for `small`/similar Whisper checkpoints given near-silent or ambiguous input — either hallucinates a canned phrase memorized from its training data (subtitle-credit lines, "subscribe" prompts) or falls into a repetition loop (the same token repeated dozens of times).

## Goals / Non-Goals

**Goals:**
- Reduce how often non-speech audio reaches Whisper at all (tighter VAD gating).
- Catch the hallucination patterns that do get through, before they reach the LLM as if they were real user input (postprocess-level filtering).
- Preserve genuine short user utterances (e.g. single-word replies like "Sí"/"No") — don't over-tighten to the point of losing real input.

**Non-Goals:**
- Building a general-purpose ML-based hallucination classifier — pattern-based filtering (repetition detection + a small known-phrase list) is sufficient for the observed failure modes.
- Fixing proper-noun transcription accuracy — separate, already-deprioritized issue.
- Anything related to audio device selection, input overflow, or TTS/duplex — resolved in the archived `fix-audio-input-overflow-cpu` / `fix-tts-audio-duplex-overflow` changes.

## Decisions

**1. Add repetition-loop detection to `app/stt/postprocess.py`.**
If a transcript's most common word (case-insensitive) accounts for more than a threshold share of total words (e.g. >50% with at least 4 repeats), treat it as a hallucination and reject it — catches "Chuchu Chuchu Chuchu..." / "¡S... ¡S... ¡S..." patterns regardless of language or exact wording, without hardcoding phrases.
*Alternative considered*: regex for exact repeated substrings — rejected, more brittle across languages/punctuation variants than a word-frequency check.

**2. Add a small known-canned-phrase blocklist to `app/stt/postprocess.py`.**
Reject exact/near matches against a short, explicit list of observed Whisper training-data leakage phrases (e.g. "subtítulos por la comunidad de amara.org", "suscríbete" as a sole/near-sole utterance). Kept intentionally small and explicit (not a broad heuristic) to avoid false-positive rejection of legitimate user speech that happens to contain common words.
*Alternative considered*: rely solely on decision 1 (repetition detection) — rejected as insufficient, since single-shot canned phrases like "¡Suscríbete!" aren't repetition loops and wouldn't be caught by that check alone.

**3. Tighten `min_speech_frames` in `app/stt/segmenter.py` modestly (e.g. 6 → 9-10 frames, ~270-300ms) rather than raising `vad_aggressiveness`.**
Raising `vad_aggressiveness` to 3 changes per-frame classification sensitivity and risks clipping the start of genuine quiet/soft speech; requiring a longer sustained run before accepting an utterance is a more targeted way to reject brief noise blips (the observed hallucination-triggering segments were short) without changing how individual frames are judged.
*Alternative considered*: raise `vad_aggressiveness` to 3 — kept as a fallback option if tightening `min_speech_frames` alone doesn't sufficiently reduce false triggers, but not the first lever, since it's coarser and affects more than just short blips.

## Risks / Trade-offs

- [Risk] Word-frequency-based repetition detection could reject a legitimately repetitive short user utterance (e.g. counting practice: "uno, dos, tres, tres, tres") → Mitigation: set the threshold conservatively (e.g. only trigger when the dominant word is ≥50% of a longer transcript with several repeats), and verify against realistic practice-session phrasing during testing.
- [Risk] The canned-phrase blocklist is inherently incomplete — new hallucinated phrases will surface over time → Mitigation: document it as a living list to extend as new patterns are observed, not a one-time fix.
- [Risk] Raising `min_speech_frames` could clip the start of short, quiet, but genuine replies → Mitigation: tune conservatively and verify single-word replies ("sí", "no", "ok") still register in testing.
