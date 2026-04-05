## History / Milestones

### **`stt-v1` — First stable local STT baseline**
This milestone establishes the first working offline speech pipeline for the voice agent.

#### **Scope**
Implemented a local, CPU-based speech-to-text pipeline with:
- microphone capture
- async queue-based ingestion
- WebRTC VAD
- utterance segmentation
- multilingual STT routing by session mode
- local Whisper transcription
- basic transcript cleanup/filtering
- console-based observability

#### **Architecture**
```text
Mic Input (sounddevice, async callback)
  -> raw audio queue
  -> WebRTC VAD + utterance segmenter
  -> faster-whisper STT
  -> transcript post-processing
  -> console output
```

#### **Modules introduced** 
##### app/audio/input.py

Captures microphone audio using sounddevice
Pushes chunks into an asyncio.Queue
Uses non-blocking callback logic with backpressure protection
app/core/context.py

Defines session modes:
pt_practice
es_interview
en_interview
Provides language routing for STT, and later for LLM/TTS
app/stt/audio_utils.py

Audio flattening / mono conversion
Resampling from 48 kHz to 16 kHz
Float32 ↔ int16 PCM conversion
Audio framing for WebRTC VAD
app/stt/vad.py

WebRTC VAD wrapper
Frame-level speech / non-speech classification
app/stt/segmenter.py

Builds utterances from VAD-positive frames
Includes:
pre-speech buffer
speech start confirmation
silence-based end-of-utterance detection
app/stt/whisper.py

Local faster-whisper integration
Language passed dynamically from session mode
Deterministic decoding settings for more stable short utterances
app/stt/postprocess.py

Cleans transcripts
Filters unstable short outputs
Avoids duplicate emissions
app/pipeline/orchestrator_async.py

Coordinates audio capture, segmentation, and transcription
Logs session info and Whisper timings
app/main.py

Entry point
Starts the pipeline with the selected session mode
Session modes
STT routing is mode-aware:

pt_practice → Portuguese (pt)
es_interview → Spanish (es)
en_interview → English (en)
This prevents Whisper from relying purely on auto-detection and improves stability for targeted language practice.

Model / runtime choices
VAD: WebRTC VAD
STT engine: faster-whisper
Whisper model: small
Compute type: int8
Execution: local CPU inference
Orchestration: Python asyncio
Observability added
session mode logging
speech start / utterance end logs
Whisper inference timing per utterance
Results at this stage
Local transcription is functioning end-to-end
English and Spanish interview prompts can be transcribed with usable quality
Portuguese / Spanish / English routing works
STT is accurate enough to continue building the rest of the voice agent
Remaining errors are mostly related to non-native pronunciation, short utterances, and local CPU-model limits
Known limitations
STT accuracy is still imperfect for accented / non-native speech
Latency is acceptable for a prototype, but not yet fully real-time conversational streaming
No LLM integration yet
No TTS integration yet
Output is currently console-only
Why this checkpoint matters
stt-v1 is the first stable foundation for the full local voice agent.

It proves that:

microphone ingestion works
speech segmentation works
multilingual STT routing works
local transcription is usable enough to move on to the next layer
Next milestone
Phase 2: STT → LLM

integrate Ollama
route prompts by session mode
generate tutor / interviewer responses
keep TTS for a later phase