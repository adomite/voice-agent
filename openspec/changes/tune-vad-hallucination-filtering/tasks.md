## 1. Postprocess filtering (`app/stt/postprocess.py`)

- [x] 1.1 Added as a phrase-repetition check (`is_repetition_loop`, regex-based: a 1-5 word phrase repeating 3+ times consecutively) rather than pure single-word dominance — generalizes to catch observed multi-word loops too (e.g. "¡Vamos a ir!" x5), which a single-word-only check would have missed. Verified in isolation against all 5 real hallucination transcripts from the ThinkPad logs plus genuine longer phrases (see commit).
- [x] 1.2 Added `is_known_hallucination` with a small normalized blocklist ("subtítulos por la comunidad de amara.org", "¡suscríbete!"/"suscríbete"). Verified against the real logged hallucinations.
- [x] 1.3 Wired both into `should_emit_transcript`, alongside the existing short-word filter.

## 2. VAD/segmenter tuning (`app/stt/segmenter.py`)

- [x] 2.1 Increased `min_speech_frames` from 6 to 9 (~270ms) in both the class default (`segmenter.py`) and the call site (`orchestrator_async.py`'s `stt_consumer`, which passes it explicitly).
- [ ] 2.2 If 2.1 alone doesn't sufficiently reduce false-positive triggers during testing, evaluate raising `vad_aggressiveness` from 2 to 3 as a fallback.

## 3. Verification — ThinkPad (primary target)

- [ ] 3.1 Run several sessions on the ThinkPad (quiet room and with typical background noise) and confirm hallucinated transcripts ("¡Suscríbete!", "Subtítulos por la comunidad de Amara.org", repetition loops) no longer appear as `[USER]` output.
- [ ] 3.2 **Found during implementation, not yet resolved**: "sí"/"no"/"ok" are rejected by the pre-existing `is_unstable_short_utterance` filter (any single word ≤3 chars), unrelated to and unaffected by this change's new filters — this was already true before this change, so it's not a regression, but it means the spec's "genuine short utterances are preserved" scenario doesn't hold for single-word replies this short. Verify longer short replies (e.g. "claro", "vale") aren't affected instead, and decide separately whether to loosen the short-word filter (out of this change's original scope).
- [ ] 3.3 Confirm normal-length genuine utterances are unaffected (no new false negatives).

## 4. Verification — MSI (regression check)

- [ ] 4.1 Run a session on the MSI and confirm no regression in transcription of genuine short or long utterances from the tightened VAD/postprocess settings.
