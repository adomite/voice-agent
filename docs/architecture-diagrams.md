# Voice Agent — Architecture & Sequence Diagrams

Grounded directly in the current code (`app/`, `main.py`, `docker-compose.yaml`, `dockerfile`, `CLAUDE.md`) as of 2026-08-30.

> **Note on stale docs:** `docs/architecture.md` and `.env.example` describe an older version of this project (ElevenLabs cloud TTS, raw OpenAI Whisper, `OPENAI_API_BASE`, Llama2). The current code path uses **Piper TTS** (`app/tts/piper_tts.py`), **faster-whisper** (`app/stt/whisper.py`), and talks to **Ollama** via `OLLAMA_BASE_URL` / `OLLAMA_MODEL` (`app/llm/ollama_client.py`). The diagrams below reflect the code as it actually runs today, not those older docs.

> **Reading order:** sections 1–3 are the high-level "where does this run and what leaves the machine" view. Sections 4–6 are the detailed per-utterance and per-machine views.

---

## 1. Network Boundary & Deployment Locality (high-level)

"Docker" here is **a container on your own laptop**, not a remote host and not a cloud VM. There is **no external server** in the runtime path. `docker-compose.yaml` uses `network_mode: "host"`, so the container shares the laptop's own network stack — `127.0.0.1` inside the container *is* the host's `127.0.0.1`. That is the entire reason the container can reach an Ollama daemon that runs **on the host, outside the container**.

```mermaid
flowchart TB
    Internet(["🌐 Internet<br/>contacted at build / first-run ONLY<br/>never during a conversation"])

    subgraph MACHINE["One physical machine — ThinkPad (venv) OR MSI (Docker) — no network egress at runtime"]
        direction TB
        Mic["🎙️ Mic"]
        Speaker["🔊 Speakers"]

        subgraph APP["voice-agent process<br/>(Python venv on ThinkPad / Docker container, network_mode host, on MSI)"]
            Pipe["capture → VAD → faster-whisper → LLM call → Piper TTS → memory"]
        end

        Ollama["Ollama daemon<br/>runs on the HOST, not in the container<br/>listens on 127.0.0.1:11434"]
        Disk[("Conversation memory<br/>local JSON files under MEMORY_DIR")]

        Mic -->|"host sound card /dev/snd"| APP
        APP -->|"synthesized speech"| Speaker
        APP -->|"HTTP POST /v1/chat/completions<br/>loopback only, via host network"| Ollama
        Ollama -->|"response text"| APP
        APP -.->|"on session close"| Disk
    end

    Internet -.->|"pip install (PyPI)"| APP
    Internet -.->|"Piper voices + Whisper 'small' model (huggingface.co)"| APP

    style Internet stroke-dasharray: 5 5
```

> **The `.env` file is misleading — those keys are dead weight.** `OPENAI_API_KEY=foo`, `OPENAI_API_BASE`, `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID` are all leftovers from the old design. The `openai` package *is* installed, but `app/llm/ollama_client.py` uses it only as a generic OpenAI-compatible HTTP client with `api_key="ollama"` hardcoded and `base_url` pointed at local Ollama — it never calls `api.openai.com`. `elevenlabs` is in `requirements.txt` but is **not imported anywhere** in `app/`; TTS is entirely local Piper. No credential in `.env` authenticates to any external service during a session.

---

## 2. Runtime Data Flow — per conversation turn (high-level)

Every stage runs locally. The only inter-process hop is a loopback HTTP call to Ollama on the same machine.

```mermaid
flowchart LR
    A["🎙️ Mic capture<br/>sounddevice"] -->|local| B["VAD + segmentation<br/>webrtcvad"]
    B -->|local| C["STT<br/>faster-whisper<br/>small, int8, CPU"]
    C -->|local| D["LLM<br/>ollama_client.py"]
    D -->|"localhost HTTP<br/>127.0.0.1:11434"| DA["Ollama daemon<br/>(host)"]
    DA -->|"response text"| D
    D -->|local| E["TTS<br/>Piper, local .onnx voice"]
    E -->|local| F["🔊 Speakers"]
    D -.->|"session-close phrase detected"| G[("memory_data/*.json<br/>history + user_profile")]
```

