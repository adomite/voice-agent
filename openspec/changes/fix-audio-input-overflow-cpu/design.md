## Context

`app/pipeline/orchestrator_async.py` already runs Whisper transcription, the Ollama call, and Piper TTS via `asyncio.to_thread(...)` (see `stt_consumer`). This means the asyncio event loop itself is not literally blocked while Whisper runs — `to_thread` hands the call to a worker thread, and `ctranslate2` (the `faster-whisper` backend) releases the GIL during native inference, so the event loop keeps servicing `audio_producer`'s `call_soon_threadsafe` callbacks normally.

The overflow is therefore not "the main thread is blocked" in the literal sense the initial hypothesis described. Reading `app/audio/input.py` clarifies the actual mechanism: the mic callback runs on a separate OS thread owned by PortAudio/ALSA, entirely outside the event loop, and does minimal work (channel averaging + a non-blocking queue put). An "input overflow" is PortAudio/ALSA reporting that its own hardware ring buffer wasn't drained before the next audio period arrived — i.e. the callback thread itself wasn't scheduled by the OS in time, not that Python-level code inside it was slow.

`faster-whisper`'s `ctranslate2` backend is itself multi-threaded on CPU and by default consumes most/all available logical CPUs for a single `transcribe()` call (`app/stt/whisper.py` does not currently pass `cpu_threads`). On the ThinkPad (i7-8550U, 4 cores / 8 threads), a ~2.3–2.5s Whisper call saturates nearly the entire machine, competing with the OS scheduler for the audio callback thread's timely execution. `hw:0,0` is a *direct* ALSA hardware device (no `dmix` software mixing layer), which has a small hardware buffer and no OS-level elastic buffering to absorb scheduling jitter — unlike the MSI's Docker ALSA passthrough path (`hw:0,7`), which sits behind a layer with more slack, and whose 12-core/16-thread CPU leaves much more headroom even though it also runs Whisper on CPU.

This refines, but does not contradict, the confirmed diagnosis: the CPU-only machine's *combination* of fewer cores and a buffer-less direct ALSA device is what turns Whisper's CPU load into an audible-to-ALSA scheduling problem. It does not reopen the audio-config diagnosis (device/gain/sample-rate) that has already been ruled out empirically.

## Goals / Non-Goals

**Goals:**
- Eliminate ALSA input overflow on the ThinkPad across 5+ consecutive utterances of clear speech, without regressing MSI's current correct behavior.
- Base the fix on the actual concurrency mechanism (CPU core contention between `ctranslate2` worker threads and the ALSA callback thread), not on the literal "blocked main thread" framing, since code inspection shows `asyncio.to_thread` is already in use.
- Make any new buffering/threading knobs environment-overridable (env vars), so ThinkPad-specific tuning cannot silently change MSI's behavior.
- Document, but do not unilaterally decide, the tradeoff of a lighter CPU-only Whisper model profile.

**Non-Goals:**
- Re-diagnosing audio device selection, mic gain, or sample rate — already ruled out empirically.
- Fixing proper-noun transcription accuracy (e.g. "Guan").
- Unifying the Ollama model across both machines.
- Building automatic hardware-profile detection; explicit env-var overrides per machine's `.env` are sufficient given there are exactly two known environments.

## Decisions

**1. Bound `ctranslate2` CPU thread usage in `app/stt/whisper.py` (primary fix).**
Pass an explicit `cpu_threads` value to `WhisperModel(...)`, overridable via an env var (e.g. `WHISPER_CPU_THREADS`), leaving 1–2 logical cores free on the ThinkPad for OS/ALSA scheduling during inference. Default preserves current (unbounded) behavior unless the env var is set, so MSI is unaffected unless explicitly configured.
*Alternative considered*: leave thread count unbounded (status quo) — rejected, this is the likely direct cause of callback-thread starvation on the 4-core ThinkPad.

