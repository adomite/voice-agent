import json
import os
from pathlib import Path
from datetime import datetime

MEMORY_DIR = Path(os.environ.get("MEMORY_DIR", "/app/memory_data"))


def _ensure_dir():
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)


def _history_path(mode_name: str) -> Path:
    return MEMORY_DIR / f"history_{mode_name}.json"


def _profile_path() -> Path:
    return MEMORY_DIR / "user_profile.json"


def load_conversation_history(mode_name: str) -> list:
    path = _history_path(mode_name)
    if path.exists():
        with open(path, "r") as f:
            return json.load(f)
    return []


def save_conversation_history(mode_name: str, history: list):
    _ensure_dir()
    path = _history_path(mode_name)
    with open(path, "w") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def load_user_profile() -> dict:
    path = _profile_path()
    if path.exists():
        with open(path, "r") as f:
            return json.load(f)
    return {
        "created_at": datetime.now().isoformat(),
        "sessions": [],
        "grammar_mistakes": {},
        "vocabulary_level": {},
        "strengths": [],
        "areas_for_improvement": [],
    }


def save_user_profile(profile: dict):
    _ensure_dir()
    path = _profile_path()
    with open(path, "w") as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)


def record_session(mode_name: str, summary: str, language: str):
    profile = load_user_profile()
    profile["sessions"].append({
        "date": datetime.now().isoformat(),
        "mode": mode_name,
        "language": language,
        "summary": summary,
    })
    save_user_profile(profile)


def get_profile_context(language: str) -> str:
    profile = load_user_profile()
    sessions = [s for s in profile["sessions"] if s["language"] == language]
    if not sessions:
        return ""
    recent = sessions[-3:]
    context = f"Previous sessions ({len(sessions)} total). Recent summaries:\n"
    for s in recent:
        context += f"- {s['date'][:10]}: {s['summary']}\n"
    return context