| Stage | Runs where | Leaves the machine? |
|---|---|---|
| Mic capture (`app/audio/input.py`, `sounddevice`) | app → host sound card (`/dev/snd`) | No |
| VAD + utterance segmentation (`app/stt/vad.py`, `segmenter.py`) | app, CPU | No |
| STT — `faster-whisper` `small` int8 (`app/stt/whisper.py`) | app, CPU on **both** machines | No — model already on local disk |
| LLM — `app/llm/ollama_client.py` | HTTP POST to `127.0.0.1:11434/v1` → Ollama daemon on host | No — loopback only |
| TTS — Piper `.onnx` voices (`app/tts/piper_tts.py`) | app, local model files | No |
| Memory — `app/memory/memory_manager.py` | writes `history_<mode>.json` + `user_profile.json` under `MEMORY_DIR` | No — local file (bind-mounted to the project dir on MSI) |

Your voice audio, transcripts, and conversation history never leave the laptop. On MSI they land in `./memory_data/` via the `./memory_data:/app/memory_data` bind mount (that directory is currently owned by `root` because the container created it).

---

## 3. Build-time vs Runtime network access

The internet is required **only** to build the image and to fetch models the first time. After that, a session works fully offline.

```mermaid
flowchart LR
    subgraph BUILD["Build / first run — network REQUIRED"]
        direction TB
        P["PyPI<br/>pip install -r requirements.txt"]
        H1["huggingface.co<br/>Piper voices en/es/pt<br/>(wget in dockerfile — MSI image)"]
        H2["huggingface.co<br/>faster-whisper 'small' model<br/>downloaded on first WhisperModel load,<br/>then cached in ~/.cache/huggingface"]
    end
    subgraph RUN["Every session afterwards — fully offline"]
        R["mic → STT → Ollama (loopback) → Piper → JSON"]
    end
    BUILD ==>|"models on local disk"| RUN
```

| When | What it fetches | Where from | Notes |
|---|---|---|---|
| `docker compose up --build` | Python dependencies | PyPI | `dockerfile` `pip install` step |
| `docker compose up --build` | Piper voice models (`en_US-ryan-high`, `es_ES-davefx-medium`, `pt_BR-faber-medium`) | `huggingface.co/rhasspy/piper-voices` | `wget` in `dockerfile`; baked into the MSI image. On ThinkPad these are provisioned manually under `PIPER_MODELS_DIR`. |
| First `WhisperModel("small")` load | faster-whisper `small` int8 weights | HuggingFace Hub | Happens on first *run*, not build; cached afterwards. Applies to both machines. |
| Every session after that | nothing | — | Pull the network cable and it still works. |

---

## 4. Pipeline Sequence Diagram (shared — identical code path on both machines)

The per-utterance call sequence in `app/pipeline/orchestrator_async.py` is the same on both machines; only environment values differ (see the parameter table below). This is one diagram covering both deployments.

