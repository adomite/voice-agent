## 0. Actual fix (confirmed root cause, see design.md Resolution)

- [x] 0.1 Isolated diagnostic (`audio_diag.py`, standalone `InputStream` with no Whisper/Ollama/TTS) confirmed overflow is 100% reproducible on `AUDIO_INPUT_DEVICE=0` (`hw:0,0`, direct ALSA) alone — 25 overflow events in 45s with nothing else running.
- [x] 0.2 Same diagnostic with `AUDIO_INPUT_DEVICE=default` (routes through PipeWire): 0 overflow events in 45s (450 chunks). Also confirmed with `AUDIO_INPUT_DEVICE=pipewire`, equivalent result.
- [x] 0.3 Set `AUDIO_INPUT_DEVICE=default` in the ThinkPad's `.env`. This is the actual fix for the original bug — everything in sections 1-4 below is a harmless but non-essential secondary mitigation.

## 1. Housekeeping (already applied during proposal)

- [x] 1.1 Deduplicate the malformed `schema`/`context` block in `openspec/config.yaml` so the OpenSpec CLI stops ignoring project context (was silently failing to parse before this change).

## 2. Whisper CPU-thread bounding (primary fix, `app/stt/whisper.py`)

- [x] 2.1 Add an env-overridable `WHISPER_CPU_THREADS` setting and pass it to `WhisperModel(..., cpu_threads=...)`; when unset, preserve current (unbounded) behavior so MSI is unaffected by default.
- [x] 2.2 (Superseded by 0.3) Tested `WHISPER_CPU_THREADS=4` on the ThinkPad — did not eliminate overflow on its own (see design.md Resolution). Not needed once `AUDIO_INPUT_DEVICE=default` is set, but kept as a harmless, still-available tuning knob.

## 3. Audio stream buffering headroom (`app/audio/input.py`)

- [x] 3.1 Make `blocksize` and PortAudio `latency` configurable via env vars (e.g. `AUDIO_BLOCKSIZE_MS`, `AUDIO_LATENCY`), defaulting to the current hardcoded values (`0.1`s blocksize, PortAudio default latency) when unset.
- [x] 3.2 (Superseded by 0.3) Tested `AUDIO_LATENCY=high` on the ThinkPad — did not eliminate overflow on its own. Not needed once `AUDIO_INPUT_DEVICE=default` is set, but kept as a harmless, still-available tuning knob.

## 4. Per-environment Whisper model profile (only if 2–3 are insufficient)

- [x] 4.1 Add an env-overridable `WHISPER_MODEL` setting (default `small`, matching current behavior) so `app/stt/whisper.py` loads the model name from config instead of the hardcoded `"small"`.
- [x] 4.2 Not needed — task 0.3 (device change) resolved the acceptance criterion without requiring a lighter model.

## 5. Verification — ThinkPad (CPU-only)

- [x] 5.1 Confirmed on the ThinkPad with `AUDIO_INPUT_DEVICE=default`: multiple real sessions (`es_practice`, several turns each), 0 `[AUDIO STATUS]` overflow lines, with and without headphones.
- [x] 5.2 Overflow-driven empty/garbage transcripts are gone. Note: a *separate*, unrelated issue remains — Whisper occasionally hallucinates on ambiguous/quiet audio picked up by an over-sensitive VAD (e.g. "¡Suscríbete!", repeated-token loops), independent of overflow, TTS, or this change's fix. Tracked as a new, separate change (VAD/hallucination tuning).
- [x] 5.3 Whisper timing with the fix: ~2.1–2.6s/utterance, consistent with the original 2.3–2.5s baseline — confirms timing was never the lever that mattered; the device change is what fixed overflow, not CPU/timing tuning.

## 6. Verification — MSI (GPU, regression check)

- [x] 6.1 Ran `pt_practice` on the MSI with its `.env` unchanged (branch rebuilt via `docker compose up --build`): 1 overflow line across 7 TTS turns in one session — consistent with the original near-zero baseline, no regression from this change's env-var additions (all default to prior behavior when unset).
- [x] 6.2 Transcription and timing on MSI remained correct and consistent with baseline (Whisper 0.79–1.00s/utterance, even faster than the original 1.33–1.64s baseline). MSI does not need `AUDIO_INPUT_DEVICE=default` — it was never on a raw `hw:X,Y` device (`hw:0,7` via Docker/PulseAudio passthrough already provides buffering).

## 7. README update — architecture (independent of audio fix)

- [x] 7.1 Replace the STT-only architecture diagram/section with the current pipeline: STT → LLM (Ollama) → TTS (Piper) → persistent memory.
- [x] 7.2 List all 9 session modes and the exact command to run each (`python main.py <mode_name>`).
- [x] 7.3 Update the "Modules introduced" section to include `app/llm/ollama_client.py`, `app/tts/piper_tts.py`, and the memory module, alongside the existing STT modules.

## 8. README update — per-machine setup (independent of audio fix)

- [x] 8.1 Document ThinkPad setup: venv creation/activation, relevant `.env` variables (`AUDIO_INPUT_DEVICE`, `AUDIO_SAMPLE_RATE`, `OLLAMA_MODEL=llama3.2:1b`, and the new knobs from tasks 2–4 if applicable), how to confirm Ollama is running (`curl 127.0.0.1:11434`), and the known CPU-timing limitation with a pointer to this change's fix.
- [x] 8.2 Document MSI setup: starting Ollama on the host before `docker compose run`, relevant `.env` variables (`AUDIO_INPUT_DEVICE=hw:0,7`, `OLLAMA_MODEL=llama3.2`), and how to confirm GPU usage (`ollama ps`).
- [x] 8.3 Add an explicit note that the two machines may require different Ollama models (lightweight on CPU vs full model with GPU) and why, without implying either machine should be unified onto one model.
