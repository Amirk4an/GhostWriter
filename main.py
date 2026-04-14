"""Точка входа VoiceFlow WL."""

from __future__ import annotations

import logging
import os
import sys
from multiprocessing import Process
from multiprocessing import Queue as mp_queue_factory
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


def main() -> None:
    """Запускает приложение и все подсистемы."""
    setup_logging()

    # В PyInstaller frozen: каталог рядом с бинарником (onedir в .app: Resources/ghost_backend/).
    if getattr(sys, "frozen", False):
        root_dir = Path(sys.executable).resolve().parent
    else:
        root_dir = Path(__file__).resolve().parent
    config_manager = ConfigManager(config_path=root_dir / "config" / "config.json")
    config = config_manager.config
    provider_factory = ProviderFactory(config_manager)

    transcription_provider = provider_factory.create_transcription_provider(config)
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
        from app.ui.status_push_client import StatusPushClient

        status_push = StatusPushClient(push_host, int(push_port))
        status_bridge = StatusBridge(on_broadcast=status_push.push_status)
        LOGGER.info("Режим единого UI: статусы в Electron (%s:%s), старый pill отключён", push_host, push_port)
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

    use_mp_pill = config.floating_pill_enabled and pill_queue is not None and not electron_ui
    if use_mp_pill:
        pill_proc = Process(
            target=run_floating_pill_loop_mp,
            args=(pill_queue, config.app_name, config.primary_color),
            daemon=True,
            name="GhostWriterPill",
        )
        pill_proc.start()

    hotkey_listener = PynputHotkeyListener(config.hotkey, config.command_mode_hotkey)
    cmd = bool(config.command_mode_hotkey.strip())
    hotkey_listener.start(
        dictate_edge=app_controller.handle_dictate_edge,
        command_press=app_controller.on_command_hotkey_press if cmd else None,
        command_release=app_controller.on_command_hotkey_release if cmd else None,
    )

    def on_quit() -> None:
        hotkey_listener.stop()

    tray = TrayApplication(
        config_manager=config_manager,
        status_provider=lambda: app_controller.status,
        on_reload_config=app_controller.reload_config,
        on_quit=on_quit,
    )
    LOGGER.info("Приложение запущено")
    tray.run()


if __name__ == "__main__":
    main()
