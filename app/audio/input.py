import os
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

    def callback(indata, frames, time, status):
        if status:
            print(f"[AUDIO STATUS] {status}")
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

    with stream:
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
                    except Exception as exc:
                        print(f"[AUDIO] failed to resume capture, will retry: {exc}")
            await asyncio.sleep(0.05)