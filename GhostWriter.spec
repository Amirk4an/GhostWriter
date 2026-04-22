# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# PyInstaller 6+ выполняет .spec через exec(); в этом контексте __file__ не задан.
# SPECPATH — каталог, в котором лежит .spec (см. документацию PyInstaller).
_SPEC_ROOT = Path(SPECPATH).resolve()

hiddenimports = ['customtkinter', 'rumps', 'pystray', 'pynput', 'faster_whisper', 'sounddevice']
hiddenimports += collect_submodules('app')

# faster-whisper VAD (onnx) и прочие ресурсы пакета — без этого в .app падает загрузка silero_vad_v6.onnx.
_datas = [
    (str(_SPEC_ROOT / "config"), "config"),
    (str(_SPEC_ROOT / ".venv" / "lib" / "python3.12" / "site-packages" / "customtkinter"), "customtkinter"),
]
_datas += collect_data_files('faster_whisper')
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
    name='GhostWriter',
)
app = BUNDLE(
    coll,
    name='GhostWriter.app',
    icon=None,
    bundle_identifier='com.ghostwriter.voiceflow',
    info_plist={
        # Трей-приложение без постоянной иконки в Dock (основной процесс).
        'LSUIElement': True,
        # Запросы TCC: без ключей macOS может молча блокировать микрофон / автоматизацию.
        'NSMicrophoneUsageDescription': (
            'Приложению нужен доступ к микрофону для записи голоса и преобразования речи в текст.'
        ),
        'NSAppleEventsUsageDescription': (
            'Приложению нужен доступ к системным событиям для вставки текста в другие программы.'
        ),
        'NSAccessibilityUsageDescription': (
            'Приложению нужен доступ к универсальному доступу для глобальных горячих клавиш и эмуляции ввода.'
        ),
        'NSHighResolutionCapable': True,
    },
)
