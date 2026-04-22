"""История диктовок в локальной SQLite (приватность: только на машине пользователя)."""

from __future__ import annotations

import logging
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
LOGGER = logging.getLogger(__name__)

HISTORY_DB_NAME = "history.db"
# Максимум записей в БД (FIFO по id).
MAX_RECORDS = 500


def default_history_db_path(*, support_subdir: str = "GhostWriter") -> Path:
    """
    Путь к ``history.db`` рядом со ``stats.json`` (тот же ``support_subdir``).

    См. ``app.platform.paths.default_app_support_dir``.
    """
    from app.platform.paths import default_app_support_dir

    return default_app_support_dir(support_subdir=support_subdir) / HISTORY_DB_NAME


@dataclass(frozen=True)
class DictationRecord:
    """Одна строка истории."""

    id: int
    created_at: str
    raw_text: str
    final_text: str
    target_app: str


class HistoryManager:
    """SQLite-хранилище: дозапись из основного процесса, чтение из дашборда (WAL)."""

    def __init__(self, db_path: Path) -> None:
        """
        Args:
            db_path: Абсолютный путь к файлу БД.
        """
        self._db_path = db_path
        # RLock: add_record/list_recent hold the lock and call init_schema(), which also locks.
        self._lock = threading.RLock()

    @classmethod
    def with_default_path(cls, *, support_subdir: str = "GhostWriter") -> HistoryManager:
        """Фабрика с путём по умолчанию."""
        return cls(default_history_db_path(support_subdir=support_subdir))

    def _connect(self) -> sqlite3.Connection:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self._db_path), timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def init_schema(self) -> None:
        """Создаёт таблицу при необходимости (идемпотентно)."""
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS dictations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        created_at TEXT NOT NULL,
                        raw_text TEXT NOT NULL,
                        final_text TEXT NOT NULL,
                        target_app TEXT NOT NULL DEFAULT ''
                    )
                    """
                )
                conn.commit()

    def add_record(self, *, raw_text: str, final_text: str, target_app: str) -> None:
        """
        Добавляет запись и при необходимости обрезает хвост до ``MAX_RECORDS``.

        Args:
            raw_text: Текст после STT (до глоссария в пайплайне уже применён — передаём как в контроллере).
            final_text: Текст после LLM / вставки.
            target_app: Имя целевого приложения или пустая строка.
        """
        created = datetime.now().astimezone().replace(microsecond=0).isoformat()
        raw = raw_text or ""
        final = final_text or ""
        target = (target_app or "").strip()

        with self._lock:
            self.init_schema()
            try:
                with self._connect() as conn:
                    conn.execute(
                        """
                        INSERT INTO dictations (created_at, raw_text, final_text, target_app)
                        VALUES (?, ?, ?, ?)
                        """,
                        (created, raw, final, target),
                    )
                    conn.commit()
                    self._trim_excess(conn)
                    conn.commit()
            except sqlite3.Error:
                LOGGER.exception("Ошибка записи в историю диктовок")

    def _trim_excess(self, conn: sqlite3.Connection) -> None:
        cur = conn.execute("SELECT id FROM dictations ORDER BY id DESC LIMIT ?", (MAX_RECORDS,))
        keep = [int(r[0]) for r in cur.fetchall()]
        if not keep:
            return
        placeholders = ",".join("?" * len(keep))
        conn.execute(f"DELETE FROM dictations WHERE id NOT IN ({placeholders})", keep)

    def list_recent(self, limit: int = 50) -> list[DictationRecord]:
        """
        Возвращает последние записи (новые сверху).

        Args:
            limit: Не больше этого числа строк.
        """
        lim = max(1, min(int(limit), 200))
        with self._lock:
            self.init_schema()
            if not self._db_path.is_file():
                return []
            try:
                with self._connect() as conn:
                    conn.row_factory = sqlite3.Row
                    cur = conn.execute(
                        """
                        SELECT id, created_at, raw_text, final_text, target_app
                        FROM dictations
                        ORDER BY id DESC
                        LIMIT ?
                        """,
                        (lim,),
                    )
                    rows = cur.fetchall()
            except sqlite3.Error:
                LOGGER.exception("Ошибка чтения истории диктовок")
                return []
        out: list[DictationRecord] = []
        for r in rows:
            out.append(
                DictationRecord(
                    id=int(r["id"]),
                    created_at=str(r["created_at"]),
                    raw_text=str(r["raw_text"] or ""),
                    final_text=str(r["final_text"] or ""),
                    target_app=str(r["target_app"] or ""),
                )
            )
        return out

    def clear_all(self) -> None:
        """Удаляет все записи."""
        with self._lock:
            self.init_schema()
            if not self._db_path.is_file():
                return
            try:
                with self._connect() as conn:
                    conn.execute("DELETE FROM dictations")
                    conn.commit()
            except sqlite3.Error:
                LOGGER.exception("Ошибка очистки истории диктовок")

    def record_count(self) -> int:
        """Число записей (для подписи в UI)."""
        with self._lock:
            self.init_schema()
            if not self._db_path.is_file():
                return 0
            try:
                with self._connect() as conn:
                    cur = conn.execute("SELECT COUNT(*) FROM dictations")
                    row = cur.fetchone()
                    return int(row[0]) if row else 0
            except sqlite3.Error:
                return 0
