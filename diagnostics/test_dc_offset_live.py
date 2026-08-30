import os
import sys
import wave

import numpy as np

AUDIO_SAMPLES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audio_samples")
WAV_PATH = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    AUDIO_SAMPLES_DIR, "live_utterances", "utterance_001.wav"
)

with wave.open(WAV_PATH, "rb") as wf:
    sr = wf.getframerate()
    n = wf.getnframes()
    raw = wf.readframes(n)

audio = np.frombuffer(raw, dtype=np.int16).astype(np.float64)
print(f"[TEST] total duration: {len(audio)/sr:.2f}s, sr={sr}")

print(f"[TEST] whole clip: mean(DC offset)={audio.mean():.1f}  rms={np.sqrt((audio**2).mean()):.1f}  peak={int(np.abs(audio).max())}")

window_s = 0.5
window = int(sr * window_s)
print(f"[TEST] per-{window_s}s-window: mean(DC) / rms / peak")
for i in range(0, len(audio), window):
    seg = audio[i:i+window]
    if len(seg) < window:
        break
    t0 = i / sr
    print(f"  [{t0:4.1f}s] mean={seg.mean():8.1f}  rms={np.sqrt((seg**2).mean()):8.1f}  peak={int(np.abs(seg).max()):6d}")
