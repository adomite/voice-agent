SESSION_MODES = {
    "pt_practice": {
        "stt_language": "pt",
        "llm_language": "pt",
        "tts_language": "pt",
        "role": "language_tutor",
        "label": "Portuguese practice",
    },
    "es_interview": {
        "stt_language": "es",
        "llm_language": "es",
        "tts_language": "es",
        "role": "job_interviewer",
        "label": "Spanish interview practice",
    },
    "en_interview": {
        "stt_language": "en",
        "llm_language": "en",
        "tts_language": "en",
        "role": "job_interviewer",
        "label": "English interview practice",
    },
}


class SessionContext:
    def __init__(self, mode_name="pt_practice"):
        if mode_name not in SESSION_MODES:
            raise ValueError(
                f"Unknown mode '{mode_name}'. Valid modes: {list(SESSION_MODES.keys())}"
            )

        self.mode_name = mode_name
        self.mode = SESSION_MODES[mode_name]

    @property
    def stt_language(self):
        return self.mode["stt_language"]

    @property
    def llm_language(self):
        return self.mode["llm_language"]

    @property
    def tts_language(self):
        return self.mode["tts_language"]

    @property
    def role(self):
        return self.mode["role"]

    @property
    def label(self):
        return self.mode["label"]