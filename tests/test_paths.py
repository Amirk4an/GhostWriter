"""Тесты единого каталога пользовательских данных."""

from __future__ import annotations

import pytest

from app.platform.paths import default_app_support_dir, single_instance_hint_path


def test_default_app_support_dir_darwin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.platform", "darwin")
    p = default_app_support_dir(support_subdir="GhostWriter")
    assert "Library" in str(p)
    assert p.name == "GhostWriter"


def test_default_app_support_dir_windows(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setattr("sys.platform", "win32")
    monkeypatch.setenv("APPDATA", str(tmp_path))
    p = default_app_support_dir(support_subdir="MyApp")
    assert p == tmp_path / "MyApp"


def test_default_app_support_dir_linux(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.platform", "linux")
    p = default_app_support_dir(support_subdir="GhostWriter")
    assert p.name == ".ghostwriter"


def test_single_instance_hint_path(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setattr("sys.platform", "win32")
    monkeypatch.setenv("APPDATA", str(tmp_path))
    h = single_instance_hint_path(support_subdir="X")
    assert h == tmp_path / "X" / "single_instance.lock"
