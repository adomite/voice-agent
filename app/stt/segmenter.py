import numpy as np
from collections import deque

from app.stt.audio_utils import downsample_audio, float32_to_int16, frame_audio
from app.stt.vad import WebRTCVAD


class WebRTCUtteranceSegmenter:
    def __init__(
        self,
        input_sample_rate=48000,
        target_sample_rate=16000,
        frame_ms=30,
        vad_aggressiveness=2,
        start_speech_frames=3,
        end_silence_frames=12,
        pre_speech_frames=6,
        min_speech_frames=9,
        raw_pre_buffer_chunks=5,
    ):
        self.input_sample_rate = input_sample_rate
        self.target_sample_rate = target_sample_rate
        self.frame_ms = frame_ms

        self.vad = WebRTCVAD(
            aggressiveness=vad_aggressiveness,
            sample_rate=target_sample_rate,
            frame_ms=frame_ms,
        )

        self.start_speech_frames = start_speech_frames
        self.end_silence_frames = end_silence_frames
        self.pre_speech_frames = pre_speech_frames
        self.min_speech_frames = min_speech_frames

        # Frame-level state (16k) drives speech/silence detection only.
        self.pre_buffer = deque(maxlen=pre_speech_frames)

        # Raw (native-sample-rate) chunk-level state mirrors the frame-level
        # state above, but holds un-resampled audio. Resampling each ~100ms
        # chunk independently and concatenating the results afterwards
        # introduces artifacts at every chunk boundary; resampling the
        # concatenated raw audio once, at utterance end, avoids that.
        self.raw_pre_buffer = deque(maxlen=raw_pre_buffer_chunks)
        self.raw_speech_chunks = []

        self.speaking = False
        self.speech_run = 0
        self.silence_run = 0
        self.speech_frame_count = 0

    def process_chunk(self, chunk):
        """
        Input:
            mic chunk at native sample rate, float32 mono/stereo
        Output:
            None if no utterance completed
            float32 utterance at target_sample_rate if utterance completed
        """
        was_speaking = self.speaking

        audio_16k = downsample_audio(
            chunk,
            orig_sr=self.input_sample_rate,
            target_sr=self.target_sample_rate,
        )

        audio_int16 = float32_to_int16(audio_16k)

        frames = frame_audio(
            audio_int16,
            sample_rate=self.target_sample_rate,
            frame_ms=self.frame_ms,
        )

        utterance_ended = False

        for frame in frames:
            speech_now = self.vad.is_speech(frame)

            if not self.speaking:
                self.pre_buffer.append(frame)

                if speech_now:
                    self.speech_run += 1
                else:
                    self.speech_run = 0

                if self.speech_run >= self.start_speech_frames:
                    self.speaking = True
                    self.silence_run = 0
                    self.speech_frame_count = len(self.pre_buffer)
                    self.pre_buffer.clear()

                    print("[SEGMENTER] speech started")

                continue

            # already speaking
            self.speech_frame_count += 1

            if speech_now:
                self.silence_run = 0
            else:
                self.silence_run += 1

            if self.silence_run >= self.end_silence_frames:
                print("[SEGMENTER] utterance ended")
                utterance_ended = True
                break

        # Chunk-level raw-audio bookkeeping mirrors the frame-level state
        # machine above, at chunk (not frame) granularity.
        if self.speaking:
            if not was_speaking:
                self.raw_speech_chunks = list(self.raw_pre_buffer) + [chunk]
                self.raw_pre_buffer.clear()
            else:
                self.raw_speech_chunks.append(chunk)
        else:
            self.raw_pre_buffer.append(chunk)

        completed_utterance = None

        if utterance_ended:
            if self.speech_frame_count >= self.min_speech_frames and self.raw_speech_chunks:
                raw_utterance = np.concatenate(self.raw_speech_chunks, axis=0)
                completed_utterance = downsample_audio(
                    raw_utterance,
                    orig_sr=self.input_sample_rate,
                    target_sr=self.target_sample_rate,
                )

            self.reset()

        return completed_utterance

    def reset(self):
        self.pre_buffer.clear()
        self.raw_pre_buffer.clear()
        self.raw_speech_chunks = []
        self.speaking = False
        self.speech_run = 0
        self.silence_run = 0
        self.speech_frame_count = 0
