import webrtcvad


class WebRTCVAD:
    def __init__(self, aggressiveness=2, sample_rate=16000, frame_ms=30):
        """
        aggressiveness:
            0 = least aggressive
            3 = most aggressive
        """
        self.vad = webrtcvad.Vad(aggressiveness)
        self.sample_rate = sample_rate
        self.frame_ms = frame_ms

    def is_speech(self, frame_int16):
        """
        frame_int16: numpy int16 frame of exactly 10/20/30 ms
        """
        return self.vad.is_speech(frame_int16.tobytes(), self.sample_rate)