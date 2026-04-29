"""Лёгкие проверки доступности API для UI (без блокировки главного потока)."""

from __future__ import annotations

import base64
import io
import logging
import wave
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
from openai import OpenAI

from app.core.provider_credentials import llm_secret_key_name, stt_secret_key_name

if TYPE_CHECKING:
    from app.core.config_manager import AppConfig, ConfigManager

LOGGER = logging.getLogger(__name__)


def _build_silence_wav_base64(*, sample_rate: int = 16000, duration_ms: int = 120) -> str:
    """Собирает короткий WAV с тишиной для безопасного selftest STT."""
    frame_count = max(1, int(sample_rate * duration_ms / 1000))
    pcm = b"\x00\x00" * frame_count
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm)
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def _build_silence_pcm16(*, sample_rate: int = 16000, duration_ms: int = 120) -> bytes:
    """Собирает короткий сырой PCM16 (mono) для STT selftest."""
    frame_count = max(1, int(sample_rate * duration_ms / 1000))
    return b"\x00\x00" * frame_count


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
    if wb == "vosk":
        try:
            from app.providers.vosk_transcription_provider import resolve_vosk_model_path

            model_path: Path = resolve_vosk_model_path(cfg)
            return True, f"Vosk: локальная модель найдена ({model_path})"
        except Exception as exc:  # noqa: BLE001
            return False, f"Vosk STT: {exc}"

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

    if wb == "gcp_speech":
        key_name = stt_secret_key_name("gcp_speech")
        assert key_name
        key = (config_manager.peek_secret(key_name) or "").strip()
        if not key:
            return False, "Не задан GCP_STT_API_KEY"
        try:
            payload = {
                "config": {
                    "encoding": "LINEAR16",
                    "sampleRateHertz": 16000,
                    "languageCode": "ru-RU",
                    "model": "latest_short",
                    "enableAutomaticPunctuation": True,
                },
                "audio": {
                    "content": _build_silence_wav_base64(),
                },
            }
            with httpx.Client(timeout=15.0) as client:
                r = client.post(
                    "https://speech.googleapis.com/v1/speech:recognize",
                    params={"key": key},
                    json=payload,
                )
                r.raise_for_status()
            return True, "Google STT: ключ принят (speech:recognize, test silence)"
        except Exception as exc:  # noqa: BLE001
            return False, f"Google STT: {exc}"

    if wb == "yandex_speech":
        key_name = stt_secret_key_name("yandex_speech")
        assert key_name
        key = (config_manager.peek_secret(key_name) or "").strip()
        if not key:
            return False, "Не задан YANDEX_API_KEY"
        folder_id = (config_manager.peek_secret("YANDEX_FOLDER_ID") or "").strip()
        params: dict[str, str] = {
            "lang": "ru-RU",
            "format": "lpcm",
            "sampleRateHertz": "16000",
            "topic": "general",
        }
        if folder_id:
            params["folderId"] = folder_id
        try:
            with httpx.Client(timeout=15.0) as client:
                r = client.post(
                    "https://stt.api.cloud.yandex.net/speech/v1/stt:recognize",
                    params=params,
                    headers={
                        "Authorization": f"Api-Key {key}",
                        "Content-Type": "application/octet-stream",
                    },
                    content=_build_silence_pcm16(),
                )
                r.raise_for_status()
            return True, "Yandex STT: ключ принят (stt:recognize, test silence)"
        except Exception as exc:  # noqa: BLE001
            return False, f"Yandex STT: {exc}"

    return False, f"Неизвестный whisper_backend: {wb}"
