"""LLM-провайдер для обработки текста через OpenAI."""

from __future__ import annotations

from typing import TYPE_CHECKING

from openai import OpenAI

from app.core.interfaces import LLMProvider

if TYPE_CHECKING:
    from app.core.config_manager import ConfigManager


class OpenAILLMProvider(LLMProvider):
    """Выполняет refinement текста через Chat Completions."""

    def __init__(self, config_manager: ConfigManager, model_name: str) -> None:
        self._config_manager = config_manager
        self._model_name = model_name

    def refine_text(self, raw_text: str, system_prompt: str) -> str:
        if not raw_text.strip():
            return ""

        api_key = self._config_manager.get_secret("OPENAI_API_KEY")
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=self._model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": raw_text},
            ],
            temperature=0.2,
        )
        content = response.choices[0].message.content or ""
        return content.strip()
