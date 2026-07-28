## Why

On the ThinkPad (CPU-only), the audio input stream recurrently overflows starting at the 2nd–3rd utterance of every session, producing empty or garbage transcripts ("you"). The MSI (Docker, GPU) does not exhibit this in 8+ consecutive utterances. Diagnosis is already complete and empirical (see comparison table below): audio device/gain/sample-rate configuration has been ruled out. The leading hypothesis is that Whisper inference on the slower CPU-only machine (2.3–2.5s/utterance vs 1.3–1.6s/utterance on GPU) starves the real-time audio callback thread of CPU cycles on `hw:0,0` (a direct ALSA device with no software buffering/dmix elasticity, unlike the MSI's Docker ALSA passthrough), causing the hardware ring buffer to overflow before the callback drains it.

Separately, the README only documents the `stt-v1` milestone (STT only) and does not reflect the current architecture (STT → LLM → TTS → memory) or the two-machine setup, making it hard for either machine's environment to be reproduced from scratch.

| Metric | ThinkPad (venv, CPU-only) | MSI (Docker, GPU) |
|---|---|---|
| Input overflow | Yes, recurrent from 2nd–3rd utterance | Not observed in 8 consecutive utterances |
| Whisper timing | 2.3–2.5s/utterance | 1.33–1.64s/utterance |
| Transcription | Empty or garbage ("you", filtered) | Correct and coherent |
| Mic / audio config | `hw:0,0`, 48000Hz, direct ALSA | `hw:0,7`, 16000Hz, ALSA passthrough in Docker |
| LLM | Ollama `llama3.2:1b`, CPU | Ollama `llama3.2:latest`, 100% GPU |

Ruled out: wrong audio device (confirmed via `sd.query_devices()`), wrong Ollama model, different Docker audio routing (MSI uses a different mic/sample rate and does not show the problem).

## What Changes

- Investigate and implement concrete options to reduce CPU-scheduling contention between Whisper inference and the real-time audio callback on `app/pipeline/orchestrator_async.py` / `app/stt/whisper.py` / `app/audio/input.py`. Candidates to evaluate (not pre-committed): bounding `faster-whisper`/ctranslate2 CPU thread usage to leave headroom for the audio callback thread, increasing `sounddevice.InputStream` buffering/latency slack to tolerate brief scheduling delays, and confirming the executor isolation already in place (`asyncio.to_thread`) is sufficient or needs to move to a process-isolated executor.
- Evaluate (document, do not unilaterally decide) a per-environment CPU-only Whisper model profile (e.g. `base`/smaller model on ThinkPad vs `small` on MSI) as a complementary or alternative mitigation, with its accuracy/latency tradeoff spelled out.
- Update `README.md` to reflect the current architecture (STT → LLM → TTS → memory, 9 session modes) and document per-machine setup (ThinkPad venv vs MSI Docker), including the CPU-timing limitation and its relation to this fix. This work is independent of the audio fix and must not block or be blocked by it.
- Fix an unrelated but discovered issue: `openspec/config.yaml` had a duplicated/malformed `schema`/`context` block causing the OpenSpec CLI to silently ignore project context; deduplicated so future changes get the intended dual-machine context and rules.

## Capabilities

### New Capabilities
- `audio-capture-reliability`: The audio input pipeline must sustain 5+ consecutive utterances of clear speech without ALSA input overflow, on both the CPU-only (ThinkPad) and GPU (MSI) environments, regardless of Whisper inference latency on that machine.

### Modified Capabilities
(none — no existing specs in `openspec/specs/`)

## Impact

- Code: `app/audio/input.py` (stream/buffer configuration), `app/stt/whisper.py` (model thread/compute configuration), `app/pipeline/orchestrator_async.py` (executor usage), possibly `app/core/context.py` or env/config loading if a per-environment profile is introduced.
- Config: potential new environment variables for CPU-thread limits and/or per-environment Whisper model selection (`.env` on each machine).
- Docs: `README.md` rewritten/extended; no change to `openspec/specs/` beyond the new `audio-capture-reliability` capability.
- Must be verified on **both** ThinkPad and MSI before this change is closed — a ThinkPad-only fix is not sufficient, and MSI's current correct behavior (no overflow, correct transcription) must not regress.
- Non-goals: proper-noun transcription accuracy (e.g. "Guan" mis-transcription) and unifying the Ollama model across machines are explicitly out of scope.
