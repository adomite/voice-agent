import asyncio
import sys
from app.pipeline.orchestrator_async import run_pipeline


def main():
    mode_name = sys.argv[1] if len(sys.argv) > 1 else "es_interview"
    print(f"[MAIN] starting mode: {mode_name}")
    try:
        asyncio.run(run_pipeline(mode_name=mode_name))
    except KeyboardInterrupt:
        print("\n👋 Stopped")


if __name__ == "__main__":
    main()