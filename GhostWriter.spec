# -*- mode: python ; coding: utf-8 -*-
import importlib.util
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# PyInstaller 6+ выполняет .spec через exec(); в этом контексте __file__ не задан.
# SPECPATH — каталог, в котором лежит .spec (см. документацию PyInstaller).
_SPEC_ROOT = Path(SPECPATH).resolve()

hiddenimports = ["customtkinter", "pystray", "pynput", "faster_whisper", "sounddevice"]
if sys.platform == "darwin":
    hiddenimports.append("rumps")
hiddenimports += collect_submodules("app")

# faster-whisper VAD (onnx) и прочие ресурсы пакета — без этого в .app падает загрузка silero_vad_v6.onnx.
_datas = [(str(_SPEC_ROOT / "config"), "config")]
_ck = importlib.util.find_spec("customtkinter")
if _ck and _ck.submodule_search_locations:
    _ck_root = Path(list(_ck.submodule_search_locations)[0])
    _datas.append((str(_ck_root), "customtkinter"))
_datas += collect_data_files('faster_whisper')
_litellm = importlib.util.find_spec("litellm")
if _litellm and _litellm.submodule_search_locations:
    _litellm_root = Path(list(_litellm.submodule_search_locations)[0])
    _litellm_backup = _litellm_root / "model_prices_and_context_window_backup.json"
    if _litellm_backup.is_file():
        _datas.append((str(_litellm_backup), "litellm"))
_models_dir = _SPEC_ROOT / "assets" / "models"
if _models_dir.is_dir():
    _datas.append((str(_models_dir), "assets/models"))

a = Analysis(
    [str(_SPEC_ROOT / "main.py")],
    pathex=[str(_SPEC_ROOT)],
    binaries=[],
    datas=_datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='GhostWriter',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="GhostWriter",
)

# macOS .app bundle; на Windows достаточно COLLECT (каталог dist/GhostWriter/).
if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="GhostWriter.app",
        icon=None,
        bundle_identifier="com.ghostwriter.voiceflow",
        info_plist={
            "LSUIElement": True,
            "NSMicrophoneUsageDescription": (
                "Приложению нужен доступ к микрофону для записи голоса и преобразования речи в текст."
            ),
            "NSAppleEventsUsageDescription": (
                "Приложению нужен доступ к системным событиям для вставки текста в другие программы."
            ),
            "NSAccessibilityUsageDescription": (
                "Приложению нужен доступ к универсальному доступу для глобальных горячих клавиш и эмуляции ввода."
            ),
            "NSHighResolutionCapable": True,
        },
    )
