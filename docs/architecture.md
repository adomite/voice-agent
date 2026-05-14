# voice-agent Architecture

This document describes the components and data flows in your voice-agent setup using:

- A locally installed Ollama model serving an OpenAI-compatible API  
- A Dockerized Python application for audio I/O, transcription, chat, and TTS  
- ElevenLabs for text-to-speech  
- The host’s audio stack (PulseAudio/ALSA)

---

## 1. High-Level Components

1. **Host Environment (Ubuntu 24.04 LTS)**
   - Hardware: MSI Prestige 14 (Intel i7 + RTX 3050 GPU)
   - Audio stack: PulseAudio (user socket at `/run/user/<UID>/pulse/native`) + ALSA (`/dev/snd`)
   - Ollama CLI & daemon installed under `~/.ollama`

2. **Ollama Model Server**
   - Runs on host as a background daemon or manual `ollama serve`
   - Listens on `127.0.0.1:11434` speaking the OpenAI Chat/Completions API  
   - Loads Llama2 (or your chosen) model into GPU/CPU

3. **Docker Container (voice-agent)**
   - Built from `Dockerfile` with:
     - Python 3.11, ffmpeg, portaudio, libsndfile, PulseAudio client
     - `requirements.txt`: Whisper, sounddevice, openai, elevenlabs, etc.
     - Application code (`main.py` + `app/` package)
   - Orchestrated via `docker-compose.yaml` with:
     - `network_mode: host` so container sees host’s loopback & Ollama API  
     - `devices: /dev/snd` for raw audio devices  
     - `volumes: /run/user/<UID>/pulse/native` for PulseAudio socket  
     - Environment vars via `.env`

4. **ElevenLabs TTS**
   - Cloud service for speech synthesis  
   - Accessed via `elevenlabs` Python SDK using `ELEVENLABS_API_KEY` and `ELEVENLABS_VOICE_ID`

---

## 2. Directory & File Layout

voice-agent/
├── ARCHITECTURE.md ← this file
├── Dockerfile ← container build recipe
├── docker-compose.yaml ← Compose spec (host networking, volumes)
├── requirements.txt ← Python deps
├── .env ← runtime configuration (API endpoints & keys)
├── main.py ← entrypoint: orchestrates audio & model calls
└── app/ ─ Python modules (transcription, chat, TTS, audio)

text


---

## 3. Environment Configuration (`.env`)

Place at project root:

Ollama (dummy key since Ollama ignores it)

OPENAI_API_KEY=foo
OPENAI_API_BASE=http://127.0.0.1:11434/v1
ElevenLabs (for TTS)

ELEVENLABS_API_KEY=<your_key>
ELEVENLABS_VOICE_ID=<your_voice_id>

text


---

## 4. Runtime Deployment

1. **Start Ollama server** (host)  
   ```bash
   ollama serve
   # logs: "Listening on 127.0.0.1:11434"

    Launch the voice-agent container (project root)

    bash

    docker compose up --build

        Container builds image, installs Python libs
        Joins host network; inherits /dev/snd + PulseAudio socket

    Interaction
        Container log prints: Listening for audio…
        Speak into laptop mic → Python captures via sounddevice
        Transcribe with Whisper (local) → get text
        Send text to Ollama via OpenAI-compatible endpoint
        Receive chat response text
        Send response to ElevenLabs TTS → get audio bytes
        Play audio via sounddevice on /dev/snd

## 5. Data Flow Sequence


[Microphone]              
     ↓ (capture PCM frames via sounddevice)
[main.py –> Whisper]
     ↓ (transcribed text)
[main.py –> OpenAI client]
     → HTTP POST to http://127.0.0.1:11434/v1/chat/completions
[Ollama daemon loads Llama2, returns response]
     ↓ (response text)
[main.py –> ElevenLabs SDK]
     → HTTP POST to ElevenLabs TTS API
[ElevenLabs returns audio binary]
     ↓ (PCM / WAV)
[main.py –> sounddevice]
     → Play through speakers

## 6. Networking & Permissions

    network_mode: host
    Container shares host’s loopback, so 127.0.0.1:11434 inside = Ollama on host
    Audio devices
        /dev/snd mounted read/write into container
        PulseAudio socket at /run/user/<UID>/pulse/native bind-mounted
        PULSE_SERVER env var inside container points to this socket
    User permissions
        Host user in audio and docker groups
        Container runs as root (default) to access devices; all audio I/O happens with host hardware

## 7. Extensibility
    Swap Ollama for OpenAI by changing .env:
        OPENAI_API_KEY=<real key>
        OPENAI_API_BASE=https://api.openai.com/v1
    Add persistence (e.g. chat history or Pinecone memory) by extending app/ modules and .env
    Use a different TTS engine by replacing the ElevenLabs client