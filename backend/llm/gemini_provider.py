from backend.llm.base import LLMProvider

try:
    import google.generativeai as genai
except ImportError:
    genai = None  # type: ignore


class GeminiProvider(LLMProvider):
    def __init__(self, api_key: str, model: str):
        if genai is None:
            raise RuntimeError("google-generativeai package not installed. pip install google-generativeai")
        genai.configure(api_key=api_key)
        self._model_name = model

    def generate(self, system: str, user: str) -> str:
        model = genai.GenerativeModel(
            model_name=self._model_name,
            system_instruction=system,
            generation_config={"temperature": 0.2},
        )
        response = model.generate_content(user)
        return response.text