```mermaid
sequenceDiagram
    participant Mic as Microphone
    participant Producer as audio_producer
    participant Queue as asyncio.Queue
    participant Seg as WebRTCUtteranceSegmenter
    participant VAD as WebRTCVAD
    participant STT as stt_consumer (orchestrator)
    participant Whisper as faster-whisper
    participant Post as postprocess
    participant Session as SessionContext
    participant LLM as Ollama (OpenAI-compatible API)
    participant TTS as Piper TTS
    participant Speaker as Speakers
    participant Mem as memory_manager

    loop capture (sounddevice callback thread)
        Mic->>Producer: PCM float32 frames
        Producer->>Queue: put_nowait(chunk) — dropped if qsize > 10
    end

    loop per queued chunk
        Queue-->>STT: await queue.get()
        STT->>Seg: process_chunk(chunk)
        Seg->>Seg: downsample_audio (native rate to 16k)
        Seg->>VAD: is_speech(frame) per 30ms frame
        VAD-->>Seg: speech / silence
        Note over Seg: after start_speech_frames of speech,<br/>marks utterance start,<br/>after end_silence_frames of silence, ends it.<br/>Raw audio is buffered and resampled once<br/>at utterance end (avoids per-chunk resample artifacts).
        Seg-->>STT: utterance_16k, or None if not yet complete
    end

    alt utterance too short or post-TTS warmup discard
        STT-->>STT: skip utterance
    else utterance accepted
        STT->>Whisper: transcribe(utterance_16k, language) [asyncio.to_thread]
        Whisper-->>STT: raw_text
        STT->>Post: clean_transcript / should_emit_transcript
        alt filtered (empty, duplicate, or unstable short output)
            Post-->>STT: reject
        else accepted
            Post-->>STT: text
            STT->>Session: add_user_message(text)
            STT->>LLM: chat.completions.create(conversation_history) [asyncio.to_thread]
            LLM-->>STT: response text
            STT->>Session: add_assistant_message(response)
            STT->>Producer: tts_active.set()
            Note over Producer: stream.stop() releases the mic device<br/>during playback — capture and playback<br/>never contend for the same hardware.
            STT->>TTS: speak(response, language)
            TTS->>Speaker: play synthesized audio
            TTS-->>STT: done
            STT->>Producer: tts_active.clear()
            Note over Producer: after a cooldown, stream.start() plus a<br/>settle window. discard_next_utterance flags<br/>the next chunk to be dropped (capture-warmup transient).
            opt end-of-session phrase detected
                STT->>Session: close_session(summary=response)
                Session->>Mem: save_conversation_history(history)
                Session->>Mem: record_session(summary)
                Mem-->>Session: history_MODE.json and user_profile.json written
            end
        end
    end
```

### Per-machine parameters (same code, different environment)

| Parameter | ThinkPad | MSI |
|---|---|---|
| `AUDIO_INPUT_DEVICE` | `default` (via PipeWire) | `hw:0,7` (raw ALSA) |
| `AUDIO_SAMPLE_RATE` | `48000` | `16000` |
| `OLLAMA_MODEL` | `llama3.2:1b` | `llama3.2` (full size, GPU) |
| Whisper compute | CPU, ~2.1–2.6s/utterance | CPU (no GPU passed to container) |
| Deployment | Python venv, direct on host | Docker container, `network_mode: host` |

---

## 5. ThinkPad Architecture

CPU-only, no Docker — the Python process runs directly on the host under PipeWire.

```mermaid
flowchart TB
    Mic["🎙️ Laptop mic<br/>(dual-array)"]
    Speaker["🔊 Speakers"]

    subgraph HOST["ThinkPad Host — Ubuntu, CPU-only"]
        PipeWire["PipeWire audio server<br/>device: 'default'"]

        subgraph VENV["Python venv process (main.py)"]
            Producer["audio_producer<br/>sounddevice InputStream<br/>AUDIO_SAMPLE_RATE=48000"]
            Queue["asyncio.Queue<br/>maxsize 20, non-blocking"]
            Segmenter["WebRTCUtteranceSegmenter<br/>downsample 48k to 16k + VAD"]
            Whisper["faster-whisper<br/>model=small, int8, CPU<br/>~2.1-2.6s/utterance"]
            OllamaClient["ollama_client.py<br/>OpenAI-compatible client"]
            Piper["Piper TTS<br/>PIPER_MODELS_DIR (local disk)"]
            MemMgr["memory_manager"]
        end

        OllamaHost["Ollama daemon (host)<br/>OLLAMA_MODEL=llama3.2:1b<br/>127.0.0.1:11434, CPU"]
        MemDisk[("MEMORY_DIR<br/>local JSON files")]
    end

    Mic --> PipeWire --> Producer
    Producer -->|float32 chunks| Queue
    Queue -->|await get| Segmenter
    Segmenter -->|utterance_16k| Whisper
    Whisper -->|transcript| OllamaClient
    OllamaClient -->|HTTP POST /v1/chat/completions| OllamaHost
    OllamaHost -->|response text| OllamaClient
    OllamaClient -->|response| Piper
    Piper --> PipeWire --> Speaker
    OllamaClient -.->|on session close| MemMgr
    MemMgr --> MemDisk
```

