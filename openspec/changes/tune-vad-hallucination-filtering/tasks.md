## 1. Postprocess filtering (`app/stt/postprocess.py`)

- [ ] 1.1 Add a repetition-loop check: reject transcripts where the most common word accounts for more than a conservative threshold (e.g. ≥50%) of total words, with a minimum repeat count (e.g. ≥4) to avoid false positives on short transcripts.
- [ ] 1.2 Add a small, explicit blocklist of known canned Whisper hallucination phrases (starting with "subtítulos por la comunidad de amara.org" and "¡suscríbete!"/"suscríbete", case-insensitive, matched when they make up the sole/near-sole content of the transcript) and reject exact/near matches.
- [ ] 1.3 Wire both checks into `should_emit_transcript`, alongside the existing short-word filter.

## 2. VAD/segmenter tuning (`app/stt/segmenter.py`)

- [ ] 2.1 Increase `min_speech_frames` from 6 to a higher value (start at 9-10, ~270-300ms) to require a longer sustained speech run before accepting an utterance.
- [ ] 2.2 If 2.1 alone doesn't sufficiently reduce false-positive triggers during testing, evaluate raising `vad_aggressiveness` from 2 to 3 as a fallback.

## 3. Verification — ThinkPad (primary target)

- [ ] 3.1 Run several sessions on the ThinkPad (quiet room and with typical background noise) and confirm hallucinated transcripts ("¡Suscríbete!", "Subtítulos por la comunidad de Amara.org", repetition loops) no longer appear as `[USER]` output.
- [ ] 3.2 Confirm genuine short replies ("sí", "no", "ok") are still captured and transcribed correctly — not accidentally filtered by the tightened `min_speech_frames` or the new postprocess checks.
- [ ] 3.3 Confirm normal-length genuine utterances are unaffected (no new false negatives).

## 4. Verification — MSI (regression check)

- [ ] 4.1 Run a session on the MSI and confirm no regression in transcription of genuine short or long utterances from the tightened VAD/postprocess settings.
