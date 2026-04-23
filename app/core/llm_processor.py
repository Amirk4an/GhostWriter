"""Оркестратор обработки текста через LLM."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.interfaces import LLMProvider


@dataclass(frozen=True)
class JournalStructuredResult:
    """Распознанный ответ LLM для режима дневника."""

    title: str
    tags: list[str]
    advice: str
    refined_text: str


def _normalize_journal_dict(data: dict[str, Any]) -> JournalStructuredResult:
    title = str(data.get("title", "") or "").strip()
    advice = str(data.get("advice", "") or "").strip()
    refined = str(data.get("refined_text", data.get("refined", "")) or "").strip()
    tags_raw = data.get("tags", [])
    tags: list[str] = []
    if isinstance(tags_raw, list):
        for item in tags_raw[:10]:
            s = str(item).strip()
            if s:
                tags.append(s)
    elif isinstance(tags_raw, str) and tags_raw.strip():
        tags = [tags_raw.strip()]
    if len(tags) > 3:
        tags = tags[:3]
    return JournalStructuredResult(title=title, tags=tags, advice=advice, refined_text=refined)


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

    def process_journal_entry(self, raw_text: str, system_prompt: str) -> JournalStructuredResult:
        """Структурированный ответ для дневника (требует LLM)."""
        text = raw_text.strip()
        if not text:
            return JournalStructuredResult(title="", tags=[], advice="", refined_text="")
        if not self._enabled or self._provider is None:
            raise RuntimeError("LLM отключён или провайдер не настроен")
        payload = self._provider.refine_journal_json(text, system_prompt)
        if not isinstance(payload, dict):
            raise RuntimeError("LLM вернул не объект JSON")
        return _normalize_journal_dict(payload)
