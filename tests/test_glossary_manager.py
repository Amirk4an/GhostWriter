"""Тесты глоссария."""

from __future__ import annotations

from pathlib import Path

from app.core.glossary_manager import apply_glossary


def test_apply_glossary_whole_word(tmp_path: Path) -> None:
    pairs = [("foo", "bar")]
    assert apply_glossary("hello foo world", pairs) == "hello bar world"
