"""Записи дневника (journal) в локальной SQLite рядом с историей диктовок."""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

LOGGER = logging.getLogger(__name__)

MAX_JOURNAL_ENTRIES = 2000


def default_journal_db_path(*, support_subdir: str = "GhostWriter") -> Path:
    """Тот же каталог, что и ``history.db`` (один файл БД)."""
    from app.core.history_manager import default_history_db_path

    return default_history_db_path(support_subdir=support_subdir)


@dataclass(frozen=True)
class JournalEntry:
    """Одна запись дневника."""

    id: int
    created_at: str
    raw_text: str
    refined_text: str
    title: str
    advice: str
    tags_json: str

    def tags_list(self) -> list[str]:
        try:
            data = json.loads(self.tags_json or "[]")
            if isinstance(data, list):
                return [str(x).strip() for x in data if str(x).strip()]
        except (json.JSONDecodeError, TypeError):
            pass
        return []


class JournalManager:
    """Таблица ``journal_entries`` в ``history.db``."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._lock = threading.RLock()

    @classmethod
    def with_default_path(cls, *, support_subdir: str = "GhostWriter") -> JournalManager:
        return cls(default_journal_db_path(support_subdir=support_subdir))

    def _connect(self) -> sqlite3.Connection:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self._db_path), timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def init_schema(self) -> None:
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS journal_entries (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        created_at TEXT NOT NULL,
                        raw_text TEXT NOT NULL,
                        refined_text TEXT NOT NULL DEFAULT '',
                        title TEXT NOT NULL DEFAULT '',
                        advice TEXT NOT NULL DEFAULT '',
                        tags TEXT NOT NULL DEFAULT '[]'
                    )
                    """
                )
                conn.commit()

    def create(
        self,
        *,
        raw_text: str,
        refined_text: str,
        title: str,
        advice: str,
        tags: list[str],
    ) -> int:
        created = datetime.now().astimezone().replace(microsecond=0).isoformat()
        tags_payload = json.dumps(tags[:20], ensure_ascii=False)
        with self._lock:
            self.init_schema()
            try:
                with self._connect() as conn:
                    cur = conn.execute(
                        """
                        INSERT INTO journal_entries (created_at, raw_text, refined_text, title, advice, tags)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            created,
                            raw_text or "",
                            refined_text or "",
                            title or "",
                            advice or "",
                            tags_payload,
                        ),
                    )
                    conn.commit()
                    new_id = int(cur.lastrowid)
                    self._trim_excess(conn)
                    conn.commit()
                    return new_id
            except sqlite3.Error:
                LOGGER.exception("Ошибка записи в дневник")
                raise

    def _trim_excess(self, conn: sqlite3.Connection) -> None:
        cur = conn.execute(
            "SELECT id FROM journal_entries ORDER BY id DESC LIMIT ?",
            (MAX_JOURNAL_ENTRIES,),
        )
        keep = [int(r[0]) for r in cur.fetchall()]
        if not keep:
            return
        placeholders = ",".join("?" * len(keep))
        conn.execute(f"DELETE FROM journal_entries WHERE id NOT IN ({placeholders})", keep)

    def get(self, entry_id: int) -> JournalEntry | None:
        with self._lock:
            self.init_schema()
            if not self._db_path.is_file():
                return None
            try:
                with self._connect() as conn:
                    conn.row_factory = sqlite3.Row
                    cur = conn.execute(
                        """
                        SELECT id, created_at, raw_text, refined_text, title, advice, tags
                        FROM journal_entries WHERE id = ?
                        """,
                        (int(entry_id),),
                    )
                    row = cur.fetchone()
            except sqlite3.Error:
                LOGGER.exception("Ошибка чтения записи дневника")
                return None
        if row is None:
            return None
        return self._row_to_entry(row)

    def list_recent(self, *, limit: int = 200, tag_filter: str | None = None) -> list[JournalEntry]:
        lim = max(1, min(int(limit), 500))
        tag_filter = (tag_filter or "").strip()
        with self._lock:
            self.init_schema()
            if not self._db_path.is_file():
                return []
            try:
                with self._connect() as conn:
                    conn.row_factory = sqlite3.Row
                    if tag_filter:
                        cur = conn.execute(
                            """
                            SELECT id, created_at, raw_text, refined_text, title, advice, tags
                            FROM journal_entries
                            WHERE tags LIKE ?
                            ORDER BY id DESC
                            LIMIT ?
                            """,
                            (f'%"{tag_filter}"%', lim),
                        )
                    else:
                        cur = conn.execute(
                            """
                            SELECT id, created_at, raw_text, refined_text, title, advice, tags
                            FROM journal_entries
                            ORDER BY id DESC
                            LIMIT ?
                            """,
                            (lim,),
                        )
                    rows = cur.fetchall()
            except sqlite3.Error:
                LOGGER.exception("Ошибка списка дневника")
                return []
        return [self._row_to_entry(r) for r in rows]

    def list_distinct_tags(self, *, limit: int = 100) -> list[str]:
        entries = self.list_recent(limit=MAX_JOURNAL_ENTRIES)
        seen: set[str] = set()
        out: list[str] = []
        for e in entries:
            for t in e.tags_list():
                key = t.lower()
                if key not in seen:
                    seen.add(key)
                    out.append(t)
                if len(out) >= limit:
                    return out
        return sorted(out, key=lambda s: s.lower())

    def update(
        self,
        entry_id: int,
        *,
        raw_text: str | None = None,
        refined_text: str | None = None,
        title: str | None = None,
        advice: str | None = None,
        tags: list[str] | None = None,
    ) -> bool:
        fields: list[str] = []
        values: list[object] = []
        if raw_text is not None:
            fields.append("raw_text = ?")
            values.append(raw_text)
        if refined_text is not None:
            fields.append("refined_text = ?")
            values.append(refined_text)
        if title is not None:
            fields.append("title = ?")
            values.append(title)
        if advice is not None:
            fields.append("advice = ?")
            values.append(advice)
        if tags is not None:
            fields.append("tags = ?")
            values.append(json.dumps(tags[:20], ensure_ascii=False))
        if not fields:
            return False
        values.append(int(entry_id))
        with self._lock:
            self.init_schema()
            try:
                with self._connect() as conn:
                    conn.execute(
                        f"UPDATE journal_entries SET {', '.join(fields)} WHERE id = ?",
                        values,
                    )
                    conn.commit()
                    return conn.total_changes > 0
            except sqlite3.Error:
                LOGGER.exception("Ошибка обновления записи дневника")
                return False

    def delete(self, entry_id: int) -> bool:
        with self._lock:
            self.init_schema()
            try:
                with self._connect() as conn:
                    conn.execute("DELETE FROM journal_entries WHERE id = ?", (int(entry_id),))
                    conn.commit()
                    return conn.total_changes > 0
            except sqlite3.Error:
                LOGGER.exception("Ошибка удаления записи дневника")
                return False

    def _row_to_entry(self, row: sqlite3.Row) -> JournalEntry:
        return JournalEntry(
            id=int(row["id"]),
            created_at=str(row["created_at"]),
            raw_text=str(row["raw_text"] or ""),
            refined_text=str(row["refined_text"] or ""),
            title=str(row["title"] or ""),
            advice=str(row["advice"] or ""),
            tags_json=str(row["tags"] or "[]"),
        )
