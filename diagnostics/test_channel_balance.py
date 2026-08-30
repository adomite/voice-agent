"""
Diagnostic: records raw stereo audio the way app/audio/input.py used to
(2 channels, downmixed to mono via mean(axis=1)), then compares:
  - each channel's rms/peak independently
  - the mono mixdown (mean of both channels)

If the mono mixdown's rms/peak is much lower than either individual
channel's, the two mic channels are partially cancelling each other on
mean(axis=1) -- this is what caused live-captured utterances to be much
quieter than an independent single-channel recording of the same speech on
the ThinkPad (see openspec/changes/archive/2026-07-28-fix-chunked-resample-audio-corruption).

Usage (run from repo root, same machine as the mic you're testing):
    source venv/bin/activate
    python diagnostics/test_channel_balance.py
Speak clearly (e.g. "la silla esta rota") when prompted.

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
CHANNELS = 2
DURATION_S = 4
DEVICE = os.environ.get("AUDIO_INPUT_DEVICE", "default")

os.makedirs(AUDIO_SAMPLES_DIR, exist_ok=True)

print(f"[INFO] device={DEVICE!r} samplerate={SAMPLERATE} channels={CHANNELS}")
print("Grabando en 3...")
time.sleep(1)
print("2...")
time.sleep(1)
print("1...")
time.sleep(1)
print(f"HABLA AHORA (grabando {DURATION_S}s)... di algo como 'la silla esta rota'")

recording = sd.rec(
    int(DURATION_S * SAMPLERATE),
    samplerate=SAMPLERATE,
    channels=CHANNELS,
    dtype="float32",
    device=DEVICE,
)
sd.wait()
print("[INFO] grabacion terminada")

left = recording[:, 0]
right = recording[:, 1]
mono_mixdown = recording.mean(axis=1)  # matches the old app/audio/input.py downmix


def stats(name, sig):
    rms = float(np.sqrt(np.mean(sig.astype(np.float64) ** 2)))
    peak = float(np.max(np.abs(sig)))
    print(f"  {name:16s} rms={rms:.5f}  peak={peak:.5f}")


print("\n=== Amplitude comparison ===")
stats("left channel", left)
stats("right channel", right)
stats("mono mixdown", mono_mixdown)

corr = float(np.corrcoef(left, right)[0, 1])
print(f"\n  correlation(left, right) = {corr:.4f}  (near -1 = near-antiphase -> cancellation on averaging)")


def save_wav(path, sig):
    audio_int16 = (np.clip(sig, -1.0, 1.0) * 32767).astype(np.int16)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLERATE)
        wf.writeframes(audio_int16.tobytes())


save_wav(os.path.join(AUDIO_SAMPLES_DIR, "chan_left.wav"), left)
save_wav(os.path.join(AUDIO_SAMPLES_DIR, "chan_right.wav"), right)
save_wav(os.path.join(AUDIO_SAMPLES_DIR, "chan_mono_mixdown.wav"), mono_mixdown)
print(f"\n[INFO] saved to {AUDIO_SAMPLES_DIR}/: chan_left.wav, chan_right.wav, chan_mono_mixdown.wav")
