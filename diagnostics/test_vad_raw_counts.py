import os
import sys
import wave

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.stt.audio_utils import downsample_audio, float32_to_int16, frame_audio
from app.stt.vad import WebRTCVAD

AUDIO_SAMPLES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audio_samples")
WAV_PATH = sys.argv[1] if len(sys.argv) > 1 else os.path.join(AUDIO_SAMPLES_DIR, "check.wav")

with wave.open(WAV_PATH, "rb") as wf:
    sr = wf.getframerate()
    n = wf.getnframes()
    raw = wf.readframes(n)

audio_int16_full = np.frombuffer(raw, dtype=np.int16)
audio_float32_full = audio_int16_full.astype(np.float32) / 32768.0

audio_16k = downsample_audio(audio_float32_full, orig_sr=sr, target_sr=16000)
audio_int16_16k = float32_to_int16(audio_16k)
frames = frame_audio(audio_int16_16k, sample_rate=16000, frame_ms=30)

vad = WebRTCVAD(aggressiveness=3, sample_rate=16000, frame_ms=30)
decisions = [vad.is_speech(f) for f in frames]

print(f"[TEST] total frames: {len(frames)} ({len(frames)*30/1000:.1f}s)")
print(f"[TEST] speech=True count: {sum(decisions)}  speech=False count: {len(decisions)-sum(decisions)}")

timeline = "".join("T" if d else "." for d in decisions)
print("[TEST] timeline (30ms/char):")
print(timeline)

best = cur = 0
for d in decisions:
    if not d:
        cur += 1
        best = max(best, cur)
    else:
        cur = 0
print(f"[TEST] longest consecutive silence run: {best} frames ({best*30}ms)")
