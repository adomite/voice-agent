## Resolution (confirmed root cause, supersedes the analysis below)

Further empirical testing (an isolated diagnostic script opening only the raw `InputStream`, no Whisper/Ollama/TTS at all) showed ALSA input overflow occurring at a steady rate purely from `AUDIO_INPUT_DEVICE=0` (`hw:0,0`, direct ALSA), with zero TTS or duplex activity involved. Switching to `AUDIO_INPUT_DEVICE=default` eliminated overflow completely and unconditionally — including in full pipeline sessions with TTS turns, both with and without this change's stop/start logic active, and both with and without headphones (which also ruled out the acoustic-echo hypothesis below).

**This change's core premise — that TTS/mic duplex contention or acoustic echo caused the overflow — was not correct.** The overflow this change set out to fix is the same overflow already resolved by the `AUDIO_INPUT_DEVICE=default` change in `fix-audio-input-overflow-cpu`. Additionally, the "Whisper hallucinating on near-silent audio right after TTS" symptom that motivated decision on the settle window (`AUDIO_RESUME_SETTLE_MS`) persists even after the real fix, with headphones on, and even before any TTS has occurred in a session — meaning it's a general VAD-sensitivity / Whisper-hallucination issue, not specific to TTS or audio duplex at all. That issue is tracked separately.

The stop/start/mute-window code implemented below is kept in place as a harmless defense-in-depth measure (it correctly scopes itself to only run around TTS and has no observed downside), but it is not necessary for, and was not the mechanism behind, the overflow fix.

## Context (original analysis, see Resolution above)

`app/audio/input.py`'s `audio_producer` opens a single `sounddevice.InputStream` for the whole session lifetime, inside a `with stream: while True: await asyncio.sleep(0.1)` loop. `app/tts/piper_tts.py`'s `speak()` runs synchronously inside `asyncio.to_thread(...)` (called from `stt_consumer` in `app/pipeline/orchestrator_async.py`) and calls `sd.play(audio, samplerate=..., device=output_device)` followed by a blocking `sd.wait()` until playback completes — meaning for the full duration of every TTS response, there are two independent PortAudio streams open at once on the same physical device: the pre-existing input stream and a newly opened output stream.

ThinkPad ground-truth data (from live testing during `fix-audio-input-overflow-cpu` verification, `WHISPER_CPU_THREADS=4`, `AUDIO_LATENCY=high`): the first utterance's capture was overflow-free, but every `[TTS] speaking...` block was immediately followed by 8–17 `[AUDIO STATUS] input overflow` lines, and two hallucinated transcripts appeared ("Subtítulos por la comunidad de Amara.org", "¡Suscríbete!") — both well-known Whisper artifacts on near-silent/noisy input, consistent with the mic picking up faint playback echo rather than real speech. MSI regression data on the same branch/commit: only 1 overflow line across 7 TTS turns in one session — MSI's `docker-compose.yml` sets `PULSE_SERVER`, so audio is routed through PulseAudio, which mixes duplex streams in software; the ThinkPad's `hw:0,0` is a direct ALSA hardware device with no such layer, so concurrent capture+playback contends directly for the hardware.

## Goals / Non-Goals

**Goals:**
- Eliminate the TTS-adjacent overflow bursts on the ThinkPad by never running mic capture and TTS playback concurrently on the same device.
- Reduce/eliminate hallucinated transcripts caused by the mic picking up the assistant's own voice.
- Keep the change minimal: this is a turn-based agent already (segmenter waits for silence to end an utterance, then the whole LLM+TTS turn runs before listening resumes conceptually) — we're making that turn-taking explicit at the audio-hardware level, not building new interaction semantics.

**Non-Goals:**
- Full-duplex barge-in (letting the user interrupt the agent mid-response) — explicitly not supported before or after this change.
- Fixing the separate "tutor sometimes responds without hearing the user" issue observed on MSI — untracked, out of scope here.
- Changing anything about the Whisper-CPU-thread mitigation from `fix-audio-input-overflow-cpu` — that remains a separate, complementary fix.

## Decisions

