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

- [x] 8.1 Listened to a freshly-saved `DEBUG_SAVE_UTTERANCES=1` WAV — confirmed correct sample rate/pitch after Resolution update 2, but revealed a new problem: audio was clean but very quiet (rms≈623, peak≈2471 / 32767) — too quiet to reliably transcribe or hear. Led to Resolution update 3 (channel-downmix cancellation + ALSA hardware gain).
- [x] 8.2 Live session with the round-3 fix (`_resolve_channels` mono capture + `amixer -c 0 sset Capture 70%`): `[USER]` transcripts now match what was said exactly ("La silla está rota.", "Necesito comprar una mesa."). Settle-window/discard-first-utterance machinery (sections 3-5) left as-is — still needed and working (`[SKIP] discarding first utterance after resume` fires correctly each resume) — not scaled back in this pass.
- [x] 8.3 Superseded by the live multi-turn test in 8.2, which is a stronger signal than a single A/B replay: multiple consecutive utterances transcribed correctly end-to-end through the real pipeline (segmenter → Whisper → Ollama → TTS), not just recorded-vs-live equivalence for one clip.
- [x] 8.4 Confirmed no regression: overflow-free (no `[AUDIO STATUS]` overflow messages), and `tune-vad-hallucination-filtering`'s filter correctly caught `¡Suscríbete!` hallucinations between real utterances (`[FILTERED]` lines) without blocking real speech.
- [x] 8.5 Decided: leaving `DEBUG_SAVE_UTTERANCES` in place (off by default, zero cost when unset) — it was essential for finding both round-3 causes and for the MSI hallucination finding below; keep as a permanent debugging aid.
- [x] 8.6 Persisted ALSA `Capture` gain via `sudo alsactl store` (2026-08-30). Note: found gain had silently reverted to 100%/+30dB at some point after the original July 28 fix, despite `alsa-restore.service` being active — the original `alsactl store` apparently never took or was overwritten. Re-set to 70%/15.75dB and re-persisted; confirmed `/var/lib/alsa/asound.state` timestamp updated and `alsa-restore.service` active. **Reboot-confirmed same day (2026-08-30): gain held at 70%/15.75dB after a real reboot — persistence verified reliable.**


## 9. Verification — MSI (regression check)

<<<<<<< Updated upstream:openspec/changes/archive/2026-07-28-fix-chunked-resample-audio-corruption/tasks.md
- [x] 9.1 Ran a full multi-turn `pt_practice` session on MSI (rebuilt container on `worktree-fix-audio-input-overflow` @ `6bc48d3`). Transcription quality was good — multiple correct Portuguese transcripts matching real speech ("Você pode conjugar ou ver você?", "Conjuga o verbo ser.", etc.). One `[AUDIO STATUS] input overflow` occurred, exactly at a TTS-resume boundary; the pipeline recovered immediately and continued correctly. This matches a symptom reported earlier in this same investigation ("on MSI... sometimes it didn't hear me, so the tutor answered itself") — i.e. a pre-existing quirk of MSI's raw ALSA `hw:0,7` device (same category as the ThinkPad's original `hw:0,0` problem, never migrated to a PipeWire-routed device on MSI), not a regression introduced by this change. See section 10 below.
- [x] 9.2 Confirmed: `_resolve_channels()`'s probe-then-open pattern resolved to `channels=1` cleanly under MSI's Docker audio passthrough (`/dev/snd` device passthrough), no busy/exclusive-access errors. No regression.

## 10. Follow-up findings (out of scope for this change, logged for future work)

- MSI's `AUDIO_INPUT_DEVICE=hw:0,7` (raw ALSA, `docker-compose.yaml`) retains the same class of resume-boundary overflow risk that was fixed on the ThinkPad by switching to the PipeWire-routed `default` device (`fix-audio-input-overflow-cpu`, archived). Never applied to MSI. Candidate for a small follow-up change mirroring that fix, if MSI has an equivalent PipeWire/`default` capture device available under Docker.
- `docker compose up --build` always launches `pt_practice` (no regression, no bug): `dockerfile` has `CMD ["python", "main.py"]` with no mode argument, and `main.py`'s `mode_name` defaults to `"pt_practice"` when none is given. Explicit mode selection requires `docker compose run voice-agent python main.py <mode>` per the README. Purely a documentation/expectation gap if it needs addressing.
- During the MSI test, a Whisper hallucination ("Legendas pela comunidade de Amara.org", the Portuguese/English variant of the amara.org captioning-credit artifact) was **not** caught by `is_known_hallucination()` and was sent to the LLM as real user input, derailing that turn. The blocklist in `app/stt/postprocess.py` only covers the Spanish wording. This is in scope for `tune-vad-hallucination-filtering` (still open), not this change.
=======

>>>>>>> Stashed changes:openspec/changes/fix-chunked-resample-audio-corruption/tasks.md
