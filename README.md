## Architecture

The voice agent is a local, multilingual (ES/EN/PT) conversational pipeline for interview practice and language learning:

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

STT, LLM, and TTS are all routed by **session mode** (see below), and past session summaries are loaded into the conversation context via `app/memory/memory_manager.py` so the agent has continuity across runs.

## Session modes

There are 9 session modes, combining language (Portuguese / Spanish / English) with a role (practice tutor / job interviewer / learning assistant). Run one with:

```bash
python main.py <mode_name>
```

| Mode | Language | Role |
|---|---|---|
| `pt_practice` | Portuguese | Language tutor |
| `pt_interview` | Portuguese | Job interviewer |
| `pt_learning` | Portuguese | Learning assistant |
| `es_practice` | Spanish | Language tutor |
| `es_interview` | Spanish | Job interviewer |
| `es_learning` | Spanish | Learning assistant |
| `en_practice` | English | Language tutor |
| `en_interview` | English | Job interviewer |
| `en_learning` | English | Learning assistant |

If no mode is given, it defaults to `pt_practice`.

## Setup

This project is actively developed across two machines with different hardware, and each has its own setup path. **Both must keep working** — a change validated only on one machine is not considered complete.

### ThinkPad (venv, CPU-only)

```bash
cd ~/voice-agent
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Relevant `.env` variables:

```bash
AUDIO_INPUT_DEVICE=default
AUDIO_SAMPLE_RATE=48000
OLLAMA_MODEL=llama3.2:1b
OLLAMA_BASE_URL=http://127.0.0.1:11434/v1
# Optional, CPU tuning (harmless, not required for the overflow fix below):
# WHISPER_CPU_THREADS=6
# AUDIO_BLOCKSIZE_MS=100
# AUDIO_LATENCY=high
```

**Important**: use `AUDIO_INPUT_DEVICE=default`, not a raw `hw:X,Y` string or numeric PortAudio index. On this hardware, `hw:0,0` is direct ALSA access with no software buffering and reliably overflows (confirmed with an isolated capture-only test, independent of Whisper/Ollama/TTS); `default` routes through PipeWire, which fixes it completely. Run `python -c "import sounddevice as sd; print(sd.query_devices())"` to see the device list if you need to confirm the mapping on a given machine.

Before starting a session, confirm Ollama is running:

```bash
curl 127.0.0.1:11434
```

Then run a session:

```bash
python main.py en_interview
```

**Known CPU limitation**: Whisper inference on this machine (4-core i7-8550U, `small` model, int8, CPU) takes roughly 2.1–2.6s per utterance — noticeably slower than the GPU-assisted MSI setup. This is expected and doesn't cause input overflow by itself; overflow was previously caused by using `hw:0,0` (raw ALSA device) for `AUDIO_INPUT_DEVICE` rather than by Whisper's timing — see `openspec/changes/fix-audio-input-overflow-cpu/` for the full diagnosis.

### MSI (Docker, GPU)

Ollama must be running on the **host** (not in the container) before starting the agent:

```bash
ollama serve
```

Then build and run the container:

```bash
cd ~/voice-agent
docker compose up --build
```

Relevant `.env` variables (also set in `docker-compose.yml`):

```bash
AUDIO_INPUT_DEVICE=hw:0,7
AUDIO_SAMPLE_RATE=16000
OLLAMA_MODEL=llama3.2
OLLAMA_BASE_URL=http://127.0.0.1:11434/v1
```

Confirm the model is actually running on GPU:

```bash
ollama ps
```

Run a session mode from inside the running container, or override the compose command, e.g.:

```bash
docker compose run voice-agent python main.py en_interview
```

### Why the two machines use different Ollama models

The ThinkPad runs `llama3.2:1b` on CPU only; the MSI runs the full `llama3.2` with GPU acceleration. This is intentional, not a temporary inconsistency: the smaller model keeps response latency reasonable on CPU-only hardware, while the MSI's GPU can handle the larger model without a latency penalty. There is no plan to unify the two — each machine should use the model appropriate for its hardware.

## Modules

- **`app/audio/input.py`** — captures microphone audio via `sounddevice`, pushes chunks into an `asyncio.Queue` with non-blocking backpressure protection.
- **`app/core/context.py`** — defines the 9 session modes and their language/role routing for STT, LLM, and TTS.
- **`app/stt/audio_utils.py`** — audio flattening/mono conversion, resampling, float32 ↔ int16 conversion, VAD framing.
- **`app/stt/vad.py`** — WebRTC VAD wrapper for frame-level speech/non-speech classification.
- **`app/stt/segmenter.py`** — builds utterances from VAD-positive frames (pre-speech buffer, speech-start confirmation, silence-based end detection).
- **`app/stt/whisper.py`** — local `faster-whisper` integration; language routed dynamically from session mode; deterministic decoding for stable short utterances.
- **`app/stt/postprocess.py`** — cleans transcripts, filters unstable short outputs, avoids duplicate emissions.
- **`app/llm/ollama_client.py`** — talks to a local Ollama server (OpenAI-compatible API) using the mode's system prompt and conversation history.
- **`app/tts/piper_tts.py`** — synthesizes and plays the assistant's spoken response via Piper, voice selected by session language.
- **`app/memory/memory_manager.py`** — persists conversation history and a running user profile (grammar mistakes, vocabulary level, session summaries) as JSON under `MEMORY_DIR`.
- **`app/pipeline/orchestrator_async.py`** — coordinates audio capture, segmentation, transcription, LLM response, and TTS; detects end-of-interview phrases; logs session info and per-stage timings.
- **`main.py`** — entry point; starts the pipeline with the selected session mode.

## Model / runtime choices

- VAD: WebRTC VAD
- STT engine: faster-whisper (`small`, int8, local CPU inference; overridable via `WHISPER_MODEL`)
- LLM: Ollama, model configurable via `OLLAMA_MODEL` per machine
- TTS: Piper, voice selected by session language
- Memory: persistent JSON per session mode + a cross-session user profile
- Orchestration: Python asyncio (`app/pipeline/orchestrator_async.py`)

## Known limitations

- STT accuracy is still imperfect for accented/non-native speech, and occasionally mis-transcribes proper nouns.
- Latency is acceptable for a prototype but not yet fully real-time conversational streaming.
- CPU-only inference (ThinkPad) is meaningfully slower than GPU-assisted inference (MSI); see the setup section above and `openspec/changes/fix-audio-input-overflow-cpu/` for the tradeoffs this creates.
- Output is voice + console; there is no UI yet.

## History / Milestones

### `stt-v1` — First stable local STT baseline

Established the first working offline speech pipeline: microphone capture, async queue-based ingestion, WebRTC VAD, utterance segmentation, multilingual STT routing by session mode, local Whisper transcription, basic transcript cleanup/filtering, console-based observability.

### LLM + memory integration

Added Ollama-based LLM responses routed by session mode (tutor / interviewer / learning assistant across PT/ES/EN, 9 modes total), Piper TTS for spoken responses, and persistent JSON memory (conversation history + cross-session user profile).

### Next milestone

Resolving CPU-only input overflow (see `openspec/changes/fix-audio-input-overflow-cpu/`) and continuing to harden the dual-machine (ThinkPad/MSI) setup.
