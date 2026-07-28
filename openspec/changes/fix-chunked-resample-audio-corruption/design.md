## Resolution update (second finding, supersedes chunked-resampling as the primary cause)

The chunked-resampling fix below was implemented and verified mechanically (synthetic-signal test), but a live ThinkPad retest still produced garbled transcripts for clear speech ("aumenta o reduce los pasos de verificación en tiempo real según señales de riesgo" → "La pausa se ha hecho de tu bodcucho"). Further isolated testing found the real cause: measuring the raw captured signal directly (via `wave`/`numpy`, no chunking involved at all) showed **severe, sustained clipping** (peak=32768 in 9 of 12 half-second windows across a 6s recording) and a **large decaying DC offset** (-28857 in the first 0.5s window, only settling to near-zero by ~3s in). A companion test showed WebRTC VAD classifying 193-196 of 200 frames (96%+) as "speech" for this same recording — with or without the chunked-resampling bug, and regardless of `vad_aggressiveness` (2 vs. 3 made almost no difference) — because the clipped/biased signal itself has elevated broadband energy that fools the classifier, not because of any threshold tuning.

This points to a multi-second hardware/driver warm-up transient on stream open — plausible on the `default` (PipeWire) device — that the existing `AUDIO_RESUME_SETTLE_MS` mute window (from the archived `fix-tts-audio-duplex-overflow`, default 300ms) was drastically too short for, and which was **never applied at all** at the very first stream open (only on resume-after-TTS) — explaining why first-utterance-of-session corruption has been a recurring pattern throughout this entire investigation.

The chunked-resampling fix (Decisions 1-3 below) is not wrong or reverted — it's a real, verified improvement and stays in place — but it was not the dominant cause of the observed garbling. See Decision 4 for the actual fix.

## Context

`app/stt/segmenter.py`'s `WebRTCUtteranceSegmenter.process_chunk(chunk)` is called once per raw mic chunk (native sample rate, ~100ms by default) as it arrives from `audio_producer`. Today it immediately calls `downsample_audio()` (`app/stt/audio_utils.py`, backed by `scipy.signal.resample`, an FFT-based resampler) on *that single chunk*, converts to int16, and slices it into 30ms VAD frames. Those already-resampled frames are appended to `self.speech_frames`, and when an utterance ends, `np.concatenate(self.speech_frames)` stitches together many independently-resampled chunks into the final audio sent to Whisper.

Diagnostic evidence: a 6-second clean recording ("Vamos a iniciar con la prueba, son hoteles baratos") was fed to `transcribe()` two ways — (1) resampled once as a whole clip: perfect transcript, exact punctuation; (2) through the live pipeline (same recording session, same hardware, same Whisper call): garbled, unrelated nonsense. Since the audio, the model, and the VAD-based turn-taking logic are all otherwise confirmed working (overflow is fixed, playback of the raw capture sounds clear), the only remaining variable is *how the final audio buffer is assembled* — and per-chunk FFT resampling followed by concatenation is a known way to introduce artifacts at each chunk boundary that a single whole-signal resample does not have.

## Goals / Non-Goals

**Goals:**
- Make the audio sent to Whisper for a completed utterance equivalent (modulo negligible chunk-boundary padding) to resampling that utterance's raw audio once, as the successful A/B test did.
- Keep the existing VAD-based speech/silence detection logic and its frame-level timing (`start_speech_frames`, `end_silence_frames`, `min_speech_frames`, `pre_speech_frames`) unchanged — that state machine isn't broken, only the final audio reconstruction is.
- Minimal, localized change: `app/stt/segmenter.py` only.

**Non-Goals:**
- VAD sensitivity tuning or hallucination-phrase filtering — separate, still-relevant concern (`tune-vad-hallucination-filtering`) for audio that's genuinely ambiguous, as opposed to this bug which corrupts unambiguous audio.
- Changing `downsample_audio()`'s resampling algorithm itself, or switching resamplers — the algorithm is fine when given a whole signal; the bug is calling it repeatedly on small independent windows, not the algorithm's choice.
- Frame-exact precision in the raw-audio buffer's start/end boundaries — chunk-granularity (~100ms) padding around the true utterance boundary is acceptable; Whisper tolerates a bit of leading/trailing silence far better than it tolerates resampling artifacts mid-utterance.

## Decisions

