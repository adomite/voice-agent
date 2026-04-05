import asyncio
from app.pipeline.orchestrator_async import run_pipeline


def main():
    # mode_name = "pt_practice"
    # later you can switch to:
    mode_name = "es_interview"
    # mode_name = "en_interview"

    try:
        asyncio.run(run_pipeline(mode_name=mode_name))
    except KeyboardInterrupt:
        print("\n👋 Stopped")


if __name__ == "__main__":
    main()