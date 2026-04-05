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

    return True