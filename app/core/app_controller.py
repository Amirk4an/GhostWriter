"""Главный контроллер пайплайна press-to-talk и command mode."""

from __future__ import annotations

import logging
import platform
import queue
import threading
import time
from dataclasses import dataclass
from multiprocessing.queues import Queue as MPQueue
from typing import TYPE_CHECKING, Any

from app.core.config_manager import ConfigManager
from app.core.glossary_manager import apply_glossary, glossary_prompt_block, load_glossary_entries
from app.core.interfaces import OutputAdapter, TranscriptionProvider
from app.core.llm_processor import LLMProcessor
from app.core.mic_meter_controller import MicMeterController
from app.core.history_manager import HistoryManager
from app.core.stats_manager import StatsManager, wav_audio_duration_seconds
from app.platform.macos_focus import get_macos_frontmost_app_name
from app.platform.output_controller import ClipboardOutputController

if TYPE_CHECKING:
    from app.ui.status_bridge import StatusBridge

LOGGER = logging.getLogger(__name__)


@dataclass
class ProcessingJob:
    """Задание на обработку записанного аудио."""

    audio_bytes: bytes
    recorded_ms: float
    paste_target_app: str | None = None
    command_selection: str | None = None


class AppController:
    """Оркестрирует запись, транскрипцию, LLM и вставку текста."""

    def __init__(
        self,
        config_manager: ConfigManager,
        audio_engine: Any,
        transcription_provider: TranscriptionProvider,
        llm_processor: LLMProcessor,
        output_adapter: OutputAdapter,
        status_bridge: StatusBridge | None = None,
        stats_manager: StatsManager | None = None,
        history_manager: HistoryManager | None = None,
    ) -> None:
        self._config_manager = config_manager
        self._audio_engine = audio_engine
        self._transcription_provider = transcription_provider
        self._llm_processor = llm_processor
        self._output_adapter = output_adapter
        self._status_bridge = status_bridge
        self._stats_manager = stats_manager
        self._history_manager = history_manager
        self._status = "Idle"
        self._recording_started_at: float | None = None
        self._paste_target_app: str | None = None
        self._command_selection_pending: str | None = None
        self._queue: queue.Queue[ProcessingJob] = queue.Queue(maxsize=self._config_manager.config.max_parallel_jobs)
        self._worker = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker.start()

        self._dictate_latch_active = False
        self._latch_arm_deadline: float | None = None
        self._latch_stop_downs: list[float] = []
        self._hold_down_at: float | None = None
        self._mic_meter = MicMeterController()

        # Ссылки на multiprocessing.Queue должны жить столько же, сколько основной процесс,
        # иначе GC может уничтожить SemLock до инициализации дочернего процесса (spawn).
        self.mp_pill_status_queue: MPQueue | None = None
        self.mp_pill_command_queue: MPQueue | None = None

    def _emit_status(self, status: str, detail: str | None = None) -> None:
        self._status = status
        if self._status_bridge is not None:
            self._status_bridge.set_status(status, detail)

    @property
    def status(self) -> str:
        return self._status

    def handle_dictate_edge(self, pressed: bool, when: float) -> None:
        """События основного хоткея: pressed=True вниз, False вверх."""
        cfg = self._config_manager.config
        if not cfg.hands_free_enabled:
            if pressed:
                self._begin_dictate_recording(latch=False)
            else:
                self._end_dictate_recording(flush=True)
            return

        if pressed:
            self._on_dictate_down(when)
        else:
            self._on_dictate_up(when)

    def _on_dictate_down(self, when: float) -> None:
        cfg = self._config_manager.config
        window = cfg.latch_arm_window_ms / 1000.0

        if self._dictate_latch_active:
            stop_window = cfg.latch_stop_double_down_ms / 1000.0
            self._latch_stop_downs.append(when)
            self._latch_stop_downs = [t for t in self._latch_stop_downs if when - t <= stop_window]
            if len(self._latch_stop_downs) >= 2:
                self._latch_stop_downs.clear()
                self._end_dictate_recording(flush=True)
            return

        if self._latch_arm_deadline is not None and when <= self._latch_arm_deadline:
            self._latch_arm_deadline = None
            self._begin_dictate_recording(latch=True)
            return

        self._hold_down_at = when
        self._begin_dictate_recording(latch=False)

    def _on_dictate_up(self, when: float) -> None:
        if self._dictate_latch_active:
            return

        cfg = self._config_manager.config
        if self._hold_down_at is None:
            return

        duration_ms = (when - self._hold_down_at) * 1000
        self._hold_down_at = None

        if duration_ms < cfg.short_tap_max_ms:
            self._abort_dictate_recording()
            self._latch_arm_deadline = when + cfg.latch_arm_window_ms / 1000.0
            self._emit_status("Idle", "Двойной тап — hands-free")
        else:
            self._end_dictate_recording(flush=True)

    def on_command_hotkey_press(self) -> None:
        """Старт command mode: чтение выделения и запись команды."""
        from app.platform.macos_ax_selection import get_focused_selected_text

        cfg = self._config_manager.config
        if not cfg.llm_enabled:
            LOGGER.warning("Command mode требует llm_enabled=true")
            self._emit_status("Error", "Включите LLM для command mode")
            return

        selection = get_focused_selected_text()
        if not selection:
            LOGGER.warning("Нет выделенного текста (AX / права доступа)")
            self._emit_status("Error", "Выделите текст")
            return

        self._command_selection_pending = selection
        self._recording_started_at = time.perf_counter()
        if platform.system() == "Darwin":
            self._paste_target_app = get_macos_frontmost_app_name()
        else:
            self._paste_target_app = None
        self.stop_mic_meter()
        try:
            self._audio_engine.start_recording()
        except RuntimeError as error:
            LOGGER.error("%s", error)
            self._emit_status("Error", str(error))
            self._command_selection_pending = None
            self._paste_target_app = None
            self._recording_started_at = None
            return
        self._emit_status("Recording", "Команда для выделения…")

    def on_command_hotkey_release(self) -> None:
        """Завершение записи голосовой команды."""
        if self._command_selection_pending is None:
            return

        audio_bytes = self._audio_engine.stop_recording()
        recorded_ms = 0.0
        if self._recording_started_at is not None:
            recorded_ms = (time.perf_counter() - self._recording_started_at) * 1000
            self._recording_started_at = None

        selection = self._command_selection_pending
        self._command_selection_pending = None
        target_app = self._paste_target_app
        self._paste_target_app = None

        if not audio_bytes:
            self._emit_status("Idle")
            return

        try:
            self._queue.put_nowait(
                ProcessingJob(
                    audio_bytes=audio_bytes,
                    recorded_ms=recorded_ms,
                    paste_target_app=target_app,
                    command_selection=selection,
                )
            )
        except queue.Full:
            LOGGER.warning("Очередь обработки заполнена, command mode пропущен")
            self._emit_status("Idle")

    def on_hotkey_press(self) -> None:
        """Совместимость со старым API и тестами."""
        self.handle_dictate_edge(True, time.perf_counter())

    def on_hotkey_release(self) -> None:
        self.handle_dictate_edge(False, time.perf_counter())

    def _begin_dictate_recording(self, *, latch: bool) -> None:
        self._dictate_latch_active = latch
        if latch:
            self._latch_stop_downs.clear()

        self._recording_started_at = time.perf_counter()
        if platform.system() == "Darwin":
            self._paste_target_app = get_macos_frontmost_app_name()
            if self._paste_target_app:
                LOGGER.debug("Цель вставки (фокус при нажатии): %s", self._paste_target_app)
        else:
            self._paste_target_app = None
        self.stop_mic_meter()
        try:
            self._audio_engine.start_recording()
        except RuntimeError as error:
            LOGGER.error("%s", error)
            self._emit_status("Error", str(error))
            self._recording_started_at = None
            self._paste_target_app = None
            self._dictate_latch_active = False
            self._hold_down_at = None
            return
        self._emit_status("Recording", "Hands-free" if latch else None)

    def _abort_dictate_recording(self) -> None:
        self._audio_engine.stop_recording()
        self._recording_started_at = None
        self._paste_target_app = None
        self._dictate_latch_active = False
        self._emit_status("Idle")

    def _end_dictate_recording(self, *, flush: bool) -> None:
        if not flush:
            return
        audio_bytes = self._audio_engine.stop_recording()
        recorded_ms = 0.0
        if self._recording_started_at is not None:
            recorded_ms = (time.perf_counter() - self._recording_started_at) * 1000
            self._recording_started_at = None

        was_latch = self._dictate_latch_active
        self._dictate_latch_active = False
        self._latch_arm_deadline = None

        if not audio_bytes:
            self._emit_status("Idle")
            self._paste_target_app = None
            return

        target_app = self._paste_target_app
        self._paste_target_app = None
        try:
            self._queue.put_nowait(
                ProcessingJob(
                    audio_bytes=audio_bytes,
                    recorded_ms=recorded_ms,
                    paste_target_app=target_app,
                    command_selection=None,
                )
            )
        except queue.Full:
            LOGGER.warning("Очередь обработки заполнена, задание пропущено")
            self._emit_status("Idle")

    def reload_config(self) -> None:
        """Перезагружает конфиг во время работы."""
        self._config_manager.reload()
        cfg = self._config_manager.config
        if hasattr(self._audio_engine, "set_input_device"):
            self._audio_engine.set_input_device(cfg.audio_input_device)
        if hasattr(self._audio_engine, "set_boost_quiet_input"):
            self._audio_engine.set_boost_quiet_input(cfg.whisper_mode_boost_input)
        LOGGER.info("Конфигурация обновлена во время выполнения")

    def apply_audio_input_device(self, device: int | None) -> None:
        """Сохраняет выбранный микрофон в config.json и применяет к движку записи."""
        cfg = self._config_manager.patch_audio_input_device(device)
        if hasattr(self._audio_engine, "set_input_device"):
            self._audio_engine.set_input_device(cfg.audio_input_device)
        if hasattr(self._audio_engine, "set_boost_quiet_input"):
            self._audio_engine.set_boost_quiet_input(cfg.whisper_mode_boost_input)
        LOGGER.info("Микрофон обновлён: %s", cfg.audio_input_device)

    def get_audio_input_device_index(self) -> int | None:
        """Возвращает текущий индекс микрофона из конфигурации."""
        return self._config_manager.config.audio_input_device

    def stop_mic_meter(self) -> None:
        """Останавливает превью уровня микрофона."""
        self._mic_meter.stop()

    def prepare_process_shutdown(self) -> None:
        """Останавливает превью и сбрасывает активную запись без постановки в очередь (выход из процесса)."""
        self.stop_mic_meter()
        self._abort_dictate_recording()

    def _worker_loop(self) -> None:
        while True:
            job = self._queue.get()
            try:
                self._emit_status("Processing")
                self._process_job(job)
            except Exception as error:  # noqa: BLE001
                self._emit_status("Error", str(error))
                LOGGER.exception("Ошибка пайплайна: %s", error)
            finally:
                if self._status != "Error":
                    self._emit_status("Idle")
                self._queue.task_done()

    def _resolve_context_suffix(self, app_name: str | None) -> str:
        if not app_name:
            return ""
        cfg = self._config_manager.config
        lower = app_name.lower()
        for needle, suffix in cfg.app_context_prompts.items():
            if needle.lower() in lower:
                return "\n\n" + suffix
        return ""

    def _process_job(self, job: ProcessingJob) -> None:
        config = self._config_manager.config
        glossary_path = self._config_manager.config_path.parent / config.user_glossary_path
        glossary_pairs = load_glossary_entries(glossary_path)
        glossary_block = glossary_prompt_block(glossary_pairs)

        def on_partial(text: str) -> None:
            if config.streaming_stt_enabled and self._status_bridge is not None:
                self._status_bridge.set_status("Processing", text[:400])

        stt_started = time.perf_counter()
        raw_text = self._transcription_provider.transcribe(
            audio_bytes=job.audio_bytes,
            sample_rate=config.sample_rate,
            language=config.language,
            on_partial=on_partial if config.streaming_stt_enabled else None,
        )
        stt_ms = (time.perf_counter() - stt_started) * 1000

        raw_text = apply_glossary(raw_text, glossary_pairs)
        raw_preview = (raw_text or "").strip()
        if not raw_preview:
            LOGGER.warning(
                "Транскрипт пустой после STT (проверьте микрофон, уровень сигнала и language в config.json)."
            )
            return

        context_suffix = self._resolve_context_suffix(job.paste_target_app)
        base_prompt = config.system_prompt + (glossary_block and ("\n\n" + glossary_block) or "")

        llm_started = time.perf_counter()
        if job.command_selection is not None:
            processed_text = self._llm_processor.refine_command(
                selection=job.command_selection,
                spoken_instruction=raw_preview,
                command_system_prompt=config.command_mode_system_prompt,
                base_system_prompt=base_prompt + context_suffix,
            )
        else:
            effective_prompt = base_prompt + context_suffix
            processed_text = self._llm_processor.refine_text(raw_text=raw_preview, system_prompt=effective_prompt)
        llm_ms = (time.perf_counter() - llm_started) * 1000

        proc_stripped = (processed_text or "").strip()

        preview = raw_preview[:120] + ("…" if len(raw_preview) > 120 else "")
        LOGGER.info("Распознано (%d симв.): %s", len(raw_preview), preview)

        paste_ok = True
        if proc_stripped:
            # Пока идёт output_text (osascript/Cmd+V), без этого pill остаётся с последним
            # partial-транскриптом — выглядит как «вечная обработка» после STT.
            if self._status_bridge is not None:
                self._status_bridge.set_status("Processing", "Вставка в приложение…")
            self._output_adapter.output_text(proc_stripped, paste_target_app=job.paste_target_app)
            if isinstance(self._output_adapter, ClipboardOutputController):
                paste_res = self._output_adapter.take_last_darwin_paste_result()
                if paste_res is not None and not paste_res[0]:
                    paste_ok = False
                    self._emit_status("Error", paste_res[1])
        elif raw_preview:
            LOGGER.warning("Текст после LLM пустой, вставка пропущена.")

        if proc_stripped and paste_ok and self._stats_manager is not None:
            llm_used = self._llm_processor.is_remote_enabled()
            audio_dur = wav_audio_duration_seconds(job.audio_bytes)
            words = len(proc_stripped.split())
            try:
                self._stats_manager.record_successful_dictation(
                    word_count=words,
                    char_count=len(proc_stripped),
                    recorded_ms=float(job.recorded_ms),
                    audio_seconds=audio_dur,
                    llm_used=llm_used,
                )
            except Exception:
                LOGGER.exception("Не удалось обновить stats.json")

        if (
            proc_stripped
            and paste_ok
            and self._history_manager is not None
            and self._config_manager.config.enable_history
        ):
            try:
                target = (job.paste_target_app or "").strip()
                self._history_manager.add_record(
                    raw_text=raw_preview,
                    final_text=proc_stripped,
                    target_app=target,
                )
            except Exception:
                LOGGER.exception("Не удалось записать историю диктовки")

        total_ms = job.recorded_ms + stt_ms + llm_ms
        LOGGER.info(
            "Latency metrics | record_ms=%.2f stt_ms=%.2f llm_ms=%.2f total_ms=%.2f",
            job.recorded_ms,
            stt_ms,
            llm_ms,
            total_ms,
        )
