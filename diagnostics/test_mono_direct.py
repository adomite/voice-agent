"""
Diagnostic: records mono directly (channels=1), matching how
app/audio/input.py captures today, and inspects the resulting signal per
0.5s window (mean/rms/peak) -- useful for checking clipping, DC offset, or
an unreasonably high/low noise floor (e.g. VAD never seeing silence because
the noise floor is too loud, or speech being too quiet to transcribe).

Usage (run from repo root, same machine as the mic you're testing):
    source venv/bin/activate
    python diagnostics/test_mono_direct.py
Stay SILENT for the first 2s, then speak "la silla esta rota", then go
silent again.

Reads AUDIO_INPUT_DEVICE / AUDIO_SAMPLE_RATE from the environment (same
variables app/audio/input.py uses), so this works unmodified on both the
ThinkPad (device=default, 48000Hz) and the MSI (device=hw:0,7, 16000Hz).
"""
import os
import time
import wave

import numpy as np
import sounddevice as sd

AUDIO_SAMPLES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audio_samples")
SAMPLERATE = int(os.environ.get("AUDIO_SAMPLE_RATE", 48000))
DURATION_S = 6
DEVICE = os.environ.get("AUDIO_INPUT_DEVICE", "default")

os.makedirs(AUDIO_SAMPLES_DIR, exist_ok=True)

print(f"[INFO] device={DEVICE!r} channels=1 samplerate={SAMPLERATE}")
print("Grabando en 3...")
time.sleep(1)
print("2...")
time.sleep(1)
print("1...")
time.sleep(1)
print(f"Quedate en SILENCIO 2s, despues di 'la silla esta rota', despues silencio de nuevo. ({DURATION_S}s total)")

recording = sd.rec(
    int(DURATION_S * SAMPLERATE),
    samplerate=SAMPLERATE,
    channels=1,
    dtype="float32",
    device=DEVICE,
)
sd.wait()
print("[INFO] grabacion terminada\n")

audio = recording[:, 0]

window_s = 0.5
window = int(SAMPLERATE * window_s)
print("per-0.5s-window: mean(DC) / rms / peak  (float32, full scale = 1.0)")
for i in range(0, len(audio), window):
    seg = audio[i:i + window]
    if len(seg) < window:
        break
    t0 = i / SAMPLERATE
    print(f"  [{t0:4.1f}s] mean={seg.mean():+.5f}  rms={np.sqrt((seg**2).mean()):.5f}  peak={np.max(np.abs(seg)):.5f}")

audio_int16 = (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16)
out_path = os.path.join(AUDIO_SAMPLES_DIR, "mono_direct.wav")
with wave.open(out_path, "wb") as wf:
    wf.setnchannels(1)
    wf.setsampwidth(2)
    wf.setframerate(SAMPLERATE)
    wf.writeframes(audio_int16.tobytes())
print(f"\n[INFO] saved: {out_path}")
