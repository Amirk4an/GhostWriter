"""Отправка статуса в Electron-оболочку по TCP (newline-delimited JSON)."""

from __future__ import annotations

import json
import logging
import socket
import threading
import time

LOGGER = logging.getLogger(__name__)


class StatusPushClient:
    """Фоновое переподключение к порту, на котором слушает Electron."""

    def __init__(self, host: str, port: int) -> None:
        self._host = host
        self._port = port
        self._lock = threading.Lock()
        self._sock: socket.socket | None = None
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._connect_loop, name="StatusPushClient", daemon=True)
        self._thread.start()

    def close(self) -> None:
        self._stop.set()
        with self._lock:
            self._close_locked()

    def push_status(self, status: str, detail: str | None) -> None:
        line = json.dumps({"status": status, "detail": detail}, ensure_ascii=False) + "\n"
        data = line.encode("utf-8")
        with self._lock:
            sock = self._sock
            if sock is None:
                return
            try:
                sock.sendall(data)
            except OSError as err:
                LOGGER.debug("status push send failed: %s", err)
                self._close_locked()

    def _close_locked(self) -> None:
        if self._sock is not None:
            try:
                self._sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None

    def _connect_loop(self) -> None:
        while not self._stop.is_set():
            try:
                sock = socket.create_connection((self._host, self._port), timeout=5)
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                eof = threading.Event()

                def drain_peer() -> None:
                    try:
                        while True:
                            chunk = sock.recv(4096)
                            if not chunk:
                                break
                    except OSError:
                        pass
                    finally:
                        eof.set()

                threading.Thread(target=drain_peer, name="StatusPushDrain", daemon=True).start()
                with self._lock:
                    self._sock = sock
                LOGGER.info("Подключение к UI (Electron) установлено: %s:%s", self._host, self._port)
                eof.wait()
                with self._lock:
                    self._close_locked()
                LOGGER.debug("Соединение с UI разорвано, переподключение…")
            except OSError as err:
                LOGGER.debug("Подключение к UI: %s", err)
            if self._stop.wait(0.3):
                break
