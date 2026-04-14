"""Точка входа VoiceFlow WL."""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import time
from typing import Any, cast
from multiprocessing import Process
from multiprocessing import Queue as mp_queue_factory
from multiprocessing import freeze_support
from multiprocessing.queues import Queue as MPQueue
from pathlib import Path

from app.core.app_controller import AppController
from app.core.audio_engine import AudioEngine
from app.core.config_manager import ConfigManager
from app.core.llm_processor import LLMProcessor
from app.core.logging_config import setup_logging
from app.core.provider_factory import ProviderFactory
from app.platform.hotkey_listener import PynputHotkeyListener
from app.platform.output_controller import ClipboardOutputController
from app.ui.floating_pill import run_floating_pill_loop_mp
from app.ui.status_bridge import StatusBridge
from app.ui.tray_app import TrayApplication

LOGGER = logging.getLogger(__name__)

# region agent log
_AGENT_DEBUG_LOG_PATH = "/Users/krasikov/projects/ghostwriter/.cursor/debug-edce00.log"


def _agent_debug_log(hypothesis_id: str, location: str, message: str, data: dict[str, object]) -> None:
    """Пишет одну строку NDJSON для отладочной сессии (не логирует секреты)."""
    try:
        Path(_AGENT_DEBUG_LOG_PATH).parent.mkdir(parents=True, exist_ok=True)
        payload: dict[str, object] = {
            "sessionId": "edce00",
            "runId": os.environ.get("GHOST_DEBUG_RUN_ID", "run1"),
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data,
            "timestamp": int(time.time() * 1000),
        }
        with open(_AGENT_DEBUG_LOG_PATH, "a", encoding="utf-8") as log_file:
            log_file.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except OSError:
        pass


# endregion


