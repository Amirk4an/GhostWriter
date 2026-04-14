"""LLM-провайдер для обработки текста через OpenAI."""

from __future__ import annotations

from openai import OpenAI

from app.core.interfaces import LLMProvider


class OpenAILLMProvider(LLMProvider):
    """Выполняет refinement текста через Chat Completions."""

    def __init__(self, api_key: str, model_name: str) -> None:
        self._client = OpenAI(api_key=api_key)
        self._model_name = model_name

    def refine_text(self, raw_text: str, system_prompt: str) -> str:
        if not raw_text.strip():
            return ""

        response = self._client.chat.completions.create(
            model=self._model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": raw_text},
            ],
            temperature=0.2,
        )
        content = response.choices[0].message.content or ""
        return content.strip()
