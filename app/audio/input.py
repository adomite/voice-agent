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


async def audio_producer(queue, tts_active: asyncio.Event):
    loop = asyncio.get_event_loop()
    device = find_input_device()

    channels = 2 if isinstance(device, str) else max(1, sd.query_devices(device)['max_input_channels'])
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
    # peak=32768 and a large decaying DC offset for ~3-4s after open).
    # 300ms was nowhere near enough; this covers both the very first open
    # and every resume after a TTS pause.
    settle_s = float(os.environ.get('AUDIO_RESUME_SETTLE_MS', 4000)) / 1000

    with stream:
        print(f"[AUDIO] settling for {settle_s:.1f}s before capture starts...")
        mute_until = time.monotonic() + settle_s
        await asyncio.sleep(settle_s)
        print("🎤 Mic is ON... speak!")
        capturing = True
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
                        # Ignore audio for a short settle window: restarting
                        # the stream can produce a hardware pop/transient
                        # that the VAD would otherwise mistake for speech.
                        mute_until = time.monotonic() + settle_s
                    except Exception as exc:
                        print(f"[AUDIO] failed to resume capture, will retry: {exc}")
            await asyncio.sleep(0.05)