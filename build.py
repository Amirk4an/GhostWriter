#!/usr/bin/env python3
"""
Сборка нативного бандла GhostWriter.app через PyInstaller и правка Info.plist.

Запуск из корня проекта (с активированным venv)::

    python3 build.py
"""

from __future__ import annotations

import os
import plistlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def _source_icon_png(project_root: Path) -> Path:
    """Возвращает путь к исходному PNG иконки и валидирует его наличие."""
    source_png = project_root / "assets" / "icons" / "app_icon.png"
    if not source_png.is_file():
        raise FileNotFoundError(
            f"Не найден исходник иконки: {source_png}. Положите PNG 1024x1024."
        )
    return source_png


def ensure_macos_icon(project_root: Path, source_png: Path) -> Path | None:
    """
    Генерирует ``.icns`` из ``assets/icons/app_icon.png`` для macOS-сборки.

    Args:
        project_root: Корень проекта.

    Returns:
        Путь к ``.icns`` или ``None``, если платформа не macOS.
    """
    if sys.platform != "darwin":
        return None

    target_icns = project_root / "assets" / "icons" / "app_icon.icns"

    if shutil.which("sips") is None or shutil.which("iconutil") is None:
        raise RuntimeError(
            "Для генерации .icns нужны системные утилиты macOS: sips и iconutil."
        )

    with tempfile.TemporaryDirectory() as tmpdir:
        iconset_dir = Path(tmpdir) / "app.iconset"
        iconset_dir.mkdir(parents=True, exist_ok=True)
        icon_sizes = [
            (16, "icon_16x16.png"),
            (32, "icon_16x16@2x.png"),
            (32, "icon_32x32.png"),
            (64, "icon_32x32@2x.png"),
            (128, "icon_128x128.png"),
            (256, "icon_128x128@2x.png"),
            (256, "icon_256x256.png"),
            (512, "icon_256x256@2x.png"),
            (512, "icon_512x512.png"),
            (1024, "icon_512x512@2x.png"),
        ]
        for size, name in icon_sizes:
            output_path = iconset_dir / name
            subprocess.run(
                [
                    "sips",
                    "-z",
                    str(size),
                    str(size),
                    "-s",
                    "format",
                    "png",
                    str(source_png),
                    "--out",
                    str(output_path),
                ],
                check=True,
                capture_output=True,
            )
        subprocess.run(
            [
                "iconutil",
                "-c",
                "icns",
                str(iconset_dir),
                "-o",
                str(target_icns),
            ],
            check=True,
            capture_output=True,
        )
    return target_icns


def ensure_windows_icon(project_root: Path, source_png: Path) -> Path | None:
    """
    Генерирует ``.ico`` из ``assets/icons/app_icon.png`` для Windows-сборки.

    Args:
        project_root: Корень проекта.
        source_png: Исходный PNG-файл.

    Returns:
        Путь к ``.ico`` или ``None``, если платформа не Windows.
    """
    if not sys.platform.startswith("win"):
        return None

    target_ico = project_root / "assets" / "icons" / "app_icon.ico"
    try:
        from PIL import Image  # noqa: PLC0415
    except ImportError as err:
        raise RuntimeError(
            "Для генерации Windows-иконки нужен Pillow: pip install pillow"
        ) from err

    icon_sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    with Image.open(source_png) as image:
        image = image.convert("RGBA")
        image.save(target_ico, format="ICO", sizes=icon_sizes)
    return target_ico


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
    icons_dir = (project_root / "assets" / "icons").resolve()
    source_png = _source_icon_png(project_root)
    macos_icon = ensure_macos_icon(project_root, source_png)
    windows_icon = ensure_windows_icon(project_root, source_png)

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
        "--add-data",
        f"{icons_dir}{sep}assets/icons",
    ]
    if sys.platform == "darwin":
        argv.extend(["--osx-bundle-identifier", "com.ghostwriter.voiceflow"])
        if macos_icon is not None:
            argv.extend(["--icon", str(macos_icon)])
    elif sys.platform.startswith("win"):
        if windows_icon is not None:
            argv.extend(["--icon", str(windows_icon)])
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
