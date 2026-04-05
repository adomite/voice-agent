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
        min_speech_frames=6,
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

        self.pre_buffer = deque(maxlen=pre_speech_frames)
        self.speech_frames = []

        self.speaking = False
        self.speech_run = 0
        self.silence_run = 0
        self.speech_frame_count = 0

    def process_chunk(self, chunk):
        """
        Input:
            mic chunk at 48k float32 mono
        Output:
            None if no utterance completed
            float32 utterance at 16k if utterance completed
        """
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

        completed_utterance = None

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
                    self.speech_frame_count = 0

                    print("[SEGMENTER] speech started")

                    self.speech_frames = list(self.pre_buffer)
                    self.pre_buffer.clear()
                    self.speech_frame_count = len(self.speech_frames)

                continue

            # already speaking
            self.speech_frames.append(frame)

            if speech_now:
                self.silence_run = 0
                self.speech_frame_count += 1
            else:
                self.silence_run += 1

            if self.silence_run >= self.end_silence_frames:
                print("[SEGMENTER] utterance ended")

                if self.speech_frame_count >= self.min_speech_frames:
                    utterance_int16 = np.concatenate(self.speech_frames)
                    completed_utterance = utterance_int16.astype(np.float32) / 32768.0
                else:
                    completed_utterance = None

                self.reset()
                break

        return completed_utterance

    def reset(self):
        self.pre_buffer.clear()
        self.speech_frames = []
        self.speaking = False
        self.speech_run = 0
        self.silence_run = 0
        self.speech_frame_count = 0