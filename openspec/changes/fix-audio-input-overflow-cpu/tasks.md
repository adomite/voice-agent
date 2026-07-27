## 1. Housekeeping (already applied during proposal)

- [x] 1.1 Deduplicate the malformed `schema`/`context` block in `openspec/config.yaml` so the OpenSpec CLI stops ignoring project context (was silently failing to parse before this change).

## 2. Whisper CPU-thread bounding (primary fix, `app/stt/whisper.py`)

- [x] 2.1 Add an env-overridable `WHISPER_CPU_THREADS` setting and pass it to `WhisperModel(..., cpu_threads=...)`; when unset, preserve current (unbounded) behavior so MSI is unaffected by default.
- [ ] 2.2 On the ThinkPad, set `WHISPER_CPU_THREADS` in its local `.env` to a value that leaves 1–2 logical cores free (starting point: 6 of 8 logical threads on the i7-8550U), and measure whether `[AUDIO STATUS]` overflow still occurs.

## 3. Audio stream buffering headroom (`app/audio/input.py`)

- [x] 3.1 Make `blocksize` and PortAudio `latency` configurable via env vars (e.g. `AUDIO_BLOCKSIZE_MS`, `AUDIO_LATENCY`), defaulting to the current hardcoded values (`0.1`s blocksize, PortAudio default latency) when unset.
- [ ] 3.2 On the ThinkPad, try an increased latency/blocksize setting via `.env` and re-test alongside task 2.2 to see whether it's needed in addition to CPU-thread bounding.

## 4. Per-environment Whisper model profile (only if 2–3 are insufficient)

- [x] 4.1 Add an env-overridable `WHISPER_MODEL` setting (default `small`, matching current behavior) so `app/stt/whisper.py` loads the model name from config instead of the hardcoded `"small"`.
- [ ] 4.2 Only if tasks 2–3 do not meet the 5-consecutive-utterance acceptance criterion on the ThinkPad: evaluate a lighter model (e.g. `base`) in its `.env`, and document the accuracy/latency tradeoff observed.

## 5. Verification — ThinkPad (CPU-only)

- [ ] 5.1 Run `python main.py en_interview` on the ThinkPad and speak 5+ consecutive clear utterances; confirm no `[AUDIO STATUS]` overflow is logged for any of them.
- [ ] 5.2 Confirm each of those utterances produces a non-empty, coherent transcript (not filtered as "you"/garbage).
- [ ] 5.3 Record the Whisper timing per utterance after the fix, for comparison against the pre-fix 2.3–2.5s baseline.

## 6. Verification — MSI (GPU, regression check)

- [ ] 6.1 Run the same session mode on the MSI with its existing `.env` unchanged; confirm 8+ consecutive utterances still show no `[AUDIO STATUS]` overflow.
- [ ] 6.2 Confirm transcription remains correct and coherent, consistent with the pre-change baseline (no accuracy or latency regression from any default-behavior change made in tasks 2–4).

## 7. README update — architecture (independent of audio fix)

- [x] 7.1 Replace the STT-only architecture diagram/section with the current pipeline: STT → LLM (Ollama) → TTS (Piper) → persistent memory.
- [x] 7.2 List all 9 session modes and the exact command to run each (`python main.py <mode_name>`).
- [x] 7.3 Update the "Modules introduced" section to include `app/llm/ollama_client.py`, `app/tts/piper_tts.py`, and the memory module, alongside the existing STT modules.

## 8. README update — per-machine setup (independent of audio fix)

- [x] 8.1 Document ThinkPad setup: venv creation/activation, relevant `.env` variables (`AUDIO_INPUT_DEVICE`, `AUDIO_SAMPLE_RATE`, `OLLAMA_MODEL=llama3.2:1b`, and the new knobs from tasks 2–4 if applicable), how to confirm Ollama is running (`curl 127.0.0.1:11434`), and the known CPU-timing limitation with a pointer to this change's fix.
- [x] 8.2 Document MSI setup: starting Ollama on the host before `docker compose run`, relevant `.env` variables (`AUDIO_INPUT_DEVICE=hw:0,7`, `OLLAMA_MODEL=llama3.2`), and how to confirm GPU usage (`ollama ps`).
- [x] 8.3 Add an explicit note that the two machines may require different Ollama models (lightweight on CPU vs full model with GPU) and why, without implying either machine should be unified onto one model.
