## Why

During verification of `tune-vad-hallucination-filtering`, deliberate, clearly-spoken ThinkPad test utterances still transcribed as garbage in the live pipeline (e.g. "Vamos a iniciar con la prueba, son hoteles baratos" came out as unrelated nonsense). A direct A/B test isolated the cause: the exact same recorded audio, fed to `transcribe()` as one continuous 6-second clip, produced a perfect transcript (down to the comma). The only difference between that test and the live pipeline is *how the audio reaches Whisper* — this is not a VAD-sensitivity or model-accuracy issue (both already addressed/ruled out), it's audio corruption introduced by the live chunking path itself.

Root cause: `app/stt/segmenter.py`'s `WebRTCUtteranceSegmenter.process_chunk()` calls `downsample_audio()` (FFT-based `scipy.signal.resample`) independently on each ~100ms raw chunk as it arrives from the mic, then concatenates the *already-resampled* per-chunk frames into the final utterance at speech-end. FFT-based resampling assumes a self-contained signal; applying it to small independent windows and stitching the results introduces discontinuities/artifacts at every ~100ms chunk boundary — degrading the audio actually sent to Whisper, even when the raw captured audio and the model itself are both fine.

## What Changes

- Keep the existing per-chunk downsample+VAD-framing path exactly as-is for speech/silence *detection* (VAD doesn't need pristine audio, just enough signal to classify frames).
- Add a parallel, chunk-granular buffer of **raw** (native sample rate, not yet resampled) audio, mirroring the existing frame-based pre-buffer/speech-accumulation state machine.
- At utterance end, build the audio actually sent to Whisper by concatenating the raw chunks (same sample rate throughout, simple contiguous concatenation, no resampling artifacts) and resampling **once**, matching exactly what the isolated A/B test did successfully.

## Capabilities

### New Capabilities
- `utterance-audio-fidelity`: Audio handed from the segmenter to STT SHALL be reconstructed without per-chunk resampling artifacts, such that a clearly-spoken utterance transcribes as accurately through the live pipeline as it does when the same audio is resampled and transcribed as a single continuous clip.

### Modified Capabilities
(none)

## Impact

- Code: `app/stt/segmenter.py` (`WebRTCUtteranceSegmenter`, the chunked-resampling fix), and `app/audio/input.py` (added per the design.md Resolution update — the mute/settle window that turned out to be the dominant fix, see below). No changes to `app/stt/audio_utils.py`, `app/stt/vad.py`, or `app/pipeline/orchestrator_async.py`.
- `AUDIO_RESUME_SETTLE_MS` (already introduced by the archived `fix-tts-audio-duplex-overflow`) default raised from 300 to 4000, and now also applied at initial stream open, not just TTS-resume — see design.md for the measured clipping/DC-offset data behind this.
- This is unrelated to and independent of the archived overflow fixes and the in-progress `tune-vad-hallucination-filtering` change — all are separate root causes for what looked like one "bad transcription" symptom. The chunked-resampling fix (segmenter.py) is a real, kept improvement, but live retesting showed it was not the dominant cause — see design.md's Resolution update for the actual dominant cause (a multi-second capture-warmup transient) and its fix.
- Verification: primarily on the ThinkPad (where this was found), with a clear-speech A/B comparison (live pipeline transcript vs. direct-file transcript of the same utterance) as the acceptance test, plus a quick MSI regression check.
- Non-goal: this does not touch VAD sensitivity or hallucination-phrase filtering (`tune-vad-hallucination-filtering`'s concern) — that remains a separate, still-relevant change for audio that's genuinely ambiguous/silent, as opposed to this bug, which corrupts audio that was never ambiguous in the first place.
