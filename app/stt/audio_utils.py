import numpy as np
from scipy.signal import resample


def flatten_audio(audio_chunk):
    """
    Convert input chunk to mono float32.
    """
    if len(audio_chunk.shape) == 2:
        audio_chunk = audio_chunk.mean(axis=1)

    return audio_chunk.flatten().astype("float32")


def downsample_audio(audio_chunk, orig_sr=48000, target_sr=16000):
    """
    Resample mono audio to target sample rate.
    """
    audio = flatten_audio(audio_chunk)

    if orig_sr == target_sr:
        return audio.astype("float32")

    target_length = int(len(audio) * target_sr / orig_sr)
    resampled = resample(audio, target_length)

    return resampled.astype("float32")


def float32_to_int16(audio):
    """
    Convert float32 [-1, 1] audio to int16 PCM.
    """
    audio = np.clip(audio, -1.0, 1.0)
    return (audio * 32767).astype(np.int16)


def int16_to_float32(audio):
    """
    Convert int16 PCM audio to float32 [-1, 1].
    """
    return (audio.astype(np.float32) / 32768.0).astype(np.float32)


def frame_audio(audio_int16, sample_rate=16000, frame_ms=30):
    """
    Split int16 PCM audio into fixed-size frames for WebRTC VAD.
    WebRTC VAD requires 10, 20, or 30 ms frames.
    """
    samples_per_frame = int(sample_rate * frame_ms / 1000)
    frames = []

    for start in range(0, len(audio_int16), samples_per_frame):
        end = start + samples_per_frame
        frame = audio_int16[start:end]

        if len(frame) == samples_per_frame:
            frames.append(frame)

    return frames