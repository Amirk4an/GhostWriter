"""Потокобезопасный мост статуса UI ↔ AppController."""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from queue import Empty, Full

from multiprocessing.queues import Queue as MPQueue

LOGGER = logging.getLogger(__name__)


class StatusBridge:
    """Хранит строку статуса и опциональную подпись (например, частичный транскрипт)."""

    def __init__(
        self,
        mp_queue: MPQueue | None = None,
        *,
        on_broadcast: Callable[[str, str | None], None] | None = None,
    ) -> None:
        self._lock = threading.Lock()
        self._status = "Idle"
        self._detail: str | None = None
        self._mp_queue: MPQueue | None = mp_queue
        self._on_broadcast = on_broadcast

    def set_on_broadcast(self, on_broadcast: Callable[[str, str | None], None] | None) -> None:
        """Подключает или меняет обработчик рассылки статуса (например, после создания StatusPushClient)."""
        self._on_broadcast = on_broadcast

    def set_status(self, status: str, detail: str | None = None) -> None:
        with self._lock:
            self._status = status
            self._detail = detail
        if self._on_broadcast is not None:
            try:
                self._on_broadcast(status, detail)
            except Exception:
                LOGGER.exception("Ошибка в on_broadcast статуса")
        if self._mp_queue is not None:
            self._push_latest_mp(status, detail)

    def _push_latest_mp(self, status: str, detail: str | None = None) -> None:
        q = self._mp_queue
        if q is None:
            return
        try:
            while True:
                q.get_nowait()
        except Empty:
            pass
        try:
            q.put_nowait((status, detail))
        except Full:
            try:
                q.get_nowait()
            except Empty:
                pass
            try:
                q.put_nowait((status, detail))
            except Full:
                pass

    def snapshot(self) -> tuple[str, str | None]:
        with self._lock:
            return self._status, self._detail
