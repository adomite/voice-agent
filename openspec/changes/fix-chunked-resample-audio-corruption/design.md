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

## Risks / Trade-offs

- [Risk] Chunk-granularity padding could occasionally include an extra ~100ms of leading/trailing near-silence in the audio sent to Whisper → Mitigation: negligible in practice; Whisper handles brief silence padding far better than mid-utterance artifacts, and this is exactly what the proven-working A/B test's whole-clip approach already tolerated.
- [Risk] Raw chunks accumulate in memory for the duration of an utterance (previously only resampled/frame-sized data was kept) → Mitigation: utterances are short (seconds, not minutes) and chunks are small (~100ms of mono float32 audio); negligible memory impact.
- [Risk] This fix and `tune-vad-hallucination-filtering`'s `min_speech_frames` tuning touch the same file (`segmenter.py`) — could conflict if applied out of order → Mitigation: this change only touches `process_chunk`/`reset`'s audio-reconstruction logic, not the frame-threshold constructor defaults `tune-vad-hallucination-filtering` already changed; verified no line-level overlap.
