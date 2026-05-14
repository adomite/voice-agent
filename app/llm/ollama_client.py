import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434/v1")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2")

client = OpenAI(
    api_key="ollama",
    base_url=OLLAMA_BASE_URL,
)


def get_llm_response(conversation_history: list) -> str:
    response = client.chat.completions.create(
        model=OLLAMA_MODEL,
        messages=conversation_history,
    )
    return response.choices[0].message.content