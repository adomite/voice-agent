## Why

While testing the `fix-audio-input-overflow-cpu` change on the ThinkPad, live logs surfaced a distinct overflow mechanism the original change didn't cover. With `WHISPER_CPU_THREADS=4` and `AUDIO_LATENCY=high` applied, the *first* utterance capture was clean (0 overflow) — but every subsequent `[TTS] speaking...` block was immediately followed by 8–17 consecutive `[AUDIO STATUS] input overflow` lines, and two utterances transcribed as classic Whisper hallucinations on near-silent/noisy audio ("Subtítulos por la comunidad de Amara.org", "¡Suscríbete!") rather than anything the user said.

This points to a mechanism unrelated to Whisper CPU contention: `app/tts/piper_tts.py`'s `speak()` opens a PortAudio *output* stream (`sd.play()` + blocking `sd.wait()`) while the mic *input* stream (`app/audio/input.py`) is still open and running. On the ThinkPad's `hw:0,0` — a direct ALSA hardware device with no software duplex/mixing layer — running capture and playback concurrently appears to starve the input hardware buffer, and the mic likely also picks up acoustic echo of the agent's own voice (no echo cancellation), which Whisper then hallucinates into garbage transcripts. On the MSI, the same session (regression-tested on this same branch) showed only 1 overflow line across 7 TTS turns — consistent with PulseAudio (`PULSE_SERVER`, set in `docker-compose.yml`) handling duplex audio in software instead of raw ALSA.

This is being tracked as its own change (rather than folded into `fix-audio-input-overflow-cpu`) because it is a different root cause with a different fix, discovered mid-verification of that change.

## What Changes

- Pause microphone capture (`app/audio/input.py`'s `InputStream`) while the assistant's TTS response is playing, and resume it after playback finishes plus a short cooldown, so the input and output paths never contend for the same ALSA hardware device at the same time.
- Wire a shared signal (e.g. `asyncio.Event`) between `app/pipeline/orchestrator_async.py`'s `stt_consumer` (which calls `speak()`) and `audio_producer`, so the producer knows when to stop/start the stream.
- This assumes turn-based interaction (the user is not expected to talk over the agent while it's speaking) — barge-in / interrupting the agent mid-response is explicitly not a goal here.

## Capabilities

### New Capabilities
- `tts-playback-audio-isolation`: While the assistant is speaking (TTS playback), the microphone input stream SHALL NOT be actively capturing, so it cannot overflow from device contention or pick up the assistant's own voice as user speech.

### Modified Capabilities
(none — `openspec/specs/` has no synced capabilities yet; `audio-capture-reliability` from `fix-audio-input-overflow-cpu` is still pending in that change, not yet archived)

## Impact

- Code: `app/audio/input.py` (expose stream start/stop control to the caller), `app/pipeline/orchestrator_async.py` (signal TTS start/end around the `speak()` call).
- No new env vars strictly required, though a small cooldown delay after TTS ends (before resuming capture) may be made configurable to avoid picking up playback tail/room echo.
- Must be verified on **both** ThinkPad and MSI: eliminates/reduces the TTS-adjacent overflow bursts on ThinkPad, and does not introduce dropped user speech or awkward turn-taking delay on either machine (including MSI, where the problem barely manifests today but the mechanism — pausing capture during playback — will still apply there).
- Related to but independent of `fix-audio-input-overflow-cpu`: that change addresses Whisper-CPU-thread contention (still useful, first-utterance capture was clean with it applied); this change addresses a second, TTS-triggered overflow source found during that change's own verification.
- Non-goal: this does not attempt real full-duplex barge-in support, nor does it address the separate "tutor sometimes responds without hearing the user" issue observed on MSI during regression testing — that is out of scope and untracked for now.
