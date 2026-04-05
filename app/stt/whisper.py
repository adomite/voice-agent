from faster_whisper import WhisperModel

# Better quality than base, still manageable on CPU
model = WhisperModel("small", compute_type="int8")


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