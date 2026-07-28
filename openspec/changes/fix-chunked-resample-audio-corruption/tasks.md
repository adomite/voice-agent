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

## 4. Verification — ThinkPad, round 2 (with the actual fix)

- [ ] 4.1 Repeat the A/B test once more: record a clear utterance, transcribe it directly and through the live pipeline (now with the 4s settle window); confirm both match.
- [ ] 4.2 Run a multi-turn live session with clear speech and confirm transcripts are coherent and match what was actually said.
- [ ] 4.3 Confirm the 4s settle window doesn't feel unusably slow in practice (only applies at session start and after each TTS turn, not continuously).
- [ ] 4.4 Confirm this doesn't regress the overflow fix or the hallucination filtering from the other changes (run a normal session end to end).

## 5. Verification — MSI (regression check)

- [ ] 5.1 Run a session on the MSI and confirm transcription quality is at least as good as before this change, and that the longer settle window doesn't meaningfully hurt turn-taking responsiveness there.
