Ad-hoc scripts written during audio/VAD/Whisper troubleshooting (ThinkPad
and MSI). Kept in the repo so they're available on both machines and so
past investigations leave a trail — see `openspec/changes/archive/` for the
write-ups these scripts produced evidence for.

Run all of these from the repo root (they import `app.*`):

```bash
source venv/bin/activate   # or the container's environment
python diagnostics/<script>.py
```

- `test_dc_offset.py` / `test_dc_offset_live.py` — inspect a WAV's DC offset, rms, and peak in 0.5s windows (clipping/transient detection). Default input is `audio_samples/check.wav` or `audio_samples/live_utterances/utterance_001.wav`; override with a path argument.
- `test_segmenter_chunked.py` / `test_segmenter_chunked_v2.py` — feed a WAV through `WebRTCUtteranceSegmenter` chunk-by-chunk and transcribe whatever utterances it emits, to compare against a whole-clip transcription.
- `test_vad_raw_counts.py` — raw WebRTC VAD speech/silence frame counts and timeline for a WAV, independent of the segmenter's state machine.
- `test_channel_balance.py` — records live stereo audio and compares per-channel vs. mono-mixdown amplitude (diagnoses channel-cancellation from averaging two out-of-phase mic channels).
- `test_mono_direct.py` — records live mono audio directly and prints per-window amplitude (diagnoses clipping / noise floor / gain-staging issues).

`test_channel_balance.py` and `test_mono_direct.py` read `AUDIO_INPUT_DEVICE`
/ `AUDIO_SAMPLE_RATE` from the environment, same as `app/audio/input.py`, so
they work unmodified on both machines (ThinkPad: `default`/48000Hz, MSI:
`hw:0,7`/16000Hz).

`audio_samples/` holds WAV fixtures these scripts read/write. The folder is
tracked; the `.wav` files inside it are gitignored (voice recordings,
binary, no reason to bloat git history) — copy one in manually if you want
to commit a specific fixture as a reference.
