## ADDED Requirements

### Requirement: No concurrent mic capture during TTS playback
While the assistant's spoken response is playing (`app/tts/piper_tts.py`'s `speak()`), the microphone input stream SHALL be stopped, so it cannot report ALSA input overflow caused by device contention with the output stream, and cannot capture the assistant's own voice as if it were user speech.

#### Scenario: TTS playback produces no input overflow
- **WHEN** the assistant's response is being spoken via TTS on the ThinkPad
- **THEN** no `[AUDIO STATUS] input overflow` is logged for the duration of that playback

#### Scenario: No self-echo transcribed as user speech
- **WHEN** the assistant finishes speaking and capture resumes
- **THEN** the next transcribed utterance corresponds to speech the user actually produced after playback ended, not audio from the assistant's own voice

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
