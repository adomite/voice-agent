import os
import time
import numpy as np
import sounddevice as sd
import asyncio


def find_input_device():
    env_device = os.environ.get('AUDIO_INPUT_DEVICE')
    if env_device is not None:
        print(f"[AUDIO] using device from env: {env_device}")
        return env_device
    devices = sd.query_devices()
    for i, dev in enumerate(devices):
        if dev['max_input_channels'] > 0:
            print(f"[AUDIO] found input device: [{i}] {dev['name']}")
            return i
    raise RuntimeError("No input device found")


def _resolve_latency():
    raw = os.environ.get('AUDIO_LATENCY')
    if raw is None:
        return None
    try:
        return float(raw)
    except ValueError:
        return raw  # e.g. 'low' / 'high', passed through to PortAudio


def _resolve_channels(device):
    # Historically this forced 2 channels for string devices (e.g. 'default')
    # and downmixed to mono in the callback via indata.mean(axis=1). That
    # downmix silently attenuates the signal whenever the two mic channels
    # aren't perfectly in-phase (common for laptop dual-mic arrays doing
    # noise cancellation) -- confirmed the 'default' PipeWire device accepts
    # a direct mono InputStream, so request mono up front instead and skip
    # the averaging step entirely.
    try:
        probe = sd.InputStream(device=device, channels=1, dtype="float32")
        probe.close()
        return 1
    except Exception:
        if isinstance(device, str):
            return 2
        return max(1, sd.query_devices(device)['max_input_channels'])


async def audio_producer(queue, tts_active: asyncio.Event, discard_next_utterance: asyncio.Event):
    loop = asyncio.get_event_loop()
    device = find_input_device()

    channels = _resolve_channels(device)
    samplerate = int(os.environ.get('AUDIO_SAMPLE_RATE', 48000))
    blocksize_ms = float(os.environ.get('AUDIO_BLOCKSIZE_MS', 100))
    latency = _resolve_latency()

    mute_until = 0.0

    def callback(indata, frames, time_info, status):
        if status:
            print(f"[AUDIO STATUS] {status}")
        if time.monotonic() < mute_until:
            # Resuming the stream after TTS can produce a brief hardware
            # pop/transient; drop it instead of letting the VAD treat it
            # as speech.
            return
        if queue.qsize() > 10:
            return

        if indata.shape[1] > 1:
            audio = indata.mean(axis=1, keepdims=True)
        else:
            audio = indata.copy()

        def safe_put():
            try:
                queue.put_nowait(audio)
            except asyncio.QueueFull:
                pass

        loop.call_soon_threadsafe(safe_put)

    print(f"[AUDIO] opening stream: device={device} samplerate={samplerate} channels={channels} "
          f"blocksize_ms={blocksize_ms} latency={latency!r}")

    stream_kwargs = dict(
        device=device,
        samplerate=samplerate,
        channels=channels,
        dtype="float32",
        blocksize=int(samplerate * (blocksize_ms / 1000)),
        callback=callback,
    )
    if latency is not None:
        stream_kwargs["latency"] = latency

    stream = sd.InputStream(**stream_kwargs)
    cooldown_s = float(os.environ.get('TTS_COOLDOWN_MS', 250)) / 1000
    # Opening/restarting the stream produces several seconds of clipped,
    # DC-biased audio before it settles (confirmed via direct measurement:
    # peak=32768 and a decaying DC offset for several seconds after open).
    # Even a generous wait (tested up to 7s) still lets through exactly one
    # spurious utterance right at the unmute boundary, regardless of how
    # long we waited beforehand -- so this settle window reduces the
    # problem to "at most one" spurious utterance per resume, and
    # discard_next_utterance (consumed once in stt_consumer) drops that
    # last one deterministically instead of chasing an ever-longer wait.
    settle_s = float(os.environ.get('AUDIO_RESUME_SETTLE_MS', 7000)) / 1000

    with stream:
        print(f"[AUDIO] settling for {settle_s:.1f}s before capture starts...")
        mute_until = time.monotonic() + settle_s
        await asyncio.sleep(settle_s)
        print("🎤 Mic is ON... speak!")
        capturing = True
        discard_next_utterance.set()
        while True:
            if tts_active.is_set() and capturing:
                # Release the device while TTS is playing so capture and
                # playback never contend for the same ALSA hardware.
                stream.stop()
                capturing = False
            elif not tts_active.is_set() and not capturing:
                await asyncio.sleep(cooldown_s)
                if not tts_active.is_set():
                    try:
                        stream.start()
                        capturing = True
                        # Ignore audio for a settle window: restarting the
                        # stream reproduces the same capture-warmup
                        # transient as the initial open.
                        mute_until = time.monotonic() + settle_s
                        discard_next_utterance.set()
                    except Exception as exc:
                        print(f"[AUDIO] failed to resume capture, will retry: {exc}")
            await asyncio.sleep(0.05)