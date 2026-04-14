"""Загрузка и применение пользовательского словаря замен."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger(__name__)


def load_glossary_entries(path: Path) -> list[tuple[str, str]]:
    """Читает user_glossary.json: объект {wrong: right} или список [wrong, right]."""
    if not path.is_file():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        LOGGER.warning("Не удалось прочитать глоссарий %s: %s", path, error)
        return []

    pairs: list[tuple[str, str]] = []
    if isinstance(raw, dict):
        for k, v in raw.items():
            if isinstance(k, str) and isinstance(v, str) and k.strip():
                pairs.append((k.strip(), v.strip()))
    elif isinstance(raw, list):
        for item in raw:
            if isinstance(item, (list, tuple)) and len(item) == 2:
                a, b = item[0], item[1]
                if isinstance(a, str) and isinstance(b, str) and a.strip():
                    pairs.append((a.strip(), b.strip()))
            elif isinstance(item, dict):
                fr = item.get("from")
                to = item.get("to")
                if isinstance(fr, str) and isinstance(to, str) and fr.strip():
                    pairs.append((fr.strip(), to.strip()))
    pairs.sort(key=lambda x: len(x[0]), reverse=True)
    return pairs


def apply_glossary(text: str, pairs: list[tuple[str, str]]) -> str:
    """Подстановка целых слов/фраз (from → to), длинные ключи первыми."""
    if not text or not pairs:
        return text
    result = text
    for wrong, right in pairs:
        if not wrong:
            continue
        if wrong.isalnum() or re.match(r"^[\w\-]+$", wrong):
            pattern = re.compile(rf"(?<!\w){re.escape(wrong)}(?!\w)", re.IGNORECASE)
            result = pattern.sub(right, result)
        else:
            result = result.replace(wrong, right)
    return result


def glossary_prompt_block(pairs: list[tuple[str, str]]) -> str:
    """Короткий блок для system prompt."""
    if not pairs:
        return ""
    lines = [f"- «{a}» → «{b}»" for a, b in pairs[:40]]
    return "Соблюдай замены терминов:\n" + "\n".join(lines)
