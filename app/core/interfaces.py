"""Контракты для модулей приложения."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable


class TranscriptionProvider(ABC):
    """Интерфейс провайдера транскрипции."""

    @abstractmethod
    def transcribe(
        self,
        audio_bytes: bytes,
        sample_rate: int,
        language: str | None = None,
        *,
        on_partial: Callable[[str], None] | None = None,
    ) -> str:
        """Преобразует аудио в текст. on_partial — опциональные промежуточные строки (streaming)."""


class LLMProvider(ABC):
    """Интерфейс LLM-провайдера."""

    @abstractmethod
    def refine_text(self, raw_text: str, system_prompt: str) -> str:
        """Очищает и улучшает текст."""


class OutputAdapter(ABC):
    """Интерфейс вывода текста в активное приложение."""

    @abstractmethod
    def output_text(self, text: str, paste_target_app: str | None = None) -> None:
        """Вставляет текст в активное поле.

        paste_target_app — имя приложения с фокусом на момент начала диктовки (macOS),
        чтобы после долгого STT вернуть фокус и вставить текст не в терминал.
        """


class HotkeyListener(ABC):
    """Интерфейс глобального слушателя хоткея."""

    @abstractmethod
    def start(
        self,
        on_press: Callable[[], None] | None = None,
        on_release: Callable[[], None] | None = None,
        *,
        dictate_edge: Callable[[bool, float], None] | None = None,
        command_press: Callable[[], None] | None = None,
        command_release: Callable[[], None] | None = None,
    ) -> None:
        """Запускает слушатель (dictate_edge или пара on_press/on_release)."""

    @abstractmethod
    def stop(self) -> None:
        """Останавливает слушатель."""
