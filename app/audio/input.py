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


async def audio_producer(queue):
    loop = asyncio.get_event_loop()
    device = find_input_device()

    channels = 2 if isinstance(device, str) else max(1, sd.query_devices(device)['max_input_channels'])
    samplerate = int(os.environ.get('AUDIO_SAMPLE_RATE', 48000))

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

    print(f"[AUDIO] opening stream: device={device} samplerate={samplerate} channels={channels}")

    stream = sd.InputStream(
        device=device,
        samplerate=samplerate,
        channels=channels,
        dtype="float32",
        blocksize=int(samplerate * 0.1),  # 100ms chunks
        callback=callback
    )

    with stream:
        print("🎤 Mic is ON... speak!")
        while True:
            await asyncio.sleep(0.1)