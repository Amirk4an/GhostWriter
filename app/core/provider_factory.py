"""Фабрика провайдеров транскрипции и LLM."""

from __future__ import annotations

from app.core.config_manager import AppConfig, ConfigManager
from app.core.interfaces import LLMProvider, TranscriptionProvider


class ProviderFactory:
    """Создает провайдеры в зависимости от конфигурации."""

    def __init__(self, config_manager: ConfigManager) -> None:
        self._config_manager = config_manager

    def create_transcription_provider(self, config: AppConfig) -> TranscriptionProvider:
        if config.whisper_backend == "local":
            from app.providers.faster_whisper_provider import FasterWhisperProvider

            return FasterWhisperProvider(model_name=config.local_whisper_model)
        if config.whisper_backend == "openai":
            from app.providers.openai_whisper_provider import OpenAIWhisperProvider

            api_key = self._config_manager.get_secret("OPENAI_API_KEY")
            return OpenAIWhisperProvider(api_key=api_key, model_name=config.whisper_model)
        raise RuntimeError(f"Неподдерживаемый whisper_backend: {config.whisper_backend}")

    def create_llm_provider(self, config: AppConfig) -> LLMProvider | None:
        if not config.llm_enabled:
            return None
        if config.model_provider == "openai":
            from app.providers.openai_llm_provider import OpenAILLMProvider

            api_key = self._config_manager.get_secret("OPENAI_API_KEY")
            return OpenAILLMProvider(api_key=api_key, model_name=config.llm_model)
        raise RuntimeError(f"Неподдерживаемый model_provider: {config.model_provider}")