**ThinkPad-specific note:** raw ALSA capture gain defaults to +30dB, which clips speech and stops VAD from ever detecting silence. Requires a per-boot fix: `amixer -c 0 sset Capture 70%`. Not represented as a pipeline node above since it's a one-time host setup step, not part of the runtime data flow.

---

## 6. MSI Architecture

Docker container + GPU host. Ollama runs on the **host**, not in the container.

```mermaid
flowchart TB
    Mic["🎙️ Mic<br/>ALSA hw:0,7"]
    Speaker["🔊 Speakers"]

    subgraph HOST["MSI Prestige 14 Host — Ubuntu, Intel i7 + RTX 3050 GPU"]
        ALSA["/dev/snd (ALSA)"]
        PulseSocket["PulseAudio user socket<br/>/run/user/1000/pulse/native"]
        OllamaHost["Ollama daemon (host)<br/>OLLAMA_MODEL=llama3.2, GPU-accelerated<br/>127.0.0.1:11434<br/>started manually: 'ollama serve'<br/>before 'docker compose up'"]
        MemDisk[("./memory_data<br/>bind-mounted JSON")]

        subgraph CONTAINER["Docker container: voice-agent<br/>network_mode: host"]
            Producer["audio_producer<br/>AUDIO_INPUT_DEVICE=hw:0,7<br/>AUDIO_SAMPLE_RATE=16000"]
            Queue["asyncio.Queue<br/>maxsize 20, non-blocking"]
            Segmenter["WebRTCUtteranceSegmenter<br/>VAD at native 16k (no resample needed)"]
            Whisper["faster-whisper<br/>model=small, int8, CPU<br/>(no GPU passthrough to container)"]
            OllamaClient["ollama_client.py<br/>OpenAI-compatible client"]
            Piper["Piper TTS<br/>voice models baked into image<br/>(downloaded at 'docker build')"]
            MemMgr["memory_manager"]
        end
    end

    Mic --> ALSA -->|device passthrough| Producer
    Producer -->|float32 chunks| Queue
    Queue -->|await get| Segmenter
    Segmenter -->|utterance_16k| Whisper
    Whisper -->|transcript| OllamaClient
    OllamaClient -->|HTTP POST /v1/chat/completions<br/>via host network| OllamaHost
    OllamaHost -->|response text| OllamaClient
    OllamaClient -->|response| Piper
    Piper --> PulseSocket --> Speaker
    OllamaClient -.->|on session close| MemMgr
    MemMgr --> MemDisk
```

**MSI-specific note:** the container gets no GPU device reservation in `docker-compose.yaml` — only `/dev/snd` is passed through. The GPU acceleration applies to the host's Ollama daemon only; `faster-whisper` inside the container still runs on CPU, same as on the ThinkPad.

---

## Structural assumptions made

- `app/core/context.py` currently defines `SessionContext` twice (the file has two full class definitions back-to-back); Python resolves this to the second, later definition, which is the one shown feeding into memory load/save above. This looks like leftover duplication in the source, not an intentional two-phase design — flagging here rather than silently picking one without comment.
- The `.env` / `.env.example` files in the repo still reference the old ElevenLabs/OpenAI-direct integration and don't reflect `OLLAMA_BASE_URL`, `OLLAMA_MODEL`, `AUDIO_INPUT_DEVICE`, etc. that the code actually reads — those variable names and their per-machine values are taken from `CLAUDE.md` and `docker-compose.yaml` instead.
