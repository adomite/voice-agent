import os

from faster_whisper import WhisperModel

# Overridable per environment (e.g. a lighter model on CPU-only machines).
# Defaults preserve prior behavior when unset.
MODEL_NAME = os.environ.get("WHISPER_MODEL", "small")

_model_kwargs = {"compute_type": "int8"}
_cpu_threads = os.environ.get("WHISPER_CPU_THREADS")
if _cpu_threads:
    # Bounds ctranslate2's worker threads so CPU-only machines can leave
    # cores free for the real-time audio callback thread. Unset means
    # ctranslate2's own default (typically all available cores).
    _model_kwargs["cpu_threads"] = int(_cpu_threads)

# Better quality than base, still manageable on CPU
model = WhisperModel(MODEL_NAME, **_model_kwargs)


def transcribe(audio_16k, language):
    segments, info = model.transcribe(
        audio_16k,
        beam_size=1,
        vad_filter=False,                 # external VAD already used
        language=language,                # routed from session mode
        task="transcribe",                # do not translate
        condition_on_previous_text=False, # reduce drift/hallucination between utterances
        temperature=0.0,                  # deterministic decoding
    )

    text_parts = []
    for seg in segments:
        text_parts.append(seg.text)

    return "".join(text_parts).strip()