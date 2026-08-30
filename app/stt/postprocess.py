import re

_PUNCTUATION_RE = re.compile(r"[¡!¿?.,;:]")


def _normalize_for_match(text: str) -> str:
    normalized = _PUNCTUATION_RE.sub("", text.strip().lower())
    return " ".join(normalized.split())


# Repeated short phrase (1-5 words) occurring 3+ times in a row, e.g.
# "Chuchu Chuchu Chuchu..." or "¡Vamos a ir! ¡Vamos a ir! ¡Vamos a ir!" --
# a common Whisper failure mode on ambiguous/near-silent audio.
_REPETITION_LOOP_RE = re.compile(r"\b(\w+(?:\s+\w+){0,4})\b(?:\s+\1\b){2,}")

_KNOWN_HALLUCINATION_PHRASES = {
    _normalize_for_match("Subtítulos por la comunidad de Amara.org"),
    _normalize_for_match("¡Suscríbete!"),
    _normalize_for_match("Suscríbete"),
}


def is_repetition_loop(text: str) -> bool:
    """
    Filter transcripts where a short word/phrase repeats several times in a
    row -- Whisper hallucinating on non-speech audio, not real speech.
    """
    return bool(_REPETITION_LOOP_RE.search(_normalize_for_match(text)))


def is_known_hallucination(text: str) -> bool:
    """
    Filter transcripts that are (near-)exactly a known canned phrase Whisper
    hallucinates on ambiguous/silent audio (training-data leakage).
    """
    return _normalize_for_match(text) in _KNOWN_HALLUCINATION_PHRASES


def clean_transcript(text: str) -> str:
    if not text:
        return ""

    text = text.strip()

    # remove obvious empty / tiny outputs
    if len(text) < 2:
        return ""

    # normalize repeated whitespace
    text = " ".join(text.split())

    return text


def is_unstable_short_utterance(text: str) -> bool:
    """
    Filter very short outputs that are often junk for non-native speech.
    Keep this conservative.
    """
    if not text:
        return True

    words = text.split()

    # single very short words are often noise or poor decoding
    if len(words) == 1 and len(words[0]) <= 3:
        return True

    return False


def should_emit_transcript(text: str, last_text: str) -> bool:
    if not text:
        return False

    if text == last_text:
        return False

    if is_unstable_short_utterance(text):
        return False

    if is_repetition_loop(text):
        return False

    if is_known_hallucination(text):
        return False

    return True