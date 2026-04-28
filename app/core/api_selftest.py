"""Лёгкие проверки доступности API для UI (без блокировки главного потока)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import httpx
from openai import OpenAI

from app.core.provider_credentials import llm_secret_key_name, stt_secret_key_name

if TYPE_CHECKING:
    from app.core.config_manager import AppConfig, ConfigManager

LOGGER = logging.getLogger(__name__)


def test_llm_connection(config_manager: ConfigManager, cfg: AppConfig) -> tuple[bool, str]:
    """Минимальный сетевой вызов к текущему LLM-провайдеру."""
    if not cfg.llm_enabled:
        return False, "LLM выключен в конфиге (llm_enabled=false)"
    mp = cfg.model_provider.lower()
    if mp == "openai":
        key = (config_manager.peek_secret("OPENAI_API_KEY") or "").strip()
        if not key:
            return False, "Не задан OPENAI_API_KEY"
        try:
            client = OpenAI(api_key=key)
            client.chat.completions.create(
                model=cfg.llm_model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=1,
                temperature=0,
            )
            return True, "OpenAI: ответ получен"
        except Exception as exc:  # noqa: BLE001
            LOGGER.debug("test_llm openai", exc_info=True)
            return False, f"OpenAI: {exc}"

    try:
        import litellm

        from app.providers.litellm_llm_provider import _litellm_model_id

        model = _litellm_model_id(mp, cfg.llm_model)
        key_name = llm_secret_key_name(mp)
        kwargs: dict = {
            "model": model,
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 1,
            "temperature": 0,
        }
        if key_name:
            api_key = (config_manager.peek_secret(key_name) or "").strip()
            if not api_key:
                return False, f"Не задан секрет {key_name}"
            kwargs["api_key"] = api_key
        litellm.completion(**kwargs)
        return True, f"LiteLLM ({model}): ответ получен"
    except Exception as exc:  # noqa: BLE001
        LOGGER.debug("test_llm litellm", exc_info=True)
        return False, f"LiteLLM: {exc}"


def test_stt_connection(config_manager: ConfigManager, cfg: AppConfig) -> tuple[bool, str]:
    """Проверка ключа STT без отправки аудио (где API это позволяет)."""
    wb = cfg.whisper_backend.lower()
    if wb == "local":
        return True, "Локальный STT — ключ не нужен"

    if wb == "openai":
        key = (config_manager.peek_secret("OPENAI_API_KEY") or "").strip()
        if not key:
            return False, "Не задан OPENAI_API_KEY"
        try:
            with httpx.Client(timeout=15.0) as client:
                r = client.get(
                    "https://api.openai.com/v1/models",
                    headers={"Authorization": f"Bearer {key}"},
                )
                r.raise_for_status()
            return True, "OpenAI: ключ принят (models)"
        except Exception as exc:  # noqa: BLE001
            return False, f"OpenAI STT: {exc}"

    if wb == "groq":
        key_name = stt_secret_key_name("groq")
        assert key_name
        key = (config_manager.peek_secret(key_name) or "").strip()
        if not key:
            return False, "Не задан GROQ_API_KEY"
        try:
            with httpx.Client(timeout=15.0) as client:
                r = client.get(
                    "https://api.groq.com/openai/v1/models",
                    headers={"Authorization": f"Bearer {key}"},
                )
                r.raise_for_status()
            return True, "Groq: ключ принят (models)"
        except Exception as exc:  # noqa: BLE001
            return False, f"Groq STT: {exc}"

    if wb == "deepgram":
        key_name = stt_secret_key_name("deepgram")
        assert key_name
        key = (config_manager.peek_secret(key_name) or "").strip()
        if not key:
            return False, "Не задан DEEPGRAM_API_KEY"
        try:
            with httpx.Client(timeout=15.0) as client:
                r = client.get(
                    "https://api.deepgram.com/v1/projects",
                    headers={"Authorization": f"Token {key}"},
                )
                r.raise_for_status()
            return True, "Deepgram: ключ принят (GET /v1/projects)"
        except Exception as exc:  # noqa: BLE001
            return False, f"Deepgram STT: {exc}"

    return False, f"Неизвестный whisper_backend: {wb}"
