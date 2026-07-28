import os
import sys
import wave

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.stt.segmenter import WebRTCUtteranceSegmenter
from app.stt.whisper import transcribe

AUDIO_SAMPLES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audio_samples")
WAV_PATH = sys.argv[1] if len(sys.argv) > 1 else os.path.join(AUDIO_SAMPLES_DIR, "check.wav")
CHUNK_MS = 100

with wave.open(WAV_PATH, "rb") as wf:
    sr = wf.getframerate()
    n = wf.getnframes()
    raw = wf.readframes(n)

audio_int16 = np.frombuffer(raw, dtype=np.int16)
audio_float32 = (audio_int16.astype(np.float32) / 32768.0).reshape(-1, 1)

chunk_samples = int(sr * CHUNK_MS / 1000)
chunks = [audio_float32[i:i + chunk_samples] for i in range(0, len(audio_float32), chunk_samples)]
print(f"[TEST] sr={sr}, total_samples={len(audio_float32)}, num_chunks={len(chunks)}")

seg = WebRTCUtteranceSegmenter(
    input_sample_rate=sr,
    target_sample_rate=16000,
    frame_ms=30,
    vad_aggressiveness=2,
    start_speech_frames=3,
    end_silence_frames=14,
    pre_speech_frames=6,
    min_speech_frames=9,
)

utterances = []
for i, c in enumerate(chunks):
    if len(c) < chunk_samples:
        continue
    result = seg.process_chunk(c)
    if result is not None:
        print(f"[TEST] utterance completed at chunk {i}, {len(result)} samples")
        utterances.append(result)

print(f"[TEST] total utterances from segmenter: {len(utterances)}")
for i, u in enumerate(utterances):
    text = transcribe(u, "es")
    print(f"[TEST] utterance {i} transcript: {text!r}")
