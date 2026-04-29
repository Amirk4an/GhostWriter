"""Имена переменных окружения / секретов для LLM и STT по выбранному провайдеру."""

from __future__ import annotations

from typing import Final

# LLM: провайдер из config.model_provider (нижний регистр) → имя ключа в .env.secrets
LLM_PROVIDER_SECRET_KEYS: Final[dict[str, str]] = {
    "openai": "OPENAI_API_KEY",
    "groq": "GROQ_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "google": "GEMINI_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "mistral": "MISTRAL_API_KEY",
    "cohere": "COHERE_API_KEY",
}

# STT: whisper_backend → секрет (local не требует)
STT_BACKEND_SECRET_KEYS: Final[dict[str, str]] = {
    "openai": "OPENAI_API_KEY",
    "groq": "GROQ_API_KEY",
    "deepgram": "DEEPGRAM_API_KEY",
    "gcp_speech": "GCP_STT_API_KEY",
    "yandex_speech": "YANDEX_API_KEY",
}

# Дополнительные секреты для некоторых STT-бэкендов.
STT_BACKEND_EXTRA_SECRET_KEYS: Final[dict[str, tuple[str, ...]]] = {
    "yandex_speech": ("YANDEX_FOLDER_ID",),
}

ALLOWED_MODEL_PROVIDERS: Final[frozenset[str]] = frozenset(LLM_PROVIDER_SECRET_KEYS) | frozenset({"ollama"})

ALLOWED_WHISPER_BACKENDS: Final[frozenset[str]] = frozenset(
    {"local", "openai", "groq", "deepgram", "gcp_speech", "yandex_speech", "vosk"},
)


def llm_secret_key_name(model_provider: str) -> str | None:
    """Имя секрета для LLM или ``None``, если ключ не обязателен (например ``ollama`` на localhost)."""
    p = (model_provider or "").strip().lower()
    return LLM_PROVIDER_SECRET_KEYS.get(p)


def stt_secret_key_name(whisper_backend: str) -> str | None:
    """Имя секрета для облачного STT или ``None`` для ``local``."""
    b = (whisper_backend or "").strip().lower()
    return STT_BACKEND_SECRET_KEYS.get(b)


def all_known_secret_env_names() -> list[str]:
    """Все поддерживаемые имена секретов для выпадающего списка в UI."""
    names = set(LLM_PROVIDER_SECRET_KEYS.values()) | set(STT_BACKEND_SECRET_KEYS.values())
    for extra_keys in STT_BACKEND_EXTRA_SECRET_KEYS.values():
        names.update(extra_keys)
    return sorted(names)


def iter_needed_secret_names(*, model_provider: str, whisper_backend: str, llm_enabled: bool) -> list[str]:
    """Какие секреты нужны при текущей комбинации провайдеров (для подсказок в дашборде)."""
    names: list[str] = []
    if llm_enabled:
        k = llm_secret_key_name(model_provider)
        if k and k not in names:
            names.append(k)
    k2 = stt_secret_key_name(whisper_backend)
    if k2 and k2 not in names:
        names.append(k2)
    for extra in STT_BACKEND_EXTRA_SECRET_KEYS.get((whisper_backend or "").strip().lower(), ()):
        if extra not in names:
            names.append(extra)
    return names