def main() -> None:
    """Запускает приложение и все подсистемы."""
    setup_logging()

    # region agent log
    import multiprocessing as mp

    _agent_debug_log(
        "H1",
        "main.py:main:entry",
        "main() старт",
        {
            "pid": os.getpid(),
            "ppid": os.getppid(),
            "argv_head": sys.argv[:6],
            "frozen": bool(getattr(sys, "frozen", False)),
            "mp_process_name": mp.current_process().name,
            "GHOST_WRITER_ELECTRON_UI": os.environ.get("GHOST_WRITER_ELECTRON_UI", ""),
            "GHOST_WRITER_PUSH_STATUS_PORT": os.environ.get("GHOST_WRITER_PUSH_STATUS_PORT", ""),
        },
    )
    try:
        ps_cmd = subprocess.run(
            ["ps", "-axo", "pid=,ppid=,comm="],
            check=False,
            capture_output=True,
            text=True,
        )
        backend_rows = [ln.strip() for ln in ps_cmd.stdout.splitlines() if "ghost_backend" in ln]
        _agent_debug_log(
            "H6",
            "main.py:main:process_snapshot",
            "снимок процессов ghost_backend при старте",
            {"count": len(backend_rows), "rows": backend_rows[:20], "pid": os.getpid()},
        )
    except OSError:
        pass
    # endregion

    # В PyInstaller frozen: каталог рядом с бинарником (onedir в .app: Resources/ghost_backend/).
    if getattr(sys, "frozen", False):
        root_dir = Path(sys.executable).resolve().parent
    else:
        root_dir = Path(__file__).resolve().parent
    config_manager = ConfigManager(config_path=root_dir / "config" / "config.json")
    config = config_manager.config
    provider_factory = ProviderFactory(config_manager)

    # region agent log
    _t_provider = time.perf_counter()
    # endregion
    transcription_provider = provider_factory.create_transcription_provider(config)
    # region agent log
    _agent_debug_log(
        "H3",
        "main.py:after_transcription_provider",
        "провайдер транскрипции создан",
        {"elapsed_ms": round((time.perf_counter() - _t_provider) * 1000), "pid": os.getpid()},
    )
    # endregion
    llm_provider = provider_factory.create_llm_provider(config)
    llm_processor = LLMProcessor(provider=llm_provider, enabled=config.llm_enabled)
    audio_engine = AudioEngine(
        sample_rate=config.sample_rate,
        channels=config.channels,
        chunk_size=config.chunk_size,
        input_device=config.audio_input_device,
        boost_quiet_input=config.whisper_mode_boost_input,
    )
    output_controller = ClipboardOutputController()
    electron_ui = os.environ.get("GHOST_WRITER_ELECTRON_UI") == "1"
    push_port = os.environ.get("GHOST_WRITER_PUSH_STATUS_PORT", "").strip()
    push_host = os.environ.get("GHOST_WRITER_PUSH_STATUS_HOST", "127.0.0.1").strip() or "127.0.0.1"

    pill_queue: MPQueue | None = None
    status_push = None
    if electron_ui and push_port:
        status_bridge = StatusBridge()
    elif electron_ui:
        LOGGER.warning(
            "GHOST_WRITER_ELECTRON_UI без GHOST_WRITER_PUSH_STATUS_PORT — статусы в оболочку не уходят",
        )
        status_bridge = StatusBridge()
    elif config.floating_pill_enabled:
        pill_queue = mp_queue_factory(maxsize=8)
        status_bridge = StatusBridge(mp_queue=pill_queue)
    else:
        status_bridge = StatusBridge()
    app_controller = AppController(
        config_manager=config_manager,
        audio_engine=audio_engine,
        transcription_provider=transcription_provider,
        llm_processor=llm_processor,
        output_adapter=output_controller,
        status_bridge=status_bridge,
    )

    if electron_ui and push_port:
        from app.platform.audio_devices import list_audio_input_devices, validate_audio_input_index
        from app.ui.status_push_client import StatusPushClient

        _push_holder: list[Any] = [None]

        def _on_ui_line(obj: dict[str, object]) -> None:
            sp = cast(Any, _push_holder[0])
            msg_type = str(obj.get("type") or "")
            request_id = obj.get("request_id")
            rid: str | None = str(request_id) if request_id is not None else None

            if msg_type == "dictate_edge":
                pressed = bool(obj.get("pressed"))
                app_controller.handle_dictate_edge(pressed, time.perf_counter())
                return

            if not isinstance(sp, StatusPushClient):
                return

            if msg_type == "list_audio_inputs":
                try:
                    devices, default_in = list_audio_input_devices()
                    current = app_controller.get_audio_input_device_index()
                    sp.push_json(
                        {
                            "type": "audio_inputs_reply",
                            "request_id": rid,
                            "ok": True,
                            "devices": devices,
                            "default_index": default_in,
                            "current_index": current,
                        }
                    )
                except Exception as err:  # noqa: BLE001
                    LOGGER.exception("list_audio_inputs")
                    sp.push_json(
                        {
                            "type": "audio_inputs_reply",
                            "request_id": rid,
                            "ok": False,
                            "error": str(err),
                        }
                    )
                return

            if msg_type == "set_audio_input_device":
                try:
                    raw = obj.get("device", None)
                    device_val: int | None
                    if raw is None:
                        device_val = None
                    else:
                        device_val = int(raw)
                        validate_audio_input_index(device_val)
                    app_controller.apply_audio_input_device(device_val)
                    sp.push_json(
                        {
                            "type": "set_audio_input_device_reply",
                            "request_id": rid,
                            "ok": True,
                            "current_index": app_controller.get_audio_input_device_index(),
                        }
                    )
                except Exception as err:  # noqa: BLE001
                    LOGGER.exception("set_audio_input_device")
                    sp.push_json(
                        {
                            "type": "set_audio_input_device_reply",
                            "request_id": rid,
                            "ok": False,
                            "error": str(err),
                        }
                    )
                return

        status_push = StatusPushClient(push_host, int(push_port), on_line=_on_ui_line)
        _push_holder[0] = status_push
        status_bridge.set_on_broadcast(status_push.push_status)
        LOGGER.info("Режим единого UI: статусы в Electron (%s:%s), старый pill отключён", push_host, push_port)

    use_mp_pill = config.floating_pill_enabled and pill_queue is not None and not electron_ui
    if use_mp_pill:
        pill_proc = Process(
            target=run_floating_pill_loop_mp,
            args=(pill_queue, config.app_name, config.primary_color),
            daemon=True,
            name="GhostWriterPill",
        )
        # region agent log
        _agent_debug_log(
            "H2",
            "main.py:pill:before_start",
            "перед Process.start(pill)",
            {"parent_pid": os.getpid(), "floating_pill_enabled": config.floating_pill_enabled},
        )
        # endregion
        pill_proc.start()
        # region agent log
        _agent_debug_log(
            "H2",
            "main.py:pill:after_start",
            "после Process.start(pill)",
            {"parent_pid": os.getpid(), "pill_child_pid": pill_proc.pid},
        )
        # endregion

    hotkey_listener: PynputHotkeyListener | None = None
    cmd = bool(config.command_mode_hotkey.strip())
    use_electron_dictation_bridge = bool(electron_ui and push_port)
    if use_electron_dictation_bridge:
        LOGGER.info("Режим Electron UI: dictation hotkey обрабатывается в Electron (TCP->backend)")
    if cmd:
        hotkey_listener = PynputHotkeyListener(config.hotkey, config.command_mode_hotkey)

        def _noop_dictate_edge(_pressed: bool, _when: float) -> None:
            """В Electron-режиме dictation идёт через оболочку; pynput не должен дублировать."""
            del _pressed, _when

        hotkey_listener.start(
            dictate_edge=app_controller.handle_dictate_edge if not use_electron_dictation_bridge else _noop_dictate_edge,
            command_press=app_controller.on_command_hotkey_press,
            command_release=app_controller.on_command_hotkey_release,
        )
    elif not use_electron_dictation_bridge:
        hotkey_listener = PynputHotkeyListener(config.hotkey, config.command_mode_hotkey)
        hotkey_listener.start(
            dictate_edge=app_controller.handle_dictate_edge,
            command_press=None,
            command_release=None,
        )

    def on_quit() -> None:
        if hotkey_listener is not None:
            hotkey_listener.stop()
        if status_push is not None:
            status_push.close()

    tray = TrayApplication(
        config_manager=config_manager,
        status_provider=lambda: app_controller.status,
        on_reload_config=app_controller.reload_config,
        on_quit=on_quit,
    )
    LOGGER.info("Приложение запущено")
    # region agent log
    _agent_debug_log(
        "H4",
        "main.py:before_tray_run",
        "перед pystray Icon.run (блокирующий цикл)",
        {"pid": os.getpid()},
    )
    # endregion
    tray.run()


if __name__ == "__main__":
    # Обязательно для PyInstaller: иначе spawn multiprocessing снова запускает тот же бинарник
    # и каждый экземпляр снова создаёт дочерние процессы (лавина ghost_backend в Activity Monitor).
    freeze_support()
    # region agent log
    _agent_debug_log(
        "H1",
        "main.py:__main__",
        "точка входа if __name__ == __main__",
        {"pid": os.getpid(), "ppid": os.getppid()},
    )
    # endregion
    main()
