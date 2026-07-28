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

## 6. Verification — ThinkPad, round 3 (settle window + deterministic discard, still broken)

- [x] 6.1 Live session with `DEBUG_SAVE_UTTERANCES=1` (temporary diagnostic, `app/pipeline/orchestrator_async.py`): first-utterance discard worked correctly, but 4-6 more spurious hallucinations still followed per resume (not "exactly one" as round 2 suggested — count varied session to session), and real `[USER]` content still didn't match what was said. Listening to the saved WAV directly: audio played back noticeably slow and distorted — the signature of a sample-rate mismatch, not a chunking or transient issue.

## 7. The actual dominant fix: correct `input_sample_rate` (`app/pipeline/orchestrator_async.py`)

- [x] 7.1 Found `WebRTCUtteranceSegmenter` was constructed with `input_sample_rate=16000` hardcoded, while the mic actually captures at `AUDIO_SAMPLE_RATE` (48000 on the ThinkPad) — making `downsample_audio()`'s `orig_sr == target_sr` short-circuit a silent no-op for the entire session, for both VAD framing and the final Whisper-bound audio. Predates every change made in this session.
- [x] 7.2 Fixed: `input_sample_rate=int(os.environ.get('AUDIO_SAMPLE_RATE', 48000))`, matching what `app/audio/input.py` actually uses to open the stream.

## 8. Verification — ThinkPad, round 4 (with the sample-rate fix)

- [ ] 8.1 Listen to a freshly-saved `DEBUG_SAVE_UTTERANCES=1` WAV and confirm it now plays back at normal speed/pitch, matching what was actually said.
- [ ] 8.2 Live session: confirm `[USER]` transcripts now match what was said, and confirm whether the settle-window/discard-first-utterance machinery from sections 3-5 is still needed at this reduced severity, or can be scaled back (e.g. shorter `AUDIO_RESUME_SETTLE_MS`) now that VAD is analyzing correctly-labeled audio.
- [ ] 8.3 Repeat the A/B test once more (record + direct transcript vs. live pipeline) to confirm both fully match.
- [ ] 8.4 Confirm this doesn't regress the overflow fix or the hallucination filtering from the other changes (run a normal multi-turn session end to end).
- [ ] 8.5 Remove or otherwise clean up the temporary `DEBUG_SAVE_UTTERANCES` diagnostic once no longer needed (or leave it, off by default, as a permanent debugging aid — decide during this verification pass).

## 9. Verification — MSI (regression check)

- [ ] 9.1 Run a session on the MSI and confirm transcription quality is at least as good as before this change. Note: MSI's `AUDIO_SAMPLE_RATE=16000` (per its `docker-compose.yml`), so the same hardcoded-16000 bug was accidentally a no-op *correctly* there — this fix should be a no-op change for MSI's behavior, not a regression risk.
