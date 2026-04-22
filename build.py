#!/usr/bin/env python3
"""
Сборка нативного бандла GhostWriter.app через PyInstaller и правка Info.plist.

Запуск из корня проекта (с активированным venv)::

    python3 build.py
"""

from __future__ import annotations

import os
import plistlib
import sys
from pathlib import Path


def _pyinstaller_argv(project_root: Path) -> list[str]:
    """Формирует аргументы для ``PyInstaller.__main__.run`` (без имени ``pyinstaller``)."""
    import customtkinter

    sep = os.pathsep
    cfg_dir = (project_root / "config").resolve()
    if not cfg_dir.is_dir():
        raise FileNotFoundError(f"Ожидается каталог config: {cfg_dir}")

    ctk_root = Path(customtkinter.__path__[0]).resolve()
    data_cfg = f"{cfg_dir}{sep}config"
    data_ctk = f"{ctk_root}{sep}customtkinter"

    argv: list[str] = [
        str(project_root / "main.py"),
        "--name",
        "GhostWriter",
        "--windowed",
        "--noconsole",
        "--onedir",
        "--noconfirm",
        "--clean",
        "--distpath",
        str(project_root / "dist"),
        "--workpath",
        str(project_root / "build" / "pyinstaller"),
        "--specpath",
        str(project_root),
        "--paths",
        str(project_root),
        "--hidden-import",
        "customtkinter",
        "--hidden-import",
        "rumps",
        "--hidden-import",
        "pystray",
        "--hidden-import",
        "pynput",
        "--hidden-import",
        "faster_whisper",
        "--hidden-import",
        "sounddevice",
        "--collect-submodules",
        "app",
        "--add-data",
        data_cfg,
        "--add-data",
        data_ctk,
    ]
    if sys.platform == "darwin":
        argv.extend(["--osx-bundle-identifier", "com.ghostwriter.voiceflow"])
    return argv


def run_pyinstaller(project_root: Path) -> None:
    """Запускает PyInstaller в текущем интерпретаторе."""
    try:
        import PyInstaller.__main__ as pyi  # noqa: PLC0415
    except ImportError as err:
        raise SystemExit("Установите PyInstaller: pip install pyinstaller") from err

    pyi.run(_pyinstaller_argv(project_root))


def find_app_bundle(dist: Path) -> Path:
    """Возвращает путь к ``GhostWriter.app`` после onedir + windowed."""
    direct = dist / "GhostWriter.app"
    if direct.is_dir():
        return direct
    nested = dist / "GhostWriter" / "GhostWriter.app"
    if nested.is_dir():
        return nested
    raise FileNotFoundError(
        f"Не найден GhostWriter.app под {dist}. Проверьте вывод PyInstaller."
    )


def patch_info_plist(app_bundle: Path) -> None:
    """
    Дополняет ``Info.plist``: LSUIElement, строки приватности, Retina.

    Args:
        app_bundle: Каталог ``*.app``.
    """
    plist_path = app_bundle / "Contents" / "Info.plist"
    if not plist_path.is_file():
        raise FileNotFoundError(plist_path)

    with plist_path.open("rb") as fp:
        data = plistlib.load(fp)

    data["LSUIElement"] = True
    data["NSMicrophoneUsageDescription"] = "Ghost Writer needs your microphone to dictate text."
    data["NSAppleEventsUsageDescription"] = (
        "Ghost Writer needs to control System Events to auto-paste text."
    )
    data["NSSpeechRecognitionUsageDescription"] = (
        "Ghost Writer needs speech recognition to transcribe your voice."
    )
    data["NSHighResolutionCapable"] = True

    with plist_path.open("wb") as fp:
        plistlib.dump(data, fp, fmt=plistlib.FMT_XML)


def main() -> None:
    project_root = Path(__file__).resolve().parent
    run_pyinstaller(project_root)
    if sys.platform != "darwin":
        print("Сборка завершена (не macOS — Info.plist не менялся).", file=sys.stderr)
        print("Сборка успешно завершена!")
        return
    app = find_app_bundle(project_root / "dist")
    patch_info_plist(app)
    print("Сборка успешно завершена!")


if __name__ == "__main__":
    main()
