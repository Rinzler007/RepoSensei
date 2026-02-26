import requests
from reposensei.llm.base import LLMProvider


class OllamaProvider(LLMProvider):
    def __init__(self, host: str, model: str):
        self.host = host.rstrip("/")
        self.model = model

    def generate(self, system: str, user: str) -> str:
        url = f"{self.host}/api/chat"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "options": {"temperature": 0.2},
        }
        r = requests.post(url, json=payload, timeout=300)
        r.raise_for_status()
        data = r.json()
        return data["message"]["content"]