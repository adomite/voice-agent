import asyncio
import os
import time
import wave

import numpy as np

from app.audio.input import audio_producer
from app.core.context import SessionContext
from app.stt.segmenter import WebRTCUtteranceSegmenter
from app.stt.whisper import transcribe
from app.stt.postprocess import clean_transcript, should_emit_transcript
from app.llm.ollama_client import get_llm_response
from app.tts.piper_tts import speak

END_PHRASES = {
    "es": ["terminamos", "fin de la entrevista", "hasta luego", "eso es todo"],
    "en": ["end interview", "we are done", "that's all", "goodbye"],
    "pt": ["terminamos", "fim da entrevista", "até logo", "é isso"],
}


def is_end_phrase(text: str, language: str) -> bool:
    text_lower = text.lower().strip()
    return any(phrase in text_lower for phrase in END_PHRASES.get(language, []))


# TEMPORARY diagnostic: set DEBUG_SAVE_UTTERANCES=1 to dump every utterance
# actually sent to Whisper as a WAV file, so it can be listened to directly.
_DEBUG_SAVE_UTTERANCES = os.environ.get("DEBUG_SAVE_UTTERANCES") == "1"
_DEBUG_DIR = os.path.expanduser("~/audio_diag/live_utterances")
_debug_counter = 0


def _debug_save_utterance(utterance_16k):
    global _debug_counter
    if not _DEBUG_SAVE_UTTERANCES:
        return
    os.makedirs(_DEBUG_DIR, exist_ok=True)
    _debug_counter += 1
    path = os.path.join(_DEBUG_DIR, f"utterance_{_debug_counter:03d}.wav")
    audio_int16 = (np.clip(utterance_16k, -1.0, 1.0) * 32767).astype(np.int16)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(audio_int16.tobytes())
    print(f"[DEBUG] saved utterance audio to {path}")


async def stt_consumer(audio_q, session, tts_active, discard_next_utterance):
    segmenter = WebRTCUtteranceSegmenter(
        input_sample_rate=16000,
        target_sample_rate=16000,
        frame_ms=30,
        vad_aggressiveness=2,
        start_speech_frames=3,
        end_silence_frames=14,
        pre_speech_frames=6,
        min_speech_frames=9,
    )

    last_text = ""

    print(f"[SESSION] mode: {session.mode_name}")
    print(f"[SESSION] label: {session.label}")
    print(f"[SESSION] STT language: {session.stt_language}")

    while True:
        chunk = await audio_q.get()
        utterance_16k = segmenter.process_chunk(chunk)

        if utterance_16k is None:
            continue
        if len(utterance_16k) < 8000:
            print("[SKIP] utterance too short")
            continue

        if discard_next_utterance.is_set():
            discard_next_utterance.clear()
            print("[SKIP] discarding first utterance after resume (capture warmup artifact)")
            continue

        _debug_save_utterance(utterance_16k)

        print("[PROCESSING] sending utterance to whisper...")
        t0 = time.perf_counter()
        raw_text = await asyncio.to_thread(
            transcribe, utterance_16k, session.stt_language
        )
        t1 = time.perf_counter()
        print(f"[TIMING] whisper took {t1 - t0:.2f}s")

        text = clean_transcript(raw_text)

        if not should_emit_transcript(text, last_text):
            if text:
                print(f"[FILTERED]: {text}")
            continue

        last_text = text
        print(f"\n[USER]: {text}")
        session.add_user_message(text)

        print("[PROCESSING] sending to Ollama...")
        t2 = time.perf_counter()
        response = await asyncio.to_thread(
            get_llm_response, session.conversation_history
        )
        t3 = time.perf_counter()
        print(f"[TIMING] ollama took {t3 - t2:.2f}s")

        session.add_assistant_message(response)
        print(f"\n[AGENT]: {response}\n")

        tts_active.set()
        try:
            await asyncio.to_thread(speak, response, session.tts_language)
        finally:
            tts_active.clear()

        if is_end_phrase(text, session.stt_language):
            session.close_session(summary=response)
            print("[SESSION] session closed and saved to memory")
            break


async def run_pipeline(mode_name="es_interview"):
    audio_q = asyncio.Queue(maxsize=20)
    session = SessionContext(mode_name=mode_name)
    tts_active = asyncio.Event()
    discard_next_utterance = asyncio.Event()

    await asyncio.gather(
        audio_producer(audio_q, tts_active, discard_next_utterance),
        stt_consumer(audio_q, session, tts_active, discard_next_utterance),
    )