**2. Increase `sounddevice.InputStream` buffering slack in `app/audio/input.py` (secondary/complementary fix).**
Make `blocksize` and/or PortAudio `latency` configurable via env vars, and evaluate increasing them on the ThinkPad to give the ALSA ring buffer more headroom to absorb brief scheduling delays. Default preserves current values unless overridden.
*Alternative considered*: only increase the Python-side `asyncio.Queue` size (`maxsize=20` in `run_pipeline`) or the callback's drop threshold (`qsize() > 10`) — rejected as insufficient alone, since the reported overflow happens at the ALSA/PortAudio hardware-buffer level, before audio ever reaches the Python queue.

**3. Keep `asyncio.to_thread` for Whisper/Ollama/TTS; do not move to a `ProcessPoolExecutor`.**
`ctranslate2` already releases the GIL during inference, so a thread (not the event loop) is the actual bottleneck resource — moving to process isolation would not free up CPU cores (the same physical cores are still saturated by inference) and would add IPC/serialization overhead for audio arrays for no benefit.
*Alternative considered*: `run_in_executor` with a `ProcessPoolExecutor` — rejected, addresses a problem (GIL contention) that isn't the actual cause here.

**4. Per-environment Whisper model profile — document as an optional complementary lever, not committed by default.**
Introduce an overridable `WHISPER_MODEL` env var (defaulting to `small`, matching current behavior) so the ThinkPad's `.env` can opt into a lighter model (e.g. `base`) if decisions 1–2 alone don't fully meet the acceptance criteria. Tradeoff (documented in README, not decided here): lighter model reduces CPU load and inference time, but may reduce accuracy for non-native/accented speech, which is already a known marginal case.

## Risks / Trade-offs

- [Risk] Bounding `cpu_threads` too aggressively increases Whisper latency further, widening the window the mic buffer must survive → Mitigation: tune empirically on the ThinkPad (start by leaving 1–2 cores free), verify against the 5-utterance acceptance criterion.
- [Risk] Increasing audio buffer/latency adds end-to-end delay between speech and utterance-end detection → Mitigation: keep the increase modest, verify the VAD segmenter's responsiveness is not noticeably degraded.
- [Risk] `InputStream` config changes could behave differently across ThinkPad's direct ALSA device vs MSI's Docker passthrough → Mitigation: env-var overrides default to current behavior; explicit validation pass required on both machines per acceptance criteria before closing.
- [Risk] A lighter CPU-only model profile could reduce transcription accuracy → Mitigation: keep it opt-in and documented as a tradeoff in README, not a default change to MSI or a mandatory part of the fix.

## Migration Plan

1. Add `WHISPER_CPU_THREADS` (and, if needed, `WHISPER_MODEL`) support to `app/stt/whisper.py`, defaulting to current behavior when unset.
2. Add buffering/latency env-var overrides to `app/audio/input.py`, defaulting to current values when unset.
3. Set ThinkPad-specific values in its local `.env` (not committed defaults) and validate: 5+ consecutive clear utterances, no `[AUDIO STATUS]` overflow log, correct transcription.
4. Re-run the same session mode on MSI with its `.env` unchanged and confirm no regression (still no overflow, timing/accuracy consistent with the original baseline in the proposal's comparison table).
5. Rollback path: every new knob defaults to current behavior when unset — reverting is a `.env` edit, not a code revert, unless the default values themselves changed.
6. README documentation work proceeds independently and does not block or wait on steps 1–4.

## Open Questions

- What `cpu_threads` value is actually optimal on the ThinkPad's i7-8550U (4C/8T)? Requires empirical tuning during implementation, not decided here.
- Do decisions 1–2 alone meet the acceptance criteria, or is the decision-4 lighter-model profile actually needed? Tasks should attempt 1–2 first and only reach for decision 4 if verification on the ThinkPad still shows overflow.
- Does the MSI's Docker ALSA passthrough already have enough buffering elasticity that latency/blocksize changes there are a no-op, or could tuning be needed on MSI too if defaults are ever changed? To be confirmed during the MSI validation pass.
