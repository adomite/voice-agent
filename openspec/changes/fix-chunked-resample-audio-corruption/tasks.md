## 1. Segmenter fix (`app/stt/segmenter.py`)

- [x] 1.1 Added `raw_pre_buffer` (bounded deque, default 5 chunks) and `raw_speech_chunks` (list, populated once speech starts), mirroring the existing frame-based `pre_buffer`/speech-accumulation state at chunk granularity.
- [x] 1.2 `process_chunk` keeps the existing per-chunk downsample+VAD-framing path unchanged for speech/silence detection; the resulting frames are no longer used to build the final utterance audio (only for the VAD decision and `speech_frame_count`).
- [x] 1.3 At utterance end, the audio returned to the caller is built by concatenating `raw_speech_chunks` (native sample rate) and calling `downsample_audio` once. Verified mechanically with a synthetic-signal test (mocked VAD): chunked reconstruction preserves signal amplitude/character with no corruption (peak 0.30000001 vs. whole-signal 0.3000001, floating-point-noise-level difference).
- [x] 1.4 `reset()` updated to also clear the new raw buffers.

## 2. Verification — ThinkPad, round 1 (found the chunked-resampling fix was insufficient)

- [x] 2.1 Repeated the A/B test with a new phrase ("aumenta o reduce los pasos de verificación en tiempo real según señales de riesgo"): live pipeline still produced unrelated garbage ("La pausa se ha hecho de tu bodcucho") despite the segmenter fix from section 1. Led to the deeper investigation below.
- [x] 2.2 Direct signal measurement (no chunking, no segmenter involved) found severe sustained clipping (peak=32768 in 9/12 half-second windows) and a large decaying DC offset (-28857 → near-zero over ~3s) in a 6s recording — confirming a multi-second capture-warmup transient, not a chunking artifact, as the dominant cause. Confirmed `vad_aggressiveness` 2 vs. 3 barely changes VAD's speech/silence classification on this signal (193/200 vs. 190/200 frames as "speech") — ruling out VAD tuning as a fix too.

## 3. The actual fix (`app/audio/input.py`)

- [x] 3.1 Apply the existing `mute_until` mechanism at initial stream open (previously only applied on resume-after-TTS), so the very first utterance of a session is also protected.
- [x] 3.2 Raise `AUDIO_RESUME_SETTLE_MS` default from 300 to 4000 (ms), matching the measured transient duration.
- [x] 3.3 Delay the "🎤 Mic is ON... speak!" print until after the settle window elapses, with an explicit "settling..." message beforehand, so the UI doesn't invite the user to talk into a dead window.

## 4. Verification — ThinkPad, round 2 (4s settle window alone)

- [x] 4.1 Live session with the 4s settle window: still 6+ spurious hallucination cycles right after "Mic is ON" and 1 after TTS-resume — 4s was not enough on its own, but no more long garbled sentences (previously "La pausa se ha hecho de tu bodcucho"-style nonsense; now only short filtered hallucinations like "¡Suscríbete!").
- [x] 4.2 Retested with `AUDIO_RESUME_SETTLE_MS=7000`: down to exactly 1 spurious cycle per resume (both at session start and after TTS) — consistently 1, not 0, regardless of 4s vs. 7s wait. This pattern (always exactly one, unaffected by wait duration) pointed away from "transient needs more time" and toward a deterministic boundary artifact right at the unmute point.

## 5. Deterministic backstop: discard the first utterance after every resume (`app/pipeline/orchestrator_async.py`, `app/audio/input.py`)

- [x] 5.1 Added a shared `discard_next_utterance` `asyncio.Event`, set by `audio_producer` right after each resume (initial stream open and every TTS-resume), consumed once by `stt_consumer` — the first utterance detected after any resume is logged and dropped instead of sent to Whisper, regardless of whether the settle window fully cleared the artifact.
- [x] 5.2 Raised the persisted `AUDIO_RESUME_SETTLE_MS` default to 7000 (matching the empirically-better result), so at most one spurious utterance needs discarding per resume rather than several.

## 6. Verification — ThinkPad, round 3 (settle window + deterministic discard)

- [ ] 6.1 Live session: confirm no hallucinated/garbled `[USER]` output appears right after "Mic is ON" or after any TTS turn (should now see `[SKIP] discarding first utterance after resume...` instead of a filtered hallucination or garbled text).
- [ ] 6.2 Repeat the A/B test once more (record + direct transcript vs. live pipeline) for a clear utterance spoken after the settle window elapses.
- [ ] 6.3 Confirm the ~7s settle window (session start + after every TTS turn) doesn't feel unusably slow in practice.
- [ ] 6.4 Confirm this doesn't regress the overflow fix or the hallucination filtering from the other changes (run a normal multi-turn session end to end).

## 7. Verification — MSI (regression check)

- [ ] 7.1 Run a session on the MSI and confirm transcription quality is at least as good as before this change, and that the 7s settle window + first-utterance discard don't meaningfully hurt turn-taking responsiveness there (MSI's baseline was already fast/clean, so this is mainly a "doesn't make it worse" check).