**1. Keep per-chunk downsampling for VAD framing; add a separate, parallel raw-chunk buffer for the audio actually sent to Whisper.**
The per-chunk downsample+frame path stays exactly as-is for feeding WebRTC VAD (a binary speech/non-speech classifier, tolerant of minor resampling imperfections). A new raw-chunk buffer (native sample rate, no resampling) mirrors the existing pre-buffer/speech-accumulation state at chunk granularity instead of frame granularity, and is what gets concatenated and resampled *once* at utterance end.
*Alternative considered*: resample the whole VAD-frame-derived buffer differently (e.g. overlap-add between chunks) — rejected as more complex than necessary; keeping a raw parallel buffer and doing one clean resample at the end is simpler and directly matches the proven-working A/B test methodology.

**2. Track raw pre-roll and speech chunks at chunk granularity, not frame granularity.**
`self.raw_pre_buffer` (a bounded deque of recent raw chunks) and `self.raw_speech_chunks` (a list, populated once speech starts) mirror `self.pre_buffer`/`self.speech_frames`'s role, but operate on whole ~100ms raw chunks instead of 30ms VAD frames — the two granularities don't line up exactly (100ms isn't a clean multiple of 30ms), so exact frame-level alignment between the VAD state machine and the raw buffer isn't attempted.
*Alternative considered*: slice each raw chunk into VAD-frame-aligned sub-segments so the raw buffer exactly matches frame-level speech boundaries — rejected as unnecessary complexity; a little extra (or slightly short) silence padding at chunk boundaries has no meaningful effect on transcription quality, unlike the resampling-artifact bug itself.

**3. `min_speech_frames` and all other VAD timing thresholds stay in frame units, unchanged by this fix.**
This change only replaces *what audio gets reconstructed once the state machine decides an utterance happened* — it doesn't change *when* that decision is made.

**4. (Added per Resolution update) Extend the mute/settle window in `app/audio/input.py` to also cover the initial stream open, and lengthen its duration to match the measured transient (~4s, not 300ms).**
`audio_producer` already had a `mute_until` mechanism (added in the archived `fix-tts-audio-duplex-overflow` to cover TTS-resume pops), but it was never applied when the stream first opens, and its 300ms duration was calibrated for a "hardware pop" hypothesis, not the multi-second clipping/DC-offset transient actually measured. Fix: apply the same `mute_until` window right after `with stream:` opens (before printing "Mic is ON"), and raise the default `AUDIO_RESUME_SETTLE_MS` from 300 to 4000, based on the measured decay (DC offset near-zero by ~3s, clipping absent by ~4-5.5s).
*Alternative considered*: investigate and eliminate the transient at its source (e.g. a different device, or PortAudio stream options that avoid it) — worth pursuing later, but muting it is a much smaller, immediately actionable change, and the transient's exact cause (PipeWire buffer pre-fill? ADC/DC-blocking filter settling?) isn't confirmed.

## Risks / Trade-offs

- [Risk] Chunk-granularity padding could occasionally include an extra ~100ms of leading/trailing near-silence in the audio sent to Whisper → Mitigation: negligible in practice; Whisper handles brief silence padding far better than mid-utterance artifacts, and this is exactly what the proven-working A/B test's whole-clip approach already tolerated.
- [Risk] Raw chunks accumulate in memory for the duration of an utterance (previously only resampled/frame-sized data was kept) → Mitigation: utterances are short (seconds, not minutes) and chunks are small (~100ms of mono float32 audio); negligible memory impact.
- [Risk] This fix and `tune-vad-hallucination-filtering`'s `min_speech_frames` tuning touch the same file (`segmenter.py`) — could conflict if applied out of order → Mitigation: this change only touches `process_chunk`/`reset`'s audio-reconstruction logic, not the frame-threshold constructor defaults `tune-vad-hallucination-filtering` already changed; verified no line-level overlap.
- [Risk] A 4-second mute window at every session start makes the app feel unresponsive if a user starts talking immediately after launch → Mitigation: print an explicit "settling for Ns" message and delay the "Mic is ON" print until after the window, so the UI signal matches actual behavior instead of inviting the user to talk into a dead window.
- [Risk] 4s is an estimate from one recording, not a guaranteed-safe value across all conditions → Mitigation: kept configurable via `AUDIO_RESUME_SETTLE_MS`; verify empirically and adjust if corruption still occurs near the boundary.
- [Risk] The transient's root cause (why `default`/PipeWire produces several seconds of clipped, DC-biased audio on open) is still unconfirmed — muting works around it but doesn't fix it → Mitigation: acceptable for now; worth a follow-up investigation if the mute duration proves unreliable or if it's specific to this one machine.
