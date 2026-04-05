import sounddevice as sd
import asyncio

async def audio_producer(queue):
    loop = asyncio.get_event_loop()

    def callback(indata, frames, time, status):
        if status:
            print(f"[AUDIO STATUS] {status}")
            return

        # avoid blocking callback thread
        if queue.qsize() > 10:
            return
         
        def safe_put():
            try:
                queue.put_nowait(indata.copy())
            except asyncio.QueueFull:
                pass
            # Push audio chunk into async queue
        loop.call_soon_threadsafe(safe_put)

    print("[AUDIO] default device:", sd.default.device)
    print("[AUDIO] opening stream: samplerate=48000, channels=1")
        

    stream = sd.InputStream(
        device=None,
        samplerate=48000,
        channels=1,
        dtype="float32",
        blocksize=4800,  # ~0.1 sec chunks
        callback=callback
    )

    with stream:
        print("🎤 Mic is ON... speak!")
        while True:
            await asyncio.sleep(0.1)