"""
Сборка и запуск десктопного ядра VoiceFlow WL.

Все тяжёлые зависимости импортируются только внутри ``run_voiceflow_application``,
чтобы при ``spawn`` и анализе пакетов не тянуть ядро при ``import app.main_runtime``.
"""

from __future__ import annotations

import logging
import signal
import sys
import threading
from pathlib import Path
from queue import Empty as QueueEmpty
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from multiprocessing.process import BaseProcess

LOGGER = logging.getLogger(__name__)


def _project_root_dir() -> Path:
    """
    Корень данных приложения: рядом с бинарником в PyInstaller или каталог репозитория.

    Returns:
        Путь к каталогу, где лежит ``config/config.json`` (в сборке — ``sys._MEIPASS``).
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent


def _reap_finished_process(proc: BaseProcess | None, timeout: float = 1.0) -> None:
    """
    Снимает зомби: ``join`` для уже завершённого дочернего процесса и освобождает дескрипторы.

    Args:
        proc: Объект ``Process`` или ``None``.
        timeout: Таймаут ``join`` в секундах.
    """
    if proc is None:
        return
    if proc.is_alive():
        return
    proc.join(timeout=timeout)
    close = getattr(proc, "close", None)
    if callable(close):
        try:
            close()
        except Exception:  # noqa: BLE001
            LOGGER.debug("Process.close после join: игнорируем", exc_info=True)


def _terminate_child_process(proc: BaseProcess | None, label: str, join_timeout: float = 2.0) -> None:
    """
    Мягко завершает дочерний ``Process``: ``terminate`` → ``join`` → при необходимости ``kill``.

    Args:
        proc: Дочерний процесс или ``None``.
        label: Подпись для логов.
        join_timeout: Секунды ожидания после ``terminate``.
    """
    if proc is None or not proc.is_alive():
        _reap_finished_process(proc)
        return
    proc.terminate()
    proc.join(timeout=join_timeout)
    if proc.is_alive():
        LOGGER.warning("%s: процесс не завершился за %.1f с, пробуем kill()", label, join_timeout)
        kill = getattr(proc, "kill", None)
        if callable(kill):
            try:
                kill()
            except Exception:  # noqa: BLE001
                LOGGER.exception("%s: kill() не удался", label)
            proc.join(timeout=1.0)
        if proc.is_alive():
            LOGGER.error("%s: процесс всё ещё жив после terminate/kill", label)
    close = getattr(proc, "close", None)
    if callable(close):
        try:
            close()
        except Exception:  # noqa: BLE001
            LOGGER.debug("%s: Process.close: игнорируем", label, exc_info=True)


def run_voiceflow_application() -> None:
    """
    Поднимает конфиг, пайплайн, трей, хоткеи и дочерние процессы pill/дашборда.

    Вызывается только из реального корневого процесса приложения (не из worker spawn).
    """
    import multiprocessing
    from multiprocessing import Process
    from multiprocessing import Queue as mp_queue_factory
    from multiprocessing.queues import Queue as MPQueue

    from app.platform.paths import single_instance_hint_path
    from app.platform.single_instance import try_acquire_single_instance_lock

    if not try_acquire_single_instance_lock():
        if sys.platform == "win32":
            print(
                "Уже запущен другой экземпляр Ghost Writer (именованный mutex single-instance).",
                file=sys.stderr,
            )
        else:
            print(
                f"Уже запущен другой экземпляр приложения (файловый lock: {single_instance_hint_path()}).",
                file=sys.stderr,
            )
        sys.exit(0)

    from app.core.app_controller import AppController
    from app.core.history_manager import HistoryManager
    from app.core.journal_manager import JournalManager
    from app.core.stats_manager import StatsManager
    from app.core.audio_engine import AudioEngine
    from app.core.config_manager import ConfigManager
    from app.core.llm_processor import LLMProcessor
    from app.core.logging_config import setup_logging
    from app.core.provider_factory import ProviderFactory
    from app.platform.gui_availability import log_apple_clt_python_warning, skip_tkinter_gui
    from app.platform.hotkey_listener import PynputHotkeyListener
    from app.platform.output_controller import ClipboardOutputController
    from app.ui.dashboard_process import DASHBOARD_FOCUS_RAISE, run_dashboard_process
    from app.ui.pill_ipc import ACTION_RELOAD_CONFIG
    from app.ui.pill_process_entry import run_floating_pill_process
    from app.ui.status_bridge import StatusBridge
    from app.ui.tray_app import TrayApplication

    setup_logging()
    log_apple_clt_python_warning()

    root_dir = _project_root_dir()
    config_json_path = str((root_dir / "config" / "config.json").resolve())
    config_manager = ConfigManager(config_path=root_dir / "config" / "config.json")
    config = config_manager.config

    provider_factory = ProviderFactory(config_manager)
    transcription_provider = provider_factory.create_transcription_provider(config)
    llm_provider = provider_factory.create_llm_provider(config)
    llm_processor = LLMProcessor(
        provider=llm_provider,
        enabled=config.llm_enabled,
        model_provider=config.model_provider,
    )
    audio_engine = AudioEngine(
        sample_rate=config.sample_rate,
        channels=config.channels,
        chunk_size=config.chunk_size,
        input_device=config.audio_input_device,
        boost_quiet_input=config.whisper_mode_boost_input,
    )
    output_controller = ClipboardOutputController()
    stats_manager = StatsManager.with_default_path()
    history_manager = HistoryManager.with_default_path()
    history_manager.init_schema()
    journal_manager = JournalManager.with_default_path()
    journal_manager.init_schema()

    _no_tk = skip_tkinter_gui()
    if _no_tk and config.floating_pill_enabled:
        LOGGER.warning(
            "GHOSTWRITER_HEADLESS=1: плавающий pill (Tk) отключён; статусы только в трее."
        )

    pill_queue: MPQueue | None = None
    pill_command_queue: MPQueue | None = None
    if config.floating_pill_enabled and not _no_tk:
        pill_queue = mp_queue_factory(maxsize=8)
        pill_command_queue = mp_queue_factory(maxsize=32)
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
        stats_manager=stats_manager,
        history_manager=history_manager,
        journal_manager=journal_manager,
    )

    app_controller.mp_pill_status_queue = pill_queue
    app_controller.mp_pill_command_queue = pill_command_queue

    host_command_queue: MPQueue | None = None
    if not _no_tk:
        host_command_queue = mp_queue_factory(maxsize=16)

    dashboard_proc_ref: list[Process | None] = [None]
    dashboard_focus_queue_ref: list[MPQueue | None] = [None]

    def spawn_dashboard_process() -> None:
        """
        Дашборд в отдельном ``Process`` с ``target`` из ``dashboard_process``:
        дочерний процесс не импортирует ``main`` (в отличие от ``subprocess`` + ``sys.executable``
        в собранном .app, где бинарник снова запускает ядро).
        """
        if skip_tkinter_gui():
            LOGGER.info("Дашборд не запускается: включён режим GHOSTWRITER_HEADLESS.")
            return
        prev = dashboard_proc_ref[0]
        prev_focus_q = dashboard_focus_queue_ref[0]
        if prev is not None and prev.is_alive():
            if prev_focus_q is not None:
                try:
                    prev_focus_q.put_nowait(DASHBOARD_FOCUS_RAISE)
                except Exception:  # noqa: BLE001
                    LOGGER.debug("Дашборд: не удалось отправить команду поднятия окна", exc_info=True)
            LOGGER.info("Дашборд уже открыт — отправлена команда поднять окно")
            return
        _reap_finished_process(prev)
        dashboard_proc_ref[0] = None
        dashboard_focus_queue_ref[0] = None
        focus_q: MPQueue = mp_queue_factory(maxsize=8)
        try:
            proc = Process(
                target=run_dashboard_process,
                args=(config_json_path, focus_q, host_command_queue),
                daemon=False,
                name="GhostWriterDashboard",
            )
            proc.start()
        except Exception:
            LOGGER.exception("Не удалось запустить процесс дашборда")
            return
        dashboard_proc_ref[0] = proc
        dashboard_focus_queue_ref[0] = focus_q

    pill_proc: Process | None = None
    _is_main = multiprocessing.current_process().name == "MainProcess"
    if (
        _is_main
        and app_controller.mp_pill_status_queue is not None
        and app_controller.mp_pill_command_queue is not None
    ):

        def _pill_command_ipc_loop() -> None:
            cmd_q = app_controller.mp_pill_command_queue
            assert cmd_q is not None
            while True:
                try:
                    msg = cmd_q.get(timeout=0.5)
                except QueueEmpty:
                    continue
                if isinstance(msg, dict) and msg.get("action") == "open_dashboard":
                    spawn_dashboard_process()

        threading.Thread(
            target=_pill_command_ipc_loop,
            daemon=True,
            name="GhostPillCommandIpc",
        ).start()

        pill_proc = Process(
            target=run_floating_pill_process,
            args=(
                app_controller.mp_pill_status_queue,
                app_controller.mp_pill_command_queue,
                config.app_name,
                config.primary_color,
            ),
            daemon=False,
            name="GhostWriterPill",
        )
        pill_proc.start()

    hotkey_listener_ref: list[PynputHotkeyListener | None] = [None]

    def restart_hotkeys() -> None:
        """Пересоздаёт слушатель глобальных хоткеев после смены конфига."""
        old = hotkey_listener_ref[0]
        if old is not None:
            try:
                old.stop()
            except Exception:  # noqa: BLE001
                LOGGER.debug("Остановка PynputHotkeyListener", exc_info=True)
            hotkey_listener_ref[0] = None
        cfg2 = config_manager.config
        cmd_h = bool(cfg2.command_mode_hotkey.strip())
        jh = bool((getattr(cfg2, "journal_hotkey", "") or "").strip())
        h = PynputHotkeyListener(
            cfg2.hotkey,
            cfg2.command_mode_hotkey,
            getattr(cfg2, "journal_hotkey", "") or "",
        )
        h.start(
            dictate_edge=app_controller.handle_dictate_edge,
            command_press=app_controller.on_command_hotkey_press if cmd_h else None,
            command_release=app_controller.on_command_hotkey_release if cmd_h else None,
            journal_edge=app_controller.handle_journal_edge if jh else None,
        )
        hotkey_listener_ref[0] = h
        LOGGER.info(
            "Hotkeys перезапущены: dictate=%s journal=%s command=%s",
            cfg2.hotkey,
            getattr(cfg2, "journal_hotkey", "") or "—",
            cfg2.command_mode_hotkey or "—",
        )

    restart_hotkeys()

    if host_command_queue is not None:

        def _host_dashboard_ipc_loop() -> None:
            while True:
                try:
                    msg = host_command_queue.get(timeout=0.5)
                except QueueEmpty:
                    continue
                if isinstance(msg, dict) and msg.get("action") == ACTION_RELOAD_CONFIG:
                    try:
                        app_controller.reload_config()
                        restart_hotkeys()
                    except Exception:  # noqa: BLE001
                        LOGGER.exception("RELOAD_CONFIG из дашборда")

        threading.Thread(
            target=_host_dashboard_ipc_loop,
            daemon=True,
            name="GhostHostDashboardIpc",
        ).start()

    shutdown_once: list[bool] = [False]

    def on_quit() -> None:
        if shutdown_once[0]:
            return
        shutdown_once[0] = True
        app_controller.prepare_process_shutdown()
        hk = hotkey_listener_ref[0]
        if hk is not None:
            hk.stop()
        _terminate_child_process(dashboard_proc_ref[0], "Дашборд")
        _terminate_child_process(pill_proc, "Pill")

    def _tray_reload_config() -> None:
        app_controller.reload_config()
        restart_hotkeys()

    def _tray_status_line() -> str:
        st, detail = status_bridge.snapshot()
        if st == "Idle" and detail:
            d = str(detail).strip()
            return d[:100] + ("…" if len(d) > 100 else "")
        if st == "Recording":
            return "Recording"
        if st == "Processing":
            return "Processing"
        if st == "Error":
            return "Error"
        return "Idle"

    tray = TrayApplication(
        config_manager=config_manager,
        status_provider=_tray_status_line,
        on_reload_config=_tray_reload_config,
        on_quit=on_quit,
        on_open_dashboard=spawn_dashboard_process,
    )

    def _handle_shutdown_signal(signum: int, _frame: object) -> None:
        LOGGER.info("Сигнал завершения процесса: %s", signum)
        on_quit()
        tray.stop()
        sys.exit(0)

    signal.signal(signal.SIGTERM, _handle_shutdown_signal)
    signal.signal(signal.SIGINT, _handle_shutdown_signal)

    LOGGER.info("Приложение запущено (python3 main.py)")
    tray.run()
