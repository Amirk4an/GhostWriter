"""Тесты SQLite-истории диктовок."""

from __future__ import annotations

from pathlib import Path

from app.core.history_manager import HistoryManager


def test_history_add_and_list(tmp_path: Path) -> None:
    db = tmp_path / "h.db"
    hm = HistoryManager(db)
    hm.add_record(raw_text="alpha", final_text="beta", target_app="TestApp")
    rows = hm.list_recent(10)
    assert len(rows) == 1
    assert rows[0].raw_text == "alpha"
    assert rows[0].final_text == "beta"
    assert rows[0].target_app == "TestApp"


def test_history_clear(tmp_path: Path) -> None:
    db = tmp_path / "h2.db"
    hm = HistoryManager(db)
    hm.add_record(raw_text="a", final_text="b", target_app="")
    hm.clear_all()
    assert hm.record_count() == 0


def test_history_trim(tmp_path: Path) -> None:
    db = tmp_path / "h3.db"
    hm = HistoryManager(db)
    for i in range(505):
        hm.add_record(raw_text=str(i), final_text=str(i), target_app="")
    assert hm.record_count() == 500
