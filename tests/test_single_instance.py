"""Тесты single-instance lock на Unix."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

import app.platform.single_instance as single_instance


@pytest.fixture(autouse=True)
def _cleanup_lock_state() -> None:
    """Сбрасывает глобальное состояние lock между тестами."""
    lock_fp = single_instance._lock_fp
    if lock_fp is not None:
        try:
            import fcntl

            fcntl.flock(lock_fp.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        lock_fp.close()
    single_instance._lock_fp = None
    single_instance._win_mutex_handle = None
    yield
    lock_fp = single_instance._lock_fp
    if lock_fp is not None:
        try:
            import fcntl

            fcntl.flock(lock_fp.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        lock_fp.close()
    single_instance._lock_fp = None
    single_instance._win_mutex_handle = None


def test_unix_lock_writes_pid_metadata(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.setenv("HOME", str(tmp_path))

    ok = single_instance.try_acquire_single_instance_lock(support_subdir="GhostWriter")
    assert ok is True

    lock_path = tmp_path / ".ghostwriter" / "single_instance.lock"
    text = lock_path.read_text(encoding="utf-8")
    assert '"pid":' in text
    assert f'"pid": {os.getpid()}' in text
    assert '"support_subdir": "GhostWriter"' in text


def test_unix_lock_rewrites_stale_file_content(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.setenv("HOME", str(tmp_path))

    lock_path = tmp_path / ".ghostwriter" / "single_instance.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text("stale-data", encoding="utf-8")

    ok = single_instance.try_acquire_single_instance_lock(support_subdir="GhostWriter")
    assert ok is True
    text = lock_path.read_text(encoding="utf-8")
    assert "stale-data" not in text
    assert '"pid":' in text
