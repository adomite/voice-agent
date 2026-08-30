## 1. Postprocess filtering (`app/stt/postprocess.py`)

- [x] 1.1 Added as a phrase-repetition check (`is_repetition_loop`, regex-based: a 1-5 word phrase repeating 3+ times consecutively) rather than pure single-word dominance — generalizes to catch observed multi-word loops too (e.g. "¡Vamos a ir!" x5), which a single-word-only check would have missed. Verified in isolation against all 5 real hallucination transcripts from the ThinkPad logs plus genuine longer phrases (see commit).
- [x] 1.2 Added `is_known_hallucination` with a small normalized blocklist ("subtítulos por la comunidad de amara.org", "¡suscríbete!"/"suscríbete"). Verified against the real logged hallucinations.
- [x] 1.3 Wired both into `should_emit_transcript`, alongside the existing short-word filter.

## 2. VAD/segmenter tuning (`app/stt/segmenter.py`)

- [x] 2.1 Increased `min_speech_frames` from 6 to 9 (~270ms) in both the class default (`segmenter.py`) and the call site (`orchestrator_async.py`'s `stt_consumer`, which passes it explicitly).
- [x] 2.2 Not needed: `min_speech_frames=9` alone was sufficient across both the ThinkPad (`fix-chunked-resample-audio-corruption` round-4 test) and MSI (regression test) live sessions — no false-positive floods observed at `vad_aggressiveness=2`. No need to raise it.

## 3. Verification — ThinkPad (primary target)

- [x] 3.1 Confirmed via the live ThinkPad session run during `fix-chunked-resample-audio-corruption`'s verification (`es_practice`, 2026-07-28): `[FILTERED]: ¡Suscríbete!` appeared twice and was correctly withheld from `[USER]` output.
- [x] 3.2 Confirmed via dedicated ThinkPad test (2026-07-28, `es_practice`): said "claro" and it reached `[USER]: claro` correctly — not rejected. The `is_unstable_short_utterance` filter only rejects words ≤3 chars ("sí"/"no"/"ok"), which "claro"/"vale" (5+ chars) don't hit; that ≤3-char behavior is pre-existing and out of this change's scope, as noted above. The scenario as scoped for this change (5+ char short replies) holds.
- [x] 3.3 Confirmed via the same session: genuine utterances ("La silla está rota.", "Necesito comprar una mesa.", "para una olla si hoy no cocino.") all reached `[USER]` output correctly — no new false negatives.

## 4. Verification — MSI (regression check)

- [x] 4.1 Confirmed via the MSI regression session run during `fix-chunked-resample-audio-corruption`'s verification (`pt_practice`, 2026-07-28): `[FILTERED]: Oi.` was correctly caught, while genuine short and long Portuguese utterances ("Conjuga o verbo ser.", "Você pode conjugar ou ver você?", etc.) all reached `[USER]` output correctly.
