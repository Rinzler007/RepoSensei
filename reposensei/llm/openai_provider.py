from reposensei.llm.base import LLMProvider

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None  # type: ignore


class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str, model: str):
        if OpenAI is None:
            raise RuntimeError("openai package not installed. pip install openai")
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def generate(self, system: str, user: str) -> str:
        resp = self.client.responses.create(
            model=self.model,
            input=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return resp.output_text