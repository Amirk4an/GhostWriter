"""Тесты JournalManager."""

from __future__ import annotations

from pathlib import Path

from app.core.journal_manager import JournalEntry, JournalManager


def test_journal_manager_crud(tmp_path: Path) -> None:
    db = tmp_path / "history.db"
    jm = JournalManager(db)
    jm.init_schema()
    eid = jm.create(
        raw_text="raw",
        refined_text="refined",
        title="T1",
        advice="be kind",
        tags=["work", "ideas"],
    )
    assert eid > 0
    got = jm.get(eid)
    assert got is not None
    assert isinstance(got, JournalEntry)
    assert got.title == "T1"
    assert got.tags_list() == ["work", "ideas"]

    ok = jm.update(eid, title="T2", tags=["x"])
    assert ok is True
    got2 = jm.get(eid)
    assert got2 is not None
    assert got2.title == "T2"
    assert got2.tags_list() == ["x"]

    recent = jm.list_recent(limit=10)
    assert len(recent) == 1
    assert jm.list_distinct_tags(limit=20) == ["x"]

    assert jm.delete(eid) is True
    assert jm.get(eid) is None
