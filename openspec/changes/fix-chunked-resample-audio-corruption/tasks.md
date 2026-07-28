## 1. Segmenter fix (`app/stt/segmenter.py`)

- [x] 1.1 Added `raw_pre_buffer` (bounded deque, default 5 chunks) and `raw_speech_chunks` (list, populated once speech starts), mirroring the existing frame-based `pre_buffer`/speech-accumulation state at chunk granularity.
- [x] 1.2 `process_chunk` keeps the existing per-chunk downsample+VAD-framing path unchanged for speech/silence detection; the resulting frames are no longer used to build the final utterance audio (only for the VAD decision and `speech_frame_count`).
- [x] 1.3 At utterance end, the audio returned to the caller is built by concatenating `raw_speech_chunks` (native sample rate) and calling `downsample_audio` once. Verified mechanically with a synthetic-signal test (mocked VAD): chunked reconstruction preserves signal amplitude/character with no corruption (peak 0.30000001 vs. whole-signal 0.3000001, floating-point-noise-level difference).
- [x] 1.4 `reset()` updated to also clear the new raw buffers.

## 2. Verification — ThinkPad (primary target)

- [ ] 2.1 Repeat the A/B test that found this bug: record a clear utterance, transcribe it directly (single resample) and through the live pipeline; confirm both now match.
- [ ] 2.2 Run a multi-turn live session with clear speech and confirm transcripts are coherent and match what was actually said, not just free of overflow/hallucination-blocklist hits.
- [ ] 2.3 Confirm this doesn't regress the overflow fix or the hallucination filtering from the other two changes (run a normal session end to end).

## 3. Verification — MSI (regression check)

- [ ] 3.1 Run a session on the MSI and confirm transcription quality is at least as good as before this change (no regression from the reconstruction-path change).
