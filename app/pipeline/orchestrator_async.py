import asyncio
import time

from app.audio.input import audio_producer
from app.core.context import SessionContext
from app.stt.segmenter import WebRTCUtteranceSegmenter
from app.stt.whisper import transcribe
from app.stt.postprocess import clean_transcript, should_emit_transcript


async def stt_consumer(audio_q, session):
    segmenter = WebRTCUtteranceSegmenter(
        input_sample_rate=48000,
        target_sample_rate=16000,
        frame_ms=30,
        vad_aggressiveness=2,
        start_speech_frames=3,
        end_silence_frames=14,
        pre_speech_frames=6,
        min_speech_frames=6,
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

        print("[PROCESSING] sending utterance to whisper...")

        t0 = time.perf_counter()
        raw_text = await asyncio.to_thread(
            transcribe,
            utterance_16k,
            session.stt_language,
        )
        t1 = time.perf_counter()

        print(f"[TIMING] whisper took {t1 - t0:.2f}s")

        text = clean_transcript(raw_text)

        if should_emit_transcript(text, last_text):
            print(f"\n[USER]: {text}")
            last_text = text
        else:
            if text:
                print(f"[FILTERED]: {text}")


async def run_pipeline(mode_name="en_interview"):
    audio_q = asyncio.Queue(maxsize=20)
    session = SessionContext(mode_name=mode_name)

    await asyncio.gather(
        audio_producer(audio_q),
        stt_consumer(audio_q, session),
    )