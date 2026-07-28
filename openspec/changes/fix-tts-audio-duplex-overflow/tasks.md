## 1. Shared TTS-active signal

- [x] 1.1 In `app/pipeline/orchestrator_async.py`, create an `asyncio.Event` (e.g. `tts_active`) in `run_pipeline` and pass it to both `audio_producer` and `stt_consumer`.
- [x] 1.2 In `stt_consumer`, set `tts_active` immediately before `await asyncio.to_thread(speak, ...)` and clear it immediately after the call returns (in a `finally` so it's always cleared even if `speak` raises).

## 2. Pause/resume mic capture around TTS

- [x] 2.1 In `app/audio/input.py`, update `audio_producer` to accept the `tts_active` event and, inside its loop, call `stream.stop()` when the event becomes set and `stream.start()` when it's cleared (plus a cooldown delay via `TTS_COOLDOWN_MS`, default 250ms, before resuming).
- [x] 2.2 Guard the resume call so a transient `stream.start()` failure logs and retries instead of propagating and killing the sibling `stt_consumer` task via `asyncio.gather`.
- [x] 2.3 (Found during first ThinkPad test of this change) Add a post-resume "settle" mute window (`AUDIO_RESUME_SETTLE_MS`, default 300ms): `stream.start()` after TTS can itself produce a hardware pop/transient that the VAD mistakes for speech, immediately eating the next turn with a spurious utterance/hallucination (e.g. "¡Suscríbete!") right after `[TTS] done`. The callback now drops audio for a short window after resume instead of queueing it.

## 3. Verification — ThinkPad (primary target)

- [x] 3.1 Confirmed: with `AUDIO_INPUT_DEVICE=default` (the actual fix, see `fix-audio-input-overflow-cpu`), no `[AUDIO STATUS] input overflow` appears anywhere, during or after TTS, with or without this change's stop/start logic. **Correction**: overflow was never actually caused by TTS/mic duplex contention — it was caused by `hw:0,0` (raw ALSA) regardless of TTS state, and disappears with `default` alone. This change's stop/start logic is unnecessary for the overflow fix, though harmless.
- [ ] 3.2 **Not resolved, and re-scoped**: hallucinated transcripts ("Subtítulos por la comunidad de Amara.org", "¡Suscríbete!") still occur after this fix, including right after `[TTS] done`. Reproduced with headphones on (rules out acoustic echo) and even on the very first utterance before any TTS has happened. This is **not** a TTS/audio-duplex issue — it's Whisper hallucinating on audio the VAD misclassifies as speech (background noise, breath, etc.). Moved to a new, separate change for VAD/hallucination tuning; not this change's responsibility.
- [x] 3.3 Turn-taking responsiveness (cooldown feel) was acceptable in all ThinkPad tests; no complaints of the agent feeling unresponsive after speaking.

## 4. Verification — MSI (regression check)

- [x] 4.1 MSI regression-tested on this branch (before the settle-window addition in 2.3, but with the stop/start logic from 2.1/2.2 active): only 1 overflow line across 7 TTS turns, consistent with pre-change baseline. Since `fix-audio-input-overflow-cpu` established MSI never needed a device change (its Docker/PulseAudio passthrough already avoids the `hw:X,Y` direct-ALSA problem), no further MSI-specific action is needed here.

## 5. Scope correction

- [x] 5.1 This change's original premise (TTS output stream contending with mic input stream on `hw:0,0`, or the mic picking up acoustic echo) is **not the actual root cause** — see `fix-audio-input-overflow-cpu`'s design.md Resolution note. The overflow this change set out to fix is the same overflow already resolved by the `AUDIO_INPUT_DEVICE=default` change. The stop/start/mute-window code implemented here is kept as a reasonable defense-in-depth measure (no observed downside, still correctly scoped to only run around TTS) but is not required for the fix.
