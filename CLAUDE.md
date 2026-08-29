# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A local, multilingual (ES/EN/PT) voice conversation pipeline for interview practice and language learning. Fully offline/local except for the LLM being served by a local Ollama instance. No UI — console + spoken audio only.

```text
Mic Input (sounddevice, async callback)
  -> raw audio queue (asyncio.Queue)
  -> WebRTC VAD + utterance segmenter
  -> faster-whisper STT (local, CPU)
  -> transcript post-processing
  -> Ollama LLM (tutor / interviewer response, mode-aware system prompt)
  -> Piper TTS (spoken response)
  -> persistent memory (conversation history + user profile, JSON)
```

## Running

```bash
python main.py <mode_name>   # defaults to pt_practice if omitted
```

Session modes combine language (`pt`/`es`/`en`) with a role (`practice`/`interview`/`learning`), e.g. `en_interview`, `pt_practice`. All 9 combinations are defined in `app/core/context.py`. Before starting, confirm Ollama is reachable: `curl 127.0.0.1:11434`.

There is no test suite, linter, or build step in this repo — changes are validated by actually running a session and listening/reading the console output (see "Verification" below).

## The two-machine constraint (critical)

This project is developed across two machines with different hardware and **both must keep working** — a fix validated on only one machine is not considered done. This is the single most important constraint when touching audio, timing, or environment config.

- **ThinkPad** — venv, CPU-only, mic `AUDIO_INPUT_DEVICE=default` (routes through PipeWire; raw `hw:0,0` reliably overflows), `AUDIO_SAMPLE_RATE=48000`, `OLLAMA_MODEL=llama3.2:1b`. Whisper inference is ~2.1-2.6s/utterance on CPU — expected, not a bug. Requires a per-boot mic gain fix: `amixer -c 0 sset Capture 70%` (raw ALSA capture defaults to +30dB, which clips speech and stops VAD from ever detecting silence).
- **MSI** — Docker + GPU, mic `AUDIO_INPUT_DEVICE=hw:0,7`, `AUDIO_SAMPLE_RATE=16000`, `OLLAMA_MODEL=llama3.2` (full-size, GPU-accelerated). Ollama runs on the **host**, not in the container, and must be started (`ollama serve`) before `docker compose up --build`. Run mode commands via `docker compose run voice-agent python main.py <mode>`.

The two machines intentionally use different Ollama model sizes — this is permanent, not a TODO to unify. Any new tunable (buffer size, thread count, model choice) must be an environment variable that defaults to current pre-change behavior when unset, so a fix for one machine can't silently change behavior on the other.

## Module map

- `app/audio/input.py` — mic capture via `sounddevice`, pushes chunks into an `asyncio.Queue` with non-blocking backpressure protection.
- `app/core/context.py` — the 9 session modes; language/role routing and system prompts for STT/LLM/TTS.
- `app/stt/audio_utils.py` — mono conversion, resampling, float32 ↔ int16, VAD framing.
- `app/stt/vad.py` — WebRTC VAD wrapper (frame-level speech/non-speech classification).
- `app/stt/segmenter.py` — builds utterances from VAD frames (pre-speech buffer, speech-start confirmation, silence-based end detection). Also holds the raw-audio buffer used to avoid per-chunk resampling artifacts (see design doc below).
- `app/stt/whisper.py` — local `faster-whisper` integration, language routed from session mode, deterministic decoding.
- `app/stt/postprocess.py` — transcript cleanup, filters unstable short outputs, de-dupes emissions.
- `app/llm/ollama_client.py` — talks to local Ollama (OpenAI-compatible API) with the mode's system prompt + history.
- `app/tts/piper_tts.py` — synthesizes + plays the response via Piper, voice selected by session language.
- `app/memory/memory_manager.py` — persists conversation history + cross-session user profile (grammar mistakes, vocab level, summaries) as JSON under `MEMORY_DIR`; past session summaries are re-loaded into context at session start.
- `app/pipeline/orchestrator_async.py` — coordinates capture → segmentation → STT → LLM → TTS, detects end-of-interview phrases, logs per-stage timings.
- `main.py` — entry point.

## Debugging audio issues

Audio bugs in this codebase have historically had chained/compounding root causes (channel downmix, resample timing, hardcoded sample rate, mic gain) that individually looked like the same symptom ("bad transcription" / "VAD hangs" / "input overflow"). **Verify empirically before assuming root cause** — don't fix based on plausible theory alone:

- `DEBUG_SAVE_UTTERANCES` env var dumps utterance audio to disk for direct listening/A-B comparison against the live transcript.
- A/B test: feed the same captured audio to `transcribe()` as one continuous clip vs. through the live chunked pipeline — divergence points at the chunking/resampling path, not VAD sensitivity or model accuracy.
- `openspec/changes/fix-chunked-resample-audio-corruption/design.md` documents the fullest diagnostic chain found so far (per-chunk FFT resample artifacts, stereo-downmix masking a hardcoded-sample-rate bug, ALSA capture gain) — read it before re-diagnosing a "bad transcription" symptom from scratch.

## OpenSpec workflow

This repo uses `openspec` (spec-driven change management) under `openspec/`: `openspec/specs/` holds accepted capability specs, `openspec/changes/` holds in-flight change proposals (`proposal.md`, `design.md`, `tasks.md`), archived under `openspec/changes/archive/`. Repo-specific rules live in `openspec/config.yaml`:

- If a change involves audio or timing, diagnosis tasks must be separated from fix tasks, and no fix should be proposed until root cause is confirmed.
- Every proposal must state explicitly whether it applies to ThinkPad, MSI, or both.

Useful commands: `openspec list`, `openspec show <item-name>`, `openspec validate <item-name>`, `openspec view` (dashboard).

## Environment variables

Key `.env` vars (see README for the full annotated list per machine): `AUDIO_INPUT_DEVICE`, `AUDIO_SAMPLE_RATE`, `OLLAMA_MODEL`, `OLLAMA_BASE_URL`, `MEMORY_DIR`, `PIPER_MODELS_DIR`, optional CPU tuning (`WHISPER_CPU_THREADS`, `AUDIO_BLOCKSIZE_MS`, `AUDIO_LATENCY`), `AUDIO_RESUME_SETTLE_MS`, `DEBUG_SAVE_UTTERANCES`.
