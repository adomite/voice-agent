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

- Code: `app/stt/segmenter.py` (`WebRTCUtteranceSegmenter`, the chunked-resampling fix), `app/audio/input.py` (settle-window fix, and — the final confirmed fix — `_resolve_channels()` capturing mono directly instead of forcing stereo + downmixing), and `app/pipeline/orchestrator_async.py` (discard-first-utterance backstop, `DEBUG_SAVE_UTTERANCES` diagnostic, and correcting `input_sample_rate` from a hardcoded 16000 to the real capture rate). No changes to `app/stt/audio_utils.py` or `app/stt/vad.py`.
- Machine-specific (ThinkPad only, not code): raw ALSA `Capture` hardware gain was maxed at +30dB, causing clipping and a noise floor loud enough to prevent VAD from ever detecting silence, once the channel-downmix cancellation (which had been masking this) was fixed. Reduced to +15.75dB (`amixer -c 0 sset Capture 70%`) — see design.md Resolution update 3. Needs persisting across reboots (tasks.md 8.6).
- `AUDIO_RESUME_SETTLE_MS` (already introduced by the archived `fix-tts-audio-duplex-overflow`) default raised from 300 to 7000, and now also applied at initial stream open, not just TTS-resume.
- The dominant root cause, found last: `stt_consumer`'s segmenter was constructed with `input_sample_rate=16000` hardcoded, while the ThinkPad's mic captures at 48000 — making resampling a silent no-op for the whole session (audio flowed through mislabeled, playing back ~3x slow/distorted). This predates every other change in this session and plausibly explains a large share of the VAD/hallucination symptoms observed throughout. Confirmed harmless on MSI, whose `AUDIO_SAMPLE_RATE=16000` happened to make the hardcoded value accidentally correct there.
- This is unrelated to and independent of the archived overflow fixes and the in-progress `tune-vad-hallucination-filtering` change — all are separate contributing causes for what looked like one "bad transcription" symptom; see design.md's two Resolution updates for the full chain of findings.
- Verification: primarily on the ThinkPad (where this was found), with a clear-speech A/B comparison (live pipeline transcript vs. direct-file transcript of the same utterance) and direct audio playback of a saved utterance as the acceptance test, plus a quick MSI regression check.
- Non-goal: this does not touch VAD sensitivity or hallucination-phrase filtering (`tune-vad-hallucination-filtering`'s concern) — worth re-evaluating whether that's still needed at the same intensity once this fix is verified, but not assumed here.
