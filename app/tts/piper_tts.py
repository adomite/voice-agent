import os
import io
import wave
import numpy as np
import sounddevice as sd
from pathlib import Path
from piper import PiperVoice

MODELS_DIR = Path(os.environ.get("PIPER_MODELS_DIR", "/app/models/piper"))


VOICE_MAP = {
    "es": "es_ES-davefx-medium",
    "en": "en_US-ryan-high",
    "pt": "pt_BR-faber-medium",
}

_voice_cache = {}


def get_voice(language: str) -> PiperVoice:
    if language not in _voice_cache:
        voice_name = VOICE_MAP[language]
        model_path = MODELS_DIR / f"{voice_name}.onnx"
        config_path = MODELS_DIR / f"{voice_name}.onnx.json"
        print(f"[TTS] loading voice: {voice_name}")
        _voice_cache[language] = PiperVoice.load(
            model_path=model_path,
            config_path=config_path,
        )
    return _voice_cache[language]


def speak(text: str, language: str, output_device=None):
    voice = get_voice(language)

    wav_buffer = io.BytesIO()
    with wave.open(wav_buffer, "wb") as wav_file:
        voice.synthesize_wav(text, wav_file)

    wav_buffer.seek(0)
    with wave.open(wav_buffer, "rb") as wav_file:
        sample_rate = wav_file.getframerate()
        n_channels = wav_file.getnchannels()
        frames = wav_file.readframes(wav_file.getnframes())

    audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
    if n_channels > 1:
        audio = audio.reshape(-1, n_channels)
    else:
        audio = audio.reshape(-1, 1)

    print(f"[TTS] speaking ({language}, {sample_rate}Hz)...")
    sd.play(audio, samplerate=sample_rate, device=output_device)
    sd.wait()
    print("[TTS] done")