## 1. Shared TTS-active signal

- [x] 1.1 In `app/pipeline/orchestrator_async.py`, create an `asyncio.Event` (e.g. `tts_active`) in `run_pipeline` and pass it to both `audio_producer` and `stt_consumer`.
- [x] 1.2 In `stt_consumer`, set `tts_active` immediately before `await asyncio.to_thread(speak, ...)` and clear it immediately after the call returns (in a `finally` so it's always cleared even if `speak` raises).

## 2. Pause/resume mic capture around TTS

- [x] 2.1 In `app/audio/input.py`, update `audio_producer` to accept the `tts_active` event and, inside its loop, call `stream.stop()` when the event becomes set and `stream.start()` when it's cleared (plus a cooldown delay via `TTS_COOLDOWN_MS`, default 250ms, before resuming).
- [x] 2.2 Guard the resume call so a transient `stream.start()` failure logs and retries instead of propagating and killing the sibling `stt_consumer` task via `asyncio.gather`.
- [x] 2.3 (Found during first ThinkPad test of this change) Add a post-resume "settle" mute window (`AUDIO_RESUME_SETTLE_MS`, default 300ms): `stream.start()` after TTS can itself produce a hardware pop/transient that the VAD mistakes for speech, immediately eating the next turn with a spurious utterance/hallucination (e.g. "¡Suscríbete!") right after `[TTS] done`. The callback now drops audio for a short window after resume instead of queueing it.

## 3. Verification — ThinkPad (primary target)

- [ ] 3.1 Run a session with several TTS turns on the ThinkPad (same env vars as the `fix-audio-input-overflow-cpu` test: `WHISPER_CPU_THREADS=4 AUDIO_LATENCY=high`) and confirm no `[AUDIO STATUS] input overflow` appears during or immediately after `[TTS] speaking...` blocks.
- [ ] 3.2 Confirm no more hallucinated transcripts of the "Subtítulos por la comunidad de Amara.org" / "¡Suscríbete!" pattern appear after this fix, including right after `[TTS] done`.
- [ ] 3.3 Confirm the user can still speak and be heard shortly after the assistant finishes talking (cooldown isn't so long it feels broken).

## 4. Verification — MSI (regression check)

- [ ] 4.1 Run a multi-turn session on the MSI and confirm transcription/turn-taking is at least as good as the pre-change baseline, with no new overflow introduced by the stop/start behavior.
