"""Тесты LLMProcessor."""

from __future__ import annotations

from app.core.interfaces import LLMProvider
from app.core.llm_processor import LLMProcessor


class DummyLLMProvider(LLMProvider):
    def refine_text(self, raw_text: str, system_prompt: str) -> str:
        return f"{system_prompt}:{raw_text}"


def test_llm_processor_passthrough_when_disabled() -> None:
    processor = LLMProcessor(provider=None, enabled=False)
    assert processor.refine_text("  hello  ", "prompt") == "hello"


def test_llm_processor_uses_provider() -> None:
    processor = LLMProcessor(provider=DummyLLMProvider(), enabled=True)
    assert processor.refine_text("hello", "sys") == "sys:hello"