**1. Pause the `InputStream` (via `stream.stop()` / `stream.start()`) around TTS playback, rather than just discarding audio at the Python callback level.**
The overflow is reported by PortAudio/ALSA at the hardware level — a callback that receives-and-discards audio still requires the input stream to be actively holding the device, which is exactly what appears to conflict with the output stream. Actually stopping the stream releases the input side of the device while `speak()`'s output stream is active, which addresses the contention at its source and also guarantees no self-echo is captured at all during that window (rather than being captured and then discarded).
*Alternative considered*: keep the stream open but drop chunks arriving while a "TTS active" flag is set — rejected as insufficient, since it doesn't address device-level contention (the overflow is generated by the driver, before any Python code runs) and still risks catching an echo tail right at the flag's edges.

**2. Signal via a shared `asyncio.Event` between `stt_consumer` and `audio_producer`, set immediately before `await asyncio.to_thread(speak, ...)` and cleared immediately after it returns, with a short cooldown before resuming capture.**
`asyncio.Event` is the simplest primitive that both coroutines (running in the same event loop, per `asyncio.gather` in `run_pipeline`) can share safely without new dependencies. A cooldown (default ~250ms, overridable via `TTS_COOLDOWN_MS`) absorbs any residual room echo/speaker ringing right after `sd.wait()` returns, before capture resumes.
*Alternative considered*: close and fully reopen the `InputStream` (`sd.InputStream(...)` constructed fresh) instead of stop/start — rejected, `stop()`/`start()` on an existing stream is cheaper and is exactly what PortAudio's API is designed for pause/resume use, avoiding repeated device-open overhead every turn.

**3. Keep this independent from, but compatible with, `fix-audio-input-overflow-cpu`'s env-var knobs.**
`WHISPER_CPU_THREADS`, `AUDIO_LATENCY`, `AUDIO_BLOCKSIZE_MS`, `WHISPER_MODEL` all continue to work unchanged; this change only adds stop/start control flow and one new optional `TTS_COOLDOWN_MS` variable, defaulting to a value that preserves safe behavior (a small nonzero cooldown, not 0, since 0 would reintroduce the echo-tail risk) rather than mimicking "no-op when unset" — there is no valid prior behavior of "capture running during playback" worth preserving as a default.

## Risks / Trade-offs

- [Risk] Stopping/restarting the stream every turn adds a hard "the agent is deaf while speaking" behavior — if a user tries to interrupt or speak over the agent, that speech is dropped entirely → Mitigation: this matches the existing turn-based design (the segmenter already only processes one utterance at a time before the LLM/TTS turn), so no functional capability is being removed; document this clearly as expected behavior, not a regression.
- [Risk] `stream.stop()` on `hw:0,7` (MSI's Docker/PulseAudio path) may behave slightly differently than on `hw:0,0` (ThinkPad direct ALSA) → Mitigation: explicit verification pass required on both machines; MSI already shows minimal overflow today, so the bar for "no regression" is low but still checked.
- [Risk] A too-short cooldown after TTS still catches echo tail; too-long a cooldown makes the agent feel unresponsive after finishing speaking → Mitigation: start with a small default (~250ms) and tune empirically on ThinkPad.
- [Risk] If `stream.stop()`/`start()` throws (e.g. device busy) it could crash the whole pipeline, similar to the Piper `FileNotFoundError` crash observed earlier which took down `asyncio.gather` entirely → Mitigation: wrap the resume call so a transient failure logs and retries rather than propagating and killing `stt_consumer`'s sibling task.
- [Confirmed on first ThinkPad test] `stream.start()` itself produces a brief hardware pop/transient on resume, which the VAD classified as speech and immediately consumed the next turn with a spurious utterance (transcribed as a hallucination, e.g. "¡Suscríbete!", right after `[TTS] done`) — effectively "eating" the user's real next input. Overflow during playback was fully gone, confirming decision 1, but this is a distinct resume-time artifact → Mitigation: added a second, post-resume mute window (`AUDIO_RESUME_SETTLE_MS`, default 300ms) in the audio callback itself, separate from the pre-resume `TTS_COOLDOWN_MS` wait, so captured frames are dropped (not queued) for a short period after `stream.start()` succeeds.
