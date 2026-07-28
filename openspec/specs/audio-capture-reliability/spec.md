# audio-capture-reliability Specification

## Purpose
TBD - created by archiving change fix-audio-input-overflow-cpu. Update Purpose after archive.
## Requirements
### Requirement: No ALSA input overflow during sustained speech on CPU-only environments
The audio capture pipeline SHALL sustain at least 5 consecutive utterances of clear speech in the `en_interview` session mode on a CPU-only environment (e.g. the ThinkPad: venv, `hw:0,0`, no GPU) without logging an `[AUDIO STATUS]` input overflow, regardless of per-utterance Whisper inference latency on that machine.

#### Scenario: Five consecutive clear utterances on CPU-only hardware
- **WHEN** a user runs `en_interview` mode on the ThinkPad and speaks 5 or more clear, distinct utterances in sequence, each followed by the assistant's response
- **THEN** no `[AUDIO STATUS]` overflow is logged for any of those utterances, and each utterance produces a non-empty, coherent transcript

### Requirement: No regression on GPU-accelerated environments
The audio capture and Whisper inference configuration changes made to address CPU-only overflow SHALL NOT introduce input overflow or degrade transcription correctness on GPU-accelerated environments (e.g. the MSI: Docker, GPU, `hw:0,7`) where no overflow was previously observed.

#### Scenario: Eight consecutive utterances on GPU hardware after the fix
- **WHEN** a user runs the same session mode on the MSI, using its existing `.env` configuration, and speaks 8 or more consecutive utterances (matching the previously observed baseline)
- **THEN** no `[AUDIO STATUS]` overflow is logged, and transcription remains correct and coherent, consistent with pre-change behavior

### Requirement: Environment-specific tuning must not be hardcoded globally
Any new buffering, CPU-thread-bounding, or model-selection knob introduced to fix CPU-only overflow SHALL be configurable per environment (e.g. via environment variables) and SHALL default to the current pre-change behavior when unset, so that applying a fix on one machine does not silently change behavior on the other.

#### Scenario: Unset override preserves prior behavior
- **WHEN** a new configuration variable (e.g. for CPU thread bounding or audio buffer latency) is left unset in a machine's `.env`
- **THEN** the pipeline behaves identically to how it did before this change was introduced on that machine

