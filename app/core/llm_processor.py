"""Оркестратор обработки текста через LLM."""

from __future__ import annotations

from app.core.interfaces import LLMProvider


class LLMProcessor:
    """Применяет system prompt и вызывает провайдер LLM."""

    def __init__(self, provider: LLMProvider | None, enabled: bool) -> None:
        self._provider = provider
        self._enabled = enabled

    def is_remote_enabled(self) -> bool:
        """``True``, если настроен провайдер и LLM не отключён в конфиге (будет сетевой вызов)."""
        return bool(self._enabled and self._provider is not None)

    def refine_text(self, raw_text: str, system_prompt: str) -> str:
        """Возвращает обработанный текст либо исходный pass-through."""
        text = raw_text.strip()
        if not text:
            return ""
        if not self._enabled or self._provider is None:
            return text
        return self._provider.refine_text(text, system_prompt)

    def refine_command(
        self,
        selection: str,
        spoken_instruction: str,
        command_system_prompt: str,
        base_system_prompt: str,
    ) -> str:
        """Переписывает выделение по голосовой команде (требует включённый LLM)."""
        sel = selection.strip()
        spoken = spoken_instruction.strip()
        if not sel or not spoken:
            return sel
        if not self._enabled or self._provider is None:
            return sel
        user_message = (
            "Выделенный текст:\n"
            f"{selection}\n\n"
            "Голосовая команда (распознана):\n"
            f"{spoken_instruction}"
        )
        combined_system = f"{base_system_prompt}\n\n{command_system_prompt}"
        return self._provider.refine_text(user_message, combined_system)
