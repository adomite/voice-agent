# tts-playback-audio-isolation Specification

## Purpose
TBD - created by archiving change fix-tts-audio-duplex-overflow. Update Purpose after archive.
## Requirements
### Requirement: No concurrent mic capture during TTS playback
While the assistant's spoken response is playing (`app/tts/piper_tts.py`'s `speak()`), the microphone input stream SHALL be stopped as a defense-in-depth measure against device-level contention with the output stream.

Note: empirical testing (see `fix-audio-input-overflow-cpu`'s design.md Resolution) found that ALSA input overflow on the ThinkPad was actually caused by `AUDIO_INPUT_DEVICE` pointing at a raw `hw:X,Y` device, not by TTS/mic duplex contention — overflow is fully resolved by `AUDIO_INPUT_DEVICE=default` alone, independent of this requirement. This requirement is kept as a harmless secondary safeguard, not as the mechanism that fixes overflow.

#### Scenario: TTS playback produces no input overflow
- **WHEN** the assistant's response is being spoken via TTS
- **THEN** no `[AUDIO STATUS] input overflow` is logged for the duration of that playback

### Requirement: Capture resumes reliably after playback
After TTS playback finishes (plus a short cooldown), the microphone input stream SHALL resume capturing, so the user is not permanently locked out of providing input after the assistant speaks.

#### Scenario: Capture resumes after cooldown
- **WHEN** TTS playback completes
- **THEN** the input stream is capturing again within the configured cooldown window, and subsequent user speech is captured and transcribed normally

### Requirement: No regression on GPU-accelerated environments
Pausing/resuming capture around TTS playback SHALL NOT introduce dropped user speech, broken turn-taking, or new overflow on GPU-accelerated environments (e.g. the MSI) where this specific overflow mechanism was only marginally observed.

#### Scenario: MSI session after the fix
- **WHEN** a full session with multiple TTS turns is run on the MSI after this change
- **THEN** transcription and turn-taking behave at least as well as before the change, with no new overflow or dropped-speech regressions

