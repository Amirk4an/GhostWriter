"""LLM через LiteLLM (несколько облачных провайдеров одним вызовом)."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

import litellm

from app.core.interfaces import LLMProvider
from app.core.provider_credentials import llm_secret_key_name

if TYPE_CHECKING:
    from app.core.config_manager import ConfigManager

LOGGER = logging.getLogger(__name__)


def _litellm_model_id(model_provider: str, llm_model: str) -> str:
    name = (llm_model or "").strip()
    if "/" in name:
        return name
    p = (model_provider or "").strip().lower()
    if p == "google":
        p = "gemini"
    return f"{p}/{name}"


class LiteLLMLLMProvider(LLMProvider):
    """Chat completion через LiteLLM."""

    def __init__(self, config_manager: ConfigManager, *, model_provider: str, llm_model: str) -> None:
        self._config_manager = config_manager
        self._model_provider = (model_provider or "").strip().lower()
        self._litellm_model = _litellm_model_id(self._model_provider, llm_model)

    def _api_key(self) -> str | None:
        key_name = llm_secret_key_name(self._model_provider)
        if not key_name:
            return None
        v = (self._config_manager.peek_secret(key_name) or "").strip()
        return v or None

    def missing_credential_message(self, config_manager: ConfigManager) -> str:
        """Пустая строка если ключ есть или не требуется; иначе текст для пользователя."""
        key_name = llm_secret_key_name(self._model_provider)
        if not key_name:
            return ""
        if (config_manager.peek_secret(key_name) or "").strip():
            return ""
        path = config_manager.secrets_env_path()
        return f"Нет ключа {key_name}. Задайте его в настройках или в файле {path}"

    def refine_text(self, raw_text: str, system_prompt: str) -> str:
        if not raw_text.strip():
            return ""
        key = self._api_key()
        kwargs: dict[str, Any] = {
            "model": self._litellm_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": raw_text},
            ],
            "temperature": 0.2,
        }
        if key:
            kwargs["api_key"] = key
        response = litellm.completion(**kwargs)
        content = response.choices[0].message.content or ""
        return content.strip()

    def refine_journal_json(self, raw_text: str, system_prompt: str) -> dict[str, Any]:
        if not raw_text.strip():
            return {}
        key = self._api_key()
        base_kwargs: dict[str, Any] = {
            "model": self._litellm_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": raw_text},
            ],
            "temperature": 0.2,
        }
        if key:
            base_kwargs["api_key"] = key

        content = ""
        try:
            response = litellm.completion(**base_kwargs, response_format={"type": "json_object"})
            content = (response.choices[0].message.content or "").strip()
        except Exception:
            LOGGER.warning("LiteLLM journal: response_format json_object не сработал, fallback на текстовый JSON")
            fb_messages = [
                {
                    "role": "system",
                    "content": system_prompt + "\n\nВерни один JSON-объект и только его, без markdown.",
                },
                {"role": "user", "content": raw_text},
            ]
            fb_kwargs = {**base_kwargs, "messages": fb_messages}
            response = litellm.completion(**fb_kwargs)
            content = (response.choices[0].message.content or "").strip()

        try:
            return json.loads(content)
        except json.JSONDecodeError:
            LOGGER.warning("LiteLLM journal: невалидный JSON, пробуем извлечь объект из текста")
            start = content.find("{")
            end = content.rfind("}")
            if start >= 0 and end > start:
                try:
                    return json.loads(content[start : end + 1])
                except json.JSONDecodeError:
                    pass
            raise
